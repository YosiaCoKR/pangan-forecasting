"""Halaman admin — Pengaturan Ambang (Peringatan Dini Harga).

Admin menyesuaikan ambang batas EWS (harga tetap dan/atau persen kenaikan)
tiap komoditas — menumpang pola halaman Pengaturan Model yang sudah ada.
Tidak melatih ulang model apa pun, hanya menyimpan nilai ambang ke
`config.json` (lewat `config.get_ambang_ews`/`set_ambang_ews`).
"""

from __future__ import annotations

import streamlit as st

from auth import require_admin, sesi_admin_saat_ini, tombol_logout
from config import get_ambang_ews, reset_ambang_ews, set_ambang_ews
from data.mock_commodities import get_komoditas_list
from db import catat_aktivitas_admin
from formatting import format_rupiah


def _ringkas_ambang(persen_kenaikan: float | None, harga_tetap: float | None) -> str:
    bagian = []
    bagian.append(f"naik≥{persen_kenaikan:.0f}%" if persen_kenaikan is not None else "naik: nonaktif")
    bagian.append(f"harga≥Rp{format_rupiah(harga_tetap)}" if harga_tetap is not None else "harga: nonaktif")
    return ", ".join(bagian)

require_admin()

st.markdown(
    """
    <div class="ppj-hero">
        <h1>🚨 Pengaturan Ambang</h1>
        <p>Atur ambang batas peringatan dini harga (H+30) tiap komoditas.</p>
    </div>
    """,
    unsafe_allow_html=True,
)

komoditas_list = get_komoditas_list()

# Slot ini diisi di akhir skrip, supaya kartu "Ambang Saat Ini" selalu
# menampilkan nilai terbaru walau baru saja diubah lewat form di bawah.
slot_ambang_aktif = st.container()

st.markdown("#### Ubah Ambang Komoditas")
_, kolom_form, _ = st.columns([1, 1.6, 1])
with kolom_form:
    with st.container(border=True):
        nama_terpilih = st.selectbox("Komoditas", options=[k.nama for k in komoditas_list], key="ambang-komoditas")
        komoditas_terpilih = next(k for k in komoditas_list if k.nama == nama_terpilih)

        ambang_sekarang = get_ambang_ews(komoditas_terpilih.slug)
        # Widget di-key per-slug (bukan cuma label) — supaya ganti pilihan
        # Komoditas benar-benar memuat ulang nilai ambang komoditas itu,
        # bukan mempertahankan angka bekas komoditas sebelumnya (Streamlit
        # menyimpan nilai widget di session_state per key, bukan membaca
        # ulang `value=` tiap render kalau key-nya tidak berubah).
        kunci_persen = f"ambang-persen-{komoditas_terpilih.slug}"
        kunci_harga = f"ambang-harga-{komoditas_terpilih.slug}"

        persen_terpilih = st.number_input(
            "Ambang kenaikan (%)",
            min_value=0.0,
            value=ambang_sekarang["persen_kenaikan"],
            step=1.0,
            format="%.0f",
            placeholder="Kosongkan untuk nonaktifkan",
            help="Peringatan muncul kalau prediksi 30 hari naik ≥ persen ini dari harga sekarang.",
            key=kunci_persen,
        )
        harga_tetap_terpilih = st.number_input(
            "Ambang harga tetap (Rp)",
            min_value=0.0,
            value=ambang_sekarang["harga_tetap"],
            step=100.0,
            format="%.0f",
            placeholder="Kosongkan untuk nonaktifkan",
            help="Peringatan muncul kalau prediksi 30 hari mencapai atau melewati harga ini.",
            key=kunci_harga,
        )

        # Pesan sukses reset "menyeberang" satu rerun (tombol reset manggil
        # st.rerun() supaya widget di atas sempat baca ulang nilai default) —
        # ditaruh di session_state lalu dibaca+dibuang sekali di sini.
        pesan_reset = st.session_state.pop("ambang-reset-pesan", None)
        if pesan_reset == komoditas_terpilih.nama:
            st.success(f"Ambang **{pesan_reset}** dikembalikan ke default.")

        # Slot juga, supaya peringatan "belum disimpan" langsung hilang di run
        # yang sama begitu tombol Simpan ditekan (bukan baru di rerun berikutnya).
        slot_peringatan = st.container()

        kolom_simpan, kolom_reset = st.columns(2)
        with kolom_simpan:
            if st.button("Simpan Ambang", width="stretch"):
                set_ambang_ews(
                    komoditas_terpilih.slug,
                    harga_tetap=harga_tetap_terpilih,
                    persen_kenaikan=persen_terpilih,
                )
                catat_aktivitas_admin(
                    "ambang_diubah",
                    sesi_admin_saat_ini(),
                    detail=f"{komoditas_terpilih.nama}: {_ringkas_ambang(persen_terpilih, harga_tetap_terpilih)}",
                )
                st.success(f"Ambang **{komoditas_terpilih.nama}** disimpan.")
        with kolom_reset:
            if st.button("Reset ke Default", width="stretch"):
                reset_ambang_ews(komoditas_terpilih.slug)
                catat_aktivitas_admin(
                    "ambang_diubah",
                    sesi_admin_saat_ini(),
                    detail=f"{komoditas_terpilih.nama}: direset ke default",
                )
                # Hapus state widget supaya baris `st.number_input` di atas
                # membaca ulang nilai default (baru saja disimpan) dari
                # `get_ambang_ews`, bukan angka lama yang masih nyantol.
                st.session_state.pop(kunci_persen, None)
                st.session_state.pop(kunci_harga, None)
                st.session_state["ambang-reset-pesan"] = komoditas_terpilih.nama
                st.rerun()

        ambang_terkini = get_ambang_ews(komoditas_terpilih.slug)
        if (persen_terpilih, harga_tetap_terpilih) != (
            ambang_terkini["persen_kenaikan"],
            ambang_terkini["harga_tetap"],
        ):
            with slot_peringatan:
                st.warning("⚠️ Perubahan belum disimpan. Klik **Simpan Ambang** untuk menerapkan.")

ambang_final = get_ambang_ews(komoditas_terpilih.slug)
with slot_ambang_aktif:
    st.markdown(f"#### Ambang Saat Ini — {komoditas_terpilih.nama}")
    with st.container(border=True):
        if ambang_final["persen_kenaikan"] is None and ambang_final["harga_tetap"] is None:
            st.caption("Belum ada ambang aktif untuk komoditas ini.")
        else:
            if ambang_final["persen_kenaikan"] is not None:
                st.markdown(f"**Kenaikan ≥ {ambang_final['persen_kenaikan']:.0f}%**")
            if ambang_final["harga_tetap"] is not None:
                st.markdown(f"**Harga ≥ Rp {format_rupiah(ambang_final['harga_tetap'])}**")

tombol_logout()
