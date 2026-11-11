"""Halaman admin — Unggah Dataset (CSV/XLSX).

Versi massal dari Input Harga Terbaru: admin mengunggah CSV berformat sama
dengan dataset riset (`tanggal` + satu kolom per komoditas), lalu tiap
tanggal di-upsert lewat `mock_prices.simpan_harga_banyak` — jalur tulis yang
SAMA dengan form input: tanggal baru ditambahkan, tanggal yang sudah ada
ditimpa, sel kosong tidak mengubah apa pun.
"""

from __future__ import annotations

import streamlit as st
from auth import require_admin, sesi_admin_saat_ini, tombol_logout
from data.mock_commodities import get_komoditas_list
from data.mock_prices import (
    baca_csv_harga,
    simpan_harga_banyak,
    sinkronisasi_aktif,
    sinkronkan_ke_github,
)
from db import catat_aktivitas_admin

require_admin()

st.markdown(
    """
    <div class="ppj-hero">
        <h1>Unggah Dataset</h1>
        <p>Unggah CSV atau XLSX harga — tanggal baru ditambahkan, tanggal yang sudah ada ditimpa.</p>
    </div>
    """,
    unsafe_allow_html=True,
)

nama_per_slug = {k.slug: k.nama for k in get_komoditas_list()}
st.caption(
    "Unggah langsung berkas unduhan \"Tabel Harga Berdasarkan Daerah\" (XLSX/CSV), "
    "atau tabel berkolom `tanggal` + nama komoditas."
)

berkas = st.file_uploader(
    "Berkas CSV atau XLSX",
    type=["csv", "xlsx"],
    help="Komoditas yang dibaca: " + ", ".join(nama_per_slug.values()) + ". Sel kosong dilewati.",
)
if berkas is not None:
    try:
        harga_per_slug, diabaikan = baca_csv_harga(berkas)
    except ValueError as exc:
        st.error(f"Berkas ditolak: {exc}")
    else:
        if diabaikan:
            st.warning("Kolom diabaikan (bukan komoditas): " + ", ".join(diabaikan))
        semua_tanggal = sorted({t for seri in harga_per_slug.values() for t in seri.index})
        st.info(
            f"{len(harga_per_slug)} komoditas, {len(semua_tanggal)} tanggal "
            f"({semua_tanggal[0]:%d %b %Y} – {semua_tanggal[-1]:%d %b %Y})."
        )
        st.dataframe(
            {nama_per_slug[slug]: seri for slug, seri in harga_per_slug.items()},
            height=240,
        )

        if st.button("Simpan ke Riwayat Harga", type="primary", width="stretch"):
            try:
                hasil = simpan_harga_banyak(harga_per_slug)
            except OSError as exc:
                st.error(f"Gagal menyimpan harga: {exc}")
            else:
                baru = sum(b for b, _ in hasil.values())
                ditimpa = sum(t for _, t in hasil.values())
                catat_aktivitas_admin(
                    "dataset_diunggah",
                    sesi_admin_saat_ini(),
                    detail=(
                        f"{berkas.name} — {len(hasil)} komoditas, {baru} titik baru, "
                        f"{ditimpa} ditimpa ({semua_tanggal[0]:%d %b %Y} – {semua_tanggal[-1]:%d %b %Y})"
                    ),
                )
                st.success(f"Tersimpan: {baru} titik harga baru, {ditimpa} ditimpa.")

                galat_sinkron = sinkronkan_ke_github()
                if galat_sinkron:
                    st.warning(
                        f"Tersimpan di server ini, TAPI gagal disalin ke repo ({galat_sinkron}) — "
                        "data bisa hilang saat hosting restart. Periksa secrets `github` lalu unggah ulang."
                    )
                elif not sinkronisasi_aktif():
                    st.warning(
                        "Tersimpan hanya di server ini — secrets `github` belum diisi, "
                        "jadi data akan hilang saat app restart."
                    )
                else:
                    st.caption("Disalin juga ke repo; commit ini memicu redeploy sebentar.")

tombol_logout()
