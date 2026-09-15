"""Grafik harga (Plotly) yang dipakai bersama — Detail Komoditas & Data Historis.

Prinsip yang dipegang: marka tipis, grid hairline redup, label nilai hanya di
titik yang penting (akhir historis & titik prediksi — bukan tiap titik),
tooltip gelap yang menyatu dengan tema aplikasi. Sumbu-Y dibiarkan mengikuti
rentang data asli (tidak dipaksa dari nol) supaya fluktuasi harga tetap
terbaca — komoditas Rp 50–70rb tidak jadi terlihat rata seperti garis lurus.
"""

from __future__ import annotations

from typing import Optional

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from formatting import format_rupiah

_WARNA_HISTORIS = "#199e70"
_WARNA_PREDIKSI = "#c98500"
_WARNA_PERINGATAN = "#e14b4b"
_WARNA_GRID = "rgba(255, 255, 255, 0.08)"
_WARNA_SUMBU = "rgba(255, 255, 255, 0.18)"
_WARNA_TEKS_MUTED = "rgba(230, 230, 224, 0.65)"
_WARNA_TEKS_PRIMER = "rgba(255, 255, 255, 0.95)"
_CINCIN_PERMUKAAN = "#0d0f0e"
# Latar chart di-set TETAP gelap (bukan transparan/ikut tema Streamlit) —
# kalau dibiarkan transparan, chart ini jadi putih kosong tanpa gridline
# terbaca saat browser/sistem pengguna memakai tema terang (semua warna
# grid/teks di atas dirancang untuk latar gelap, jadi nyaris tak terlihat
# di atas latar putih). Dengan latar tetap gelap, chart selalu konsisten
# terlepas dari preferensi tema perangkat pengguna.
_WARNA_LATAR = "#12181a"


