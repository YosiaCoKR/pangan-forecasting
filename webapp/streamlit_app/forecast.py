"""Pemuat model riset (MSTL + GA-LightGBM) — TIDAK melatih ulang di sini.

Memuat 3 jenis artefak dari `webapp/research/` (read-only, hasil pipeline
`code.ipynb`) dan meng-cache-nya di memori supaya cuma dibaca dari disk
sekali per proses Streamlit:

- `models/trend_model.pkl`    — dict[nama_komoditas] -> sktime `TrendForecaster`
  (ekstrapolasi komponen trend MSTL).
- `models/seasonal_model.pkl` — dict[nama_komoditas] -> statsmodels
  `DecomposeResult` (hasil `MSTL(...).fit()`; punya `.trend`, `.seasonal`,
  `.resid` dari data train riset).
- `final_model/final_model_prediction_<nama_komoditas>_h<horizon>.joblib`
  — skforecast `ForecasterDirect` (GA-LightGBM) yang dilatih di residual
  MSTL train, satu per komoditas x horizon (1/7/30 hari).

`nama_komoditas` di sini adalah nama tampilan komoditas (mis. "Beras
Kualitas Bawah I") — persis sama dengan `Komoditas.nama` di
`data.mock_commodities` dan nama kolom di `DATASET-BERAS.csv`, karena itu
yang dipakai sebagai bagian nama file artefak oleh notebook riset.

Catatan: PRD menyebut nama artefak `stl_results.pkl` & `trend_models.pkl`,
namun pipeline riset yang sebenarnya (`code.ipynb`) menghasilkan
`models/seasonal_model.pkl` & `models/trend_model.pkl` — modul ini memuat
nama file yang benar-benar ada di `webapp/research/`.

`susun_residual_mstl` menyusun fitur residual dari harga terbaru sebagai
`last_window`, dan `ramalkan_harga` memakainya untuk meramal H+1..H+30
lewat forecaster GA-LightGBM yang sudah terlatih (tanpa retraining) —
lihat docstring masing-masing fungsi untuk detail alurnya.

`ramalkan_harga` di-cache lewat `st.cache_data`, di-kunci dari ISI
`riwayat` (bukan cuma nama/horizon) — begitu admin menyimpan harga baru,
`riwayat` berubah, kunci cache ikut berubah, dan hasil lama otomatis tidak
terpakai lagi tanpa perlu kode invalidasi manual.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import joblib
import numpy as np
import pandas as pd
import streamlit as st
from skforecast.utils import load_forecaster
from sktime.forecasting.trend import TrendForecaster
from statsmodels.tsa.seasonal import DecomposeResult

RESEARCH_DIR = Path(__file__).resolve().parent.parent / "research"
MODELS_DIR = RESEARCH_DIR / "models"
FINAL_MODEL_DIR = RESEARCH_DIR / "final_model"

HORIZON_TERSEDIA: tuple[int, ...] = (1, 7, 30)
NAMA_MODEL = "GA-LightGBM + MSTL (riset)"

# Model riset dilatih pada harga dalam RIBUAN rupiah (mis. nilai `13.25` di
# DATASET-BERAS.csv = Rp 13.250/kg) — dikonfirmasi lewat `mstl.observed`
# (skala puluhan, bukan puluhan-ribu). Semua konversi ke/dari Rupiah aktual
# di aplikasi web harus lewat konstanta ini.
SKALA_HARGA = 1000


class ModelRisetError(RuntimeError):
    """Artefak model riset (.pkl/.joblib) tidak ditemukan atau gagal dimuat."""


_cache_trend_model: dict[str, TrendForecaster] | None = None
_cache_seasonal_model: dict[str, DecomposeResult] | None = None
_cache_forecaster: dict[tuple[str, int], Any] = {}


def _muat_pkl(path: Path, label: str) -> Any:
    if not path.exists():
        raise ModelRisetError(f"{label} tidak ditemukan di {path}.")
    try:
        return joblib.load(path)
    except Exception as exc:  # noqa: BLE001 — dibungkus jadi error domain yang jelas
        raise ModelRisetError(f"Gagal memuat {label} dari {path}: {exc}") from exc


def muat_trend_model() -> dict[str, TrendForecaster]:
    """dict[nama_komoditas] -> `TrendForecaster` (cached, dimuat sekali)."""
    global _cache_trend_model
    if _cache_trend_model is None:
        _cache_trend_model = _muat_pkl(MODELS_DIR / "trend_model.pkl", "Trend model")
    return _cache_trend_model


def muat_seasonal_model() -> dict[str, DecomposeResult]:
    """dict[nama_komoditas] -> `DecomposeResult` hasil MSTL train (cached)."""
    global _cache_seasonal_model
    if _cache_seasonal_model is None:
        _cache_seasonal_model = _muat_pkl(MODELS_DIR / "seasonal_model.pkl", "Seasonal model (MSTL)")
    return _cache_seasonal_model


def muat_forecaster_residual(nama_komoditas: str, horizon: int) -> Any:
    """`ForecasterDirect` (GA-LightGBM) residual untuk satu komoditas x horizon (cached)."""
    if horizon not in HORIZON_TERSEDIA:
        raise ValueError(f"Horizon {horizon} tidak didukung — pilih salah satu dari {HORIZON_TERSEDIA}.")

    kunci = (nama_komoditas, horizon)
    if kunci not in _cache_forecaster:
        path = FINAL_MODEL_DIR / f"final_model_prediction_{nama_komoditas}_h{horizon}.joblib"
        if not path.exists():
            raise ModelRisetError(f"Forecaster residual tidak ditemukan untuk '{nama_komoditas}' h={horizon} ({path}).")
        try:
            _cache_forecaster[kunci] = load_forecaster(str(path), verbose=False, suppress_warnings=True)
        except Exception as exc:  # noqa: BLE001
            raise ModelRisetError(f"Gagal memuat forecaster residual dari {path}: {exc}") from exc
    return _cache_forecaster[kunci]


def muat_model_komoditas(nama_komoditas: str, horizon: int) -> dict[str, Any]:
    """Muat trio model (trend, MSTL/seasonal, forecaster residual) untuk satu komoditas x horizon.

    Semua dimuat dari artefak hasil riset tanpa pelatihan ulang. Dipakai
    sebagai titik masuk oleh pra-proses MSTL & peramalan bertahap pada
    task selanjutnya.
    """
    trend_model = muat_trend_model()
    seasonal_model = muat_seasonal_model()

    if nama_komoditas not in trend_model:
        raise ModelRisetError(f"Trend model untuk '{nama_komoditas}' tidak ditemukan.")
    if nama_komoditas not in seasonal_model:
        raise ModelRisetError(f"Seasonal model (MSTL) untuk '{nama_komoditas}' tidak ditemukan.")

    return {
        "trend_forecaster": trend_model[nama_komoditas],
        "mstl": seasonal_model[nama_komoditas],
        "forecaster_residual": muat_forecaster_residual(nama_komoditas, horizon),
    }


def daftar_komoditas_tersedia() -> list[str]:
    """Nama komoditas yang punya trend & seasonal model — untuk validasi/diagnostik."""
    return sorted(muat_trend_model().keys())


def _tile_last_cycle(values: np.ndarray, period: int, n_steps: int) -> np.ndarray:
    """Ulang siklus terakhir (mis. 7 titik musiman mingguan) sampai `n_steps` — sama seperti
    `tile_last_cycle` di `code.ipynb`, dipakai untuk memproyeksikan komponen musiman MSTL
    yang sudah beku (tidak di-refit) ke tanggal-tanggal setelah akhir data train."""
    cycle = np.asarray(values, dtype=float)[-period:]
    reps = int(np.ceil(n_steps / period))
    return np.tile(cycle, reps)[:n_steps]


def _komponen_trend_musiman(tanggal_index: pd.DatetimeIndex, akhir_train: pd.Timestamp, trend_forecaster: TrendForecaster, mstl: DecomposeResult) -> np.ndarray:
    """Trend (diekstrapolasi) + musiman (di-tile) untuk tiap tanggal di `tanggal_index`,
    relatif terhadap `akhir_train` — dipakai baik untuk menyusun residual (dikurangkan
    dari harga aktual) maupun merekonstruksi harga dari residual prediksi (dijumlahkan)."""
    langkah = (tanggal_index - akhir_train).days.to_numpy()
    n_steps = int(langkah.max())

    trend_pred = np.asarray(trend_forecaster.predict(fh=np.arange(1, n_steps + 1))).ravel()
    seasonal_mingguan = _tile_last_cycle(mstl.seasonal["seasonal_7"].values, 7, n_steps)
    seasonal_tahunan = _tile_last_cycle(mstl.seasonal["seasonal_365"].values, 365, n_steps)

    idx = langkah - 1  # step ke-k (1-based) -> indeks array ke-(k-1)
    return trend_pred[idx] + seasonal_mingguan[idx] + seasonal_tahunan[idx]


def susun_residual_mstl(riwayat: pd.DataFrame, trend_forecaster: TrendForecaster, mstl: DecomposeResult) -> pd.Series:
    """Susun deret residual MSTL (fitur input forecaster) dari harga TERBARU.

    `riwayat` adalah DataFrame kolom `tanggal`/`harga` dalam Rupiah (bentuk
    yang dikembalikan `data.mock_prices.get_price_history`).

    Trend & musiman dipakai dari model yang SUDAH terlatih (tanpa refit
    MSTL) — trend diekstrapolasi lewat `trend_forecaster.predict`, musiman
    di-tile dari pola siklus terakhir hasil training. Ini kebalikan dari
    `reconstruct_harga_test` di `code.ipynb`: di sana trend+musiman+residual
    dijumlah untuk merekonstruksi harga; di sini trend+musiman dikurangkan
    dari harga aktual untuk mendapatkan residual sebagai fitur.

    Hanya titik dengan tanggal SETELAH akhir data train model
    (`mstl.trend.index[-1]`) yang dihitung — itulah rentang yang belum
    "diketahui" modelnya sehingga residualnya relevan sebagai `last_window`
    forecaster pada langkah peramalan bertahap.

    Mengembalikan `pd.Series` residual (indeks tanggal) dalam skala model
    (`SKALA_HARGA`) — BUKAN Rupiah. Kosong kalau tidak ada titik `riwayat`
    yang jatuh setelah akhir data train.
    """
    akhir_train = mstl.trend.index[-1]

    harga = riwayat.set_index("tanggal")["harga"].sort_index()
    harga_baru = harga[harga.index > akhir_train]
    if harga_baru.empty:
        return pd.Series(dtype=float, name="residual")

    komponen = _komponen_trend_musiman(harga_baru.index, akhir_train, trend_forecaster, mstl)
    harga_skala_model = harga_baru.to_numpy() / SKALA_HARGA
    residual = harga_skala_model - komponen

    # ForecasterDirect mewajibkan `last_window` ber-frekuensi eksplisit (bukan
    # cuma DatetimeIndex biasa) — filtering di atas menghilangkan atribut
    # `.freq` walau tanggalnya tetap harian berurutan, jadi diset ulang.
    hasil = pd.Series(residual, index=harga_baru.index, name="residual").asfreq("D")
    return hasil


@st.cache_data(show_spinner="Menghitung prediksi...", ttl=3600, max_entries=200)
def ramalkan_harga(riwayat: pd.DataFrame, nama_komoditas: str, horizon: int) -> pd.Series:
    """Ramalkan harga H+1..H+`horizon` (Rupiah) dari harga TERBARU — tanpa pelatihan ulang.

    Di-cache (`st.cache_data`) memakai `riwayat` sebagai bagian kunci cache —
    dipanggil ulang dengan riwayat yang identik akan langsung mengembalikan
    hasil tersimpan tanpa menjalankan forecaster lagi. Kunci otomatis
    berubah begitu `riwayat` berubah (mis. admin menyimpan harga baru), jadi
    entri lama otomatis tidak pernah terpakai lagi tanpa perlu invalidasi
    manual — `ttl=3600` (1 jam) & `max_entries=200` cuma jaring pengaman
    supaya entri basi/menumpuk tidak menahan memori selamanya di proses
    yang jalan lama.

    Alurnya (menumpang pola `code.ipynb`, dibalik untuk data baru/live):
    1. `susun_residual_mstl` menyusun residual dari harga terbaru sebagai
       `last_window` forecaster GA-LightGBM (`forecaster_residual`).
    2. Forecaster memprediksi residual H+1..H+`horizon` sekaligus —
       skforecast `ForecasterDirect` memakai fitur lag/rolling/kalender
       dari `last_window` untuk tiap langkah, setara secara konsep dengan
       "satu langkah dimasukkan kembali ke deret" di notebook riset, tanpa
       melatih ulang estimator manapun.
    3. Setiap residual diubah balik jadi harga: `trend (diekstrapolasi) +
       musiman (di-tile) + residual`, persis `reconstruct_harga_test` di
       `code.ipynb`, lalu dikonversi ke Rupiah (kali `SKALA_HARGA`).

    Mengembalikan `pd.Series` harga (Rupiah) berindeks tanggal, dari H+1
    sampai H+`horizon` hari setelah titik data terakhir di `riwayat`.

    Melempar `ModelRisetError` kalau riwayat harga tidak cukup (tidak ada
    titik setelah akhir data train model, atau lebih pendek dari
    `window_size` forecaster) untuk menyusun `last_window`.
    """
    model = muat_model_komoditas(nama_komoditas, horizon)
    trend_forecaster = model["trend_forecaster"]
    mstl = model["mstl"]
    forecaster_residual = model["forecaster_residual"]

    akhir_train = mstl.trend.index[-1]
    last_window = susun_residual_mstl(riwayat, trend_forecaster, mstl)
    if last_window.empty:
        raise ModelRisetError(
            f"Tidak ada harga '{nama_komoditas}' setelah akhir data train model "
            f"({akhir_train.date()}) — tidak bisa menyusun last_window peramalan."
        )
    if len(last_window) < forecaster_residual.window_size:
        raise ModelRisetError(
            f"Riwayat harga '{nama_komoditas}' terlalu pendek ({len(last_window)} hari setelah "
            f"akhir data train) — forecaster butuh minimal {forecaster_residual.window_size} hari."
        )

    residual_pred = forecaster_residual.predict(steps=horizon, last_window=last_window)

    komponen = _komponen_trend_musiman(residual_pred.index, akhir_train, trend_forecaster, mstl)
    harga_rupiah = (residual_pred.to_numpy() + komponen) * SKALA_HARGA

    return pd.Series(harga_rupiah, index=residual_pred.index, name="harga_prediksi")


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


def ramalkan_hasil_horizon(riwayat: pd.DataFrame, nama_komoditas: str, horizon: int) -> HasilPeramalan:
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
