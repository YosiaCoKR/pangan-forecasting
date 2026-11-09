"""Halaman publik Performa Model — seberapa akurat prediksi harga di situs ini.

Angka metrik datang dari `metrik_model.muat_metrik()` (salinan tabel
backtesting walk-forward di `webapp/research/code_run_all_new.ipynb`), bukan
hitung ulang di aplikasi. Halaman ini sengaja menonjolkan "Akurasi"
(= 100 - MAPE) karena itu yang paling mudah dibaca masyarakat umum, sementara
MAE/RMSE dalam Rupiah dan perbandingan LightGBM vs XGBoost tetap tersedia di
tabel untuk yang ingin memeriksa.
"""

from __future__ import annotations

import forecast
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
                help="Akurasi = 100% - MAPE (rata-rata selisih prediksi vs harga asli).",
            )
            st.caption(
                f"Rata-rata selisih ± Rp {format_rupiah(baris['mae_rupiah'])}/kg  \n"
                f"Model terbaik: **{baris['model_terbaik']}**"
            )

st.caption(
    f"Model yang dipakai aplikasi untuk {nama_terpilih} saat ini: "
    f"**{forecast.model_aktif(nama_terpilih).nama}** (dipilih admin di Pengaturan Model)."
)

st.markdown("#### LightGBM vs XGBoost")
tabel = metrik.rename(
    columns={
        "horizon": "Horizon (hari)",
        "mape_lightgbm": "MAPE LightGBM (%)",
        "mape_xgboost": "MAPE XGBoost (%)",
        "model_terbaik": "Model terbaik",
        "mae_rupiah": "MAE model terbaik (Rp/kg)",
        "rmse_rupiah": "RMSE model terbaik (Rp/kg)",
    }
)[
    [
        "Horizon (hari)",
        "MAPE LightGBM (%)",
        "MAPE XGBoost (%)",
        "Model terbaik",
        "MAE model terbaik (Rp/kg)",
        "RMSE model terbaik (Rp/kg)",
    ]
]
st.dataframe(
    tabel,
    hide_index=True,
    width="stretch",
    column_config={
        "MAPE LightGBM (%)": st.column_config.NumberColumn(format="%.4f"),
        "MAPE XGBoost (%)": st.column_config.NumberColumn(format="%.4f"),
        "MAE model terbaik (Rp/kg)": st.column_config.NumberColumn(format="%.0f"),
        "RMSE model terbaik (Rp/kg)": st.column_config.NumberColumn(format="%.0f"),
    },
)

with st.expander("Cara membaca angka di atas"):
    st.markdown(
        """
- **MAPE** (*Mean Absolute Percentage Error*) — rata-rata selisih prediksi
  terhadap harga asli, dalam persen. Semakin kecil semakin baik; **Akurasi**
  di kartu atas hanyalah `100% - MAPE`. Contoh: MAPE 3% pada harga
  Rp 30.000/kg berarti prediksi rata-rata melenceng sekitar Rp 900.
- **MAE** — rata-rata selisih dalam Rupiah per kg. Contoh: MAE Rp 2.000
  berarti prediksi rata-rata melenceng sekitar Rp 2.000 dari harga asli.
- **RMSE** — mirip MAE, tapi memberi bobot lebih besar pada kesalahan besar.
  Contoh: MAE Rp 2.000 sementara RMSE Rp 5.000 berarti kebanyakan hari
  melencengnya kecil, tapi ada beberapa hari yang melencengnya jauh;
  kalau RMSE hampir sama dengan MAE, selisihnya rata setiap hari.
        """
    )

st.markdown("#### Semua Komoditas")
semua = metrik_model.muat_metrik().rename(
    columns={
        "komoditas": "Komoditas",
        "horizon": "Horizon (hari)",
        "mape_lightgbm": "MAPE LightGBM (%)",
        "mape_xgboost": "MAPE XGBoost (%)",
        "model_terbaik": "Model terbaik",
    }
)
st.dataframe(
    semua[
        [
            "Komoditas",
            "Horizon (hari)",
            "MAPE LightGBM (%)",
            "MAPE XGBoost (%)",
            "Model terbaik",
        ]
    ],
    hide_index=True,
    width="stretch",
    # Tinggi dipaksa setinggi semua baris: default-nya tabel 27 baris
    # punya scroll sendiri, dan scroll di dalam scroll bikin orang kelewat baris.
    height=35 * (len(semua) + 1) + 3,
    column_config={
        "MAPE LightGBM (%)": st.column_config.NumberColumn(format="%.4f"),
        "MAPE XGBoost (%)": st.column_config.NumberColumn(format="%.4f"),
    },
)
