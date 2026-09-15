"""Data harga historis — dasar dari dataset riset ASLI, edit admin persisten ke `.pkl`.

Riwayat dasar tiap komoditas dimuat dari `DATASET-BERAS.csv` (dataset riset
sungguhan yang juga dipakai melatih model MSTL/GA-LightGBM — lihat
`_muat_dataset_riset`), BUKAN lagi random walk tiruan. Dataset ini mencakup
~60 hari data SETELAH akhir data train model, cukup untuk peramalan langsung
bisa dicoba tanpa menunggu admin mengisi harga dulu (lihat docstring
`_bangun_riwayat`). Begitu admin menyimpan harga lewat halaman Input Harga
Terbaru, perubahan itu **sungguhan** ditulis ke `harga_historis.pkl` di
sebelah modul ini dan dimuat balik saat aplikasi start — bukan lagi sekadar
cache memori yang hilang setelah proses berhenti. Kontrak fungsi
(`get_price_history`, `get_dashboard_cards`) dipertahankan supaya halaman
tidak perlu diubah lagi.

`tambah_harga_baru` juga langsung memicu rerun pra-proses MSTL (lihat
`_rerun_pra_proses`) atas riwayat terbaru — bukan pelatihan ulang model,
cuma memastikan data yang baru disimpan admin memang bisa diolah forecaster
sebelum pengunjung publik memintanya.
"""

from __future__ import annotations

import logging
import pickle
import zlib
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd

import forecast
from data.mock_commodities import Komoditas, get_komoditas_by_slug, get_komoditas_list

_log = logging.getLogger(__name__)

RENTANG_HARI_MAKS = 90
_PKL_PATH = Path(__file__).parent / "harga_historis.pkl"

