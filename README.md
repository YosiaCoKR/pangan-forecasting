# Prediksi Pangan Jogja

Aplikasi skripsi untuk memantau dan memprediksi harga 9 komoditas pangan di Provinsi DIY (6 jenis beras, bawang merah, cabai rawit hijau, cabai rawit merah). Prediksi 1, 7, dan 30 hari dibuat oleh model **LightGBM yang hyperparameter-nya dioptimasi dengan Genetic Algorithm (GA-LightGBM)**, dilatih di notebook riset lalu dimuat oleh aplikasi Streamlit tanpa pelatihan ulang.

## Fitur

### Publik

- **Dashboard**: harga terkini 9 komoditas per kategori, tren dibanding kemarin, dan ringkasan jumlah komoditas yang naik, turun, atau tetap. Prediksi 1/7/30 hari bisa langsung dihitung dari kartu tiap komoditas.
- **Detail komoditas**: grafik harga 90 hari plus lintasan prediksi harian sampai H+1, H+7, atau H+30.
- **Data historis**: tren harga 30/60/90 hari ke belakang.
- **Aktual vs Prediksi**: perbandingan harga aktual dengan tiga lintasan prediksi untuk semua komoditas.
- **Peringatan dini (EWS)**: banner dan pop-up bila prediksi H+30 melewati ambang komoditas tersebut (default kenaikan ≥ 10%, atau harga tetap yang diatur admin).
- Tampilan mengikuti mode terang/gelap perangkat pengguna, termasuk grafik.

### Admin

- Login dengan username dan kata sandi dari environment variable (tanpa tabel akun).
- Input harga terbaru; tersimpan ke `data/harga_historis.pkl` dan cache prediksi komoditas itu langsung dihitung ulang.
- Pengaturan ambang EWS per komoditas (persen kenaikan atau harga tetap).
- Pengaturan model aktif. **Catatan:** daftar model di halaman ini masih data tiruan (`data/mock_models.py`); prediksi selalu memakai model di `webapp/research/final_model/`.
- Audit log: login/logout dan setiap perubahan data admin dicatat ke SQLite (`tracking.db`).

## Struktur repository

```text
pangan-forecasting/
├── README.md
├── venv/                              # virtual environment lokal (tidak di-commit)
└── webapp/
    ├── research/
    │   ├── code_run_all.ipynb         # pipeline lengkap: EDA, GA, evaluasi, simpan model
    │   ├── code_run_training.ipynb    # memuat hasil GA (forecast_ga/) yang sudah ada
    │   ├── DATASET-BERAS.csv          # harga harian 9 komoditas (ribuan rupiah)
    │   ├── requirements.txt           # dependency notebook
    │   ├── forecast_ga/               # forecaster hasil GA (27 file .joblib)
    │   ├── final_model/               # 27 model final yang DIMUAT APLIKASI
    │   └── models/                    # hyperparameter GA (+ artefak MSTL lama, tidak dipakai lagi)
    └── streamlit_app/
        ├── app.py                     # entry point & navigasi
        ├── forecast.py                # muat model final + hitung prediksi
        ├── ews.py                     # deteksi peringatan dini H+30
        ├── komponen_prediksi.py       # panel prediksi bersama (dashboard/detail/historis)
        ├── charting.py                # grafik harga Plotly (ikut tema terang/gelap)
        ├── auth.py                    # login admin & proteksi halaman
        ├── config.py                  # model aktif & ambang EWS (config.json)
        ├── db.py                      # audit log (SQLite)
        ├── formatting.py              # format rupiah, waktu, status tren
        ├── test_forecast.py           # cek cepat transformasi input model
        ├── requirements.txt
        ├── .env.example               # contoh kredensial admin
        ├── .streamlit/config.toml     # tema terang & gelap, font
        ├── assets/styles.css          # gaya kustom (token warna ikut tema)
        ├── data/
        │   ├── mock_commodities.py    # daftar 9 komoditas (nama, slug, unit, ikon)
        │   ├── mock_prices.py         # riwayat harga dari DATASET-BERAS.csv + input admin
        │   └── mock_models.py         # daftar model tiruan untuk halaman admin
        └── views/
            ├── dashboard.py
            ├── detail_komoditas.py
            ├── historis.py
            ├── perbandingan_prediksi.py
            ├── admin_login.py
            ├── admin_input_harga.py
            ├── admin_model_settings.py
            ├── admin_ambang_settings.py
            └── admin_audit_log.py
```

