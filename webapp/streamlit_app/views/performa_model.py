"""Halaman publik Performa Model — seberapa akurat prediksi harga di situs ini.

Sengaja SEDERHANA: masyarakat umum hanya perlu tahu seberapa dekat prediksi
dengan harga asli, jadi yang tampil cuma "Akurasi" dan rata-rata selisih
Rupiah dari model TERBAIK per horizon. Perbandingan LightGBM vs XGBoost,
MAPE/MAE/RMSE, grafik, dan penjelasannya ada di halaman admin
`views/admin_evaluasi_model.py`.

Angka metrik datang dari `metrik_model.muat_metrik()` (salinan tabel
backtesting walk-forward di `webapp/research/code_run_all_new.ipynb`), bukan
hitung ulang di aplikasi.
"""

from __future__ import annotations

import metrik_model
import streamlit as st
from data.mock_commodities import get_komoditas_list
from formatting import format_rupiah

LABEL_HORIZON = {1: "Besok (H+1)", 7: "1 Minggu (H+7)", 30: "1 Bulan (H+30)"}

st.markdown(
    """
    <div class="ppj-hero">
        <h1>Performa Model Prediksi</h1>
        <p>Hasil uji model pada data harga sungguhan — supaya terlihat seberapa
        jauh prediksi di situs ini bisa dipercaya.</p>
    </div>
    """,
    unsafe_allow_html=True,
)

komoditas_list = get_komoditas_list()
nama_list = [k.nama for k in komoditas_list]
# Datang dari tombol di halaman Detail Komoditas: komoditas yang baru dilihat
# langsung terpilih di sini, bukan balik ke item pertama.
slug_dari_detail = st.session_state.get("komoditas_dipilih")
komoditas_awal = next((k for k in komoditas_list if k.slug == slug_dari_detail), None)

nama_terpilih = st.selectbox(
    "Komoditas",
    options=nama_list,
    index=nama_list.index(komoditas_awal.nama) if komoditas_awal else 0,
)

metrik = metrik_model.metrik_komoditas(nama_terpilih)
if metrik.empty:
    st.markdown(
        '<div class="ppj-placeholder">Metrik model belum tersedia untuk komoditas ini.</div>',
        unsafe_allow_html=True,
    )
    st.stop()

st.markdown("#### Akurasi Prediksi")
for kolom, (_, baris) in zip(st.columns(len(metrik), gap="medium"), metrik.iterrows()):
    with kolom:
        with st.container(border=True):
            st.metric(
                LABEL_HORIZON.get(baris["horizon"], f"H+{baris['horizon']}"),
                f"{baris['akurasi']:.2f}%",
                help="Semakin mendekati 100%, semakin dekat prediksi dengan harga asli.",
            )
            st.caption(
                f"Rata-rata meleset ± Rp {format_rupiah(baris['mae_rupiah'])}/kg  \n"
                f"Model terbaik: **{baris['model_terbaik']}**"
            )

st.caption(
    "Akurasi diukur dengan menguji model pada harga sungguhan yang belum pernah dilihatnya. "
    "Makin jauh hari yang diprediksi, wajar kalau akurasinya sedikit turun."
)
