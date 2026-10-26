"""Halaman admin — Pengaturan Model.

Dua tingkat pilihan, keduanya tersimpan di `config.json`:

1. **Model default global** — dipakai komoditas yang tidak disetel khusus.
2. **Model per komoditas** — override opsional. Artefak riset memang satu
   per komoditas x horizon (`final_lgbm_<nama>_h<h>.joblib`), jadi mis. Beras
   Kualitas Bawah I boleh pakai XGBoost sementara Beras Medium I tetap
   LightGBM.

Aplikasi tidak melatih atau mengubah parameter model apa pun — hanya memilih
artefak mana yang dimuat. Pilihan di sini dibaca `forecast.model_aktif(nama)`,
jadi seluruh halaman publik (Dashboard, Detail Komoditas, EWS) langsung ikut.

Daftar komoditas di tabel diturunkan dari kolom `DATASET-BERAS.csv` lewat
`data.mock_commodities` — dataset baru + notebook dijalankan ulang berarti
baris tabel ini ikut berubah sendiri.
"""

from __future__ import annotations

import forecast
import pandas as pd
import streamlit as st
from auth import require_admin, sesi_admin_saat_ini, tombol_logout
from config import get_model_per_komoditas, set_model_aktif, set_model_komoditas
from data.mock_commodities import get_komoditas_list
from db import catat_aktivitas_admin

require_admin()

st.markdown(
    """
    <div class="ppj-hero">
        <h1>Pengaturan Model</h1>
        <p>Pilih model default, atau setel model berbeda untuk tiap komoditas.</p>
    </div>
    """,
    unsafe_allow_html=True,
)

LABEL_IKUT_DEFAULT = "— Ikut default global —"

kunci_model_list = list(forecast.MODEL_TERSEDIA)
# Label tabel pakai `nama` model; peta balik dibutuhkan karena `data_editor`
# mengembalikan label yang dipilih, bukan kuncinya.
label_per_kunci = {kunci: info.nama for kunci, info in forecast.MODEL_TERSEDIA.items()}
kunci_per_label = {nama: kunci for kunci, nama in label_per_kunci.items()}

# Slot diisi di akhir skrip supaya kartu ringkasan selalu menampilkan nilai
# terbaru walau baru saja diubah lewat form di bawahnya.
slot_model_aktif = st.container()

st.markdown("#### Model Default Global")
_, kolom_form, _ = st.columns([1, 1.6, 1])
with kolom_form:
    with st.container(border=True):
        model_aktif_sekarang = forecast.model_aktif().kunci
        kunci_terpilih = st.selectbox(
            "Pilih model default",
            options=kunci_model_list,
            index=kunci_model_list.index(model_aktif_sekarang),
            format_func=lambda kunci: forecast.MODEL_TERSEDIA[kunci].nama,
        )
        model_terpilih = forecast.MODEL_TERSEDIA[kunci_terpilih]
        st.caption(
            f"{model_terpilih.deskripsi} · artefak di `research/{model_terpilih.folder}/`"
        )

        # Slot juga, supaya peringatan "belum disimpan" langsung hilang di run
        # yang sama begitu tombol Simpan ditekan (bukan baru di rerun berikutnya).
        slot_peringatan = st.container()

        if st.button("Simpan Model Default", width="stretch"):
            if kunci_terpilih == model_aktif_sekarang:
                st.info("Model ini sudah jadi default.")
            else:
                set_model_aktif(kunci_terpilih)
                catat_aktivitas_admin(
                    "model_diubah",
                    sesi_admin_saat_ini(),
                    detail=f"default global: {model_aktif_sekarang} -> {kunci_terpilih}",
                )
                # Prediksi lama masih tersimpan di `st.cache_data` dengan kunci
                # model LAMA, jadi cukup dibiarkan — kunjungan berikutnya memakai
                # `kunci_model` baru dan otomatis menghitung ulang.
                st.success(f"Model default diubah ke **{model_terpilih.nama}**.")

        model_aktif_terkini = forecast.model_aktif().kunci
        if kunci_terpilih != model_aktif_terkini:
            with slot_peringatan:
                st.warning(
                    "⚠️ Perubahan belum disimpan. Klik **Simpan Model Default** untuk menerapkan."
                )

st.markdown("#### Model per Komoditas")
komoditas_list = get_komoditas_list()
override_tersimpan = get_model_per_komoditas()
nama_default_terkini = forecast.model_aktif().nama

with st.container(border=True):
    st.caption(
        f"Komoditas yang dibiarkan *{LABEL_IKUT_DEFAULT}* memakai "
        f"**{nama_default_terkini}**. Ubah kolom **Model**, lalu klik Simpan."
    )

    tabel_awal = pd.DataFrame(
        {
            "Komoditas": [f"{k.ikon} {k.nama}" for k in komoditas_list],
            "Model": [
                label_per_kunci.get(override_tersimpan.get(k.nama), LABEL_IKUT_DEFAULT)
                for k in komoditas_list
            ],
        }
    )

    tabel_diedit = st.data_editor(
        tabel_awal,
        hide_index=True,
        width="stretch",
        disabled=["Komoditas"],
        column_config={
            "Komoditas": st.column_config.TextColumn("Komoditas", width="medium"),
            "Model": st.column_config.SelectboxColumn(
                "Model",
                options=[LABEL_IKUT_DEFAULT, *label_per_kunci.values()],
                required=True,
                width="large",
            ),
        },
        key="tabel-model-komoditas",
    )

    if st.button("Simpan Model per Komoditas", width="stretch"):
        perubahan: list[str] = []
        for komoditas, label_baru in zip(komoditas_list, tabel_diedit["Model"]):
            kunci_baru = kunci_per_label.get(label_baru)  # None = ikut default
            kunci_lama = override_tersimpan.get(komoditas.nama)
            if kunci_baru != kunci_lama:
                set_model_komoditas(komoditas.nama, kunci_baru)
                perubahan.append(
                    f"{komoditas.nama}: {kunci_lama or 'default'} -> {kunci_baru or 'default'}"
                )

        if not perubahan:
            st.info("Tidak ada perubahan untuk disimpan.")
        else:
            catat_aktivitas_admin(
                "model_diubah",
                sesi_admin_saat_ini(),
                detail="; ".join(perubahan),
            )
            st.success(f"{len(perubahan)} komoditas diperbarui.")
            st.rerun()

with slot_model_aktif:
    st.markdown("#### Ringkasan Model Terpakai")
    info_default = forecast.model_aktif()
    with st.container(border=True):
        st.markdown(f"**Default global: {info_default.nama}**")
        st.caption(
            f"{info_default.deskripsi} · artefak di `research/{info_default.folder}/`"
        )

        khusus = get_model_per_komoditas()
        if khusus:
            st.markdown("Komoditas dengan model khusus:")
            for nama_komoditas, kunci in khusus.items():
                nama_model = label_per_kunci.get(kunci, kunci)
                st.markdown(f"- {nama_komoditas} → **{nama_model}**")
        else:
            st.caption("Semua komoditas memakai model default.")

tombol_logout()
