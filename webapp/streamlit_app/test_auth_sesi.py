"""Cek masa berlaku & kerahasiaan sesi admin.

Jalankan: `python test_auth_sesi.py` (dari folder streamlit_app).
Yang diuji: keputusan "sesi masih hidup?" (`auth._sesi_masih_hidup`), batas
umur absolut, tidak adanya kredensial default, dan janji bahwa id sesi tidak
pernah ikut ke URL maupun ke log audit. Daftar sesi dipakai sebagai dict
biasa, jadi tidak butuh server Streamlit yang jalan.
"""

import inspect
import os

import auth

# --- batas idle bergulir -----------------------------------------------------
assert auth._TIMEOUT_IDLE == 15 * 60, "timeout idle sesi admin harus 15 menit"

# Sesi tak dikenal (mis. sisa sesi setelah server restart) → ditolak.
assert not auth._sesi_masih_hidup({}, "sid-asing", 1000.0)

# Masih di dalam jendela → diterima & waktu aktivitas di-refresh, bukan
# dihitung dari waktu login (jendela bergulir).
sesi = {"sid": (1000.0, 1000.0)}
assert auth._sesi_masih_hidup(sesi, "sid", 1000.0 + 14 * 60)
assert sesi["sid"][1] == 1000.0 + 14 * 60, "aktivitas terakhir harus ikut maju"
assert sesi["sid"][0] == 1000.0, "waktu DIBUAT tidak boleh ikut maju"
assert auth._sesi_masih_hidup(sesi, "sid", 1000.0 + 28 * 60), (
    "aktivitas pada menit ke-14 harusnya memperpanjang sesi 15 menit lagi"
)

# Tepat di batas masih boleh, lebih dari itu gugur & dibuang dari daftar.
sesi = {"sid": (1000.0, 1000.0)}
assert auth._sesi_masih_hidup(sesi, "sid", 1000.0 + auth._TIMEOUT_IDLE)
sesi = {"sid": (1000.0, 1000.0)}
assert not auth._sesi_masih_hidup(sesi, "sid", 1000.0 + auth._TIMEOUT_IDLE + 1)
assert "sid" not in sesi, "sesi kedaluwarsa harus dihapus dari daftar"

# --- batas umur absolut ------------------------------------------------------
# Sesi yang terus dipakai tetap harus mati pada 8 jam: ini yang membatasi
# berapa lama sesi yang bocor/terlupakan bisa dipelihara hidup.
assert auth._TIMEOUT_ABSOLUT == 8 * 60 * 60, "umur maksimum sesi harus 8 jam"
sesi = {"sid": (0.0, auth._TIMEOUT_ABSOLUT)}  # rajin aktif sampai detik terakhir
assert not auth._sesi_masih_hidup(sesi, "sid", auth._TIMEOUT_ABSOLUT + 1), (
    "sesi harus gugur di umur 8 jam walau aktivitasnya baru saja"
)
assert "sid" not in sesi, "sesi lewat umur absolut harus dihapus dari daftar"

# --- id sesi tidak boleh bocor ----------------------------------------------
# Id sesi setara token akses. Dulu dititipkan di `st.query_params` (?sid=...)
# sehingga ikut riwayat browser & screenshot; sekarang murni sisi server.
sumber_auth = inspect.getsource(auth)
kode_auth = "\n".join(
    baris for baris in sumber_auth.splitlines() if not baris.lstrip().startswith("#")
)
assert "st.query_params" not in kode_auth.replace(auth.__doc__ or "", ""), (
    "id sesi tidak boleh dititipkan ke URL — pakai cookie HttpOnly kalau "
    "butuh tahan refresh"
)

# Sesi tahan refresh lewat sessionStorage tab; id dari browser hanya boleh
# diterima kalau masih terdaftar di server.
assert "sessionStorage.setItem" in kode_auth, "id sesi harus dititipkan ke sessionStorage"
assert "hasil.sid in _sesi_aktif()" in kode_auth, "id dari browser harus dicek ke daftar sesi server"

id_sesi = auth.secrets.token_urlsafe(32)
assert len(id_sesi) >= 22, "id sesi terlalu pendek"

# Yang masuk log audit adalah hash pendek, bukan id sesinya — kalau tidak,
# pembaca tabel log bisa membajak sesi admin yang masih hidup.
kode = auth._kode_audit(id_sesi)
assert kode != id_sesi and kode not in id_sesi, "id sesi tidak boleh bocor ke log audit"
assert len(kode) == 12 and auth._kode_audit(id_sesi) == kode, "kode audit harus pendek & stabil"

# --- tidak ada kredensial default -------------------------------------------
# Deploy yang lupa mengisi secrets harus GAGAL TERTUTUP, bukan terbuka dengan
# admin/admin123 yang bisa ditebak siapa pun.
asli = {k: os.environ.get(k) for k in ("ADMIN_USERNAME", "ADMIN_PASSWORD")}
try:
    for k in asli:
        os.environ.pop(k, None)
    assert auth.username_admin() == "", "tidak boleh ada username default"
    assert auth.kata_sandi_admin() == "", "tidak boleh ada kata sandi default"
    assert not auth.admin_dikonfigurasi(), "tanpa env var, admin harus dianggap belum siap"
    assert not auth.login("admin", "admin123"), "kredensial lama admin/admin123 harus ditolak"
    assert not auth.login("", ""), "kredensial kosong harus ditolak"
finally:
    for k, v in asli.items():
        if v is not None:
            os.environ[k] = v

print("OK — sesi admin: idle 15 menit bergulir, umur maks 8 jam, id sesi tidak "
      "masuk URL/log, tanpa kredensial default")
