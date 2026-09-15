"""Halaman admin — Input Harga Terbaru.

Menyimpan ke cache riwayat harga tiruan (mock, in-memory) untuk tahap
frontend; diganti dengan append ke file `.pkl` sungguhan pada task backend.
"""

from __future__ import annotations

from datetime import date

import streamlit as st

from auth import require_admin, sesi_admin_saat_ini, tombol_logout
from data.mock_commodities import get_komoditas_list
from data.mock_prices import tambah_harga_baru
from db import catat_aktivitas_admin
from formatting import format_rupiah

require_admin()

st.markdown(
    """
    <div class="ppj-hero">
        <h1>✏️ Input Harga Terbaru</h1>
        <p>Catat harga terbaru satu komoditas untuk tanggal tertentu (data tiruan).</p>
    </div>
    """,
    unsafe_allow_html=True,
)

komoditas_list = get_komoditas_list()

_, kolom_form, _ = st.columns([1, 1.6, 1])
with kolom_form:
    with st.container(border=True):
        with st.form("form-input-harga", clear_on_submit=True):
            nama_terpilih = st.selectbox("Komoditas", options=[k.nama for k in komoditas_list])
            tanggal_terpilih = st.date_input("Tanggal", value=date.today(), max_value=date.today())
            harga_baru = st.number_input(
                "Harga baru (Rp)",
                min_value=0.0,
                value=None,
                step=25.0,
                format="%.0f",
                placeholder="Contoh: 12000",
                help="Harga per satuan komoditas dalam Rupiah, harus lebih besar dari 0.",
            )
            submit = st.form_submit_button("Simpan", width="stretch")

        if submit:
            if harga_baru is None:
                st.error("Harga wajib diisi.")
            elif harga_baru <= 0:
                st.error("Harga harus lebih besar dari 0.")
            else:
                komoditas_terpilih = next(k for k in komoditas_list if k.nama == nama_terpilih)
                try:
                    tambah_harga_baru(komoditas_terpilih.slug, tanggal_terpilih, harga_baru)
                except OSError as exc:
                    # Kegagalan tulis `.pkl` (disk penuh, berkas terkunci, dst.) —
                    # jangan biarkan traceback mentah tampil ke admin.
                    st.error(f"Gagal menyimpan harga: {exc}")
                else:
                    catat_aktivitas_admin(
                        "harga_diperbarui",
                        sesi_admin_saat_ini(),
                        detail=(
                            f"{komoditas_terpilih.nama} @ {tanggal_terpilih.strftime('%d %b %Y')}: "
                            f"Rp {format_rupiah(harga_baru)}"
                        ),
                    )
                    st.success(
                        f"Harga {komoditas_terpilih.nama} pada {tanggal_terpilih.strftime('%d %b %Y')} "
                        f"disimpan: Rp {format_rupiah(harga_baru)}. Prediksi di halaman publik otomatis "
                        f"memakai data terbaru ini pada permintaan berikutnya."
                    )

tombol_logout()