# Harga dasar dipakai HANYA sebagai fallback random walk kalau suatu saat
# ada komoditas baru yang belum punya kolom di `DATASET-BERAS.csv` — untuk
# 9 komoditas tetap saat ini, jalur ini tidak pernah terpakai (semuanya ada
# di dataset riset).
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
    """Muat & bersihkan `DATASET-BERAS.csv` sekali per proses (cached).

    Pra-proses PERSIS sama seperti `code.ipynb` (index tanggal harian lewat
    `asfreq("D")` + interpolasi berbasis waktu untuk mengisi celah) supaya
    konsisten dengan data yang dipakai melatih model MSTL/GA-LightGBM —
    `forecast.py` memuat model hasil riset, modul ini yang memuat dataset
    mentahnya (satu-satunya pembaca CSV di aplikasi).
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
    # `forecast.SKALA_HARGA`) — dikonversi ke Rupiah aktual di sini supaya
    # kontrak `get_price_history` (selalu Rupiah aktual) tetap konsisten.
    harga = dataset[nama_komoditas].dropna() * forecast.SKALA_HARGA
    return pd.DataFrame({"tanggal": harga.index, "harga": harga.to_numpy()})


def _muat_riwayat_dari_pkl() -> None:
    """Muat harga hasil input admin sebelumnya (kalau ada) saat modul di-import."""
    if _PKL_PATH.exists():
        with open(_PKL_PATH, "rb") as berkas:
            _cache_riwayat.update(pickle.load(berkas))


def _simpan_riwayat_ke_pkl() -> None:
    """Tulis seluruh cache riwayat ke `.pkl` — dipanggil tiap admin menyimpan harga."""
    with open(_PKL_PATH, "wb") as berkas:
        pickle.dump(_cache_riwayat, berkas)


_muat_riwayat_dari_pkl()


@dataclass(frozen=True)
class KartuHarga:
    komoditas: Komoditas
    harga_terbaru: float
    harga_kemarin: float
    diperbarui_pada: datetime


def _seed_dari_slug(slug: str) -> int:
    return zlib.crc32(slug.encode("utf-8"))


def _bangun_riwayat(slug: str, harga_dasar: float) -> pd.DataFrame:
    """Riwayat harga PENUH untuk satu komoditas — dari dataset riset ASLI
    kalau komoditasnya ada di `DATASET-BERAS.csv` (selalu benar untuk 9
    komoditas tetap saat ini), atau random walk tiruan sebagai fallback.

    Dataset riset mencakup data sampai ~60 hari SETELAH akhir data train
    model (`mstl.trend.index[-1]`, lihat `forecast.py`) — cukup untuk
    langsung meramal begitu aplikasi jalan (forecaster butuh minimal
    `window_size` 30 hari setelah akhir train), TANPA perlu admin mengisi
    harga dulu. Titik terakhir dataset bukan "hari ini" (data riset berhenti
    di tanggal tertentu) — itu sebabnya `get_kartu_harga` menampilkan waktu
    update dari tanggal titik terakhir yang sungguhan, bukan jam-lalu tiruan.
    """
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
    """Riwayat harga harian (kolom: tanggal, harga) untuk `hari` terakhir."""
    if slug not in _cache_riwayat:
        harga_dasar = _HARGA_DASAR.get(slug, 10_000)
        _cache_riwayat[slug] = _bangun_riwayat(slug, harga_dasar)
    return _cache_riwayat[slug].tail(hari).reset_index(drop=True)


def tambah_harga_baru(slug: str, tanggal, harga: float) -> None:
    """Tambah/perbarui satu titik harga untuk admin — di-append ke `.pkl` sungguhan.

    Efeknya langsung terlihat: dashboard, detail, dan data historis membaca
    dari cache riwayat yang sama, dan hasilnya sekarang ditulis ke
    `harga_historis.pkl` supaya bertahan setelah aplikasi di-restart.
    """
    if slug not in _cache_riwayat:
        harga_dasar = _HARGA_DASAR.get(slug, 10_000)
        _cache_riwayat[slug] = _bangun_riwayat(slug, harga_dasar)

    df = _cache_riwayat[slug]
    tanggal_ts = pd.Timestamp(tanggal)

    if (df["tanggal"] == tanggal_ts).any():
        df.loc[df["tanggal"] == tanggal_ts, "harga"] = harga
    else:
        baris_baru = pd.DataFrame({"tanggal": [tanggal_ts], "harga": [harga]})
        df = pd.concat([df, baris_baru], ignore_index=True)

    _cache_riwayat[slug] = df.sort_values("tanggal").reset_index(drop=True)
    _simpan_riwayat_ke_pkl()
    _rerun_pra_proses(slug)


def _rerun_pra_proses(slug: str) -> None:
    """Jalankan ulang pra-proses MSTL & isi ulang cache prediksi (BUKAN
    pelatihan ulang) begitu admin menyimpan harga baru.

    Dua manfaat sekaligus:
    1. Masalah data/model untuk komoditas ini ketahuan saat itu juga (di
       halaman admin), bukan baru muncul belakangan saat pengunjung publik
       meminta prediksi.
    2. Cache `forecast.ramalkan_harga` (kunci dari isi `riwayat`) langsung
       terisi ulang untuk ke-3 horizon — kunjungan publik BERIKUTNYA ke
       Dashboard/Detail Komoditas/Data Historis untuk komoditas ini langsung
       kena cache-hit, bukan menunggu forecaster jalan saat halaman dibuka.
       Entri cache lama (riwayat sebelum diedit) otomatis tidak pernah
       terpakai lagi karena kuncinya sudah beda — tidak perlu invalidasi
       manual, lihat docstring `forecast.ramalkan_harga`.
    """
    komoditas = get_komoditas_by_slug(slug)
    if komoditas is None:
        return

    try:
        trend_model = forecast.muat_trend_model()
        seasonal_model = forecast.muat_seasonal_model()
        if komoditas.nama not in trend_model or komoditas.nama not in seasonal_model:
            return
        riwayat = get_price_history(slug, hari=RENTANG_HARI_MAKS)
        forecast.susun_residual_mstl(riwayat, trend_model[komoditas.nama], seasonal_model[komoditas.nama])

        for horizon in forecast.HORIZON_TERSEDIA:
            forecast.ramalkan_harga(riwayat, komoditas.nama, horizon)
    except forecast.ModelRisetError:
        # Artefak model riset belum/tidak tersedia, atau riwayat belum cukup
        # panjang untuk forecaster — bukan tanggung jawab tambah_harga_baru
        # untuk menggagalkan penyimpanan harga karena itu.
        pass
    except Exception:
        # Kegagalan TAK terduga di pra-proses/cache-warm — harga admin SUDAH
        # tersimpan di atas (baris `_simpan_riwayat_ke_pkl()`) sebelum fungsi
        # ini dipanggil, jadi kegagalan di sini tidak boleh sampai membuat
        # halaman admin nge-crash / terlihat seperti penyimpanan gagal.
        # Dicatat ke log server supaya operator tetap bisa melacaknya.
        _log.exception("Gagal rerun pra-proses/isi cache untuk %s", slug)


def get_kartu_harga(slug: str) -> KartuHarga | None:
    """Harga terbaru + waktu update untuk satu komoditas (dipakai kartu & hero detail).

    `None` juga kalau `riwayat` kosong (bukan cuma komoditas tak dikenal) —
    saat ini tak akan pernah terjadi untuk 9 komoditas tetap (`_bangun_riwayat`
    selalu berhasil memuat dari dataset riset), tapi menjaga kontrak "None
    kalau data belum ada" tetap berlaku untuk jalur fallback random walk
    (komoditas di luar dataset riset).
    """
    komoditas = get_komoditas_by_slug(slug)
    if komoditas is None:
        return None

    riwayat = get_price_history(slug, hari=2)
    if riwayat.empty:
        return None
    harga_terbaru = float(riwayat["harga"].iloc[-1])
    harga_kemarin = float(riwayat["harga"].iloc[0]) if len(riwayat) > 1 else harga_terbaru
    # Waktu update = tanggal titik harga TERAKHIR yang sungguhan (bukan lagi
    # jam-lalu tiruan) — `format_waktu_pembaruan` otomatis jatuh ke format
    # tanggal absolut kalau titik itu lebih dari 24 jam lalu, yang biasanya
    # benar di sini: riwayat riset berhenti di data train+test model, bisa
    # beberapa minggu sebelum hari ini sampai admin mengisi harga terbaru.
    diperbarui_pada = riwayat["tanggal"].iloc[-1].to_pydatetime()
    return KartuHarga(komoditas, harga_terbaru, harga_kemarin, diperbarui_pada)


def get_dashboard_cards() -> list[KartuHarga]:
    """Harga terbaru + waktu update tiap komoditas, untuk kartu di Dashboard Pangan."""
    kartu = (get_kartu_harga(k.slug) for k in get_komoditas_list())
    return [k for k in kartu if k is not None]
