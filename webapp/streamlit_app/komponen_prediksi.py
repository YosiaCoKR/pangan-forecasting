"""Komponen bersama panel "Prediksi Harga" — horizon-picker + hasil.

Diekstrak dari `views/detail_komoditas.py` supaya halaman lain yang butuh
kontrol prediksi interaktif (horizon 1/7/30 hari, tombol "Prediksi", metrik
hasil) tinggal panggil `panel_prediksi()` tanpa duplikasi kode. State
(rentang aktif) di-scope lewat `key_prefix` (biasanya slug komoditas) supaya
beberapa panel dalam sesi yang sama tidak bentrok session_state-nya.
"""

from __future__ import annotations

import logging

import pandas as pd
import streamlit as st

import forecast
from formatting import format_rupiah

RENTANG_PREDIKSI = {"1 Hari": 1, "7 Hari": 7, "30 Hari": 30}

_log = logging.getLogger(__name__)


def _ramalkan(riwayat: pd.DataFrame, nama_komoditas: str, hari_ke_depan: int) -> forecast.HasilPeramalan | None:
    try:
        return forecast.ramalkan_hasil_horizon(riwayat, nama_komoditas, hari_ke_depan)
    except forecast.ModelRisetError:
        # Kegagalan yang SUDAH diantisipasi (artefak model tidak ada, riwayat
        # kurang panjang) — placeholder rapi ditampilkan oleh pemanggil.
        return None
    except Exception:
        # Kegagalan TAK terduga (bug library, data tak wajar, dll.) — jangan
        # sampai satu komoditas/horizon nge-crash seluruh halaman publik.
        # Dicatat ke log server (bukan ditampilkan ke pengguna) supaya
        # operator tetap bisa melacak masalahnya.
        _log.exception("Gagal meramal %s h=%s", nama_komoditas, hari_ke_depan)
        return None


def panel_prediksi(
    key_prefix: str, riwayat: pd.DataFrame, nama_komoditas: str
) -> tuple[int | None, forecast.HasilPeramalan | None]:
    """Render horizon-picker + tombol Prediksi + hasil (metrik & caption).

    Mengembalikan `(rentang_terpilih, hasil)` supaya pemanggil bisa memakai
    hasil yang sama untuk elemen lain (mis. lintasan prediksi di grafik)
    tanpa menghitung ulang lewat `forecast.ramalkan_hasil_horizon`.
    """
    label_rentang = st.segmented_control(
        "Rentang prediksi",
        options=list(RENTANG_PREDIKSI.keys()),
        default="7 Hari",
        key=f"rentang-prediksi-{key_prefix}",
        label_visibility="collapsed",
    )
    if st.button(
        "Prediksi",
        key=f"tombol-prediksi-{key_prefix}",
        width="stretch",
        disabled=label_rentang is None,
    ):
        st.session_state[f"prediksi-aktif-{key_prefix}"] = RENTANG_PREDIKSI[label_rentang]
        st.rerun()

    rentang_terpilih = st.session_state.get(f"prediksi-aktif-{key_prefix}")
    hasil = _ramalkan(riwayat, nama_komoditas, rentang_terpilih) if rentang_terpilih else None
    gagal_diramal = rentang_terpilih is not None and hasil is None

    if hasil:
        st.metric(label="Harga saat ini", value=f"Rp {format_rupiah(hasil.harga_sekarang)}")
        st.metric(
            label=f"Prediksi {rentang_terpilih} hari lagi",
            value=f"Rp {format_rupiah(hasil.harga_prediksi)}",
            delta=f"{hasil.persen_perubahan:+.2f}%",
        )
        st.caption(f"Dihitung dengan model **{hasil.model_dipakai}**.")
    elif gagal_diramal:
        st.markdown(
            '<div class="ppj-placeholder">Prediksi belum tersedia untuk komoditas '
            "dan rentang ini.</div>",
            unsafe_allow_html=True,
        )
    else:
        st.caption("Pilih rentang lalu klik **Prediksi** untuk melihat hasilnya.")

    return rentang_terpilih, hasil
