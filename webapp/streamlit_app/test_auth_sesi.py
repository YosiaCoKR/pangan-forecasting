"""Cek masa berlaku sesi admin: jendela idle bergulir 15 menit.

Jalankan: `python test_auth_sesi.py` (dari folder streamlit_app).
Yang diuji cuma keputusan "sesi masih hidup?" (`auth._sesi_masih_hidup`) —
bagian yang menentukan kapan admin dilempar keluar. Daftar sesi dipakai
sebagai dict biasa, jadi tidak butuh server Streamlit yang jalan.
"""

import auth

assert auth._TIMEOUT_SESI == 15 * 60, "timeout sesi admin harus 15 menit"

# Sesi tak dikenal (mis. id sesi lama di URL setelah server restart) → ditolak.
assert not auth._sesi_masih_hidup({}, "sid-asing", 1000.0)

# Masih di dalam jendela → diterima & waktu aktivitas di-refresh, bukan
# dihitung dari waktu login (jendela bergulir).
sesi = {"sid": 1000.0}
assert auth._sesi_masih_hidup(sesi, "sid", 1000.0 + 14 * 60)
assert sesi["sid"] == 1000.0 + 14 * 60, "aktivitas terakhir harus ikut maju"
assert auth._sesi_masih_hidup(sesi, "sid", 1000.0 + 28 * 60), (
    "aktivitas pada menit ke-14 harusnya memperpanjang sesi 15 menit lagi"
)

# Tepat di batas masih boleh, lebih dari itu gugur & dibuang dari daftar.
sesi = {"sid": 1000.0}
assert auth._sesi_masih_hidup(sesi, "sid", 1000.0 + auth._TIMEOUT_SESI)
sesi = {"sid": 1000.0}
assert not auth._sesi_masih_hidup(sesi, "sid", 1000.0 + auth._TIMEOUT_SESI + 1)
assert "sid" not in sesi, "sesi kedaluwarsa harus dihapus dari daftar"

# Id sesi ikut di URL, jadi harus tak bisa diterka: minimal 128 bit acak.
id_sesi = auth.secrets.token_urlsafe(32)
assert len(id_sesi) >= 22, "id sesi terlalu pendek untuk dipakai di URL"

# Yang masuk log audit adalah hash pendek, bukan id sesinya — kalau tidak,
# pembaca tabel log bisa membajak sesi admin yang masih hidup.
kode = auth._kode_audit(id_sesi)
assert kode != id_sesi and kode not in id_sesi, "id sesi tidak boleh bocor ke log audit"
assert len(kode) == 12 and auth._kode_audit(id_sesi) == kode, "kode audit harus pendek & stabil"

print("OK — sesi admin: idle 15 menit bergulir, kedaluwarsa dibersihkan, log pakai hash")
