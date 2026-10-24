"""Cek `komponen_prediksi._rincian_harian`: penomoran H+, format harga, dan
yang paling penting — baris terakhir tabel HARUS setuju dengan metrik ringkas
(`persen_perubahan`) yang tampil di atas popover.

Jalankan: `python test_komponen_prediksi.py` (dari folder streamlit_app).
"""

import pandas as pd

import forecast
from komponen_prediksi import _rincian_harian

harga_sekarang = 10_000.0
trajektori = pd.Series(
    [10_100.0, 10_500.0, 9_900.0],
    index=pd.date_range("2026-01-02", periods=3, freq="D"),
)
hasil = forecast.HasilPeramalan(
    harga_sekarang=harga_sekarang,
    harga_prediksi=float(trajektori.iloc[-1]),
    persen_perubahan=(float(trajektori.iloc[-1]) - harga_sekarang) / harga_sekarang * 100,
    model_dipakai="uji",
    trajektori=trajektori,
)

tabel = _rincian_harian(hasil)

assert len(tabel) == len(trajektori), "jumlah baris harus sama dengan panjang lintasan"
assert list(tabel["Hari"]) == ["H+1", "H+2", "H+3"]
assert list(tabel["Tanggal"]) == ["02 Jan 2026", "03 Jan 2026", "04 Jan 2026"]
assert list(tabel["Harga"]) == ["Rp 10.100", "Rp 10.500", "Rp 9.900"]

# Kumulatif dari harga sekarang, bukan dari hari sebelumnya: H+3 turun ke 9.900
# berarti -1,00% dari 10.000 (kalau dihitung harian hasilnya -5,71%).
assert list(tabel["Perubahan"]) == ["+1.00%", "+5.00%", "-1.00%"]

# Invarian yang menjaga popover tidak berbohong terhadap metrik di atasnya.
assert tabel["Perubahan"].iloc[-1] == f"{hasil.persen_perubahan:+.2f}%"
assert tabel["Harga"].iloc[-1] == "Rp 9.900"

print("ok rincian harian")
