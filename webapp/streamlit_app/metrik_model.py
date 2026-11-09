"""Metrik performa model riset — dibaca dari `data/metrik_model.csv`.

Angkanya BUKAN hasil hitung ulang di aplikasi: itu salinan tabel
`df_walkforward_comparison` di `webapp/research/code_run_all_new.ipynb`
(backtesting walk-forward, 252 observasi per komoditas x horizon, refit tiap
fold) untuk LightGBM vs XGBoost, termasuk kolom putusan "Model Terbaik
(MAPE)" dari notebook itu sendiri.

Dipakai tabel walk-forward, bukan evaluasi sekali-jalan pada data test:
pada data test harga beras nyaris datar sehingga MAPE-nya ~0% (orde 1e-14)
dan akan terbaca seperti "model sempurna" di halaman publik. Walk-forward
mengevaluasi 252 titik berturut-turut, jadi angkanya jujur.

MAE/RMSE di CSV masih skala dataset riset (ribuan rupiah, lihat
`forecast.SKALA_HARGA`); konversi ke Rupiah terjadi di sini supaya halaman
tampilan tidak perlu tahu soal skala.

Latih ulang notebook -> perbarui CSV ini (satu berkas, tanpa sentuh kode).
"""

from __future__ import annotations

from pathlib import Path

import forecast
import pandas as pd

METRIK_PATH = Path(__file__).parent / "data" / "metrik_model.csv"

# Nama model di kolom `model_terbaik` CSV -> kunci di `forecast.MODEL_TERSEDIA`.
_KUNCI_MODEL = {"LightGBM": "lightgbm", "XGBoost": "xgboost"}


def muat_metrik() -> pd.DataFrame:
    return pd.read_csv(METRIK_PATH)


def metrik_komoditas(nama_komoditas: str) -> pd.DataFrame:
    """Baris metrik satu komoditas + kolom turunan model pemenangnya.

    Kolom turunan: `mape_terbaik`, `akurasi` (= 100 - MAPE), `mae_rupiah`,
    `rmse_rupiah` — semuanya mengikuti model di `model_terbaik`, bukan
    minimum per metrik, supaya satu baris tetap bercerita tentang SATU model.
    """
    df = muat_metrik()
    df = df[df["komoditas"] == nama_komoditas].sort_values("horizon").reset_index(drop=True)
    if df.empty:
        return df

    sufiks = df["model_terbaik"].map(_KUNCI_MODEL)
    pilih = lambda metrik: [  # noqa: E731 - ambil metrik milik model pemenang per baris
        df.at[i, f"{metrik}_{sufiks[i]}"] for i in df.index
    ]
    df["mape_terbaik"] = pilih("mape")
    df["akurasi"] = 100 - df["mape_terbaik"]
    df["mae_rupiah"] = [m * forecast.SKALA_HARGA for m in pilih("mae")]
    df["rmse_rupiah"] = [m * forecast.SKALA_HARGA for m in pilih("rmse")]
    return df
