"""Cek metrik performa model yang ditampilkan halaman publik Performa Model.

Jalankan: `python test_metrik_model.py` (dari folder streamlit_app).
Read-only — cuma membaca `data/metrik_model.csv`, dataset, dan config.

Invarian yang dijaga: CSV metrik harus menutup SEMUA komoditas x horizon yang
dipakai aplikasi (kalau dataset riset bertambah kolom tapi CSV belum
diperbarui, halaman Performa Model akan kosong tanpa ada yang sadar), dan
kolom turunan harus mengambil metrik milik model pemenang — bukan minimum
per metrik.
"""

import forecast
import metrik_model
from data.mock_commodities import get_komoditas_list

df = metrik_model.muat_metrik()
nama_komoditas = [k.nama for k in get_komoditas_list()]

# --- cakupan: semua komoditas x horizon aplikasi ada di CSV ---
pasangan_csv = set(zip(df["komoditas"], df["horizon"]))
for nama in nama_komoditas:
    for h in forecast.HORIZON_TERSEDIA:
        assert (nama, h) in pasangan_csv, (
            f"metrik {nama} h={h} belum ada di data/metrik_model.csv — "
            "jalankan ulang notebook riset lalu perbarui CSV-nya"
        )

# --- model_terbaik harus nama model yang benar-benar dikenal aplikasi ---
nama_model_dikenal = {m.nama for m in forecast.MODEL_TERSEDIA.values()}
tak_dikenal = set(df["model_terbaik"]) - nama_model_dikenal
assert not tak_dikenal, f"model_terbaik tak dikenal: {tak_dikenal}"

# --- kolom turunan konsisten dengan model pemenang tiap baris ---
for nama in nama_komoditas:
    metrik = metrik_model.metrik_komoditas(nama)
    assert len(metrik) == len(forecast.HORIZON_TERSEDIA), f"{nama}: jumlah horizon salah"
    for _, baris in metrik.iterrows():
        kunci = "lightgbm" if baris["model_terbaik"] == "LightGBM" else "xgboost"
        assert baris["mape_terbaik"] == baris[f"mape_{kunci}"], (
            f"{nama} h={baris['horizon']}: mape_terbaik bukan milik {baris['model_terbaik']}"
        )
        assert baris["akurasi"] == 100 - baris["mape_terbaik"]
        assert baris["mae_rupiah"] == baris[f"mae_{kunci}"] * forecast.SKALA_HARGA
        assert baris["rmse_rupiah"] == baris[f"rmse_{kunci}"] * forecast.SKALA_HARGA
        # Pemenang tidak boleh lebih buruk dari pesaingnya (putusan notebook
        # memakai MAPE, jadi kalau ini gagal berarti CSV salah salin).
        pesaing = "xgboost" if kunci == "lightgbm" else "lightgbm"
        assert baris["mape_terbaik"] <= baris[f"mape_{pesaing}"], (
            f"{nama} h={baris['horizon']}: model_terbaik justru MAPE-nya lebih besar"
        )

print("OK: metrik model konsisten untuk", len(nama_komoditas), "komoditas")
