# Prediksi Pangan Jogja

![Python](https://img.shields.io/badge/python-3.14-blue) ![Streamlit](https://img.shields.io/badge/Streamlit-1.64.0-blue) ![LightGBM](https://img.shields.io/badge/LightGBM-4.7.0-blue) ![XGBoost](https://img.shields.io/badge/XGBoost-3.4.1-blue)

Aplikasi Streamlit untuk memantau dan memprediksi harga (H+1, H+7, H+30) sembilan komoditas pangan di Daerah Istimewa Yogyakarta, menggunakan model LightGBM dan XGBoost yang sudah dilatih.

## Features

- Dashboard harga terkini, grafik historis, dan prediksi sampai 30 hari
- Peringatan dini kenaikan harga dengan ambang yang bisa diatur
- Panel admin: input harga, unggah dataset (CSV/XLSX), pilih model, audit log

## Tech Stack

- **App:** Python 3.14, Streamlit, Pandas, Plotly, SQLite
- **Model:** skforecast, scikit-learn, LightGBM, XGBoost
- **Tooling:** Docker, Ruff, pre-commit, GitHub Actions

## Cara Menjalankan

### Lokal

```bash
git clone https://github.com/YosiaCoKR/pangan-forecasting.git
cd pangan-forecasting
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

cp webapp/streamlit_app/.env.example webapp/streamlit_app/.env   # isi ADMIN_USERNAME & ADMIN_PASSWORD

cd webapp/streamlit_app
streamlit run app.py
```

Buka http://localhost:8501.

### Docker

```bash
docker build -t pangan-forecasting .
docker run -p 8501:8501 --env-file webapp/streamlit_app/.env pangan-forecasting
```

### Testing

Tesnya berupa script biasa, jalankan dari `webapp/streamlit_app`:

```bash
python test_forecast.py
```

## Project Structure

```text
pangan-forecasting/
├── Dockerfile
├── requirements.txt
└── webapp/
    ├── research/          # notebook training, dataset, artefak model (final_lgbm/, final_xgb/)
    └── streamlit_app/
        ├── app.py         # entry point
        ├── forecast.py    # load model & prediksi
        ├── ews.py         # peringatan dini
        ├── db.py          # SQLite (tracking.db)
        ├── views/         # halaman dashboard & admin
        └── test_*.py
```

made with ❤️ by [YosiaCoKR](https://github.com/YosiaCoKR)
