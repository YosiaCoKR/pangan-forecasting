"""Pemuat model riset (LightGBM / XGBoost hasil tuning, log + differencing) — TIDAK melatih ulang di sini.

Pipeline `code.ipynb` (bagian 17 dst.): target model adalah `log1p(harga)`
dengan harga dalam RIBUAN rupiah; differencing orde 1 dilakukan DI DALAM
skforecast `ForecasterDirect` (`differentiation=1`), jadi prediksinya sudah
kembali ke level log harga dan cukup dibalik dengan `expm1`. Tidak ada lagi
dekomposisi MSTL/trend/musiman.

Artefak yang dimuat (read-only, di-cache di memori per proses Streamlit)
— satu forecaster per komoditas x horizon (1/7/30 hari), untuk tiap model di
`MODEL_TERSEDIA`:
`final_lgbm/final_lgbm_<nama_komoditas>_h<horizon>.joblib` (LightGBM)
`final_xgb/final_xgb_<nama_komoditas>_h<horizon>.joblib` (XGBoost)

Model mana yang dipakai ditentukan admin lewat halaman Pengaturan Model
(tersimpan di `config.json`, dibaca lewat `model_aktif()`) — ada satu model
default global PLUS override opsional per komoditas, jadi mis. Beras Kualitas
Bawah I bisa pakai XGBoost sementara komoditas lain tetap LightGBM. Kedua artefak
dihasilkan pipeline yang sama di `code_run_all.ipynb` (bagian 35-43), jadi
jalur pemuatan, `window_size`, dan pembalikan skala-nya identik.

`nama_komoditas` adalah nama tampilan komoditas (mis. "Beras Kualitas Bawah
I") — persis sama dengan `Komoditas.nama` di `data.mock_commodities` dan
nama kolom di `DATASET-BERAS.csv`, karena itu yang dipakai notebook riset
sebagai bagian nama file artefak.

`ramalkan_harga` di-cache lewat `st.cache_data`, di-kunci dari ISI
`riwayat` (bukan cuma nama/horizon) — begitu admin menyimpan harga baru,
`riwayat` berubah, kunci cache ikut berubah, dan hasil lama otomatis tidak
terpakai lagi tanpa perlu kode invalidasi manual. `kunci_model` sengaja
dibuat parameter WAJIB di fungsi itu (bukan dibaca dari config di dalamnya)
supaya ikut jadi bagian kunci cache — kalau tidak, ganti model aktif akan
mengembalikan prediksi model lama dari cache.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import config
import numpy as np
import pandas as pd
import streamlit as st
from skforecast.utils import load_forecaster

RESEARCH_DIR = Path(__file__).resolve().parent.parent / "research"

HORIZON_TERSEDIA: tuple[int, ...] = (1, 7, 30)


@dataclass(frozen=True)
class InfoModel:
    """Satu model riset siap pakai — folder + prefix nama file artefaknya.

    `kunci` adalah nilai yang tersimpan di `config.json` (bukan `nama`),
    supaya label tampilan bisa diubah tanpa membuat pilihan admin yang
    sudah tersimpan jadi tidak dikenali lagi.
    """

    kunci: str
    nama: str
    deskripsi: str
    folder: str
    prefix: str

    def path_artefak(self, nama_komoditas: str, horizon: int) -> Path:
        return RESEARCH_DIR / self.folder / f"{self.prefix}_{nama_komoditas}_h{horizon}.joblib"


MODEL_TERSEDIA: dict[str, InfoModel] = {
    "lightgbm": InfoModel(
        kunci="lightgbm",
        nama="LightGBM",
        deskripsi="LightGBM, hyperparameter hasil tuning (objective regression_l1)",
        folder="final_lgbm",
        prefix="final_lgbm",
    ),
    "xgboost": InfoModel(
        kunci="xgboost",
        nama="XGBoost",
        deskripsi="XGBoost pembanding, protokol tuning identik (objective reg:absoluteerror)",
        folder="final_xgb",
        prefix="final_xgb",
    ),
}
MODEL_DEFAULT = "lightgbm"


def model_aktif(nama_komoditas: str | None = None) -> InfoModel:
    """Model yang dipilih admin di Pengaturan Model.

    Urutan prioritas: override khusus `nama_komoditas` (kalau admin
    menyetelnya) -> model default global -> `MODEL_DEFAULT`. Artefak memang
    satu per komoditas x horizon, jadi tiap komoditas boleh pakai model yang
    berbeda — mis. Beras Kualitas Bawah I pakai XGBoost sementara yang lain
    tetap LightGBM.

    Jatuh ke `MODEL_DEFAULT` kalau `config.json` belum pernah diisi ATAU
    berisi kunci yang tidak dikenal (mis. sisa konfigurasi versi lama) —
    halaman publik tidak boleh gagal cuma karena nilai konfigurasi basi.
    """
    kunci = config.get_model_komoditas(nama_komoditas) if nama_komoditas else None
    kunci = kunci or config.get_model_aktif() or MODEL_DEFAULT
    return MODEL_TERSEDIA.get(kunci, MODEL_TERSEDIA[MODEL_DEFAULT])

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


_cache_forecaster: dict[tuple[str, str, int], Any] = {}


def muat_forecaster(nama_komoditas: str, horizon: int, kunci_model: str) -> Any:
    """`ForecasterDirect` satu model x komoditas x horizon (cached per proses)."""
    if horizon not in HORIZON_TERSEDIA:
        raise ValueError(
            f"Horizon {horizon} tidak didukung, pilih salah satu dari {HORIZON_TERSEDIA}."
        )
    if kunci_model not in MODEL_TERSEDIA:
        raise ValueError(
            f"Model '{kunci_model}' tidak dikenal, pilih salah satu dari {tuple(MODEL_TERSEDIA)}."
        )

    info = MODEL_TERSEDIA[kunci_model]
    kunci = (kunci_model, nama_komoditas, horizon)
    if kunci not in _cache_forecaster:
        path = info.path_artefak(nama_komoditas, horizon)
        if not path.exists():
            raise ModelRisetError(
                f"Forecaster {info.nama} tidak ditemukan untuk "
                f"'{nama_komoditas}' h={horizon} ({path})."
            )
        try:
            forecaster = load_forecaster(str(path), verbose=False, suppress_warnings=True)
        except Exception as exc:
            raise ModelRisetError(f"Gagal memuat forecaster dari {path}: {exc}") from exc

        # ponytail: cek heuristik skala data latih, bukan versi artefak. Kalau
        # notebook kelak menyimpan metadata pipeline, cek metadata itu saja.
        if float(forecaster.last_window_.iloc[-1, 0]) < _BATAS_BAWAH_LOG:
            raise ModelRisetError(
                f"Forecaster {info.nama} '{nama_komoditas}' h={horizon} masih artefak lama "
                f"(bukan skala log1p) — jalankan ulang code_run_all.ipynb untuk "
                f"menyimpan ulang {info.folder}/."
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
def ramalkan_harga(
    riwayat: pd.DataFrame, nama_komoditas: str, horizon: int, kunci_model: str
) -> pd.Series:
    """Ramalkan harga H+1..H+`horizon` (Rupiah) dari harga TERBARU, tanpa pelatihan ulang.

    Di-cache (`st.cache_data`) memakai `riwayat` DAN `kunci_model` sebagai
    bagian kunci cache — riwayat identik dengan model yang sama langsung
    mengembalikan hasil tersimpan; begitu riwayat berubah (admin menyimpan
    harga baru) atau model aktif diganti, kuncinya ikut berubah. `ttl` &
    `max_entries` cuma jaring pengaman memori untuk proses yang jalan lama.

    `kunci_model` wajib diisi eksplisit (pakai `model_aktif().kunci` untuk
    model pilihan admin) justru supaya ikut masuk kunci cache.

    Mengembalikan `pd.Series` harga (Rupiah) berindeks tanggal, dari H+1
    sampai H+`horizon` hari setelah titik data terakhir di `riwayat`.
    """
    forecaster = muat_forecaster(nama_komoditas, horizon, kunci_model)
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
    riwayat: pd.DataFrame,
    nama_komoditas: str,
    horizon: int,
    kunci_model: str | None = None,
) -> HasilPeramalan:
    """Hasil ringkas peramalan untuk horizon yang dipilih pengguna (1/7/30 hari).

    Titik masuk utama modul ini untuk halaman — membungkus `ramalkan_harga`
    (lintasan harian penuh) jadi satu hasil siap-pakai: `harga_prediksi`
    adalah titik H+`horizon` dari lintasan itu, `persen_perubahan` dihitung
    terhadap harga aktual terakhir di `riwayat`.

    `kunci_model=None` (default) berarti pakai model pilihan admin —
    pembacaan config-nya dilakukan DI SINI, bukan di dalam `ramalkan_harga`
    yang di-cache, supaya kunci cache tetap menyebut model yang konkret.
    """
    info = MODEL_TERSEDIA[kunci_model] if kunci_model else model_aktif(nama_komoditas)
    harga_sekarang = float(riwayat.sort_values("tanggal")["harga"].iloc[-1])

    trajektori = ramalkan_harga(riwayat, nama_komoditas, horizon, info.kunci)
    harga_prediksi = float(trajektori.iloc[-1])
    persen_perubahan = (harga_prediksi - harga_sekarang) / harga_sekarang * 100

    return HasilPeramalan(
        harga_sekarang=harga_sekarang,
        harga_prediksi=harga_prediksi,
        persen_perubahan=persen_perubahan,
        model_dipakai=info.nama,
        trajektori=trajektori,
    )
