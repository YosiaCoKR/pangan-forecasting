"""Log aktivitas (SQLite ringan) — satu-satunya penggunaan database di aplikasi.

Sesuai PRD: database tidak pernah menyimpan data harga, komoditas, hasil
prediksi, maupun akun. Hanya audit ringan — login/logout admin (tanpa tabel
`users`, identitas cukup peran "admin") DAN perubahan data yang admin buat
(harga, model aktif, ambang EWS) supaya audit log benar-benar bisa
menelusuri APA yang berubah, bukan cuma KAPAN admin masuk/keluar.
"""

from __future__ import annotations

import sqlite3
from datetime import datetime
from pathlib import Path

_DB_PATH = Path(__file__).parent / "tracking.db"


def _get_connection() -> sqlite3.Connection:
    conn = sqlite3.connect(_DB_PATH)
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS admin_login_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            waktu TEXT NOT NULL,
            aksi TEXT NOT NULL,
            sesi TEXT NOT NULL
        )
        """
    )
    # Migrasi ringan: kolom `detail` (opsional) ditambahkan belakangan untuk
    # mencatat APA yang berubah (mis. "Beras Kualitas Bawah I: Rp 13.500"),
    # bukan cuma nama aksi generik. SQLite tak punya "ADD COLUMN IF NOT
    # EXISTS", jadi dicek dulu lewat PRAGMA — idempoten, aman dipanggil
    # ulang tiap koneksi baru dibuka.
    kolom = {baris[1] for baris in conn.execute("PRAGMA table_info(admin_login_logs)")}
    if "detail" not in kolom:
        conn.execute("ALTER TABLE admin_login_logs ADD COLUMN detail TEXT")
    return conn


def catat_aktivitas_admin(aksi: str, sesi: str, detail: str | None = None) -> None:
    """Catat satu baris log aktivitas admin.

    `aksi`: "login"/"logout" (sesi admin) atau aksi perubahan data —
    "harga_diperbarui", "model_diubah", "ambang_diubah". `sesi`: penanda
    sesi tab admin (lihat `auth.sesi_admin_saat_ini`), supaya semua aksi
    dalam satu sesi login bisa dikorelasikan saat audit. `detail`: ringkasan
    APA yang berubah, opsional (kosong untuk login/logout).
    """
    with _get_connection() as conn:
        conn.execute(
            "INSERT INTO admin_login_logs (waktu, aksi, sesi, detail) VALUES (?, ?, ?, ?)",
            (datetime.now().isoformat(timespec="seconds"), aksi, sesi, detail),
        )


def ambil_log_admin(batas: int = 50) -> list[sqlite3.Row]:
    """Baris log terbaru dulu — dipakai untuk audit di panel admin bila perlu."""
    with _get_connection() as conn:
        conn.row_factory = sqlite3.Row
        return conn.execute(
            "SELECT waktu, aksi, sesi, detail FROM admin_login_logs ORDER BY id DESC LIMIT ?",
            (batas,),
        ).fetchall()
