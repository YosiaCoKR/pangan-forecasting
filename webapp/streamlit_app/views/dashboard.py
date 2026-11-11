"""Halaman Dashboard Pangan (publik) — pilih komoditas + detailnya (grafik
harian/mingguan/bulanan, prediksi, ambang batas). Tidak ada lagi grid kartu:
satu komoditas tampil besar, sisanya dipilih lewat dropdown."""

from __future__ import annotations

import streamlit as st

from data.mock_prices import KartuHarga, get_dashboard_cards
from formatting import tren_status
from views.detail_komoditas import tampilkan_detail


def _gambar_hero(kartu_list: list[KartuHarga]) -> None:
    jumlah = {"naik": 0, "turun": 0, "tetap": 0}
    for kartu in kartu_list:
        status, _ = tren_status(kartu.harga_terbaru, kartu.harga_kemarin)
        jumlah[status] += 1

    st.markdown(
        f"""
        <div class="ppj-hero ppj-hero-split">
            <div>
                <h1>Prediksi Pangan Jogja</h1>
                <p>Harga {len(kartu_list)} komoditas pangan di Yogyakarta hari ini, lengkap dengan prediksinya.</p>
            </div>
            <div class="ppj-hero-stats">
                <div><strong>{jumlah["naik"]}</strong><span>naik</span></div>
                <div><strong>{jumlah["turun"]}</strong><span>turun</span></div>
                <div><strong>{jumlah["tetap"]}</strong><span>tetap</span></div>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def tampilkan_dashboard() -> None:
    kartu_list = get_dashboard_cards()
    _gambar_hero(kartu_list)

    if not kartu_list:
        # Pertahanan tampilan kalau daftar komoditas/harga kosong (mis. data
        # sumber belum siap) — grid kosong tanpa penjelasan terlihat seperti
        # halaman rusak, bukan cuma "belum ada data".
        st.markdown(
            '<div class="ppj-placeholder">Data harga komoditas belum tersedia.</div>',
            unsafe_allow_html=True,
        )
        return

    # Detail langsung di Dashboard: pilih komoditas, lihat grafik & prediksinya
    # tanpa pindah halaman. Pilihan disimpan di `komoditas_dipilih` supaya
    # halaman Performa Model membuka komoditas yang sama.
    nama_list = [k.komoditas.nama for k in kartu_list]
    slug_per_nama = {k.komoditas.nama: k.komoditas.slug for k in kartu_list}
    slug_awal = st.session_state.get("komoditas_dipilih")
    nama_awal = next((n for n, s in slug_per_nama.items() if s == slug_awal), nama_list[0])
    nama_terpilih = st.selectbox("Pilih komoditas", options=nama_list, index=nama_list.index(nama_awal))
    st.session_state["komoditas_dipilih"] = slug_per_nama[nama_terpilih]
    tampilkan_detail(slug_per_nama[nama_terpilih])

tampilkan_dashboard()
