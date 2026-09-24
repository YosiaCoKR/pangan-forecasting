"""Perbandingan harga aktual dengan tiga lintasan prediksi untuk semua komoditas."""

from __future__ import annotations

import forecast
import plotly.graph_objects as go
import streamlit as st
from data.mock_commodities import get_komoditas_list
from data.mock_prices import get_price_history

_HORIZONS = (1, 7, 30)
_WARNA_MODEL = {1: "#3b82f6", 7: "#f59e0b", 30: "#ef4444"}
_WARNA_AKTUAL = "#199e70"
_LATAR_CHART = "#12181a"


def _buat_grafik(slug: str, nama: str, unit: str) -> go.Figure | None:
    riwayat = get_price_history(slug, hari=90)
    if riwayat.empty:
        return None

    fig = go.Figure()
    fig.add_trace(
        go.Scatter(
            x=riwayat["tanggal"],
            y=riwayat["harga"],
            mode="lines",
            name="Harga aktual",
            line=dict(color=_WARNA_AKTUAL, width=2.5),
            hovertemplate="Aktual<br>%{x|%d %b %Y}<br>Rp %{y:,.0f}<extra></extra>",
        )
    )

    for horizon in _HORIZONS:
        try:
            prediksi = forecast.ramalkan_harga(riwayat, nama, horizon)
        except forecast.ModelRisetError as error:
            st.warning(f"Prediksi H+{horizon} untuk {nama} belum tersedia: {error}")
            continue

        tanggal_gabungan = [riwayat["tanggal"].iloc[-1], *prediksi.index]
        harga_gabungan = [riwayat["harga"].iloc[-1], *prediksi.to_numpy()]
        fig.add_trace(
            go.Scatter(
                x=tanggal_gabungan,
                y=harga_gabungan,
                mode="lines+markers",
                name=f"Prediksi H+{horizon}",
                line=dict(color=_WARNA_MODEL[horizon], width=2, dash="dash"),
                marker=dict(size=4),
                hovertemplate=(
                    f"Prediksi H+{horizon}<br>%{{x|%d %b %Y}}<br>"
                    "Rp %{y:,.0f}<extra></extra>"
                ),
            )
        )

    fig.update_layout(
        title=dict(text=nama, x=0.02, xanchor="left", font=dict(size=15)),
        height=365,
        margin=dict(l=68, r=20, t=58, b=45),
        paper_bgcolor=_LATAR_CHART,
        plot_bgcolor=_LATAR_CHART,
        template="plotly_white",
        hovermode="x unified",
        showlegend=True,
        legend=dict(
            orientation="h",
            yanchor="bottom",
            y=1.01,
            x=0,
            font=dict(size=10, color="rgba(230,230,224,0.8)"),
            bgcolor="rgba(0,0,0,0)",
        ),
        font=dict(color="rgba(230,230,224,0.8)"),
        separators=",.",
    )
    fig.update_xaxes(
        title="Tanggal",
        tickformat="%d %b",
        showgrid=False,
        color="rgba(230,230,224,0.7)",
        linecolor="rgba(255,255,255,0.18)",
        showline=True,
    )
    fig.update_yaxes(
        title=f"Rp/{unit}",
        tickformat=",.0f",
        showgrid=True,
        gridcolor="rgba(255,255,255,0.08)",
        zeroline=False,
        color="rgba(230,230,224,0.7)",
    )
    return fig


st.markdown(
    """
    <div class="ppj-hero">
        <h1>📊 Aktual vs Prediksi</h1>
        <p>27 lintasan prediksi dari 9 komoditas dan 3 horizon model.</p>
    </div>
    """,
    unsafe_allow_html=True,
)

st.caption(
    "Garis hijau menunjukkan harga aktual 90 hari terakhir. "
    "Garis putus-putus menunjukkan prediksi H+1, H+7, dan H+30 dari model GA-LightGBM + MSTL."
)

komoditas_list = get_komoditas_list()
for nomor_baris in range(0, len(komoditas_list), 3):
    kolom = st.columns(3, gap="medium")
    for kolom_tampil, komoditas in zip(
        kolom, komoditas_list[nomor_baris : nomor_baris + 3]
    ):
        with kolom_tampil:
            grafik = _buat_grafik(komoditas.slug, komoditas.nama, komoditas.unit)
            if grafik is None:
                st.info(f"Data aktual {komoditas.nama} belum tersedia.")
            else:
                st.plotly_chart(grafik, width="stretch", theme=None)

st.caption(
    "Nilai akhir setiap kurva dapat dilihat dengan mengarahkan kursor ke titik prediksi terakhir."
)
