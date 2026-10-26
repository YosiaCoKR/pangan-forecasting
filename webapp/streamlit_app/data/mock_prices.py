"""Data harga historis — dasar dari dataset riset ASLI, edit admin persisten ke `.pkl`.

Riwayat tiap komoditas dimuat dari `DATASET-BERAS.csv` (dataset yang juga
dipakai melatih model — lihat `_muat_dataset_riset`). Harga yang disimpan
admin lewat halaman Input Harga Terbaru ditulis ke `harga_historis.pkl` di
sebelah modul ini dan dimuat balik saat aplikasi start, jadi tidak hilang
begitu proses berhenti.

Kolom dataset adalah satu-satunya sumber daftar komoditas (lihat
`data.mock_commodities`) — ganti dataset + jalankan ulang notebook, dan
riwayat, kartu dashboard, serta form input harga ikut berubah sendiri.
"""

from __future__ import annotations

import pickle
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

import forecast
import pandas as pd

from data.mock_commodities import Komoditas, get_komoditas_by_slug, get_komoditas_list

RENTANG_HARI_MAKS = 90
_PKL_PATH = Path(__file__).parent / "harga_historis.pkl"

_cache_riwayat: dict[str, pd.DataFrame] = {}
_cache_dataset_riset: pd.DataFrame | None = None


def _muat_dataset_riset() -> pd.DataFrame:
    """Muat & bersihkan `DATASET-BERAS.csv` sekali per proses (cached).

    Pra-proses persis sama seperti notebook riset (`asfreq("D")` + interpolasi
    berbasis waktu) supaya konsisten dengan data yang dipakai melatih model.
    """
    global _cache_dataset_riset
    if _cache_dataset_riset is None:
        df = pd.read_csv(forecast.RESEARCH_DIR / "DATASET-BERAS.csv")
        df.index = pd.DatetimeIndex(df["tanggal"], yearfirst=True)
        df = df.drop(columns=["tanggal"]).asfreq("D")
        _cache_dataset_riset = df.interpolate(method="time", limit_direction="forward")
    return _cache_dataset_riset


def _riwayat_riset_komoditas(nama_komoditas: str) -> pd.DataFrame | None:
    """Riwayat harga (Rupiah aktual, kolom tanggal/harga) satu komoditas dari
    dataset riset, atau `None` kalau kolomnya tidak ada di dataset."""
    dataset = _muat_dataset_riset()
    if nama_komoditas not in dataset.columns:
        return None

    # Nilai CSV dalam RIBUAN rupiah (sama seperti training model — lihat
    # `forecast.SKALA_HARGA`), dikonversi ke Rupiah aktual di sini supaya
    # kontrak `get_price_history` (selalu Rupiah aktual) konsisten.
    harga = dataset[nama_komoditas].dropna() * forecast.SKALA_HARGA
    return pd.DataFrame({"tanggal": harga.index, "harga": harga.to_numpy()})


def _muat_riwayat_dari_pkl() -> None:
    """Muat harga hasil input admin sebelumnya (kalau ada) saat modul di-import."""
    if _PKL_PATH.exists():
        try:
            with open(_PKL_PATH, "rb") as berkas:
                _cache_riwayat.update(pickle.load(berkas))
        except Exception:
            # `.pkl` korup/separuh tertulis — jangan sampai seluruh aplikasi
            # gagal start; riwayat jatuh ke dataset riset saja.
            _cache_riwayat.clear()


def _simpan_riwayat_ke_pkl() -> None:
    """Tulis seluruh cache riwayat ke `.pkl` (atomik: tulis `.tmp` lalu rename)."""
    sementara = _PKL_PATH.with_suffix(".pkl.tmp")
    with open(sementara, "wb") as berkas:
        pickle.dump(_cache_riwayat, berkas)
    sementara.replace(_PKL_PATH)


_muat_riwayat_dari_pkl()


@dataclass(frozen=True)
class KartuHarga:
    komoditas: Komoditas
    harga_terbaru: float
    harga_kemarin: float
    diperbarui_pada: datetime


