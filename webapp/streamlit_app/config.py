"""Konfigurasi aplikasi yang bisa diubah admin lewat panel (mis. model aktif,
ambang batas peringatan dini per komoditas).

Disimpan di `config.json` (bukan environment variable) karena nilainya
berubah lewat interaksi admin saat aplikasi berjalan, beda dengan
`ADMIN_PASSWORD` yang disetel sekali saat deploy — lihat `auth.py`.
"""

from __future__ import annotations

import json
from pathlib import Path

_CONFIG_PATH = Path(__file__).parent / "config.json"

# Ambang default "wajar" — kenaikan >10% dari harga sekarang dianggap layak
# diperingatkan untuk komoditas pangan pokok mana pun; `harga_tetap` dibiarkan
# kosong (belum ada batas absolut) sampai admin menetapkannya sendiri lewat
# halaman Pengaturan Ambang. Daftar slug di-hardcode (bukan import dari
# `data.mock_commodities`) supaya modul konfigurasi ini tetap berdiri sendiri
# tanpa bergantung ke lapisan data.
_PERSEN_KENAIKAN_DEFAULT = 10.0
# Dipakai halaman Pengaturan Ambang untuk tombol "Reset ke Default" —
# publik (bukan `_AMBANG_EWS_DEFAULT`) karena dibaca dari luar modul ini.
AMBANG_EWS_DEFAULT = {"harga_tetap": None, "persen_kenaikan": _PERSEN_KENAIKAN_DEFAULT}
_SLUG_KOMODITAS = (
    "beras-kualitas-bawah-i",
    "beras-kualitas-bawah-ii",
    "beras-kualitas-medium-i",
    "beras-kualitas-medium-ii",
    "beras-kualitas-super-i",
    "beras-kualitas-super-ii",
    "bawang-merah-ukuran-sedang",
    "cabai-rawit-hijau",
    "cabai-rawit-merah",
)


def _ambang_ews_default() -> dict[str, dict]:
    return {
        slug: {"harga_tetap": None, "persen_kenaikan": _PERSEN_KENAIKAN_DEFAULT}
        for slug in _SLUG_KOMODITAS
    }


_DEFAULT_CONFIG = {"model_aktif": None, "ambang_ews": _ambang_ews_default()}


def _muat_config() -> dict:
    if _CONFIG_PATH.exists():
        try:
            with open(_CONFIG_PATH, encoding="utf-8") as berkas:
                return {**_DEFAULT_CONFIG, **json.load(berkas)}
        except (json.JSONDecodeError, OSError):
            # config.json rusak/kosong (mis. proses server terhenti di tengah
            # penulisan) — jangan sampai seluruh halaman admin ikut error,
            # kembali ke default dan biarkan admin menyimpan ulang pilihannya.
            return dict(_DEFAULT_CONFIG)
    return dict(_DEFAULT_CONFIG)


def _simpan_config(config: dict) -> None:
    # Tulis ke berkas sementara lalu rename (atomik di level filesystem) —
    # supaya config.json tidak pernah dalam keadaan terpotong separuh kalau
    # proses server mati persis saat menulis.
    berkas_sementara = _CONFIG_PATH.with_suffix(".json.tmp")
    with open(berkas_sementara, "w", encoding="utf-8") as berkas:
        json.dump(config, berkas, indent=2)
    berkas_sementara.replace(_CONFIG_PATH)


def get_model_aktif() -> str | None:
    return _muat_config().get("model_aktif")


def set_model_aktif(nama_file: str) -> None:
    config = _muat_config()
    config["model_aktif"] = nama_file
    _simpan_config(config)


def get_ambang_ews(slug: str) -> dict:
    """Ambang EWS (`harga_tetap`, `persen_kenaikan`) untuk satu komoditas —
    nilai default kalau belum pernah diubah admin lewat Pengaturan Ambang."""
    ambang = _muat_config()["ambang_ews"]
    return ambang.get(slug, {"harga_tetap": None, "persen_kenaikan": _PERSEN_KENAIKAN_DEFAULT})


def set_ambang_ews(slug: str, *, harga_tetap: float | None, persen_kenaikan: float | None) -> None:
    """Simpan ambang EWS satu komoditas — komoditas lain tidak ikut berubah."""
    config = _muat_config()
    config["ambang_ews"][slug] = {"harga_tetap": harga_tetap, "persen_kenaikan": persen_kenaikan}
    _simpan_config(config)


def reset_ambang_ews(slug: str) -> None:
    """Kembalikan ambang EWS satu komoditas ke nilai default (`AMBANG_EWS_DEFAULT`)."""
    set_ambang_ews(
        slug,
        harga_tetap=AMBANG_EWS_DEFAULT["harga_tetap"],
        persen_kenaikan=AMBANG_EWS_DEFAULT["persen_kenaikan"],
    )
