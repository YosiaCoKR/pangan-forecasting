"""Cek `forecast.susun_last_window` (skala log1p, panjang window, celah tanggal)
dan registry `forecast.MODEL_TERSEDIA` (artefak lengkap, kedua model bisa meramal).

Jalankan: `python test_forecast.py` (dari folder streamlit_app).
"""

import numpy as np
import pandas as pd

import forecast

tanggal = pd.date_range("2025-01-01", periods=40, freq="D").delete(10)  # satu hari bolong
riwayat = pd.DataFrame({"tanggal": tanggal, "harga": np.linspace(13000, 14000, len(tanggal))})

lw = forecast.susun_last_window(riwayat, window_size=31)
assert len(lw) == 31 and lw.index.freqstr == "D"
assert np.allclose(np.expm1(lw.iloc[-1]) * forecast.SKALA_HARGA, 14000)

try:
    forecast.susun_last_window(riwayat.head(5), window_size=31)
    raise AssertionError("riwayat pendek harus ditolak")
except forecast.ModelRisetError:
    pass

print("ok last_window")

# --- registry model: tiap model punya 27 artefak (9 komoditas x 3 horizon) ---
for kunci, info in forecast.MODEL_TERSEDIA.items():
    assert info.kunci == kunci, f"kunci registry {kunci} tidak konsisten"
    folder = forecast.RESEARCH_DIR / info.folder
    assert folder.is_dir(), f"folder artefak {folder} tidak ada"
    jumlah = len(list(folder.glob(f"{info.prefix}_*_h*.joblib")))
    assert jumlah == 27, f"{kunci}: {jumlah} artefak cocok prefix, harusnya 27"

assert forecast.MODEL_DEFAULT in forecast.MODEL_TERSEDIA
assert forecast.model_aktif().kunci in forecast.MODEL_TERSEDIA

try:
    forecast.muat_forecaster("Beras Kualitas Medium I", 7, "model_tidak_ada")
    raise AssertionError("kunci model asing harus ditolak")
except ValueError:
    pass

# Kedua model benar-benar bisa dimuat & meramal dari riwayat yang sama,
# dan hasilnya BEDA — bukti pilihan model di admin benar-benar nyambung.
_hasil = {}
for kunci in forecast.MODEL_TERSEDIA:
    pred = forecast.ramalkan_harga.__wrapped__(riwayat, "Beras Kualitas Medium I", 7, kunci)
    assert len(pred) == 7 and (pred > 0).all(), f"{kunci}: prediksi tidak wajar"
    _hasil[kunci] = pred.to_numpy()

assert not np.allclose(_hasil["lightgbm"], _hasil["xgboost"]), (
    "LightGBM & XGBoost memberi prediksi identik — kemungkinan folder/prefix artefak tertukar"
)

print("ok model registry")