def get_price_history(slug: str, hari: int = RENTANG_HARI_MAKS) -> pd.DataFrame:
    """Riwayat harga harian (kolom: tanggal, harga) untuk `hari` terakhir."""
    if slug not in _cache_riwayat:
        komoditas = get_komoditas_by_slug(slug)
        riwayat = _riwayat_riset_komoditas(komoditas.nama) if komoditas else None
        if riwayat is None:
            return pd.DataFrame(columns=["tanggal", "harga"])
        _cache_riwayat[slug] = riwayat
    return _cache_riwayat[slug].tail(hari).reset_index(drop=True)


def harga_terakhir(slug: str) -> float | None:
    """Harga terbaru satu komoditas — dipakai form admin sebagai nilai awal."""
    riwayat = get_price_history(slug, hari=1)
    return None if riwayat.empty else float(riwayat["harga"].iloc[-1])


def simpan_harga_batch(tanggal, harga_per_slug: dict[str, float]) -> int:
    """Simpan harga beberapa komoditas sekaligus untuk SATU tanggal.

    Titik yang tanggalnya sudah ada di riwayat DIPERBARUI (bukan diduplikasi),
    yang belum ada ditambahkan. `.pkl` ditulis sekali di akhir, bukan per
    komoditas, supaya menyimpan 9 kolom tetap satu operasi tulis.

    Cache prediksi tidak perlu diinvalidasi manual: kunci `st.cache_data` di
    `forecast.ramalkan_harga` dihitung dari ISI `riwayat`, jadi riwayat yang
    berubah otomatis punya kunci baru (lihat docstring `forecast.ramalkan_harga`).

    Mengembalikan jumlah komoditas yang benar-benar tersimpan.
    """
    tanggal_ts = pd.Timestamp(tanggal)
    tersimpan = 0

    for slug, harga in harga_per_slug.items():
        get_price_history(slug, hari=1)  # pastikan riwayat dasar sudah dimuat
        df = _cache_riwayat.get(slug)
        if df is None:
            continue

        if (df["tanggal"] == tanggal_ts).any():
            df.loc[df["tanggal"] == tanggal_ts, "harga"] = harga
        else:
            df = pd.concat(
                [df, pd.DataFrame({"tanggal": [tanggal_ts], "harga": [harga]})],
                ignore_index=True,
            )
        _cache_riwayat[slug] = df.sort_values("tanggal").reset_index(drop=True)
        tersimpan += 1

    if tersimpan:
        _simpan_riwayat_ke_pkl()
    return tersimpan


def get_kartu_harga(slug: str) -> KartuHarga | None:
    """Harga terbaru + waktu update satu komoditas (kartu dashboard & hero detail)."""
    komoditas = get_komoditas_by_slug(slug)
    if komoditas is None:
        return None

    riwayat = get_price_history(slug, hari=2)
    if riwayat.empty:
        return None
    harga_terbaru = float(riwayat["harga"].iloc[-1])
    harga_kemarin = float(riwayat["harga"].iloc[0]) if len(riwayat) > 1 else harga_terbaru
    # Waktu update = tanggal titik harga TERAKHIR yang sungguhan (bukan
    # jam-lalu tiruan) — `format_waktu_pembaruan` otomatis jatuh ke format
    # tanggal absolut kalau titik itu lebih dari 24 jam lalu, yang biasanya
    # benar di sini: riwayat riset berhenti di data train+test model.
    diperbarui_pada = riwayat["tanggal"].iloc[-1].to_pydatetime()
    return KartuHarga(komoditas, harga_terbaru, harga_kemarin, diperbarui_pada)


def get_dashboard_cards() -> list[KartuHarga]:
    """Harga terbaru + waktu update tiap komoditas, untuk kartu di Dashboard Pangan."""
    kartu = (get_kartu_harga(k.slug) for k in get_komoditas_list())
    return [k for k in kartu if k is not None]
