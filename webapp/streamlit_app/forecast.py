"""Pemuat model riset (GA-LightGBM, log + differencing) — TIDAK melatih ulang di sini.

Pipeline `code.ipynb` (bagian 17 dst.): target model adalah `log1p(harga)`
dengan harga dalam RIBUAN rupiah; differencing orde 1 dilakukan DI DALAM
skforecast `ForecasterDirect` (`differentiation=1`), jadi prediksinya sudah
kembali ke level log harga dan cukup dibalik dengan `expm1`. Tidak ada lagi
dekomposisi MSTL/trend/musiman.

Artefak yang dimuat (read-only, di-cache di memori per proses Streamlit):
`final_model/final_model_prediction_<nama_komoditas>_h<horizon>.joblib`
— satu forecaster per komoditas x horizon (1/7/30 hari).

`nama_komoditas` adalah nama tampilan komoditas (mis. "Beras Kualitas Bawah
I") — persis sama dengan `Komoditas.nama` di `data.mock_commodities` dan
nama kolom di `DATASET-BERAS.csv`, karena itu yang dipakai notebook riset
sebagai bagian nama file artefak.

`ramalkan_harga` di-cache lewat `st.cache_data`, di-kunci dari ISI
`riwayat` (bukan cuma nama/horizon) — begitu admin menyimpan harga baru,
`riwayat` berubah, kunci cache ikut berubah, dan hasil lama otomatis tidak
terpakai lagi tanpa perlu kode invalidasi manual.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import streamlit as st
from skforecast.utils import load_forecaster

RESEARCH_DIR = Path(__file__).resolve().parent.parent / "research"
FINAL_MODEL_DIR = RESEARCH_DIR / "final_model"

HORIZON_TERSEDIA: tuple[int, ...] = (1, 7, 30)
NAMA_MODEL = "GA-LightGBM (log + differencing)"

# Model riset dilatih pada harga dalam RIBUAN rupiah (nilai `13.25` di
# DATASET-BERAS.csv = Rp 13.250/kg). Semua konversi ke/dari Rupiah aktual di
# aplikasi web harus lewat konstanta ini.
SKALA_HARGA = 1000

# log1p(0.5) ≈ 0.4 — harga pangan mana pun (≥ Rp 500) di skala log jauh di
# atas ini. Forecaster yang data latihnya berakhir di sekitar nol berarti
# artefak LAMA (dilatih pada residual MSTL), bukan pipeline log saat ini.
_BATAS_BAWAH_LOG = np.log1p(0.5)


class ModelRisetError(RuntimeError):
    """Artefak model riset tidak ada, gagal dimuat, basi, atau riwayat kurang."""


_cache_forecaster: dict[tuple[str, int], Any] = {}


def muat_forecaster(nama_komoditas: str, horizon: int) -> Any:
    """`ForecasterDirect` (GA-LightGBM) untuk satu komoditas x horizon (cached)."""
    if horizon not in HORIZON_TERSEDIA:
        raise ValueError(
            f"Horizon {horizon} tidak didukung, pilih salah satu dari {HORIZON_TERSEDIA}."
        )

    kunci = (nama_komoditas, horizon)
    if kunci not in _cache_forecaster:
        path = FINAL_MODEL_DIR / f"final_model_prediction_{nama_komoditas}_h{horizon}.joblib"
        if not path.exists():
            raise ModelRisetError(
                f"Forecaster tidak ditemukan untuk '{nama_komoditas}' h={horizon} ({path})."
            )
        try:
            forecaster = load_forecaster(str(path), verbose=False, suppress_warnings=True)
        except Exception as exc:
            raise ModelRisetError(f"Gagal memuat forecaster dari {path}: {exc}") from exc

        # ponytail: cek heuristik skala data latih, bukan versi artefak. Kalau
        # notebook kelak menyimpan metadata pipeline, cek metadata itu saja.
        if float(forecaster.last_window_.iloc[-1, 0]) < _BATAS_BAWAH_LOG:
            raise ModelRisetError(
                f"Forecaster '{nama_komoditas}' h={horizon} masih artefak lama "
                "(bukan skala log1p) — jalankan ulang code.ipynb untuk menyimpan ulang final_model/."
            )
        _cache_forecaster[kunci] = forecaster
    return _cache_forecaster[kunci]


def susun_last_window(riwayat: pd.DataFrame, window_size: int) -> pd.Series:
    """`last_window` forecaster dari harga TERBARU: `log1p(harga / SKALA_HARGA)`.

    Pra-proses sama seperti dataset riset (`asfreq("D")` + interpolasi
    berbasis waktu) supaya indeks harian tanpa celah — fitur kalender
    forecaster dihitung dari indeks ini.
    """
    harga = (
        riwayat.sort_values("tanggal")
        .set_index("tanggal")["harga"]
        .pipe(lambda s: s.set_axis(pd.DatetimeIndex(s.index)))
        .asfreq("D")
        .interpolate(method="time")
        .dropna()
    )
    if len(harga) < window_size:
        raise ModelRisetError(
            f"Riwayat harga cuma {len(harga)} hari, forecaster butuh minimal {window_size} hari."
        )
    return np.log1p(harga.iloc[-window_size:] / SKALA_HARGA).rename("y")


@st.cache_data(show_spinner="Menghitung prediksi...", ttl=3600, max_entries=200)
def ramalkan_harga(riwayat: pd.DataFrame, nama_komoditas: str, horizon: int) -> pd.Series:
    """Ramalkan harga H+1..H+`horizon` (Rupiah) dari harga TERBARU, tanpa pelatihan ulang.

    Di-cache (`st.cache_data`) memakai `riwayat` sebagai bagian kunci cache —
    riwayat identik langsung mengembalikan hasil tersimpan; begitu riwayat
    berubah (admin menyimpan harga baru) kuncinya ikut berubah. `ttl` &
    `max_entries` cuma jaring pengaman memori untuk proses yang jalan lama.

    Mengembalikan `pd.Series` harga (Rupiah) berindeks tanggal, dari H+1
    sampai H+`horizon` hari setelah titik data terakhir di `riwayat`.
    """
    forecaster = muat_forecaster(nama_komoditas, horizon)
    last_window = susun_last_window(riwayat, forecaster.window_size)

    pred_log = forecaster.predict(steps=horizon, last_window=last_window)
    harga_rupiah = np.expm1(np.asarray(pred_log, dtype=float).ravel()) * SKALA_HARGA

    return pd.Series(harga_rupiah, index=pred_log.index, name="harga_prediksi")


@dataclass(frozen=True)
class HasilPeramalan:
    """Hasil prediksi untuk SATU horizon terpilih — bentuknya sengaja disamakan
    dengan `data.mock_prices.HasilPrediksi` supaya halaman yang sudah ada
    (mis. panel Prediksi Harga di Detail Komoditas) tidak perlu berubah."""

    harga_sekarang: float
    harga_prediksi: float
    persen_perubahan: float
    model_dipakai: str
    trajektori: pd.Series  # harga harian H+1..H+horizon (untuk grafik)


def ramalkan_hasil_horizon(
    riwayat: pd.DataFrame, nama_komoditas: str, horizon: int
) -> HasilPeramalan:
    """Hasil ringkas peramalan untuk horizon yang dipilih pengguna (1/7/30 hari).

    Titik masuk utama modul ini untuk halaman — membungkus `ramalkan_harga`
    (lintasan harian penuh) jadi satu hasil siap-pakai: `harga_prediksi`
    adalah titik H+`horizon` dari lintasan itu, `persen_perubahan` dihitung
    terhadap harga aktual terakhir di `riwayat`.
    """
    harga_sekarang = float(riwayat.sort_values("tanggal")["harga"].iloc[-1])

    trajektori = ramalkan_harga(riwayat, nama_komoditas, horizon)
    harga_prediksi = float(trajektori.iloc[-1])
    persen_perubahan = (harga_prediksi - harga_sekarang) / harga_sekarang * 100

    return HasilPeramalan(
        harga_sekarang=harga_sekarang,
        harga_prediksi=harga_prediksi,
        persen_perubahan=persen_perubahan,
        model_dipakai=NAMA_MODEL,
        trajektori=trajektori,
    )
