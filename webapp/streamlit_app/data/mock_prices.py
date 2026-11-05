"""Data harga historis — dasar dari dataset riset ASLI, edit admin persisten ke `.pkl`.

Riwayat tiap komoditas dimuat dari `DATASET-BERAS-NEW.csv` (dataset yang juga
dipakai melatih model — lihat `_muat_dataset_riset`). Harga yang disimpan
admin lewat halaman Input Harga Terbaru ditulis ke `harga_historis.pkl` di
sebelah modul ini dan dimuat balik saat aplikasi start.

Di HOSTING itu belum cukup: filesystem Streamlit Community Cloud ephemeral,
`.pkl` lokal terhapus tiap container restart/redeploy. Karena itu
`sinkronkan_ke_github()` meng-commit berkas yang sama ke repo, supaya harga
ikut ter-clone saat container baru dibuat. Tidak ada jalur "fetch": clone
repo-nya sendiri yang membawa berkas itu masuk.

Kolom dataset adalah satu-satunya sumber daftar komoditas (lihat
`data.mock_commodities`) — ganti dataset + jalankan ulang notebook, dan
riwayat, kartu dashboard, serta form input harga ikut berubah sendiri.
"""

from __future__ import annotations

import base64
import pickle
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

import forecast
import pandas as pd
import requests
import streamlit as st

from data.mock_commodities import Komoditas, get_komoditas_by_slug, get_komoditas_list

RENTANG_HARI_MAKS = 90
_PKL_PATH = Path(__file__).parent / "harga_historis.pkl"

# Posisi `.pkl` RELATIF terhadap akar repo — itu yang dipakai GitHub Contents
# API sebagai path berkas. Diturunkan, bukan dihardcode, supaya tetap benar
# kalau folder app dipindah.
_PKL_REPO_PATH = _PKL_PATH.resolve().relative_to(Path(__file__).resolve().parents[3]).as_posix()
_TIMEOUT_API = 10

_cache_riwayat: dict[str, pd.DataFrame] = {}
_cache_dataset_riset: pd.DataFrame | None = None


def _muat_dataset_riset() -> pd.DataFrame:
    """Muat & bersihkan `DATASET-BERAS-NEW.csv` sekali per proses (cached).

    Pra-proses persis sama seperti notebook riset (`asfreq("D")` + interpolasi
    berbasis waktu) supaya konsisten dengan data yang dipakai melatih model.
    """
    global _cache_dataset_riset
    if _cache_dataset_riset is None:
        df = pd.read_csv(forecast.DATASET_PATH)
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


def _konfigurasi_github() -> dict[str, str] | None:
    """Kredensial sinkronisasi dari `st.secrets`, atau None kalau belum diisi.

    Bentuk yang dibaca (`.streamlit/secrets.toml` lokal, atau Secrets di
    Streamlit Cloud) — token TIDAK pernah dicatat/ditampilkan di mana pun:

        [github]
        token = "github_pat_..."              # scope: Contents read+write
        repo = "NamaAkun/pangan-forecasting"
        branch = "main"                       # opsional
    """
    try:
        bagian = st.secrets.get("github")
    except Exception:
        # Tidak ada secrets.toml sama sekali (mis. jalan lokal / test).
        return None
    if not bagian or not bagian.get("token") or not bagian.get("repo"):
        return None
    return {
        "token": str(bagian["token"]),
        "repo": str(bagian["repo"]),
        "branch": str(bagian.get("branch", "main")),
    }


def sinkronisasi_aktif() -> bool:
    """Secrets `github` sudah diisi?

    Dipakai halaman admin untuk membedakan "benar-benar tersalin ke repo"
    dari "fitur belum dinyalakan" — DUA-DUANYA membuat
    `sinkronkan_ke_github()` mengembalikan None, dan tanpa pembeda ini
    admin diberi tahu harganya aman permanen padahal tidak ada apa pun
    yang tersalin.
    """
    return _konfigurasi_github() is not None


def sinkronkan_ke_github() -> str | None:
    """Commit `harga_historis.pkl` ke repo lewat GitHub Contents API.

    ALASAN: filesystem Streamlit Community Cloud ephemeral — `.pkl` lokal
    hilang tiap container restart atau redeploy, jadi input harga admin
    lenyap tanpa pesan. Dengan meng-commit berkas itu ke repo, harga ikut
    TER-CLONE saat container baru dibuat; tidak perlu kode "fetch" sama
    sekali, karena clone-nya sendiri sudah membawa berkasnya.

    Mengembalikan `None` kalau sukses ATAU kalau fitur belum dikonfigurasi,
    dan string alasan kalau GAGAL. Pemanggil WAJIB menampilkan alasan itu ke
    admin: tulis lokal sudah sukses, jadi tanpa pesan admin akan mengira
    harganya aman padahal salinan tahan-restart-nya tidak jadi.

    Efek samping yang harus diberitahukan ke admin: commit ini memicu
    redeploy Streamlit Cloud, jadi app akan restart beberapa saat setelahnya.
    """
    konfigurasi = _konfigurasi_github()
    if konfigurasi is None:
        return None

    url = f"https://api.github.com/repos/{konfigurasi['repo']}/contents/{_PKL_REPO_PATH}"
    kepala = {
        "Authorization": f"Bearer {konfigurasi['token']}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }

    try:
        isi = _PKL_PATH.read_bytes()
    except OSError as exc:
        return f"tidak bisa membaca {_PKL_PATH.name}: {exc}"

    try:
        # GitHub butuh `sha` blob LAMA untuk menimpa berkas yang sudah ada;
        # 404 berarti berkasnya belum pernah ada, jadi `sha` dikosongkan.
        cek = requests.get(
            url, headers=kepala, params={"ref": konfigurasi["branch"]}, timeout=_TIMEOUT_API
        )
        if cek.status_code == 200:
            sha_lama = cek.json().get("sha")
        elif cek.status_code == 404:
            sha_lama = None
        else:
            return f"gagal membaca berkas di repo (HTTP {cek.status_code})"

        muatan = {
            "message": f"data(harga): sinkronisasi input admin {datetime.now():%Y-%m-%d %H:%M}",
            "content": base64.b64encode(isi).decode("ascii"),
            "branch": konfigurasi["branch"],
        }
        if sha_lama:
            muatan["sha"] = sha_lama

        kirim = requests.put(url, headers=kepala, json=muatan, timeout=_TIMEOUT_API)
        if kirim.status_code not in (200, 201):
            # Pesan GitHub aman ditampilkan (tidak memuat token), tapi
            # dipotong supaya body panjang tidak membanjiri UI admin.
            return f"commit ditolak (HTTP {kirim.status_code}): {kirim.text[:200]}"
    except requests.RequestException as exc:
        return f"tidak bisa menghubungi GitHub: {exc}"

    return None


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
