# Python 3.14 = versi yang sama dengan devcontainer & yang dipakai melatih
# artefak model (lihat catatan pin di requirements.txt).
FROM python:3.14-slim

# libgomp1: LightGBM butuh OpenMP dari sistem; image slim tidak membawanya.
RUN apt-get update \
    && apt-get install -y --no-install-recommends libgomp1 \
    && rm -rf /var/lib/apt/lists/*

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

COPY requirements.txt .
RUN pip install -r requirements.txt

RUN useradd --create-home app
# --chown: app menulis tracking.db, config.json, dan harga_historis.pkl di
# folder streamlit_app saat runtime.
COPY --chown=app:app webapp/ webapp/

USER app
# WORKDIR di folder app supaya Streamlit membaca .streamlit/config.toml (tema).
WORKDIR /app/webapp/streamlit_app

EXPOSE 8501
CMD ["streamlit", "run", "app.py", "--server.address=0.0.0.0", "--server.port=8501", "--server.headless=true"]
