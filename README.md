# Prediksi Pangan Jogja

![Python](https://img.shields.io/badge/python-3-blue) ![scikit-learn](https://img.shields.io/badge/scikit--learn-1.3.0-blue) ![LightGBM](https://img.shields.io/badge/LightGBM-3.3.5-blue) ![XGBoost](https://img.shields.io/badge/XGBoost-1.7.6-blue) ![Streamlit](https://img.shields.io/badge/Streamlit-1.30.0-blue) ![Pandas](https://img.shields.io/badge/Pandas-2.0.3-blue) ![Plotly](https://img.shields.io/badge/Plotly-5.15.0-blue)

Aplikasi Streamlit untuk memantau harga dan membuat prediksi H+1, H+7, dan H+30 bagi sembilan komoditas pangan di Daerah Istimewa Yogyakarta. Model LightGBM dilatih menggunakan data historis, lalu dipakai aplikasi untuk menampilkan prediksi dan peringatan dini perubahan harga.

## ✨ Features

- Dashboard harga terkini dan perubahan harga harian untuk sembilan komoditas.
- Grafik harga historis dan lintasan prediksi sampai 30 hari.
- Peringatan dini berdasarkan ambang kenaikan harga yang dapat diatur admin.
- Halaman admin untuk memasukkan harga, mengatur ambang, dan melihat audit log.
- Prediksi menggunakan forecaster yang telah dilatih, tanpa pelatihan ulang saat aplikasi berjalan.

## 🛠️ Tech Stack

Python, Streamlit, Pandas, Plotly, scikit-learn, skforecast, LightGBM, XGBoost, SQLite

## 🚀 Getting Started

### Prerequisites

- Python 3

### Installation

```bash
git clone https://github.com/YosiaCoKR/pangan-forecasting.git
cd pangan-forecasting
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

Untuk mengatur akun admin, salin `webapp/streamlit_app/.env.example` menjadi `webapp/streamlit_app/.env`, lalu isi `ADMIN_USERNAME` dan `ADMIN_PASSWORD`.

### Usage

```bash
cd webapp/streamlit_app
streamlit run app.py
```

Untuk menjalankan tes aplikasi:

```bash
python test_forecast.py
```

## 📁 Project Structure

```text
pangan-forecasting/
├── README.md
├── requirements.txt
└── webapp/
    ├── research/
    │   ├── DATASET-BERAS-NEW.csv
    │   ├── code_run_all_new.ipynb
    │   ├── code_run_training.ipynb
    │   ├── final_lgbm/
    │   ├── final_xgb/
    │   └── params/
    └── streamlit_app/
        ├── app.py
        ├── forecast.py
        ├── ews.py
        ├── db.py
        ├── config.py
        ├── requirements.txt
        ├── data/
        └── views/
```

## 📊 Results (khusus project ML)

Evaluasi memakai split kronologis terakhir dari `TimeSeriesSplit(n_splits=5)` pada `DATASET-BERAS-NEW.csv`. Skor menggabungkan 342 prediksi uji dari sembilan komoditas dan horizon H+1, H+7, serta H+30. MAE dan RMSE menggunakan satuan ribu rupiah.

made with ❤️ by [YosiaCoKR](https://github.com/YosiaCoKR)
