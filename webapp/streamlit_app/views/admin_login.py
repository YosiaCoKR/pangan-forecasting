"""Halaman login Panel Admin — form username + kata sandi dari konfigurasi.

Setelah berhasil masuk, halaman ini jadi hub navigasi ke halaman admin
lain (Input Harga Terbaru, Pengaturan Model, dst.) di balik gerbang
`auth.admin_sudah_masuk()`. Halaman-halaman itu juga baru muncul di
sidebar setelah login — lihat `app.py`.
"""

from __future__ import annotations

import streamlit as st

from auth import admin_sudah_masuk, login, tombol_logout


def _form_login() -> None:
    st.markdown(
        """
        <div class="ppj-hero">
            <h1>🔒 Panel Admin</h1>
            <p>Masukkan username &amp; kata sandi admin untuk mengelola harga &amp; model prediksi.</p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    _, kolom_tengah, _ = st.columns([1, 1.4, 1])
    with kolom_tengah:
        with st.container(border=True):
            with st.form("form-login-admin"):
                username = st.text_input("Username admin")
                kata_sandi = st.text_input("Kata sandi admin", type="password")
                submit = st.form_submit_button("Masuk", width="stretch")

            if submit:
                if login(username, kata_sandi):
                    st.rerun()
                else:
                    st.error("Username atau kata sandi salah. Coba lagi.")


def _tampilan_sudah_masuk() -> None:
    st.markdown(
        """
        <div class="ppj-hero">
            <h1>🔒 Panel Admin</h1>
            <p>Anda sedang masuk sebagai admin. Pilih menu di bawah untuk melanjutkan.</p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    kolom_a, kolom_b, kolom_c, kolom_d = st.columns(4)
    with kolom_a:
        with st.container(border=True):
            st.markdown("#### ✏️ Input Harga Terbaru")
            st.caption("Catat harga terbaru satu komoditas untuk tanggal tertentu.")
            st.page_link("views/admin_input_harga.py", label="Buka halaman", icon="➡️")
    with kolom_b:
        with st.container(border=True):
            st.markdown("#### ⚙️ Pengaturan Model")
            st.caption("Lihat model aktif & ganti dengan model lain yang tersedia.")
            st.page_link("views/admin_model_settings.py", label="Buka halaman", icon="➡️")
    with kolom_c:
        with st.container(border=True):
            st.markdown("#### 🚨 Pengaturan Ambang")
            st.caption("Atur ambang batas peringatan dini harga tiap komoditas.")
            st.page_link("views/admin_ambang_settings.py", label="Buka halaman", icon="➡️")
    with kolom_d:
        with st.container(border=True):
            st.markdown("#### 🗂️ Audit Log")
            st.caption("Lihat riwayat login & logout admin.")
            st.page_link("views/admin_audit_log.py", label="Buka halaman", icon="➡️")

    tombol_logout()


if admin_sudah_masuk():
    _tampilan_sudah_masuk()
else:
    _form_login()
