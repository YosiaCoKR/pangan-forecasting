"""Halaman Dashboard Pangan (publik) — kartu 9 komoditas + detail-nya."""

from __future__ import annotations

import streamlit as st

from data.mock_commodities import get_kategori_list
from data.mock_prices import KartuHarga, get_dashboard_cards, get_price_history
from formatting import format_rupiah, format_waktu_pembaruan, tren_status
from komponen_prediksi import panel_prediksi

_KELAS_TREN_KARTU = {"naik": "ppj-trend-up", "turun": "ppj-trend-down", "tetap": "ppj-trend-flat"}


def _tren_harian(kartu: KartuHarga) -> tuple[str, str]:
    """(kelas_css, label) panah naik/turun/tetap dibanding harga kemarin."""
    status, label = tren_status(kartu.harga_terbaru, kartu.harga_kemarin)
    return _KELAS_TREN_KARTU[status], label


def _gambar_kartu(kartu: KartuHarga) -> None:
    harga_format = format_rupiah(kartu.harga_terbaru)
    kelas_tren, label_tren = _tren_harian(kartu)

    st.markdown(
        f"""
        <div class="ppj-card">
            <div class="ppj-card-head">
                <span class="ppj-card-icon">{kartu.komoditas.ikon}</span>
                <h4>{kartu.komoditas.nama}</h4>
            </div>
            <p class="ppj-price">Rp {harga_format} <span class="ppj-unit">/ {kartu.komoditas.unit}</span></p>
            <p class="{kelas_tren}">{label_tren} dari kemarin</p>
            <p class="ppj-updated">🕒 {format_waktu_pembaruan(kartu.diperbarui_pada)}</p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    # Komponen prediksi bersama (sama dengan Detail Komoditas) — dipasang
    # langsung di kartu supaya horizon 1/7/30 hari bisa diramal tanpa perlu
    # pindah halaman dulu.
    riwayat = get_price_history(kartu.komoditas.slug, hari=90)
    with st.container(border=True, key=f"kartu-prediksi-{kartu.komoditas.slug}"):
        panel_prediksi(kartu.komoditas.slug, riwayat, kartu.komoditas.nama)

    if st.button("Lihat Detail", key=f"detail-{kartu.komoditas.slug}", width="stretch"):
        st.session_state["komoditas_dipilih"] = kartu.komoditas.slug
        st.switch_page("views/detail_komoditas.py")


def tampilkan_grid_dashboard() -> None:
    st.markdown(
        """
        <div class="ppj-hero">
            <h1>🌾 Prediksi Pangan Jogja</h1>
            <p>Pantau harga 9 komoditas pangan di Yogyakarta &amp; lihat prediksinya.</p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    kartu_list = get_dashboard_cards()
    kolom_per_baris = 3

    if not kartu_list:
        # Pertahanan tampilan kalau daftar komoditas/harga kosong (mis. data
        # sumber belum siap) — grid kosong tanpa penjelasan terlihat seperti
        # halaman rusak, bukan cuma "belum ada data".
        st.markdown(
            '<div class="ppj-placeholder">Data harga komoditas belum tersedia.</div>',
            unsafe_allow_html=True,
        )
        return

    for kunci_kategori, label_kategori in get_kategori_list():
        kelompok = [k for k in kartu_list if k.komoditas.kategori == kunci_kategori]
        if not kelompok:
            continue

        st.markdown(f"#### {label_kategori}")
        for awal in range(0, len(kelompok), kolom_per_baris):
            kolom = st.columns(kolom_per_baris)
            for kolom_slot, kartu in zip(kolom, kelompok[awal : awal + kolom_per_baris]):
                with kolom_slot:
                    with st.container(border=False):
                        _gambar_kartu(kartu)
        st.markdown('<div class="ppj-spacer-md"></div>', unsafe_allow_html=True)


tampilkan_grid_dashboard()
