"""Daftar komoditas pangan — DITURUNKAN dari kolom `DATASET-BERAS.csv`.

Bukan lagi daftar hardcode: nama komoditas = nama kolom dataset riset, persis
sama dengan yang dipakai notebook sebagai bagian nama file artefak model
(`final_lgbm_<nama>_h<horizon>.joblib`). Jadi kalau dataset diganti/diperluas
lalu notebook dijalankan ulang, seluruh aplikasi (dashboard, input harga
admin, pengaturan ambang) otomatis ikut kolom barunya tanpa edit kode.

`slug` dibuat dari nama (lowercase, spasi jadi `-`) supaya tetap cocok dengan
kunci `ambang_ews` di `config.json` yang sudah tersimpan.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from functools import lru_cache

import forecast
import pandas as pd


@dataclass(frozen=True)
class Komoditas:
    slug: str
    nama: str
    unit: str
    kategori: str
    ikon: str


# Kata kunci pertama yang cocok di nama komoditas menentukan kategori & ikon.
# Komoditas baru yang tak cocok mana pun jatuh ke "lainnya" — tetap tampil,
# cuma ikonnya generik.
_PETA_KATEGORI: tuple[tuple[str, str, str, str], ...] = (
    ("beras", "beras", "🌾 Beras", "🌾"),
    ("bawang", "bumbu", "🧅 Bumbu Dapur", "🧅"),
    ("cabai", "bumbu", "🧅 Bumbu Dapur", "🌶️"),
)
_KATEGORI_LAINNYA = ("lainnya", "📦 Lainnya", "📦")


def buat_slug(nama: str) -> str:
    """ "Beras Kualitas Bawah I" -> "beras-kualitas-bawah-i"."""
    return re.sub(r"[^a-z0-9]+", "-", nama.lower()).strip("-")


def _kategori_ikon(nama: str) -> tuple[str, str, str]:
    nama_kecil = nama.lower()
    for kata, kategori, label, ikon in _PETA_KATEGORI:
        if kata in nama_kecil:
            return kategori, label, ikon
    return _KATEGORI_LAINNYA


@lru_cache(maxsize=1)
def nama_kolom_dataset() -> tuple[str, ...]:
    """Nama kolom harga di `DATASET-BERAS.csv` (tanpa kolom `tanggal`).

    Cuma header yang dibaca (`nrows=0`), jadi murah dipanggil dari mana pun;
    hasilnya di-cache sekali per proses.
    """
    kolom = pd.read_csv(forecast.RESEARCH_DIR / "DATASET-BERAS.csv", nrows=0).columns
    return tuple(k for k in kolom if k != "tanggal")


def get_komoditas_list() -> list[Komoditas]:
    """Semua komoditas sesuai kolom dataset riset, urut seperti di dataset."""
    hasil = []
    for nama in nama_kolom_dataset():
        kategori, _label, ikon = _kategori_ikon(nama)
        hasil.append(Komoditas(buat_slug(nama), nama, "kg", kategori, ikon))
    return hasil


def get_komoditas_by_slug(slug: str) -> Komoditas | None:
    return next((k for k in get_komoditas_list() if k.slug == slug), None)


def get_kategori_list() -> list[tuple[str, str]]:
    """Urutan kategori untuk pengelompokan tampilan: (kunci, label).

    Hanya kategori yang benar-benar ada komoditasnya — kalau dataset baru
    tidak punya cabai/bawang, grup "Bumbu Dapur" tidak ikut tampil kosong.
    """
    kategori_ada = {k.kategori for k in get_komoditas_list()}
    urut = [(kat, label) for _kata, kat, label, _ikon in _PETA_KATEGORI] + [
        (_KATEGORI_LAINNYA[0], _KATEGORI_LAINNYA[1])
    ]
    terlihat: list[tuple[str, str]] = []
    for kategori, label in urut:
        if kategori in kategori_ada and kategori not in {k for k, _ in terlihat}:
            terlihat.append((kategori, label))
    return terlihat
