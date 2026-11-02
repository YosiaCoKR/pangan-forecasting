"""Gerbang akses admin — username + kata sandi dari konfigurasi aplikasi.

Tidak ada tabel `users` maupun akun terdaftar (sesuai PRD): username & kata
sandi disetel sekali lewat environment variable, bukan pendaftaran akun.
Status masuk admin disimpan sebagai sesi sisi server: id sesi acak dipegang
di `st.query_params` (ikut URL, jadi tahan refresh browser — `st.session_state`
sendiri hilang begitu halaman di-reload), sedangkan waktu aktivitas terakhir
dipegang proses server. Sesi gugur sendiri setelah 15 menit tanpa aktivitas
(`_TIMEOUT_SESI`) dan ikut hilang kalau server di-restart. Setiap
login/logout dicatat ke `db.admin_login_logs` (audit ringan, tanpa identitas
selain peran "admin") — yang masuk log cuma hash pendek id sesi
(`_kode_audit`), bukan id sesinya.

Konsekuensi yang perlu diketahui: karena ikut di URL, id sesi itu setara
token akses — URL halaman admin jangan dibagikan/di-screenshot selama sesi
masih hidup. Kalau nanti butuh yang lebih rapat, pindahkan id sesi ke cookie
HttpOnly (butuh komponen cookie manager atau reverse proxy auth) tanpa
mengubah bagian lain modul ini.

Kredensial dibaca dari environment variable `ADMIN_USERNAME`/`ADMIN_PASSWORD`.
Untuk pengembangan lokal, salin `.env.example` jadi `.env` (sudah
di-gitignore) dan isi nilainya — `load_dotenv()` di bawah memuatnya otomatis
tanpa perlu export manual di shell. Kalau `.env`/env var tidak ada, dipakai
nilai default dev supaya halaman tetap bisa dicoba.
"""

from __future__ import annotations

import hashlib
import os
import secrets
import time
from pathlib import Path

import streamlit as st
from dotenv import load_dotenv

from db import catat_aktivitas_admin

load_dotenv(Path(__file__).parent / ".env")

_ADMIN_USERNAME_DEFAULT = "admin"  # dev/demo — WAJIB diganti via ADMIN_USERNAME di produksi
_ADMIN_PASSWORD_DEFAULT = "admin123"  # dev/demo — WAJIB diganti via ADMIN_PASSWORD di produksi
_SESI_ID_KEY = "admin_sesi_id"
_QP_SESI = "sid"  # nama query param pembawa id sesi di URL
_SESI_BERAKHIR_KEY = "admin_sesi_berakhir"  # penanda untuk pesan "sesi habis" di halaman login
_TIMEOUT_SESI = 15 * 60  # detik tanpa aktivitas sebelum sesi admin gugur


def username_admin() -> str:
    return os.environ.get("ADMIN_USERNAME", _ADMIN_USERNAME_DEFAULT)


def kata_sandi_admin() -> str:
    return os.environ.get("ADMIN_PASSWORD", _ADMIN_PASSWORD_DEFAULT)


@st.cache_resource
def _sesi_aktif() -> dict[str, float]:
    """Daftar sesi admin yang hidup: `{id_sesi: epoch aktivitas terakhir}`.

    `cache_resource` dipakai supaya satu dict ini dibagi semua koneksi
    browser di proses server yang sama — itulah yang membuat sesi selamat
    dari reload halaman, karena `st.session_state` dibuang Streamlit setiap
    kali tab dimuat ulang.
    """
    return {}


def _sesi_masih_hidup(sesi: dict[str, float], id_sesi: str, sekarang: float) -> bool:
    """Sesi masih valid? Kalau ya, waktu aktivitas di-refresh (jendela
    bergulir: 15 menit dihitung dari interaksi terakhir, bukan dari login).
    Kalau sudah lewat timeout, sesi dibuang dari daftar."""
    terakhir = sesi.get(id_sesi)
    if terakhir is None or sekarang - terakhir > _TIMEOUT_SESI:
        sesi.pop(id_sesi, None)
        return False
    sesi[id_sesi] = sekarang
    return True


def admin_sudah_masuk() -> bool:
    """Gerbang tunggal status admin — sekaligus memulihkan sesi setelah
    reload (id sesi dibaca ulang dari query param) dan memperpanjang masa
    aktifnya."""
    id_sesi = st.session_state.get(_SESI_ID_KEY) or st.query_params.get(_QP_SESI)
    if not id_sesi:
        return False
    if not _sesi_masih_hidup(_sesi_aktif(), id_sesi, time.time()):
        _lupakan_sesi_lokal()
        st.session_state[_SESI_BERAKHIR_KEY] = True
        return False
    st.session_state[_SESI_ID_KEY] = id_sesi
    # Ditulis ulang tiap run: Streamlit mengosongkan query param setiap kali
    # pindah halaman, jadi tanpa ini URL halaman admin lain kehilangan id
    # sesi dan reload di sana balik ke form login.
    st.query_params[_QP_SESI] = id_sesi
    return True


