"""Halaman admin — Input Harga Terbaru.

SATU inputan per kolom dataset: baris form diturunkan dari
`data.mock_commodities.get_komoditas_list()`, yang isinya kolom harga
`DATASET-BERAS.csv`. Jadi kalau dataset diganti dan notebook dijalankan
ulang dengan kolom berbeda, form ini otomatis ikut — tidak ada daftar
komoditas yang dihardcode di sini.

Admin memilih satu tanggal, lalu mengisi harga komoditas mana saja (kolom
yang dibiarkan kosong tidak diubah). Hasilnya ditulis ke
`data/harga_historis.pkl` lewat `mock_prices.simpan_harga_batch` — satu
operasi tulis untuk seluruh form — dan langsung dipakai halaman publik:
cache prediksi dikunci dari ISI riwayat, jadi riwayat yang berubah otomatis
memicu perhitungan ulang tanpa invalidasi manual.
"""

from __future__ import annotations

from datetime import date

import streamlit as st
from auth import require_admin, sesi_admin_saat_ini, tombol_logout
from data.mock_commodities import get_komoditas_list
from data.mock_prices import harga_terakhir, simpan_harga_batch
from db import catat_aktivitas_admin
from formatting import format_rupiah

require_admin()

JUMLAH_KOLOM_GRID = 3

st.markdown(
    """
    <div class="ppj-hero">
        <h1>Input Harga Terbaru</h1>
        <p>Satu inputan per komoditas — isi yang perlu diperbarui, biarkan sisanya kosong.</p>
    </div>
    """,
    unsafe_allow_html=True,
)

komoditas_list = get_komoditas_list()
if not komoditas_list:
    st.error("Tidak ada kolom komoditas yang terbaca dari dataset riset.")
    st.stop()

with st.form("form-input-harga"):
    tanggal_terpilih = st.date_input(
        "Tanggal harga",
        value=date.today(),
        max_value=date.today(),
        help="Tanggal berlakunya harga di bawah. Titik yang tanggalnya sudah ada akan diperbarui.",
    )

    st.markdown("##### Harga per Komoditas (Rp)")
    nilai_terisi: dict[str, float | None] = {}
    kolom_grid = st.columns(JUMLAH_KOLOM_GRID, gap="medium")
    for nomor, komoditas in enumerate(komoditas_list):
        terakhir = harga_terakhir(komoditas.slug)
        with kolom_grid[nomor % JUMLAH_KOLOM_GRID]:
            nilai_terisi[komoditas.slug] = st.number_input(
                f"{komoditas.ikon} {komoditas.nama}",
                min_value=0.0,
                value=None,
                step=25.0,
                format="%.0f",
                placeholder=(
                    f"Terakhir: {format_rupiah(terakhir)}"
                    if terakhir
                    else "Contoh: 12000"
                ),
                help=f"Harga per {komoditas.unit} dalam Rupiah. Kosongkan kalau tidak berubah.",
                key=f"harga-{komoditas.slug}",
            )

    simpan = st.form_submit_button("Simpan Harga", width="stretch", type="primary")

if simpan:
    harga_valid = {
        slug: h for slug, h in nilai_terisi.items() if h is not None and h > 0
    }
    harga_nol = [slug for slug, h in nilai_terisi.items() if h is not None and h <= 0]

    if harga_nol:
        st.error("Harga harus lebih besar dari 0 — periksa kembali kolom yang diisi.")
    elif not harga_valid:
        st.warning("Belum ada harga yang diisi.")
    else:
        try:
            tersimpan = simpan_harga_batch(tanggal_terpilih, harga_valid)
        except OSError as exc:
            # Kegagalan tulis `.pkl` (disk penuh, berkas terkunci, dst.) —
            # jangan biarkan traceback mentah tampil ke admin.
            st.error(f"Gagal menyimpan harga: {exc}")
        else:
            nama_per_slug = {k.slug: k.nama for k in komoditas_list}
            rincian = ", ".join(
                f"{nama_per_slug[slug]}: Rp {format_rupiah(harga)}"
                for slug, harga in harga_valid.items()
            )
            catat_aktivitas_admin(
                "harga_diperbarui",
                sesi_admin_saat_ini(),
                detail=f"{tanggal_terpilih.strftime('%d %b %Y')} — {rincian}",
            )
            st.success(
                f"{tersimpan} harga disimpan untuk {tanggal_terpilih.strftime('%d %b %Y')}. "
                "Halaman publik memakai data terbaru ini pada permintaan berikutnya."
            )
            with st.expander("Lihat yang baru disimpan"):
                for slug, harga in harga_valid.items():
                    st.markdown(
                        f"- **{nama_per_slug[slug]}** — Rp {format_rupiah(harga)}"
                    )

tombol_logout()
