"""Halaman admin — Evaluasi Model (versi lengkap dari Performa Model publik).

Halaman publik hanya menampilkan akurasi model terbaik. Di sini admin melihat
semuanya: MAPE/MAE/RMSE LightGBM vs XGBoost per horizon, grafik
perbandingannya, model yang sedang dipakai aplikasi, dan cara membaca tiap
metrik — bahan untuk memutuskan pilihan di Pengaturan Model.

Sumber angka sama: `metrik_model.muat_metrik()`.
"""

from __future__ import annotations

import forecast
import metrik_model
import plotly.express as px
import streamlit as st
from auth import require_admin, tombol_logout
from data.mock_commodities import get_komoditas_list

require_admin()

st.markdown(
    """
    <div class="ppj-hero">
        <h1>Evaluasi Model</h1>
        <p>Perbandingan lengkap LightGBM vs XGBoost dari backtesting walk-forward.</p>
    </div>
    """,
    unsafe_allow_html=True,
)

nama_terpilih = st.selectbox("Komoditas", options=[k.nama for k in get_komoditas_list()])
metrik = metrik_model.metrik_komoditas(nama_terpilih)
if metrik.empty:
    st.warning("Metrik model belum tersedia untuk komoditas ini.")
    tombol_logout()
    st.stop()

model_dipakai = forecast.model_aktif(nama_terpilih).nama
st.info(
    f"Model yang dipakai aplikasi untuk {nama_terpilih}: **{model_dipakai}** "
    "(ubah di Pengaturan Model)."
)

st.markdown("#### Grafik Perbandingan")
METRIK_GRAFIK = {
    "MAPE (%)": ("mape", 1),
    "MAE (Rp/kg)": ("mae", forecast.SKALA_HARGA),
    "RMSE (Rp/kg)": ("rmse", forecast.SKALA_HARGA),
}
label_metrik = st.radio("Metrik", list(METRIK_GRAFIK), horizontal=True)
awalan, skala = METRIK_GRAFIK[label_metrik]
data_grafik = metrik.assign(
    Horizon="H+" + metrik["horizon"].astype(str),
    LightGBM=metrik[f"{awalan}_lightgbm"] * skala,
    XGBoost=metrik[f"{awalan}_xgboost"] * skala,
).melt(id_vars="Horizon", value_vars=["LightGBM", "XGBoost"], var_name="Model", value_name=label_metrik)
st.plotly_chart(
    px.bar(data_grafik, x="Horizon", y=label_metrik, color="Model", barmode="group"),
    width="stretch",
)
st.caption("Batang lebih pendek = kesalahan lebih kecil = model lebih baik.")

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

with st.expander("Cara membaca angka di atas", expanded=True):
    st.markdown(
        """
- **MAPE** (*Mean Absolute Percentage Error*) — rata-rata selisih prediksi
  terhadap harga asli, dalam persen. Semakin kecil semakin baik; **Akurasi**
  di halaman publik hanyalah `100% - MAPE`. Contoh: MAPE 3% pada harga
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

tombol_logout()
