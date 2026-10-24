from __future__ import annotations

import logging

import forecast
import pandas as pd
import streamlit as st
from formatting import format_rupiah

RENTANG_PREDIKSI = {"1 Hari": 1, "7 Hari": 7, "30 Hari": 30}

_log = logging.getLogger(__name__)


def _ramalkan(
    riwayat: pd.DataFrame, nama_komoditas: str, hari_ke_depan: int
) -> forecast.HasilPeramalan | None:
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


def _rincian_harian(hasil: forecast.HasilPeramalan) -> pd.DataFrame:
    """Lintasan harian H+1..H+horizon jadi tabel siap tampil.

    `hasil.trajektori` sudah berisi harga tiap hari (dipakai juga oleh grafik
    di Detail Komoditas) — di sini cuma diformat; tidak ada peramalan ulang.
    Kolom "Perubahan" adalah selisih KUMULATIF terhadap harga aktual terakhir,
    bukan terhadap hari sebelumnya, supaya konsisten dengan `persen_perubahan`
    pada metrik ringkas di atas panel.
    """
    trajektori = hasil.trajektori
    persen = (trajektori - hasil.harga_sekarang) / hasil.harga_sekarang * 100
    return pd.DataFrame(
        {
            "Hari": [f"H+{nomor}" for nomor in range(1, len(trajektori) + 1)],
            "Tanggal": trajektori.index.strftime("%d %b %Y"),
            "Harga": [f"Rp {format_rupiah(nilai)}" for nilai in trajektori],
            "Perubahan": [f"{nilai:+.2f}%" for nilai in persen],
        }
    )


def panel_prediksi(
    key_prefix: str, riwayat: pd.DataFrame, nama_komoditas: str
) -> tuple[int | None, forecast.HasilPeramalan | None]:
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
        st.session_state[f"prediksi-aktif-{key_prefix}"] = RENTANG_PREDIKSI[
            label_rentang
        ]
        st.rerun()

    rentang_terpilih = st.session_state.get(f"prediksi-aktif-{key_prefix}")
    hasil = (
        _ramalkan(riwayat, nama_komoditas, rentang_terpilih)
        if rentang_terpilih
        else None
    )
    gagal_diramal = rentang_terpilih is not None and hasil is None

    if hasil:
        st.metric(
            label="Harga saat ini", value=f"Rp {format_rupiah(hasil.harga_sekarang)}"
        )
        st.metric(
            label=f"Prediksi {rentang_terpilih} hari lagi",
            value=f"Rp {format_rupiah(hasil.harga_prediksi)}",
            delta=f"{hasil.persen_perubahan:+.2f}%",
        )
        st.caption(f"Dihitung dengan model **{hasil.model_dipakai}**.")

        # Rincian per hari hanya berguna kalau lintasannya lebih dari satu
        # titik — untuk horizon 1 hari, metrik di atas SUDAH angka H+1.
        if len(hasil.trajektori) > 1:
            with st.popover(
                f"Lihat rincian {rentang_terpilih} hari", width="stretch"
            ):
                st.caption(
                    "Perubahan dihitung dari harga saat ini "
                    f"(Rp {format_rupiah(hasil.harga_sekarang)})."
                )
                st.dataframe(
                    _rincian_harian(hasil),
                    hide_index=True,
                    width="stretch",
                )
    elif gagal_diramal:
        st.markdown(
            '<div class="ppj-placeholder">Prediksi belum tersedia untuk komoditas '
            "dan rentang ini.</div>",
            unsafe_allow_html=True,
        )
    else:
        st.caption("Pilih rentang, lalu klik **Prediksi**.")

    return rentang_terpilih, hasil