def masuk_sebagai_admin() -> None:
    # Token sesi penuh dari CSPRNG (±256 bit): id ini praktis jadi "kata
    # sandi sementara" karena ikut di URL, jadi tidak boleh bisa diterka —
    # pencarian di `_sesi_aktif()` tidak punya rate limit apa pun.
    id_sesi = secrets.token_urlsafe(32)
    _sesi_aktif()[id_sesi] = time.time()
    st.session_state[_SESI_ID_KEY] = id_sesi
    st.session_state.pop(_SESI_BERAKHIR_KEY, None)
    st.query_params[_QP_SESI] = id_sesi


def sesi_berakhir_karena_idle() -> bool:
    """Sekali-pakai: True kalau sesi sebelumnya baru saja gugur karena idle —
    dipakai halaman login untuk menjelaskan kenapa admin tiba-tiba keluar."""
    return bool(st.session_state.pop(_SESI_BERAKHIR_KEY, False))


def _lupakan_sesi_lokal() -> None:
    st.session_state.pop(_SESI_ID_KEY, None)
    if _QP_SESI in st.query_params:
        del st.query_params[_QP_SESI]


def _kode_audit(id_sesi: str) -> str:
    """Kode korelasi untuk log audit — hash pendek dari id sesi, BUKAN id
    sesinya sendiri. Id sesi setara token akses (ikut di URL), jadi tidak
    boleh ikut tersimpan di `admin_login_logs`: siapa pun yang bisa membaca
    tabel log jangan sampai bisa membajak sesi admin yang masih hidup."""
    return hashlib.sha256(id_sesi.encode()).hexdigest()[:12]


def sesi_admin_saat_ini() -> str:
    """Penanda sesi admin (bukan identitas pengguna, bukan pula token
    sesinya) — dipakai di log aktivitas, baik login/logout di sini maupun
    perubahan data (harga, model aktif, ambang EWS) yang dicatat dari halaman
    admin masing-masing, supaya semua aksi dalam satu sesi login bisa
    dikorelasikan saat audit."""
    id_sesi = st.session_state.get(_SESI_ID_KEY) or st.query_params.get(_QP_SESI)
    return _kode_audit(id_sesi) if id_sesi else "tanpa-sesi"


def login(username: str, kata_sandi: str) -> bool:
    """"Endpoint" login admin — verifikasi username + kata sandi & aktifkan sesi.

    Aplikasi ini adalah Streamlit monolith tanpa server API terpisah (sesuai
    arsitektur PRD): "endpoint" di sini adalah fungsi Python yang dipanggil
    langsung oleh halaman UI, bukan rute HTTP. Username & kata sandi berasal
    dari konfigurasi (env var), bukan tabel akun terdaftar.
    """
    if username == username_admin() and kata_sandi == kata_sandi_admin():
        masuk_sebagai_admin()
        catat_aktivitas_admin("login", sesi_admin_saat_ini())
        return True
    return False


def keluar_dari_admin() -> None:
    id_sesi = st.session_state.get(_SESI_ID_KEY) or st.query_params.get(_QP_SESI)
    if id_sesi and _sesi_aktif().pop(id_sesi, None) is not None:
        catat_aktivitas_admin("logout", _kode_audit(id_sesi))
    _lupakan_sesi_lokal()
    st.session_state.pop(_SESI_BERAKHIR_KEY, None)


def require_admin() -> None:
    """Panggil di awal skrip halaman admin selain login (Pengaturan
    Model, dst). Menghentikan render halaman kalau sesi admin belum aktif,
    supaya rute admin tidak bisa dilihat isinya lewat akses URL langsung
    tanpa login.
    """
    if not admin_sudah_masuk():
        st.warning(
            "Anda harus masuk sebagai admin terlebih dahulu. "
            "Buka halaman **Panel Admin** di menu untuk masuk."
        )
        st.stop()


def tombol_logout() -> None:
    """Tombol keluar admin — dipasang di tiap halaman kerja admin (Input
    Harga, Pengaturan Model, Pengaturan Ambang), bukan cuma di hub Panel
    Admin, supaya admin bisa logout dari halaman manapun tanpa harus
    navigasi balik ke hub dulu.
    """
    st.markdown('<div class="ppj-spacer-sm"></div>', unsafe_allow_html=True)
    if st.button("Kunci Panel Admin"):
        keluar_dari_admin()
        st.rerun()