def gambar_grafik_harga(
    riwayat: pd.DataFrame,
    unit: str,
    *,
    height: int = 380,
    trajektori_prediksi: Optional[pd.Series] = None,
    prediksi_label: Optional[str] = None,
    prediksi_persen: Optional[float] = None,
    sorot_peringatan: bool = False,
) -> None:
    """Gambar grafik garis harga historis, dengan lintasan prediksi harian opsional.

    `trajektori_prediksi` (kalau ada) adalah `pd.Series` berindeks tanggal
    (H+1..H+n) — garis putus-putus disambung dari titik historis terakhir
    lewat SELURUH titik lintasan, bukan cuma garis lurus ke satu titik akhir
    (`forecast.ramalkan_harga` mengembalikan lintasan harian penuh, bukan
    cuma nilai di H+n). Label nilai tetap hanya di titik akhir lintasan —
    label per-hari untuk 30 titik akan bertumpuk dan tak terbaca.

    `sorot_peringatan=True` menambah cincin merah di titik AKHIR lintasan —
    dipakai pemanggil saat titik itu (H+30) memicu peringatan dini (EWS),
    supaya titik yang jadi alasan peringatan langsung terlihat di grafik,
    bukan cuma disebut di teks banner/pop-up.
    """
    ada_prediksi = trajektori_prediksi is not None and not trajektori_prediksi.empty

    tanggal_akhir = riwayat["tanggal"].iloc[-1]
    harga_akhir = float(riwayat["harga"].iloc[-1])

    fig = go.Figure()
    fig.add_trace(
        go.Scatter(
            x=riwayat["tanggal"],
            y=riwayat["harga"],
            mode="lines",
            line=dict(color=_WARNA_HISTORIS, width=2),
            name="Harga historis",
            hovertemplate="%{x|%d %b %Y}<br>Rp %{y:,.0f}<extra></extra>",
        )
    )
    fig.add_trace(
        go.Scatter(
            x=[tanggal_akhir],
            y=[harga_akhir],
            mode="markers",
            marker=dict(size=8, color=_WARNA_HISTORIS, line=dict(width=2, color=_CINCIN_PERMUKAAN)),
            showlegend=False,
            hoverinfo="skip",
        )
    )
    # Label harga terkini hanya ditampilkan kalau TIDAK ada prediksi — begitu
    # prediksi aktif, titik historis & titik prediksi bisa berdekatan (rentang
    # 1/7 hari), dan harga terkini sudah tertulis besar di kartu di atas grafik,
    # jadi melabeli titik ini lagi cuma bikin dua label bertumpuk (lihat
    # marks-and-anatomy: label yang bentrok jangan ditumpuk).
    if not ada_prediksi:
        fig.add_annotation(
            x=tanggal_akhir,
            y=harga_akhir,
            text=f"Rp {format_rupiah(harga_akhir)}",
            showarrow=False,
            xanchor="left",
            yanchor="bottom",
            xshift=10,
            yshift=6,
            font=dict(color=_WARNA_TEKS_PRIMER, size=12),
        )

    if ada_prediksi:
        x_prediksi = [tanggal_akhir, *trajektori_prediksi.index]
        y_prediksi = [harga_akhir, *trajektori_prediksi.to_numpy()]
        fig.add_trace(
            go.Scatter(
                x=x_prediksi,
                y=y_prediksi,
                mode="lines+markers",
                line=dict(color=_WARNA_PREDIKSI, width=2, dash="dash"),
                marker=dict(
                    size=5,
                    symbol="diamond",
                    color=_WARNA_PREDIKSI,
                    line=dict(width=1, color=_CINCIN_PERMUKAAN),
                ),
                name=prediksi_label or "Prediksi",
                hovertemplate="%{x|%d %b %Y}<br>Prediksi: Rp %{y:,.0f}<extra></extra>",
            )
        )
        prediksi_tanggal_akhir = trajektori_prediksi.index[-1]
        prediksi_harga_akhir = float(trajektori_prediksi.iloc[-1])
        label_prediksi = f"Rp {format_rupiah(prediksi_harga_akhir)}"
        if prediksi_persen is not None:
            label_prediksi += f"  ({prediksi_persen:+.1f}%)"
        fig.add_annotation(
            x=prediksi_tanggal_akhir,
            y=prediksi_harga_akhir,
            text=label_prediksi,
            showarrow=False,
            xanchor="left",
            yanchor="top",
            xshift=10,
            yshift=-6,
            font=dict(color=_WARNA_TEKS_PRIMER, size=12),
        )

        if sorot_peringatan:
            fig.add_trace(
                go.Scatter(
                    x=[prediksi_tanggal_akhir],
                    y=[prediksi_harga_akhir],
                    mode="markers",
                    marker=dict(size=18, symbol="circle-open", color=_WARNA_PERINGATAN, line=dict(width=3)),
                    name="⚠️ Memicu peringatan",
                    hoverinfo="skip",
                )
            )

    fig.update_layout(
        margin=dict(l=90, r=110, t=10, b=40),
        height=height,
        xaxis_title="Tanggal",
        yaxis_title=f"Harga (Rp/{unit})",
        template="plotly_white",
        paper_bgcolor=_WARNA_LATAR,
        plot_bgcolor=_WARNA_LATAR,
        hovermode="x unified",
        # Legend selalu tampil — bukan cuma saat prediksi aktif — supaya garis
        # "Harga historis" juga eksplisit terlabel di halaman Data Historis
        # (yang tak pernah punya trace prediksi), bukan cuma bisa ditebak dari
        # judul sumbu-Y. Trace ambang batas (Fase 3) akan otomatis ikut masuk
        # legend ini begitu ditambahkan, tanpa perlu ubahan lagi di sini.
        showlegend=True,
        legend=dict(
            orientation="h",
            yanchor="bottom",
            y=1.02,
            xanchor="left",
            x=0,
            bgcolor="rgba(0,0,0,0)",
            font=dict(color=_WARNA_TEKS_MUTED, size=12),
        ),
        separators=",.",
        hoverlabel=dict(
            bgcolor="#181c1a",
            bordercolor="rgba(255,255,255,0.15)",
            font=dict(color=_WARNA_TEKS_PRIMER, size=13),
        ),
        font=dict(color=_WARNA_TEKS_MUTED),
    )
    fig.update_xaxes(
        tickformat="%d %b",
        showgrid=False,
        color=_WARNA_TEKS_MUTED,
        linecolor=_WARNA_SUMBU,
        showline=True,
    )
    fig.update_yaxes(
        tickformat=",.0f",
        showgrid=True,
        gridcolor=_WARNA_GRID,
        gridwidth=1,
        zeroline=False,
        color=_WARNA_TEKS_MUTED,
        rangemode="normal",
    )
    st.plotly_chart(fig, width="stretch", theme=None)
