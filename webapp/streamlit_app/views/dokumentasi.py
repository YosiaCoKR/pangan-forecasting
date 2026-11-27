"""Halaman publik Dokumentasi — akses Manual Book aplikasi (PDF di Google Drive).

Manual Book diperbarui di Drive, bukan di repo: cukup ganti `MANUAL_BOOK_ID`
kalau berkasnya diganti.
"""

from __future__ import annotations

import streamlit as st

MANUAL_BOOK_ID = "1EIOFU8-2VTfwiVK8MXXaoCsrTQ7pRqJF"
MANUAL_BOOK_URL = f"https://drive.google.com/file/d/{MANUAL_BOOK_ID}/view?usp=sharing"

st.markdown(
    """
    <div class="ppj-hero">
        <h1>Dokumentasi</h1>
        <p>Panduan lengkap memakai situs Prediksi Pangan Jogja — dari membaca
        dashboard sampai fitur admin — ada di Manual Book berikut.</p>
    </div>
    """,
    unsafe_allow_html=True,
)

st.link_button(
    "Buka Manual Book", MANUAL_BOOK_URL, icon=":material/menu_book:", type="primary"
)
st.iframe(f"https://drive.google.com/file/d/{MANUAL_BOOK_ID}/preview", height=800)
