"""Cek `forecast.susun_last_window`: skala log1p, panjang window, celah tanggal diisi.

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

print("ok")
