"""Halaman admin — Audit Log.

Menampilkan riwayat aktivitas admin — login/logout DAN perubahan data
(harga, model aktif, ambang EWS) — dibaca dari `db.ambil_log_admin` (SQLite
ringan, satu-satunya database aplikasi, lihat docstring `db.py`). Sumbernya
sudah nyata (tiap halaman admin mencatat aksinya sendiri lewat
`db.catat_aktivitas_admin`), jadi halaman ini langsung memakai data itu,
bukan angka tiruan.
"""

from __future__ import annotations

from datetime import datetime

import streamlit as st

from auth import require_admin, tombol_logout
from db import ambil_log_admin

require_admin()

st.markdown(
    """
    <div class="ppj-hero">
        <h1>🗂️ Audit Log</h1>
        <p>Riwayat login/logout &amp; perubahan data admin (harga, model aktif, ambang EWS).</p>
    </div>
    """,
    unsafe_allow_html=True,
)

baris = ambil_log_admin()

_LABEL_AKSI = {
    "login": "🟢 Masuk",
    "logout": "🔴 Keluar",
    "harga_diperbarui": "✏️ Harga diperbarui",
    "model_diubah": "⚙️ Model diubah",
    "ambang_diubah": "🚨 Ambang diubah",
}
_AKSI_DARI_LABEL = {
    "Masuk": "login",
    "Keluar": "logout",
    "Harga diperbarui": "harga_diperbarui",
    "Model diubah": "model_diubah",
    "Ambang diubah": "ambang_diubah",
}

if not baris:
    st.markdown(
        '<div class="ppj-placeholder">Belum ada aktivitas tercatat.</div>',
        unsafe_allow_html=True,
    )
else:
    tanggal_semua = [datetime.fromisoformat(b["waktu"]).date() for b in baris]
    tanggal_awal_data, tanggal_akhir_data = min(tanggal_semua), max(tanggal_semua)

    with st.container(border=True):
        kolom_aksi, kolom_tanggal = st.columns([1, 2])
        with kolom_aksi:
            aksi_terpilih = st.selectbox(
                "Aksi",
                options=["Semua", "Masuk", "Keluar", "Harga diperbarui", "Model diubah", "Ambang diubah"],
            )
        with kolom_tanggal:
            rentang_tanggal = st.date_input(
                "Rentang tanggal",
                value=(tanggal_awal_data, tanggal_akhir_data),
                min_value=tanggal_awal_data,
                max_value=tanggal_akhir_data,
            )

        baris_terfilter = baris
        if aksi_terpilih != "Semua":
            baris_terfilter = [b for b in baris_terfilter if b["aksi"] == _AKSI_DARI_LABEL[aksi_terpilih]]

        # `st.date_input` mode rentang mengembalikan tuple 1 elemen selagi
        # pengguna baru memilih tanggal awal (belum pilih tanggal akhir) —
        # filter tanggal ditunda sampai keduanya lengkap, supaya tabel tidak
        # berkedip kosong di tengah pengguna memilih rentang.
        if isinstance(rentang_tanggal, tuple) and len(rentang_tanggal) == 2:
            mulai, akhir = rentang_tanggal
            baris_terfilter = [
                b for b in baris_terfilter if mulai <= datetime.fromisoformat(b["waktu"]).date() <= akhir
            ]

        if not baris_terfilter:
            st.markdown(
                '<div class="ppj-placeholder">Tidak ada aktivitas yang cocok dengan filter ini.</div>',
                unsafe_allow_html=True,
            )
        else:
            if len(baris_terfilter) == len(baris):
                st.caption(f"Menampilkan semua {len(baris)} aktivitas.")
            else:
                st.caption(f"Menampilkan {len(baris_terfilter)} dari {len(baris)} aktivitas.")

            st.dataframe(
                [
                    {
                        "Waktu": datetime.fromisoformat(b["waktu"]).strftime("%d %b %Y, %H:%M:%S"),
                        "Aksi": _LABEL_AKSI.get(b["aksi"], b["aksi"]),
                        "Detail": b["detail"] or "—",
                        "Sesi": b["sesi"],
                    }
                    for b in baris_terfilter
                ],
                width="stretch",
                hide_index=True,
                column_config={
                    "Waktu": st.column_config.TextColumn(width="medium"),
                    "Aksi": st.column_config.TextColumn(width="small"),
                    "Detail": st.column_config.TextColumn(
                        width="medium",
                        help="Ringkasan apa yang berubah — kosong (—) untuk aksi masuk/keluar.",
                    ),
                    "Sesi": st.column_config.TextColumn(
                        width="medium",
                        help="Penanda sesi tab admin (bukan identitas pengguna) — dipakai untuk mengorelasikan aksi-aksi dalam satu sesi login yang sama.",
                    ),
                },
            )

tombol_logout()
