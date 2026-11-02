"""Cek kesiapan hosting: dataset yang dibaca app = dataset yang melatih model.

Jalankan: `python test_deploy_siap.py` (dari folder streamlit_app).

Ini jaring pengaman untuk deploy. Yang gampang rusak tanpa error tampak:
- `forecast.DATASET_PATH` diarahkan balik ke dataset lama, sementara artefak
  di `final_lgbm/`/`final_xgb/` dilatih dengan DATASET-BERAS-NEW.csv;
- versi pustaka di `requirements.txt` root dilonggarkan, lalu
  `load_forecaster()` memuat pickle tapi memberi angka berbeda.

Keduanya tidak melempar exception di halaman — grafik cuma jadi salah. Jadi
di sini yang dicek: berkas datasetnya benar, kolomnya cocok dengan nama
artefak, dan SEMUA komoditas x horizon benar-benar bisa diramalkan.
"""

import pandas as pd

import forecast
from data.mock_commodities import get_komoditas_list
from data.mock_prices import get_price_history

# 1. App harus membaca dataset yang dipakai melatih artefak Okt-2026.
assert forecast.DATASET_PATH.name == "DATASET-BERAS-NEW.csv", (
    f"App membaca {forecast.DATASET_PATH.name}, padahal artefak di "
    f"{forecast.MODEL_TERSEDIA['lightgbm'].folder}/ dilatih dengan DATASET-BERAS-NEW.csv"
)
assert forecast.DATASET_PATH.exists(), f"Dataset tidak ada: {forecast.DATASET_PATH}"

# 2. Satu-satunya sumber nama berkas dataset adalah DATASET_PATH — kalau ada
#    modul yang membaca CSV lain, daftar komoditas bisa menyimpang dari nama
#    artefak dan prediksi gagal diam-diam.
kolom_dataset = tuple(
    k for k in pd.read_csv(forecast.DATASET_PATH, nrows=0).columns if k != "tanggal"
)
komoditas = get_komoditas_list()
assert tuple(k.nama for k in komoditas) == kolom_dataset, (
    "Daftar komoditas tidak sama dengan kolom dataset: "
    f"{[k.nama for k in komoditas]} vs {list(kolom_dataset)}"
)
assert len(komoditas) == 9, f"Harap 9 komoditas, dapat {len(komoditas)}"

# 3. Tiap komoditas x horizon harus punya artefak DAN bisa menghasilkan angka
#    yang masuk akal. Dicek untuk SEMUA model yang bisa dipilih admin, karena
#    halaman Pengaturan Model mengizinkan override per komoditas.
diperiksa = 0
for kunci_model in forecast.MODEL_TERSEDIA:
    for kom in komoditas:
        riwayat = get_price_history(kom.slug, 90)
        harga_kini = float(riwayat.sort_values("tanggal")["harga"].iloc[-1])
        for horizon in forecast.HORIZON_TERSEDIA:
            hasil = forecast.ramalkan_hasil_horizon(
                riwayat, kom.nama, horizon, kunci_model=kunci_model
            )
            label = f"{kunci_model}/{kom.nama}/h{horizon}"
            assert len(hasil.trajektori) == horizon, (
                f"{label}: lintasan {len(hasil.trajektori)} titik, harap {horizon}"
            )
            # Harga pangan tidak melompat >80% dalam 30 hari; batas longgar ini
            # cuma untuk menangkap artefak basi / skala kebalik (mis. lupa
            # expm1 atau SKALA_HARGA), bukan menilai akurasi model.
            assert 0 < hasil.harga_prediksi < harga_kini * 1.8, (
                f"{label}: prediksi Rp{hasil.harga_prediksi:,.0f} tidak masuk akal "
                f"(harga kini Rp{harga_kini:,.0f}) — artefak basi atau skala kebalik?"
            )
            assert abs(hasil.persen_perubahan) < 80, (
                f"{label}: perubahan {hasil.persen_perubahan:+.1f}% di luar batas waras"
            )
            diperiksa += 1

print(f"OK — dataset {forecast.DATASET_PATH.name}, {len(komoditas)} komoditas, "
      f"{diperiksa} prediksi (model x komoditas x horizon) lolos.")