Meski namanya `mock_prices.py`, riwayat harga di aplikasi berasal dari dataset riset asli (`DATASET-BERAS.csv`), bukan data acak.

## Pipeline model

Satu model per komoditas × horizon, total **27 model** (9 komoditas × 3 horizon).

1. Harga harian (dalam ribuan rupiah) dirapikan: `asfreq("D")` lalu celah diisi dengan interpolasi berbasis waktu.
2. Target diubah ke skala log: `log1p(harga)`.
3. `skforecast.ForecasterDirect` dengan `differentiation=1`. Model mempelajari perubahan harian log harga. Fitur: lag 1/7/30, rolling mean/std/min/max 7 dan 30 hari, serta fitur kalender siklikal.
4. Hyperparameter LightGBM dicari dengan Genetic Algorithm (`pygad`).
5. Prediksi dikembalikan ke rupiah: `expm1(prediksi) × 1000`.

Di aplikasi, `forecast.py` mengulang langkah 1, 2, dan 5 pada 90 hari harga terakhir, lalu memanggil model di `final_model/`. Tidak ada pelatihan ulang. Hasilnya di-cache per isi riwayat, sehingga otomatis dihitung ulang saat admin memasukkan harga baru.

## Persiapan

Butuh Python 3 dan Streamlit **≥ 1.53** (tema terang/gelap terpisah dan `icon_position` di tombol).

```bash
python -m venv venv
source venv/bin/activate            # fish: source venv/bin/activate.fish
pip install -r webapp/streamlit_app/requirements.txt
```

Kredensial admin: salin `.env.example` menjadi `.env` di `webapp/streamlit_app/`, lalu isi `ADMIN_USERNAME` dan `ADMIN_PASSWORD`. Tanpa `.env`, aplikasi memakai nilai demo `admin` / `admin123`. **Ganti untuk produksi.**

## Menjalankan aplikasi

```bash
cd webapp/streamlit_app
streamlit run app.py
```

Buka URL yang ditampilkan Streamlit (biasanya `http://localhost:8501`). Halaman admin ada di menu **Admin → Panel Admin**.

Cek cepat transformasi input model:

```bash
cd webapp/streamlit_app
python test_forecast.py              # mencetak "ok"
```

## Melatih ulang model

```bash
pip install -r webapp/research/requirements.txt
cd webapp/research
jupyter notebook code_run_all.ipynb
```

Pilih **Kernel → Restart Kernel and Run All Cells**, jangan menjalankan sel satu per satu. Sel penyimpanan (bagian 34) menyimpan isi variabel `forecasters_ga` yang ada di memori kernel. Kalau sel pelatihan GA (bagian 21 sampai 24) tidak ikut dijalankan, yang tersimpan adalah model dari sesi sebelumnya. Proses GA untuk 27 model memakan waktu cukup lama.

Setelah selesai, pastikan file di `final_model/` bertanggal hari ini, lalu restart Streamlit:

```bash
ls -la webapp/research/final_model | head
```

### Pengaman artefak lama

`forecast.py` menolak model yang data latihnya tidak berada di skala `log1p` harga, misalnya model lama yang dilatih pada residual MSTL. Komoditas dengan model seperti itu menampilkan **"Prediksi belum tersedia"**, bukan angka yang salah. Kalau kartu suatu komoditas terus menampilkan pesan ini, latih ulang model dengan langkah di atas.

## Teknologi

Python, Streamlit, Pandas, Plotly, skforecast, LightGBM, pygad (Genetic Algorithm), scikit-learn, SQLite, python-dotenv, Jupyter Notebook.
