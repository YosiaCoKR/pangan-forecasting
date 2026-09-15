"""Deteksi Peringatan Dini Harga (EWS) — bandingkan prediksi H+30 terhadap
ambang batas per komoditas (`config.get_ambang_ews`).

Selalu memakai jalur prediksi 30 hari (BUKAN horizon yang sedang dipilih
pengguna di panel prediksi interaktif) — sesuai PRD ("EWS dari jalur
prediksi 30 hari") dan notebook riset (bagian "Early Warning System (H+30)").

Modul ini baru menyediakan DETEKSI + banner peringatan sederhana. Pop-up
(`st.dialog`) dan sorotan titik di grafik ditambahkan pada task tersendiri.
"""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

import config
import forecast

HORIZON_EWS = 30


@dataclass(frozen=True)
class HasilPeringatan:
    aktif: bool
    harga_prediksi: float
    persen_perubahan: float
    ambang_persen: float | None
    ambang_harga_tetap: float | None
    alasan: str | None  # "persen" | "harga_tetap" | None (tidak ada peringatan)


def periksa_peringatan(riwayat: pd.DataFrame, slug: str, nama_komoditas: str) -> HasilPeringatan | None:
    """Cek apakah prediksi H+30 komoditas ini melewati ambang EWS-nya.

    Mengembalikan `None` kalau prediksi H+30 gagal dihitung (model riset
    belum tersedia, riwayat kurang panjang, dst.) — pemanggil cukup
    menganggap "tidak ada peringatan" untuk kasus ini, bukan menganggap
    error, supaya halaman publik tidak pernah gagal cuma gara-gara EWS.
    """
    try:
        hasil = forecast.ramalkan_hasil_horizon(riwayat, nama_komoditas, HORIZON_EWS)
    except forecast.ModelRisetError:
        return None
    except Exception:
        return None

    ambang = config.get_ambang_ews(slug)
    ambang_persen = ambang.get("persen_kenaikan")
    ambang_harga = ambang.get("harga_tetap")

    alasan = None
    if ambang_persen is not None and hasil.persen_perubahan >= ambang_persen:
        alasan = "persen"
    elif ambang_harga is not None and hasil.harga_prediksi >= ambang_harga:
        alasan = "harga_tetap"

    return HasilPeringatan(
        aktif=alasan is not None,
        harga_prediksi=hasil.harga_prediksi,
        persen_perubahan=hasil.persen_perubahan,
        ambang_persen=ambang_persen,
        ambang_harga_tetap=ambang_harga,
        alasan=alasan,
    )
