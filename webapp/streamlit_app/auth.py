"""Gerbang akses admin — username + kata sandi dari konfigurasi aplikasi.

Tidak ada tabel `users` maupun akun terdaftar (sesuai PRD): username & kata
sandi disetel sekali lewat environment variable, bukan pendaftaran akun.

Sesi admin disimpan SEPENUHNYA di sisi server: `st.session_state` memegang id
sesi untuk tab yang sedang terbuka, dan `_sesi_aktif()` (dibagi antar koneksi
di proses yang sama) memegang waktu dibuat + waktu aktivitas terakhir. Sesi
gugur setelah 15 menit tanpa aktivitas (`_TIMEOUT_IDLE`), paling lama 8 jam
sejak login walaupun terus dipakai (`_TIMEOUT_ABSOLUT`), dan ikut hilang kalau
server di-restart.

Id sesi SENGAJA TIDAK pernah masuk URL. Versi sebelumnya menitipkannya di
`st.query_params` (`?sid=...`) supaya sesi tahan refresh browser, tapi itu
membuat URL setara kata sandi: ikut tersimpan di riwayat browser, ikut
ter-screenshot, dan ikut terkirim kalau URL-nya dibagikan. Untuk panel yang
bisa mengubah harga & model, harga kenyamanan itu terlalu mahal. Konsekuensi
yang diterima: refresh halaman (F5) berarti login ulang. Pindah halaman lewat
menu TIDAK memutus sesi, karena navigasi `st.Page` tidak memuat ulang browser.

Kalau nanti sesi perlu tahan refresh, jalur yang benar adalah cookie HttpOnly
+ Secure + SameSite=Strict (butuh komponen cookie manager atau reverse proxy
auth) — BUKAN mengembalikan id sesi ke URL.

Kredensial dibaca dari environment variable `ADMIN_USERNAME`/`ADMIN_PASSWORD`.
Di Streamlit Community Cloud, isi keduanya di Settings > Secrets sebagai kunci
level atas (Streamlit mempromosikannya jadi environment variable sebelum skrip
jalan). Untuk lokal, salin `.env.example` jadi `.env` (sudah di-gitignore).
TIDAK ADA kredensial default: kalau belum disetel, login selalu gagal
(`admin_dikonfigurasi()` False) supaya panel admin tidak pernah terbuka dengan
kata sandi yang bisa ditebak. Halaman publik tetap jalan normal.

Setiap login/logout dicatat ke `db.admin_login_logs` (audit ringan, tanpa
identitas selain peran "admin") — yang masuk log cuma hash pendek id sesi
(`_kode_audit`), bukan id sesinya.
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

_SESI_ID_KEY = "admin_sesi_id"
_SESI_BERAKHIR_KEY = "admin_sesi_berakhir"  # penanda pesan "sesi habis" di halaman login
_TIMEOUT_IDLE = 15 * 60  # detik tanpa aktivitas sebelum sesi gugur
_TIMEOUT_ABSOLUT = 8 * 60 * 60  # umur maksimum sesi sejak login, walau terus aktif

# Kompatibilitas nama lama (dipakai pesan di halaman login & test).
_TIMEOUT_SESI = _TIMEOUT_IDLE


def username_admin() -> str:
    """Username admin, atau string kosong kalau belum dikonfigurasi."""
    return os.environ.get("ADMIN_USERNAME", "")


def kata_sandi_admin() -> str:
    """Kata sandi admin, atau string kosong kalau belum dikonfigurasi."""
    return os.environ.get("ADMIN_PASSWORD", "")


def admin_dikonfigurasi() -> bool:
    """Kredensial admin sudah disetel? Kalau False, `login()` selalu gagal.

    Dipakai halaman login untuk menjelaskan kenapa form-nya tidak bisa
    dipakai, alih-alih menampilkan "kata sandi salah" yang menyesatkan.
    """
    return bool(username_admin()) and bool(kata_sandi_admin())


@st.cache_resource
def _sesi_aktif() -> dict[str, tuple[float, float]]:
    """Sesi admin yang hidup: `{id_sesi: (epoch dibuat, epoch aktivitas terakhir)}`.

    `cache_resource` dipakai supaya satu dict ini dibagi semua koneksi browser
    di proses server yang sama — itu yang membuat status login tetap berlaku
    antar rerun dan antar halaman tanpa menitipkan apa pun ke URL.
    """
    return {}


def _sesi_masih_hidup(
    sesi: dict[str, tuple[float, float]], id_sesi: str, sekarang: float
) -> bool:
    """Sesi masih valid? Kalau ya, waktu aktivitas di-refresh.

    Dua batas yang dicek:
    - idle bergulir: 15 menit dihitung dari interaksi TERAKHIR, bukan login;
    - umur absolut: 8 jam sejak login, walau admin terus aktif — supaya sesi
      yang bocor/terlupakan tidak bisa dipelihara hidup selamanya.

    Sesi yang gugur dibuang dari daftar.
    """
    catatan = sesi.get(id_sesi)
    if catatan is None:
        return False
    dibuat, terakhir = catatan
    if sekarang - terakhir > _TIMEOUT_IDLE or sekarang - dibuat > _TIMEOUT_ABSOLUT:
        sesi.pop(id_sesi, None)
        return False
    sesi[id_sesi] = (dibuat, sekarang)
    return True


def admin_sudah_masuk() -> bool:
    """Gerbang tunggal status admin — sekaligus memperpanjang masa aktif sesi."""
    id_sesi = st.session_state.get(_SESI_ID_KEY)
    if not id_sesi:
        return False
    if not _sesi_masih_hidup(_sesi_aktif(), id_sesi, time.time()):
        st.session_state.pop(_SESI_ID_KEY, None)
        st.session_state[_SESI_BERAKHIR_KEY] = True
        return False
    return True


def masuk_sebagai_admin() -> None:
    # Token sesi dari CSPRNG (±256 bit). Tidak ikut di URL, tapi tetap dibuat
    # tak-terka: pencarian di `_sesi_aktif()` tidak punya rate limit apa pun.
    id_sesi = secrets.token_urlsafe(32)
    sekarang = time.time()
    _sesi_aktif()[id_sesi] = (sekarang, sekarang)
    st.session_state[_SESI_ID_KEY] = id_sesi
    st.session_state.pop(_SESI_BERAKHIR_KEY, None)


def sesi_berakhir_karena_idle() -> bool:
    """Sekali-pakai: True kalau sesi sebelumnya baru saja gugur karena idle —
    dipakai halaman login untuk menjelaskan kenapa admin tiba-tiba keluar."""
    return bool(st.session_state.pop(_SESI_BERAKHIR_KEY, False))


def _kode_audit(id_sesi: str) -> str:
    """Kode korelasi untuk log audit — hash pendek dari id sesi, BUKAN id
    sesinya sendiri. Id sesi setara token akses, jadi tidak boleh ikut
    tersimpan di `admin_login_logs`: siapa pun yang bisa membaca tabel log
    jangan sampai bisa membajak sesi admin yang masih hidup."""
    return hashlib.sha256(id_sesi.encode()).hexdigest()[:12]


def sesi_admin_saat_ini() -> str:
    """Penanda sesi admin (bukan identitas pengguna, bukan pula token sesinya)
    — dipakai di log aktivitas, baik login/logout di sini maupun perubahan data
    (harga, model aktif, ambang EWS) yang dicatat dari halaman admin
    masing-masing, supaya semua aksi dalam satu sesi login bisa dikorelasikan
    saat audit."""
    id_sesi = st.session_state.get(_SESI_ID_KEY)
    return _kode_audit(id_sesi) if id_sesi else "tanpa-sesi"


def login(username: str, kata_sandi: str) -> bool:
    """"Endpoint" login admin — verifikasi username + kata sandi & aktifkan sesi.

    Aplikasi ini adalah Streamlit monolith tanpa server API terpisah (sesuai
    arsitektur PRD): "endpoint" di sini adalah fungsi Python yang dipanggil
    langsung oleh halaman UI, bukan rute HTTP.

    Gagal tertutup (`False`) kalau kredensial belum dikonfigurasi — tidak ada
    nilai default yang bisa ditebak. Perbandingan memakai
    `secrets.compare_digest` supaya lama eksekusinya tidak bergantung pada
    berapa karakter awal yang sudah benar.
    """
    if not admin_dikonfigurasi():
        return False
    # Kedua compare_digest selalu dijalankan (bukan `and` yang korslet) supaya
    # username salah dan kata sandi salah tidak bisa dibedakan dari waktu.
    nama_cocok = secrets.compare_digest(username, username_admin())
    sandi_cocok = secrets.compare_digest(kata_sandi, kata_sandi_admin())
    if nama_cocok and sandi_cocok:
        masuk_sebagai_admin()
        catat_aktivitas_admin("login", sesi_admin_saat_ini())
        return True
    return False


def keluar_dari_admin() -> None:
    id_sesi = st.session_state.get(_SESI_ID_KEY)
    if id_sesi and _sesi_aktif().pop(id_sesi, None) is not None:
        catat_aktivitas_admin("logout", _kode_audit(id_sesi))
    st.session_state.pop(_SESI_ID_KEY, None)
    st.session_state.pop(_SESI_BERAKHIR_KEY, None)


def require_admin() -> None:
    """Panggil di awal skrip halaman admin selain login (Pengaturan Model,
    dst). Menghentikan render halaman kalau sesi admin belum aktif, supaya
    rute admin tidak bisa dilihat isinya lewat akses URL langsung tanpa login.
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
