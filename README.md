# Prediksi Pangan Jogja

> Dashboard Streamlit untuk memantau dan memprediksi harga 9 komoditas pangan di Daerah Istimewa Yogyakarta (H+1, H+7, H+30).

![Python](https://img.shields.io/badge/python-3.14-blue) ![Streamlit](https://img.shields.io/badge/Streamlit-1.64.0-blue) ![LightGBM](https://img.shields.io/badge/LightGBM-4.7.0-blue) ![XGBoost](https://img.shields.io/badge/XGBoost-3.4.1-blue) ![skforecast](https://img.shields.io/badge/skforecast-0.25.0-blue) ![Docker](https://img.shields.io/badge/Docker-ready-2496ED) ![CI](https://github.com/YosiaCoKR/pangan-forecasting/actions/workflows/main.yml/badge.svg)

## Description

Harga beras, bawang merah, dan cabai rawit bisa naik tajam dalam hitungan hari. Repo ini berisi dua bagian:

1. **Riset** (`webapp/research/`): notebook untuk EDA, feature engineering, tuning hyperparameter dengan Genetic Algorithm, evaluasi walk-forward, dan penyimpanan model final LightGBM & XGBoost.
2. **Aplikasi** (`webapp/streamlit_app/`): dashboard publik yang memuat model final itu (tanpa melatih ulang), menampilkan prediksi, dan memberi peringatan dini (EWS) bila harga diprediksi melewati ambang. Ada panel admin untuk input harga, unggah dataset, memilih model, dan mengatur ambang.

## Table of Contents

- [Features](#features)
- [Tech Stack](#tech-stack)
- [Prerequisites](#prerequisites)
- [Installation (lokal)](#installation-lokal)
- [Configuration](#configuration)
- [Usage](#usage)
- [Docker](#docker)
- [Dataset](#dataset)
- [Model & Methodology](#model--methodology)
- [Results](#results)
- [Project Structure](#project-structure)
- [Testing](#testing)
- [Development Tools](#development-tools)
- [Troubleshooting](#troubleshooting)

## Features

**Halaman publik**

- **Dashboard Pangan**: harga terkini, perubahan harian, dan status peringatan dini untuk 9 komoditas.
- **Detail komoditas**: grafik harga historis plus lintasan prediksi H+1, H+7, dan H+30.
- **Data Historis**: riwayat harga per komoditas dengan rentang tanggal yang bisa dipilih.
- **Performa Model**: MAE, RMSE, MAPE, dan akurasi hasil backtesting walk-forward per komoditas × horizon.
- **Dokumentasi**: panduan pemakaian di dalam aplikasi.

**Panel admin** (login dengan `ADMIN_USERNAME` / `ADMIN_PASSWORD`)

- **Input Harga Terbaru**: input harga harian, yang langsung dipakai untuk prediksi berikutnya.
- **Unggah Dataset**: unggah `.csv` / `.xlsx`. Tanggal baru ditambahkan, tanggal yang sudah ada ditimpa.
- **Pengaturan Model**: pilih LightGBM atau XGBoost sebagai model default global, dengan override per komoditas.
- **Evaluasi Model**: bandingkan metrik kedua model.
- **Pengaturan Ambang**: atur ambang EWS per komoditas, berupa persentase kenaikan (default 10%) dan/atau harga tetap.
- **Audit Log**: catatan login, logout, dan aktivitas admin, disimpan di SQLite.

**Detail teknis**

- Sesi admin dikelola server: gugur setelah 15 menit idle, maksimal 8 jam. Id sesi tidak pernah masuk URL.
- Kalau sinkronisasi GitHub diaktifkan, harga yang diinput admin di-commit ke repo lewat GitHub Contents API, supaya tidak hilang saat container Streamlit Cloud di-restart.

## Tech Stack

| Category | Technology |
|---|---|
| Language | Python 3.14 |
| Web app | Streamlit 1.64.0, Plotly 7.1.0 |
| Data | pandas 2.3.3, NumPy 2.5.3, openpyxl 3.1.5 |
| Forecasting | skforecast 0.25.0 (`ForecasterDirect`), LightGBM 4.7.0, XGBoost 3.4.1, scikit-learn 1.9.1 |
| Tuning (riset) | pygad (Genetic Algorithm), statsmodels, feature_engine |
| Storage | SQLite (audit log), JSON (konfigurasi admin), pickle (riwayat harga) |
| DevOps | Docker, Dev Container / Codespaces, GitHub Actions, ruff, pre-commit |

## Prerequisites

- **Python 3.14.** Versi ini wajib: kode memakai sintaks `except A, B` (PEP 758) yang baru ada di 3.14, dan model dilatih dengan versi library yang di-pin di `requirements.txt`.
- Git.
- Docker (opsional, untuk menjalankan lewat container).

## Installation (lokal)

1. Clone repository

   ```bash
   git clone https://github.com/YosiaCoKR/pangan-forecasting.git
   cd pangan-forecasting
   ```

2. Buat virtual environment dan install dependencies

   ```bash
   python3.14 -m venv .venv
   source .venv/bin/activate        # Windows: .venv\Scripts\activate
   pip install -r requirements.txt
   ```

3. Siapkan kredensial admin

   ```bash
   cp webapp/streamlit_app/.env.example webapp/streamlit_app/.env
   # lalu edit ADMIN_USERNAME dan ADMIN_PASSWORD di file .env
   ```

> [!NOTE]
> Di Linux, LightGBM butuh library OpenMP sistem (`libgomp1` di Debian/Ubuntu). Biasanya sudah terpasang; kalau muncul error `libgomp.so.1`, jalankan `sudo apt install libgomp1`.

## Configuration

### Environment variables

| Variable | Description | Default |
|---|---|---|
| `ADMIN_USERNAME` | Username untuk membuka Panel Admin | kosong (login admin selalu gagal) |
| `ADMIN_PASSWORD` | Kata sandi Panel Admin | kosong (login admin selalu gagal) |

Tidak ada kredensial default. Kalau kedua variabel belum diisi, halaman publik tetap jalan, tapi panel admin tidak bisa dibuka.

Sumbernya, sesuai cara menjalankan:

- **Lokal**: `webapp/streamlit_app/.env` (dibaca `python-dotenv`).
- **Docker**: `--env-file` atau `-e` saat `docker run` (lihat [Docker](#docker)).
- **Streamlit Community Cloud**: _Manage app → Settings → Secrets_, sebagai kunci **level atas** (lihat `.streamlit/secrets.toml.example`).

### Sinkronisasi harga ke GitHub (opsional)

Supaya harga yang diinput admin tetap ada setelah redeploy, tambahkan bagian berikut di `webapp/streamlit_app/.streamlit/secrets.toml` (atau Secrets di Streamlit Cloud):

```toml
[github]
token = "<github-fine-grained-token>"   # scope: Contents read & write
repo = "<akun>/pangan-forecasting"
branch = "main"                          # opsional
```

Kalau bagian ini tidak ada, sinkronisasi nonaktif dan harga hanya disimpan di `data/harga_historis.pkl` lokal.

### File yang ditulis aplikasi saat runtime

Semuanya ada di `webapp/streamlit_app/` dan sudah masuk `.gitignore`, kecuali `harga_historis.pkl`:

| File | Isi |
|---|---|
| `config.json` | model aktif, override model per komoditas, ambang EWS |
| `tracking.db` | audit log admin (SQLite) |
| `data/harga_historis.pkl` | harga yang diinput atau diunggah admin (sengaja di-commit, untuk sinkronisasi) |

## Usage

Jalankan dari folder app, supaya tema di `.streamlit/config.toml` ikut terbaca:

```bash
cd webapp/streamlit_app
streamlit run app.py
```

Lalu buka <http://localhost:8501>.

### Format unggah dataset (admin)

Buka **Panel Admin → Unggah Dataset**, lalu unggah `.csv` atau `.xlsx` (sheet pertama) dengan format seperti `webapp/research/dataset.csv`:

- Kolom `tanggal` berformat `YYYY-MM-DD` (atau sel bertipe tanggal di Excel), tidak boleh di masa depan.
- Satu kolom per komoditas, dengan nama yang persis sama seperti di dataset. Kolom lain diabaikan.
- Harga boleh dalam ribuan rupiah (`10.400`) atau rupiah penuh (`10400`). Nilai di bawah 1000 dianggap ribuan.
- Sel kosong dilewati. Kalau ada tanggal yang salah format atau harga yang bukan angka / ≤ 0, seluruh berkas ditolak.

Tabel unduhan "Tabel Harga Berdasarkan Daerah" (format lebar: satu baris per komoditas, kolom tanggal `DD/ MM/ YYYY`, harga ditulis `16,450`) juga bisa langsung diunggah. Komoditas di luar dataset diabaikan. Setiap unggahan tercatat di **Audit Log**.

### Menjalankan notebook riset

Dependency notebook ada di file terpisah:

```bash
pip install -r webapp/research/requirements.txt jupyter
jupyter lab webapp/research/
```

> [!WARNING]
> `webapp/research/requirements.txt` tidak di-pin. Kalau kamu melatih ulang lalu menimpa artefak di `final_lgbm/` / `final_xgb/`, pastikan versi scikit-learn, LightGBM, XGBoost, skforecast, dan NumPy sama dengan `requirements.txt` di root. Kalau tidak, aplikasi bisa memuat model tapi memberi angka yang berbeda tanpa error.

## Docker

Image berbasis `python:3.14-slim`, jalan sebagai user non-root `app`, dan expose port `8501`. `.dockerignore` memakai pola allowlist: yang masuk ke image hanya `requirements.txt`, `webapp/streamlit_app/`, model `final_lgbm/` & `final_xgb/`, dan `dataset.csv`. File `.env`, `secrets.toml`, `tracking.db`, `config.json`, dan file test tidak ikut.

### 1. Build image

Dari root repo:

```bash
docker build -t pangan-forecasting .
```

### 2. Jalankan container

```bash
docker run -d --name pangan-forecasting \
  -p 8501:8501 \
  --env-file webapp/streamlit_app/.env \
  pangan-forecasting
```

Buka <http://localhost:8501>. File `.env` tidak ikut ke image, jadi kredensial admin dikirim lewat `--env-file`. Alternatifnya pakai `-e ADMIN_USERNAME=... -e ADMIN_PASSWORD=...`.

Untuk mengaktifkan [sinkronisasi GitHub](#sinkronisasi-harga-ke-github-opsional), mount `secrets.toml` secara read-only:

```bash
docker run -d --name pangan-forecasting \
  -p 8501:8501 \
  --env-file webapp/streamlit_app/.env \
  -v "$PWD/webapp/streamlit_app/.streamlit/secrets.toml:/app/webapp/streamlit_app/.streamlit/secrets.toml:ro" \
  pangan-forecasting
```

### 3. Perintah sehari-hari

```bash
docker logs -f pangan-forecasting     # lihat log
docker stop pangan-forecasting        # hentikan
docker start pangan-forecasting       # jalankan lagi (data tetap ada)
docker rm -f pangan-forecasting       # hapus container (data ikut hilang)
```

> [!IMPORTANT]
> `config.json`, `tracking.db`, dan `harga_historis.pkl` ditulis di dalam container. Semuanya tetap ada selama `stop` / `start`, tapi hilang saat container dihapus (`docker rm`) atau dibuat ulang setelah rebuild image. Aktifkan sinkronisasi GitHub kalau input harga admin harus tetap tersimpan.

### Dev Container / Codespaces

`.devcontainer/devcontainer.json` memakai image `python:3-3.14-bookworm`, menginstall `requirements.txt`, lalu otomatis menjalankan Streamlit di port 8501. Buka repo di VS Code dengan **Dev Containers: Reopen in Container**, atau buat Codespace dari GitHub.

## Dataset

- **Berkas utama**: `webapp/research/dataset.csv`, data harian dari **4 Jan 2021 sampai 3 Agu 2026** (±2.000 baris), dipakai untuk melatih model dan sebagai riwayat harga di aplikasi.
- **Satuan**: ribuan rupiah per kg (`10.400` = Rp10.400). Aplikasi mengonversinya ke rupiah penuh.
- **Komoditas (9)**: Beras Kualitas Bawah I & II, Beras Kualitas Medium I & II, Beras Kualitas Super I & II, Bawang Merah Ukuran Sedang, Cabai Rawit Hijau, Cabai Rawit Merah.
- **Pra-proses**: `asfreq("D")` lalu interpolasi berbasis waktu untuk mengisi tanggal yang bolong, sama di notebook dan di aplikasi.
- `data_aktual.csv` → `data_aktual_cleaned.csv`: data aktual terbaru yang diinterpolasi linear di `intepolate.ipynb`, dipakai untuk membandingkan prediksi dengan harga aktual.

<!-- TODO: tambahkan sumber resmi dataset (mis. nama instansi / portal) dan lisensinya. -->

## Model & Methodology

Pipeline lengkapnya ada di `webapp/research/code.ipynb`:

1. **EDA**: missing value, distribusi & outlier, korelasi, uji stasioneritas ADF.
2. **Transformasi**: target `log1p(harga)`, dengan differencing orde 1 di dalam `ForecasterDirect` (`differentiation=1`).
3. **Feature engineering**, lalu satu forecaster per **komoditas × horizon** (1, 7, 30 hari), jadi 27 model per algoritma.
4. **Baseline** (parameter default) vs **tuning hyperparameter dengan Genetic Algorithm** (pygad).
   - LightGBM: objective `regression_l1`
   - XGBoost (pembanding): objective `reg:absoluteerror`, dengan protokol tuning yang sama
5. **Evaluasi**: tes sekali jalan pada data test, plus **backtesting walk-forward** (252 observasi per komoditas × horizon, refit tiap fold).
6. **Simpan model final** ke `final_lgbm/`, `final_xgb/`, `final_lgbm_default/`, dan `final_xgb_default/` (`.joblib`), dengan hyperparameter terbaik di `params/`.

Notebook pendukung:

| Notebook | Fungsi |
|---|---|
| `predict.ipynb` | prediksi geser mingguan dengan model final (tanpa retraining), plus ringkasan MAPE per model & horizon |
| `plot_prediksi.ipynb` | grafik prediksi vs harga aktual, LightGBM (GA) vs XGBoost (GA) |
| `intepolate.ipynb` | interpolasi `data_aktual.csv` menjadi `data_aktual_cleaned.csv` |

Aplikasi hanya **memuat** artefak `final_lgbm/` dan `final_xgb/` (lihat `forecast.py`), tidak melatih ulang.

## Results

MAPE hasil backtesting walk-forward (252 observasi per baris), memakai model terbaik per komoditas × horizon. Sumber: `webapp/streamlit_app/data/metrik_model.csv`, yang juga ditampilkan di halaman **Performa Model**.

| Komoditas | H+1 | H+7 | H+30 |
|---|---|---|---|
| Beras Kualitas Bawah I | 0.02% (XGBoost) | 0.06% (LightGBM) | 0.17% (LightGBM) |
| Beras Kualitas Bawah II | 0.01% (XGBoost) | 0.04% (LightGBM) | 0.11% (LightGBM) |
| Beras Kualitas Medium I | 0.01% (XGBoost) | 0.05% (LightGBM) | 0.15% (LightGBM) |
| Beras Kualitas Medium II | 0.02% (XGBoost) | 0.06% (LightGBM) | 0.13% (LightGBM) |
| Beras Kualitas Super I | 0.02% (XGBoost) | 0.07% (LightGBM) | 0.24% (LightGBM) |
| Beras Kualitas Super II | 0.02% (XGBoost) | 0.07% (LightGBM) | 0.18% (LightGBM) |
| Bawang Merah Ukuran Sedang | 0.41% (XGBoost) | 1.59% (LightGBM) | 3.36% (XGBoost) |
| Cabai Rawit Hijau | 1.62% (XGBoost) | 4.76% (LightGBM) | 7.99% (LightGBM) |
| Cabai Rawit Merah | 3.19% (LightGBM) | 8.54% (LightGBM) | 18.09% (XGBoost) |

Harga beras relatif stabil sehingga error-nya sangat kecil. Cabai rawit paling volatil, dan error-nya naik tajam di H+30.

## Project Structure

```text
pangan-forecasting/
├── Dockerfile                 # image Streamlit (python:3.14-slim, non-root)
├── .dockerignore              # allowlist isi image
├── requirements.txt           # dependency app (di-pin, versi training model)
├── ruff.toml                  # konfigurasi lint & format
├── .pre-commit-config.yaml    # hook ruff sebelum commit
├── .devcontainer/             # Dev Container / Codespaces
├── .github/workflows/main.yml # CI: ruff check + format check
└── webapp/
    ├── research/
    │   ├── code.ipynb         # pipeline utama: EDA → tuning GA → walk-forward → simpan model
    │   ├── predict.ipynb      # prediksi geser mingguan
    │   ├── plot_prediksi.ipynb
    │   ├── intepolate.ipynb
    │   ├── dataset.csv        # dataset training (ribuan Rp)
    │   ├── final_lgbm/        # 27 model LightGBM (GA) dipakai app
    │   ├── final_xgb/         # 27 model XGBoost (GA) dipakai app
    │   ├── final_*_default/   # model baseline (parameter default)
    │   └── params/            # hyperparameter terbaik & transformer
    └── streamlit_app/
        ├── app.py             # entry point + navigasi halaman
        ├── forecast.py        # pemuat model & prediksi H+1/H+7/H+30
        ├── ews.py             # logika peringatan dini
        ├── auth.py            # login & sesi admin
        ├── config.py          # config.json (model aktif, ambang)
        ├── db.py              # SQLite audit log
        ├── metrik_model.py    # baca metrik walk-forward
        ├── data/              # komoditas, riwayat harga, metrik_model.csv
        ├── views/             # halaman publik & admin
        ├── assets/styles.css
        ├── .streamlit/        # tema + contoh secrets
        └── test_*.py          # self-check berbasis assert
```

## Testing

Test berupa script `assert` biasa (tanpa pytest). Jalankan dari folder app:

```bash
cd webapp/streamlit_app
python test_forecast.py            # last window, registry model, semua model bisa meramal
python test_deploy_siap.py         # dataset & artefak cocok, semua komoditas × horizon jalan
python test_harga_dan_model.py     # input harga & unggah dataset
python test_auth_sesi.py           # login, timeout sesi
python test_komponen_prediksi.py
python test_metrik_model.py
python test_sinkronisasi_harga.py  # sinkronisasi harga ke GitHub (API di-mock)
```

Atau jalankan semuanya sekaligus:

```bash
for t in test_*.py; do python "$t" || break; done
```

## Development Tools

```bash
pip install ruff pre-commit
pre-commit install        # ruff check --fix + ruff format setiap commit
ruff check .              # lint
ruff format --check .     # cek format
```

GitHub Actions (`.github/workflows/main.yml`) menjalankan `ruff check` dan `ruff format --check` dengan Python 3.14 di setiap push dan pull request ke `main`.

## Troubleshooting

| Masalah | Penyebab & solusi |
|---|---|
| `permission denied while trying to connect to the docker API at unix:///var/run/docker.sock` | User belum masuk grup `docker`. Jalankan `sudo usermod -aG docker $USER`, lalu logout/login (atau `newgrp docker`). |
| `SyntaxError` di `config.py` (`except ..., ...`) | Python yang dipakai di bawah 3.14. Pakai Python 3.14, atau jalankan lewat Docker. |
| Login admin selalu gagal | `ADMIN_USERNAME` / `ADMIN_PASSWORD` belum disetel. Cek `.env` (lokal) atau `--env-file` (Docker). |
| `OSError: libgomp.so.1` saat import LightGBM | Install OpenMP: `sudo apt install libgomp1`. Image Docker sudah menyertakannya. |
| Port 8501 sudah dipakai | Pakai port lain, mis. `streamlit run app.py --server.port 8502` atau `docker run -p 8502:8501 ...`. |
| Tema tidak muncul / halaman putih polos | Jalankan `streamlit run` dari dalam `webapp/streamlit_app/` supaya `.streamlit/config.toml` terbaca. |
| Harga input admin hilang setelah redeploy | Filesystem container tidak persisten. Aktifkan [sinkronisasi GitHub](#sinkronisasi-harga-ke-github-opsional). |

---

made with ❤️ by [YosiaCoKR](https://github.com/YosiaCoKR)
