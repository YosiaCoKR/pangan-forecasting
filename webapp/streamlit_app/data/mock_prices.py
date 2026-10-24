from __future__ import annotations

import zlib
from dataclasses import dataclass
from datetime import datetime

import forecast
import numpy as np
import pandas as pd

from data.mock_commodities import Komoditas, get_komoditas_by_slug, get_komoditas_list

RENTANG_HARI_MAKS = 90


_HARGA_DASAR = {
    "beras-kualitas-bawah-i": 10_650,
    "beras-kualitas-bawah-ii": 10_150,
    "beras-kualitas-medium-i": 12_050,
    "beras-kualitas-medium-ii": 11_300,
    "beras-kualitas-super-i": 13_100,
    "beras-kualitas-super-ii": 12_700,
    "bawang-merah-ukuran-sedang": 34_500,
    "cabai-rawit-hijau": 58_000,
    "cabai-rawit-merah": 71_250,
}

_cache_riwayat: dict[str, pd.DataFrame] = {}
_cache_dataset_riset: pd.DataFrame | None = None


def _muat_dataset_riset() -> pd.DataFrame:

    global _cache_dataset_riset
    if _cache_dataset_riset is None:
        df = pd.read_csv(forecast.RESEARCH_DIR / "DATASET-BERAS.csv")
        df.index = pd.DatetimeIndex(df["tanggal"], yearfirst=True)
        df = df.drop(columns=["tanggal"]).asfreq("D")
        _cache_dataset_riset = df.interpolate(method="time", limit_direction="forward")
    return _cache_dataset_riset


def _riwayat_riset_komoditas(nama_komoditas: str) -> pd.DataFrame | None:

    dataset = _muat_dataset_riset()
    if nama_komoditas not in dataset.columns:
        return None

    harga = dataset[nama_komoditas].dropna() * forecast.SKALA_HARGA
    return pd.DataFrame({"tanggal": harga.index, "harga": harga.to_numpy()})


@dataclass(frozen=True)
class KartuHarga:
    komoditas: Komoditas
    harga_terbaru: float
    harga_kemarin: float
    diperbarui_pada: datetime


def _seed_dari_slug(slug: str) -> int:
    return zlib.crc32(slug.encode("utf-8"))


def _bangun_riwayat(slug: str, harga_dasar: float) -> pd.DataFrame:
    komoditas = get_komoditas_by_slug(slug)
    riwayat_riset = _riwayat_riset_komoditas(komoditas.nama) if komoditas else None
    if riwayat_riset is not None:
        return riwayat_riset

    rng = np.random.default_rng(_seed_dari_slug(slug))
    langkah = rng.normal(loc=0, scale=harga_dasar * 0.006, size=RENTANG_HARI_MAKS)
    jalan_acak = np.cumsum(langkah)
    harga = jalan_acak - jalan_acak[-1] + harga_dasar
    harga = np.clip(np.round(harga / 25) * 25, harga_dasar * 0.6, None)

    tanggal_akhir = datetime.now().date()
    tanggal = pd.date_range(end=tanggal_akhir, periods=RENTANG_HARI_MAKS, freq="D")
    return pd.DataFrame({"tanggal": tanggal, "harga": harga})


def get_price_history(slug: str, hari: int = RENTANG_HARI_MAKS) -> pd.DataFrame:
    if slug not in _cache_riwayat:
        harga_dasar = _HARGA_DASAR.get(slug, 10_000)
        _cache_riwayat[slug] = _bangun_riwayat(slug, harga_dasar)
    return _cache_riwayat[slug].tail(hari).reset_index(drop=True)


def get_kartu_harga(slug: str) -> KartuHarga | None:
    komoditas = get_komoditas_by_slug(slug)
    if komoditas is None:
        return None

    riwayat = get_price_history(slug, hari=2)
    if riwayat.empty:
        return None
    harga_terbaru = float(riwayat["harga"].iloc[-1])
    harga_kemarin = (
        float(riwayat["harga"].iloc[0]) if len(riwayat) > 1 else harga_terbaru
    )
    # Waktu update = tanggal titik harga TERAKHIR yang sungguhan (bukan lagi
    # jam-lalu tiruan) — `format_waktu_pembaruan` otomatis jatuh ke format
    # tanggal absolut kalau titik itu lebih dari 24 jam lalu, yang biasanya
    # benar di sini: riwayat riset berhenti di data train+test model, bisa
    # beberapa minggu sebelum hari ini sampai admin mengisi harga terbaru.
    diperbarui_pada = riwayat["tanggal"].iloc[-1].to_pydatetime()
    return KartuHarga(komoditas, harga_terbaru, harga_kemarin, diperbarui_pada)


def get_dashboard_cards() -> list[KartuHarga]:
    kartu = (get_kartu_harga(k.slug) for k in get_komoditas_list())
    return [k for k in kartu if k is not None]
