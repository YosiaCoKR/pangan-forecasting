# Alur Data — Prediksi Pangan Jogja

Dokumen ini menjelaskan **ke mana data mengalir** dan **berkas mana yang
bertanggung jawab**, untuk dua alur utama:

1. [Admin memasukkan harga baru](#alur-1--admin-memasukkan-harga-baru)
2. [Pengguna menekan tombol Prediksi](#alur-2--pengguna-menekan-tombol-prediksi)

Semua jalur di bawah sudah diverifikasi langsung dari kode, bukan perkiraan.

---

## Peta Berkas

```
webapp/
├── research/                          # Hasil riset — read-only bagi aplikasi
│   ├── DATASET-BERAS-NEW.csv          # Dataset yang dipakai melatih model
│   ├── final_lgbm/*.joblib            # Artefak LightGBM (9 komoditas × 3 horizon)
│   └── final_xgb/*.joblib             # Artefak XGBoost (pembanding)
│
└── streamlit_app/
    ├── app.py                         # Entry point + daftar halaman
    │
    ├── views/                         # Satu berkas = satu halaman
    │   ├── dashboard.py               # Kartu 9 komoditas + panel prediksi
    │   ├── detail_komoditas.py        # Grafik + garis ramalan + banner EWS
    │   ├── historis.py                # Grafik tren 30/60/90 hari
    │   ├── admin_input_harga.py       # FORM INPUT HARGA  ← alur 1 mulai di sini
    │   ├── admin_model_settings.py    # Pilih model aktif
    │   ├── admin_ambang_settings.py   # Atur ambang EWS
    │   └── admin_audit_log.py         # Tampilkan log aktivitas
    │
    ├── komponen_prediksi.py           # Tombol & panel Prediksi (dipakai 3 halaman)
    ├── forecast.py                    # MESIN PREDIKSI     ← alur 2 inti
    ├── ews.py                         # Peringatan Dini (selalu horizon 30 hari)
    ├── charting.py                    # Grafik Plotly
    ├── auth.py                        # Login & sesi admin
    ├── config.py                      # Baca/tulis config.json
    ├── db.py                          # Audit log (SQLite)
    │
    ├── data/
    │   ├── mock_commodities.py        # Daftar komoditas (dari kolom CSV)
    │   ├── mock_prices.py             # PENYIMPANAN HARGA  ← alur 1 inti
    │   └── harga_historis.pkl         # Harga hasil input admin (persisten)
    │
    ├── config.json                    # Model aktif + ambang EWS
    └── tracking.db                    # Audit log admin
```

---

## Alur 1 — Admin Memasukkan Harga Baru

### Gambaran singkat

```
Form admin  →  validasi  →  RAM  →  .pkl  →  GitHub  →  audit log
```

### Langkah demi langkah

**① Admin mengisi form**
`views/admin_input_harga.py`

Satu `st.number_input` per komoditas, masing-masing ber-key `harga-<slug>`.
Daftar komoditasnya **tidak di-hardcode** — diambil dari
`data.mock_commodities.get_komoditas_list()`, yang isinya kolom
`DATASET-BERAS-NEW.csv`. Ganti dataset, form ini ikut berubah sendiri.

**② Validasi di halaman**
`views/admin_input_harga.py`

| Kondisi | Yang terjadi |
|---|---|
| Semua kolom kosong | `"Belum ada harga yang diisi."` — tidak ada yang disimpan |
| Ada nilai ≤ 0 | `"Harga harus lebih besar dari 0"` — seluruh form ditolak |
| Ada nilai valid | Lanjut ke langkah ③ |

Kolom yang dibiarkan kosong **tidak diubah** — hanya yang diisi yang tersimpan.

**③ Menulis ke memori**
`data/mock_prices.py` → `simpan_harga_batch(tanggal, harga_per_slug)`

- Kalau tanggal itu **sudah ada** di riwayat → baris itu **diperbarui**
- Kalau **belum ada** → baris baru **ditambahkan**, lalu diurutkan per tanggal
- Hasilnya disimpan di `_cache_riwayat[slug]`, sebuah `DataFrame` di memori

**④ Menulis ke berkas**
`data/mock_prices.py` → `_simpan_riwayat_ke_pkl()`

Ditulis **atomik**: isi dituangkan ke `harga_historis.pkl.tmp` dulu, baru
di-*rename* menjadi `harga_historis.pkl`. Tujuannya supaya berkas tidak pernah
berada dalam keadaan separuh tertulis kalau proses mati di tengah jalan.

Penulisan dilakukan **sekali di akhir** untuk seluruh form, bukan per
komoditas — menyimpan 9 kolom tetap satu operasi tulis.

**⑤ Menyalin ke GitHub**
`data/mock_prices.py` → `sinkronkan_ke_github()`

Ini yang membuat harga **bertahan melewati restart hosting**. Filesystem
Streamlit Community Cloud bersifat sementara: `.pkl` lokal terhapus setiap
container dibuat ulang. Dengan meng-commit berkas itu ke repo lewat GitHub
Contents API, harga ikut **ter-clone** saat container baru dibuat.

> Tidak ada kode "download". Clone repo-nya sendiri yang membawa berkas itu
> masuk — itulah kenapa pendekatan ini sederhana.

Aktif hanya kalau Secrets berisi section `[github]`:

```toml
[github]
token  = "github_pat_..."              # izin: Contents = Read and write
repo   = "YosiaCoKR/pangan-forecasting"
branch = "main"
```

Tiga kemungkinan hasilnya, dan masing-masing ditampilkan berbeda di layar:

| Keadaan | Yang admin lihat |
|---|---|
| Berhasil commit | Caption *"Disalin juga ke repo…"* |
| Gagal (token salah, jaringan mati) | ⚠️ Warning berisi alasan konkretnya |
| Secrets belum diisi | ⚠️ Warning bahwa harga akan hilang saat restart |

> Membedakan ketiganya penting: dua keadaan terakhir sama-sama berarti
> "harga belum aman", dan admin harus tahu itu — bukan dibiarkan mengira
> datanya sudah tersalin permanen.

**⑥ Mencatat ke audit log**
`db.py` → `catat_aktivitas_admin("harga_diperbarui", sesi, detail)` → `tracking.db`

Yang dicatat: waktu, jenis aksi, penanda sesi, dan **detail apa yang berubah**
(mis. `"05 Nov 2026 — Cabai Rawit Merah: Rp 48.000"`).

### Saat aplikasi dinyalakan ulang

`data/mock_prices.py` menjalankan `_muat_riwayat_dari_pkl()` saat modul
di-*import*:

```
harga_historis.pkl ada?
├── Ya  → dimuat ke _cache_riwayat          (harga hasil input admin)
└── Tidak/korup → _cache_riwayat dikosongkan
                  → riwayat jatuh ke DATASET-BERAS-NEW.csv  (data riset asli)
```

Berkas `.pkl` yang rusak **tidak membuat aplikasi gagal start** — ia hanya
kembali ke dataset riset.

---

## Alur 2 — Pengguna Menekan Tombol Prediksi

### Gambaran singkat

```
Klik Prediksi  →  ambil riwayat  →  pilih model  →  muat artefak .joblib
               →  susun last_window  →  predict()  →  balik ke Rupiah  →  tampil
```

### Langkah demi langkah

**① Pengguna memilih rentang lalu menekan Prediksi**
`komponen_prediksi.py` → `panel_prediksi(key_prefix, riwayat, nama_komoditas)`

Komponen yang sama dipakai di **tiga halaman**: Dashboard, Detail Komoditas,
dan Data Historis. Rentang yang dipilih disimpan di
`st.session_state["prediksi-aktif-<key_prefix>"]`.

**② Riwayat harga diambil**
`data/mock_prices.py` → `get_price_history(slug, hari=90)`

90 hari terakhir, kolom `tanggal` dan `harga` (Rupiah asli).

**③ Menentukan model yang dipakai**
`forecast.py` → `model_aktif(nama_komoditas)` → membaca `config.json`

Urutan prioritasnya:

```
override khusus komoditas ini  →  model default global  →  LightGBM
```

Jadi Beras Kualitas Bawah I bisa memakai XGBoost sementara komoditas lain
tetap LightGBM.

**④ Memuat artefak model**
`forecast.py` → `muat_forecaster(nama_komoditas, horizon, kunci_model)`

Berkas yang dibaca:

```
research/final_lgbm/final_lgbm_<nama komoditas>_h<horizon>.joblib
research/final_xgb/final_xgb_<nama komoditas>_h<horizon>.joblib
```

Satu artefak untuk tiap **model × komoditas × horizon** — total 54 berkas.
Di-cache dengan `@lru_cache(maxsize=12)` supaya tidak dibaca ulang dari disk
setiap kali, tapi tetap terbatas agar pemakaian memori tidak membengkak.

**Model TIDAK pernah dilatih ulang di aplikasi.** Yang terjadi hanya memuat
artefak hasil notebook riset lalu memanggil `predict()`.

**⑤ Menyusun `last_window`**
`forecast.py` → `susun_last_window(riwayat, window_size)`

Ini bagian yang paling mudah salah dipahami, jadi perlu dijelaskan:

```
harga Rupiah  →  asfreq("D") + interpolasi waktu  →  bagi 1000  →  log1p()
   13.750              isi tanggal bolong            13,75       2,693...
```

Tiga hal yang terjadi:

1. **`asfreq("D")` + interpolasi** — indeks harian dirapatkan supaya tidak ada
   tanggal bolong, karena fitur kalender model dihitung dari indeks ini.
   Pra-prosesnya **sama persis** dengan notebook riset.
2. **Dibagi 1000** — model dilatih pada harga dalam **ribuan rupiah**
   (`13.25` di CSV = Rp 13.250). Konstantanya `forecast.SKALA_HARGA`.
3. **`log1p()`** — target model adalah log harga.

Kalau riwayatnya lebih pendek dari `window_size` yang dibutuhkan forecaster,
dilempar `ModelRisetError` dan halaman menampilkan placeholder rapi — tidak
error.

**⑥ Memprediksi**
`forecast.py` → `ramalkan_harga(...)`

```python
pred_log     = forecaster.predict(steps=horizon, last_window=last_window)
harga_rupiah = np.expm1(pred_log) * 1000     # kebalikan dari langkah ⑤
```

*Differencing* orde 1 dilakukan **di dalam** `ForecasterDirect` skforecast
(`differentiation=1`), jadi hasil `predict()` sudah kembali ke level log harga
dan cukup dibalik dengan `expm1`.

**⑦ Merangkum hasil**
`forecast.py` → `ramalkan_hasil_horizon(...)` → objek `HasilPeramalan`

| Field | Isi |
|---|---|
| `harga_sekarang` | Harga aktual terakhir dari riwayat |
| `harga_prediksi` | Titik H+horizon dari lintasan |
| `persen_perubahan` | Selisih terhadap harga sekarang |
| `model_dipakai` | "LightGBM" / "XGBoost" |
| `trajektori` | Harga harian H+1…H+horizon (untuk grafik & tabel rincian) |

**⑧ Ditampilkan**

- `komponen_prediksi.py` → metrik, persentase, nama model, tabel rincian harian
- `charting.py` → `gambar_grafik_harga()` menggambar riwayat + garis ramalan
- `ews.py` → `periksa_peringatan()` membandingkan ramalan **H+30** dengan
  ambang di `config.json`; kalau terlampaui, muncul banner + pop-up

---

## Titik Temu Dua Alur

Ini konsep terpenting di seluruh sistem, dan paling mungkin ditanyakan:

> **Begitu admin menyimpan harga baru, prediksi otomatis ikut berubah —
> tanpa satu baris pun kode invalidasi cache.**

Caranya: `forecast.ramalkan_harga` dibungkus `@st.cache_data`, dan kunci
cache-nya dihitung dari **ISI** `riwayat` — bukan sekadar nama komoditas.

```
Admin simpan harga baru
      ↓
_cache_riwayat[slug] berubah isinya
      ↓
get_price_history() mengembalikan DataFrame yang berbeda
      ↓
kunci st.cache_data otomatis berbeda
      ↓
prediksi dihitung ulang  ✅
```

Kalau kuncinya hanya `(nama_komoditas, horizon)`, harga baru akan tersimpan
tapi prediksinya tetap memakai hasil lama — dan tidak ada yang menyadarinya.

Alasan serupa berlaku untuk `kunci_model`: parameter itu **sengaja wajib
diisi** di `ramalkan_harga`, bukan dibaca dari config di dalam fungsinya.
Kalau dibaca di dalam, mengganti model aktif tidak akan mengubah kunci cache,
sehingga prediksi model lama akan dikembalikan.

---

## Berkas yang Berubah Saat Aplikasi Dipakai

| Berkas | Diubah oleh | Bertahan setelah restart? |
|---|---|---|
| `data/harga_historis.pkl` | Input Harga Terbaru | ✅ ya — disalin ke repo |
| `config.json` | Pengaturan Model & Ambang | ❌ tidak — belum disinkronkan |
| `tracking.db` | Semua aksi admin | ❌ tidak |

> `config.json` dan `tracking.db` belum punya mekanisme seperti `.pkl`.
> Artinya pilihan model dan ambang EWS kembali ke default setiap aplikasi
> restart. Kalau itu perlu bertahan juga, polanya sudah ada di
> `sinkronkan_ke_github()` dan tinggal diterapkan ke dua berkas itu.

---

## Yang TIDAK Dilakukan Aplikasi

Penting untuk membatasi klaim saat presentasi:

- **Tidak melatih ulang model.** Pelatihan hanya di notebook riset
  (`code_run_all_new.ipynb`); aplikasi hanya memuat `.joblib` dan memanggil
  `predict()`.
- **Tidak menyimpan harga di database.** `tracking.db` hanya berisi audit log.
  Harga ada di `.pkl`, komoditas berasal dari kolom CSV.
- **Tidak ada tabel pengguna.** Kredensial admin dibaca dari environment
  variable; tidak ada pendaftaran akun.
- **Tidak menyimpan sesi di URL atau cookie.** Konsekuensinya reload = login
  ulang — disengaja, agar URL tidak setara kata sandi.
