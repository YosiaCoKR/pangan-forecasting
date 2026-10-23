"""Halaman admin — Pengaturan Model.

Admin melihat model aktif dan memilih model lain dari `forecast.MODEL_TERSEDIA`
(artefak hasil riset yang benar-benar ada di folder `research/`) — aplikasi
tidak melatih atau mengubah parameter model apa pun, hanya menyimpan pilihan
ke `config.json`. Pilihan itulah yang dibaca `forecast.model_aktif()`, jadi
seluruh halaman publik (Detail Komoditas, Dashboard, EWS)
langsung ikut memakai model yang dipilih di sini.
"""

from __future__ import annotations

import forecast
import streamlit as st

from auth import require_admin, sesi_admin_saat_ini, tombol_logout
from config import set_model_aktif
from db import catat_aktivitas_admin

require_admin()

st.markdown(
    """
    <div class="ppj-hero">
        <h1>Pengaturan Model</h1>
        <p>Lihat &amp; ganti model prediksi yang aktif dipakai seluruh halaman aplikasi.</p>
    </div>
    """,
    unsafe_allow_html=True,
)

kunci_model_list = list(forecast.MODEL_TERSEDIA)

# Slot ini diisi di akhir skrip, supaya kartu "Model Aktif" selalu
# menampilkan nilai terbaru walau baru saja diubah lewat form di bawah.
slot_model_aktif = st.container()

st.markdown("#### Ganti Model Aktif")
_, kolom_form, _ = st.columns([1, 1.6, 1])
with kolom_form:
    with st.container(border=True):
        model_aktif_sekarang = forecast.model_aktif().kunci
        kunci_terpilih = st.selectbox(
            "Pilih model",
            options=kunci_model_list,
            index=kunci_model_list.index(model_aktif_sekarang),
            format_func=lambda kunci: forecast.MODEL_TERSEDIA[kunci].nama,
        )
        model_terpilih = forecast.MODEL_TERSEDIA[kunci_terpilih]
        st.caption(f"{model_terpilih.deskripsi} · artefak di `research/{model_terpilih.folder}/`")

        # Slot juga, supaya peringatan "belum disimpan" langsung hilang di run
        # yang sama begitu tombol Simpan ditekan (bukan baru di rerun berikutnya).
        slot_peringatan = st.container()

        if st.button("Simpan Model Aktif", width="stretch"):
            if kunci_terpilih == model_aktif_sekarang:
                st.info("Model ini sudah aktif.")
            else:
                set_model_aktif(kunci_terpilih)
                catat_aktivitas_admin(
                    "model_diubah",
                    sesi_admin_saat_ini(),
                    detail=f"{model_aktif_sekarang} -> {kunci_terpilih}",
                )
                # Prediksi lama masih tersimpan di `st.cache_data` dengan kunci
                # model LAMA, jadi cukup dibiarkan — kunjungan berikutnya memakai
                # `kunci_model` baru dan otomatis menghitung ulang.
                st.success(f"Model aktif diubah ke **{model_terpilih.nama}**.")

        model_aktif_terkini = forecast.model_aktif().kunci
        if kunci_terpilih != model_aktif_terkini:
            with slot_peringatan:
                st.warning("⚠️ Perubahan belum disimpan. Klik **Simpan Model Aktif** untuk menerapkan.")

info_aktif = forecast.model_aktif()
with slot_model_aktif:
    st.markdown("#### Model Aktif Saat Ini")
    with st.container(border=True):
        st.markdown(f"**{info_aktif.nama}**")
        st.caption(f"{info_aktif.deskripsi} · artefak di `research/{info_aktif.folder}/`")

tombol_logout()
