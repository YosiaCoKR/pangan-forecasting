"""Tampilan detail komoditas: hero info harga, grafik historis + garis prediksi.

Prediksi memakai model riset asli lewat `forecast.ramalkan_hasil_horizon`
(MSTL + GA-LightGBM, tanpa pelatihan ulang) — bukan lagi
`data.mock_prices.get_mock_prediction`. Panel kontrol prediksi (horizon
picker, tombol, hasil) ada di `komponen_prediksi.panel_prediksi` — komponen
bersama supaya halaman lain yang butuh kontrol serupa tak perlu duplikasi.
Anotasi ambang batas & pop-up peringatan dini ditambahkan pada task
tersendiri — di sini fokus pada grafik (riwayat + garis prediksi).
"""

from __future__ import annotations

import pandas as pd
import streamlit as st

import ews
import forecast
from charting import gambar_grafik_harga
from data.mock_commodities import get_komoditas_by_slug
from data.mock_prices import get_kartu_harga, get_price_history
from formatting import format_rupiah, format_waktu_pembaruan, tren_status
from komponen_prediksi import panel_prediksi

_KELAS_TREN_HERO = {
    "naik": "ppj-hero-trend-up",
    "turun": "ppj-hero-trend-down",
    "tetap": "ppj-hero-trend-flat",
}


def _gambar_chart(
    riwayat: pd.DataFrame,
    unit: str,
    hari_ke_depan: int | None = None,
    hasil: forecast.HasilPeramalan | None = None,
    peringatan_aktif: bool = False,
) -> None:
    if riwayat.empty:
        # Sama seperti historis.py — riwayat kosong (mis. komoditas baru
        # tanpa data harga sama sekali) tetap dapat placeholder rapi,
        # bukan grafik Plotly kosong tanpa penjelasan.
        st.markdown(
            '<div class="ppj-placeholder">Data historis belum tersedia untuk komoditas ini.</div>',
            unsafe_allow_html=True,
        )
        return

    ada_prediksi = hari_ke_depan is not None and hasil is not None

    if not ada_prediksi:
        gambar_grafik_harga(riwayat, unit)
        return

    gambar_grafik_harga(
        riwayat,
        unit,
        trajektori_prediksi=hasil.trajektori,
        prediksi_label=f"Prediksi {hari_ke_depan} hari",
        prediksi_persen=hasil.persen_perubahan,
        # Titik yang memicu EWS selalu di H+30 (lihat `ews.HORIZON_EWS`) —
        # cuma disorot kalau pengguna memang sedang melihat lintasan 30 hari,
        # supaya titik yang disorot benar-benar ada di grafik yang tampil.
        sorot_peringatan=peringatan_aktif and hari_ke_depan == ews.HORIZON_EWS,
    )


def _gambar_hero(slug: str) -> None:
    kartu = get_kartu_harga(slug)
    if kartu is None:
        return

    komoditas = kartu.komoditas
    status, label_tren = tren_status(kartu.harga_terbaru, kartu.harga_kemarin)
    kelas_tren = _KELAS_TREN_HERO[status]

    st.markdown(
        f"""
        <div class="ppj-hero ppj-hero-detail">
            <div class="ppj-hero-detail-head">
                <span class="ppj-hero-detail-icon">{komoditas.ikon}</span>
                <div>
                    <h1>{komoditas.nama}</h1>
                    <p>Grafik pergerakan harga 90 hari terakhir (data tiruan).</p>
                </div>
            </div>
            <div class="ppj-hero-detail-price">
                <span class="ppj-hero-price-value">Rp {format_rupiah(kartu.harga_terbaru)}</span>
                <span class="ppj-hero-unit">/ {komoditas.unit}</span>
                <span class="{kelas_tren}">{label_tren}</span>
                <span class="ppj-hero-updated">🕒 {format_waktu_pembaruan(kartu.diperbarui_pada)}</span>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def _detail_peringatan(peringatan: ews.HasilPeringatan) -> str:
    if peringatan.alasan == "persen":
        return f"naik **{peringatan.persen_perubahan:+.1f}%** (ambang: {peringatan.ambang_persen:.0f}%)"
    return f"mencapai **Rp {format_rupiah(peringatan.harga_prediksi)}** (ambang: Rp {format_rupiah(peringatan.ambang_harga_tetap)})"


@st.dialog("⚠️ Peringatan Dini Harga")
def _popup_peringatan(nama_komoditas: str, peringatan: ews.HasilPeringatan) -> None:
    st.write(f"Harga **{nama_komoditas}** diprediksi {_detail_peringatan(peringatan)} dalam 30 hari ke depan.")
    if st.button("Tutup", width="stretch"):
        st.rerun()


def _gambar_peringatan(slug: str, riwayat: pd.DataFrame, nama_komoditas: str) -> bool:
    """Banner (selalu terlihat) + pop-up sekali per sesi kalau prediksi H+30
    melewati ambang komoditas ini. Mengembalikan True kalau peringatan
    aktif, supaya grafik (`_gambar_chart`) tahu perlu menyorot titik H+30
    atau tidak saat pengguna sedang melihat lintasan 30 hari.

    Pop-up cuma muncul SEKALI per komoditas per sesi (bukan tiap rerun
    skrip, mis. tiap klik tombol lain di halaman ini) — ditandai lewat
    session_state, supaya tidak mengganggu.
    """
    peringatan = ews.periksa_peringatan(riwayat, slug, nama_komoditas)
    if peringatan is None or not peringatan.aktif:
        return False

    st.warning(
        f"⚠️ **Peringatan Dini** — harga {nama_komoditas} diprediksi "
        f"{_detail_peringatan(peringatan)} dalam 30 hari ke depan."
    )

    kunci_sudah_tampil = f"peringatan-popup-tampil-{slug}"
    if not st.session_state.get(kunci_sudah_tampil):
        st.session_state[kunci_sudah_tampil] = True
        _popup_peringatan(nama_komoditas, peringatan)

    return True


def tampilkan_detail(slug: str) -> None:
    komoditas = get_komoditas_by_slug(slug)
    if komoditas is None:
        st.error("Komoditas tidak ditemukan.")
        return

    if st.button("← Kembali ke Dashboard"):
        st.session_state.pop("komoditas_dipilih", None)
        st.switch_page("views/dashboard.py")

    _gambar_hero(slug)

    riwayat = get_price_history(slug, hari=90)
    peringatan_aktif = _gambar_peringatan(slug, riwayat, komoditas.nama)

    kolom_chart, kolom_prediksi = st.columns([3, 1], gap="medium")

    with kolom_prediksi:
        st.markdown("#### Prediksi Harga")
        with st.container(border=True, key=f"kartu-prediksi-{slug}"):
            rentang_terpilih, hasil = panel_prediksi(slug, riwayat, komoditas.nama)

    with kolom_chart:
        st.markdown("#### Grafik Harga")
        _gambar_chart(riwayat, komoditas.unit, rentang_terpilih, hasil, peringatan_aktif)


_slug_terpilih = st.session_state.get("komoditas_dipilih")
if _slug_terpilih:
    tampilkan_detail(_slug_terpilih)
else:
    st.warning("Komoditas belum dipilih.")
    if st.button("← Kembali ke Dashboard"):
        st.switch_page("views/dashboard.py")
