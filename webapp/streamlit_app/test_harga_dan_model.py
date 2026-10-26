"""Cek daftar komoditas dinamis (dari kolom dataset), simpan harga batch, dan
pemilihan model per komoditas.

Jalankan: `python test_harga_dan_model.py` (dari folder streamlit_app).
Tidak menyentuh `data/harga_historis.pkl` maupun `config.json` sungguhan —
keduanya dialihkan ke berkas sementara dulu.
"""

import json
import tempfile
from datetime import timedelta
from pathlib import Path

import pandas as pd

_tmp = Path(tempfile.mkdtemp(prefix="ppj-test-"))

import config

config._CONFIG_PATH = _tmp / "config.json"

import forecast
from data.mock_commodities import (
    buat_slug,
    get_kategori_list,
    get_komoditas_list,
    nama_kolom_dataset,
)

# --- daftar komoditas benar-benar mengikuti kolom dataset ---
kolom = nama_kolom_dataset()
komoditas = get_komoditas_list()
assert [k.nama for k in komoditas] == list(kolom), (
    "daftar komoditas tidak sama dengan kolom dataset"
)
assert "tanggal" not in kolom, "kolom tanggal tidak boleh jadi komoditas"
assert buat_slug("Beras Kualitas Bawah I") == "beras-kualitas-bawah-i"
# Slug harus tetap cocok dengan kunci `ambang_ews` yang sudah tersimpan,
# kalau tidak ambang EWS lama jadi tak terpakai tanpa ada yang sadar.
ambang_lama = json.loads(Path("config.json").read_text(encoding="utf-8"))["ambang_ews"]
assert set(k.slug for k in komoditas) == set(ambang_lama), (
    "slug bergeser dari kunci ambang_ews"
)
assert get_kategori_list(), "kategori tampilan tidak boleh kosong"
print("ok komoditas dinamis")

# --- artefak model ada untuk SETIAP komoditas x horizon x model ---
for info in forecast.MODEL_TERSEDIA.values():
    for k in komoditas:
        for horizon in forecast.HORIZON_TERSEDIA:
            path = info.path_artefak(k.nama, horizon)
            assert path.exists(), f"artefak hilang: {path}"
print("ok artefak lengkap per komoditas")

# --- model per komoditas: override > default global > MODEL_DEFAULT ---
config.set_model_aktif("lightgbm")
assert forecast.model_aktif().kunci == "lightgbm"
assert forecast.model_aktif("Beras Kualitas Bawah I").kunci == "lightgbm", (
    "tanpa override harus ikut default"
)

config.set_model_komoditas("Beras Kualitas Bawah I", "xgboost")
assert forecast.model_aktif("Beras Kualitas Bawah I").kunci == "xgboost", (
    "override tidak terpakai"
)
assert forecast.model_aktif("Beras Kualitas Medium I").kunci == "lightgbm", (
    "override bocor ke komoditas lain"
)
assert forecast.model_aktif().kunci == "lightgbm", "default global ikut berubah"

config.set_model_komoditas("Beras Kualitas Bawah I", None)
assert forecast.model_aktif("Beras Kualitas Bawah I").kunci == "lightgbm", (
    "override tidak terhapus"
)

config.set_model_komoditas("Beras Kualitas Bawah I", "model_hantu")
assert forecast.model_aktif("Beras Kualitas Bawah I").kunci == forecast.MODEL_DEFAULT, (
    "kunci model tak dikenal harus jatuh ke MODEL_DEFAULT, bukan KeyError"
)
config.set_model_komoditas("Beras Kualitas Bawah I", None)
print("ok model per komoditas")

# --- simpan harga batch: perbarui tanggal lama, tambah tanggal baru, persisten ---
from data import mock_prices

mock_prices._PKL_PATH = _tmp / "harga_historis.pkl"

slug_a, slug_b = komoditas[0].slug, komoditas[1].slug
# `hari` besar supaya dapat riwayat PENUH — default-nya cuma 90 hari terakhir,
# yang menyembunyikan baris baru karena jumlahnya tetap 90.
SEMUA = 10**6
sebelum = mock_prices.get_price_history(slug_a, hari=SEMUA)
baris_sebelum = len(sebelum)
tanggal_ada = sebelum["tanggal"].iloc[-1].date()

tersimpan = mock_prices.simpan_harga_batch(tanggal_ada, {slug_a: 99_000.0})
assert tersimpan == 1
sesudah = mock_prices.get_price_history(slug_a, hari=SEMUA)
assert len(sesudah) == baris_sebelum, (
    "tanggal yang sudah ada harus diperbarui, bukan diduplikasi"
)
assert mock_prices.harga_terakhir(slug_a) == 99_000.0

tanggal_baru = tanggal_ada + timedelta(days=1)
tersimpan = mock_prices.simpan_harga_batch(
    tanggal_baru, {slug_a: 12_345.0, slug_b: 11_111.0}
)
assert tersimpan == 2
assert len(mock_prices.get_price_history(slug_a, hari=SEMUA)) == baris_sebelum + 1
assert mock_prices.harga_terakhir(slug_a) == 12_345.0
assert mock_prices.harga_terakhir(slug_b) == 11_111.0
# Riwayat wajib tetap urut tanggal — forecaster membangun last_window dari ekornya.
tanggal_urut = mock_prices.get_price_history(slug_a, hari=SEMUA)["tanggal"]
assert tanggal_urut.is_monotonic_increasing, "riwayat tidak urut tanggal setelah simpan"

assert mock_prices._PKL_PATH.exists(), "`.pkl` tidak ditulis"
muat_ulang = pd.read_pickle(mock_prices._PKL_PATH)
assert float(muat_ulang[slug_a]["harga"].iloc[-1]) == 12_345.0, (
    "harga tidak bertahan di `.pkl`"
)
print("ok simpan harga batch")

# --- harga hasil input admin benar-benar mengubah prediksi ---
riwayat = mock_prices.get_price_history(
    komoditas[0].slug, hari=mock_prices.RENTANG_HARI_MAKS
)
pred = forecast.ramalkan_harga.__wrapped__(riwayat, komoditas[0].nama, 7, "lightgbm")
assert len(pred) == 7 and (pred > 0).all(), (
    "prediksi dari riwayat hasil edit admin tidak wajar"
)
print("ok prediksi dari riwayat tersimpan")

print("SEMUA OK")
