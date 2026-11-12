"""Generate forecasts and compare them with actual prices in thousand Rp/kg."""

from pathlib import Path

import numpy as np
import pandas as pd
from skforecast.utils import load_forecaster
from sklearn.metrics import (
    mean_absolute_error,
    mean_absolute_percentage_error,
    root_mean_squared_error,
)

BASE_DIR = Path(__file__).resolve().parent
ACTUALS_PATH = BASE_DIR / "data_aktual.csv"
HORIZONS = (1, 7, 30)
MODEL_SPECS = (
    ("LightGBM default", "final_lgbm_default"),
    ("LightGBM GA", "final_lgbm"),
    ("XGBoost default", "final_xgb_default"),
    ("XGBoost GA", "final_xgb"),
)
PREDICTIONS_PATH = BASE_DIR / "prediksi_semua_model.csv"
COMPARISON_PATH = BASE_DIR / "hasil_perbandingan_aktual.csv"
METRICS_PATH = BASE_DIR / "metrik_semua_model.csv"


def read_actuals(path: Path) -> tuple[pd.DataFrame, list[str]]:
    if not path.exists():
        raise FileNotFoundError(f"File data aktual tidak ditemukan: {path}")

    actuals = pd.read_csv(path)
    if "tanggal" not in actuals.columns:
        raise ValueError(f"Kolom 'tanggal' tidak ditemukan di {path}.")

    commodities = [column for column in actuals.columns if column != "tanggal"]
    if not commodities:
        raise ValueError(f"Kolom komoditas tidak ditemukan di {path}.")

    actuals["tanggal"] = pd.to_datetime(
        actuals["tanggal"], errors="raise"
    ).dt.normalize()
    if actuals["tanggal"].duplicated().any():
        raise ValueError(f"Data aktual memiliki tanggal duplikat: {path}")
    actuals[commodities] = actuals[commodities].apply(pd.to_numeric, errors="raise")
    return actuals, commodities


def generate_predictions(commodities: list[str], model_dir: Path) -> pd.DataFrame:
    rows = []
    for model_name, folder in MODEL_SPECS:
        for commodity in commodities:
            for horizon in HORIZONS:
                model_path = (
                    model_dir / folder / f"{folder}_{commodity}_h{horizon}.joblib"
                )
                if not model_path.exists():
                    raise FileNotFoundError(
                        f"Model belum tersedia: {model_path}. "
                        "Jalankan ulang notebook untuk menyimpan semua model."
                    )

                forecaster = load_forecaster(
                    str(model_path),
                    verbose=False,
                    suppress_warnings=True,
                )
                forecast_log = forecaster.predict(steps=horizon)
                if len(forecast_log) != horizon:
                    raise ValueError(
                        f"Model {model_path} mengembalikan {len(forecast_log)} "
                        f"prediksi, seharusnya {horizon}."
                    )

                target_dates = pd.DatetimeIndex(forecast_log.index).normalize()
                origin_date = pd.Timestamp(
                    forecaster.last_window_.index[-1]
                ).normalize()
                forecast_prices = np.expm1(
                    np.asarray(forecast_log, dtype=float).ravel()
                )
                rows.extend(
                    {
                        "model": model_name,
                        "komoditas": commodity,
                        "tanggal_origin": origin_date,
                        "horizon_hari": horizon,
                        "langkah_ke": step,
                        "tanggal_target": target_date,
                        "prediksi_ribu_rp_per_kg": float(prediction),
                    }
                    for step, (target_date, prediction) in enumerate(
                        zip(target_dates, forecast_prices), start=1
                    )
                )

    return pd.DataFrame(rows)


def compare_with_actuals(
    predictions: pd.DataFrame, actuals: pd.DataFrame, commodities: list[str]
) -> tuple[pd.DataFrame, pd.DataFrame]:
    actuals_long = actuals.melt(
        id_vars="tanggal",
        value_vars=commodities,
        var_name="komoditas",
        value_name="aktual_ribu_rp_per_kg",
    )
    comparison = predictions.merge(
        actuals_long,
        how="left",
        left_on=["komoditas", "tanggal_target"],
        right_on=["komoditas", "tanggal"],
    ).drop(columns="tanggal")
    comparison["status"] = np.where(
        comparison["aktual_ribu_rp_per_kg"].notna(),
        "sudah dievaluasi",
        "menunggu data aktual",
    )
    comparison["error"] = (
        comparison["aktual_ribu_rp_per_kg"] - comparison["prediksi_ribu_rp_per_kg"]
    ).where(comparison["aktual_ribu_rp_per_kg"].notna())
    comparison["absolute_error"] = comparison["error"].abs()

    scored = comparison.loc[comparison["aktual_ribu_rp_per_kg"].notna()]
    metric_rows = []
    for (model, commodity, horizon), group in scored.groupby(
        ["model", "komoditas", "horizon_hari"], sort=True
    ):
        metric_rows.append(
            {
                "model": model,
                "komoditas": commodity,
                "horizon_hari": horizon,
                "jumlah_aktual": len(group),
                "mae": mean_absolute_error(
                    group["aktual_ribu_rp_per_kg"],
                    group["prediksi_ribu_rp_per_kg"],
                ),
                "rmse": root_mean_squared_error(
                    group["aktual_ribu_rp_per_kg"],
                    group["prediksi_ribu_rp_per_kg"],
                ),
                "mape_persen": mean_absolute_percentage_error(
                    group["aktual_ribu_rp_per_kg"],
                    group["prediksi_ribu_rp_per_kg"],
                )
                * 100,
            }
        )

    metrics = pd.DataFrame(
        metric_rows,
        columns=[
            "model",
            "komoditas",
            "horizon_hari",
            "jumlah_aktual",
            "mae",
            "rmse",
            "mape_persen",
        ],
    )
    return comparison, metrics


def main() -> None:
    actuals, commodities = read_actuals(ACTUALS_PATH)
    predictions = generate_predictions(commodities, BASE_DIR)
    comparison, metrics = compare_with_actuals(predictions, actuals, commodities)

    predictions.to_csv(PREDICTIONS_PATH, index=False, encoding="utf-8-sig")
    comparison.to_csv(COMPARISON_PATH, index=False, encoding="utf-8-sig")
    metrics.to_csv(METRICS_PATH, index=False, encoding="utf-8-sig")

    actual_count = int(comparison["aktual_ribu_rp_per_kg"].notna().sum())
    print(f"Prediksi tersimpan: {PREDICTIONS_PATH}")
    print(f"Perbandingan aktual tersimpan: {COMPARISON_PATH}")
    print(f"Ringkasan metrik tersimpan: {METRICS_PATH}")
    print(
        f"{len(predictions)} prediksi dibuat; "
        f"{actual_count} prediksi sudah memiliki data aktual."
    )
    if metrics.empty:
        print("Belum ada data aktual yang cocok untuk menghitung metrik.")
    else:
        print(metrics.to_string(index=False))


if __name__ == "__main__":
    main()
