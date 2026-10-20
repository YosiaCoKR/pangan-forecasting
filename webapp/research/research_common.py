"""Komponen bersama untuk `code_run_all.ipynb` dan `code_run_training.ipynb`.

Pipeline harga pangan: imputasi → `log1p` → *differencing* orde 1 →
`ForecasterDirect`. Modul ini memuat bagian yang identik di kedua notebook
(pemuatan data, konfigurasi fitur, evaluasi, plot, EWS, penyimpanan model).
Pencarian hyperparameter dengan Genetic Algorithm tetap berada di
`code_run_all.ipynb` karena hanya dipakai di sana.
"""

from dataclasses import dataclass, field
from pathlib import Path

import lightgbm as lgb
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import xgboost as xgb
from skforecast.direct import ForecasterDirect
from skforecast.model_selection import TimeSeriesFold, backtesting_forecaster
from skforecast.preprocessing import CalendarFeatures, RollingFeatures
from skforecast.utils import save_forecaster
from sklearn.metrics import (
    mean_absolute_error,
    mean_absolute_percentage_error,
    root_mean_squared_error,
)
from sklearn.model_selection import TimeSeriesSplit
from sklearn.preprocessing import FunctionTransformer, StandardScaler

HORIZONS = (1, 7, 30)
LAGS = (1, 7, 30)
DIFFERENTIATION = 1  # model memprediksi perubahan harian log harga
THRESHOLD = {"Bahaya": 20, "Warning": 10, "Waspada": 5}  # urut dari paling berat


# --------------------------------------------------------------------------
# transformasi skala dan metrik
# --------------------------------------------------------------------------
def log_to_price(log_values):
    """Kembalikan prediksi skala log1p ke skala harga."""
    return np.expm1(np.asarray(log_values, dtype=float).ravel())


def price_metrics(actual, predicted):
    """MAE, RMSE, dan MAPE (%) pada skala harga."""
    return {
        "MAE": mean_absolute_error(actual, predicted),
        "RMSE": root_mean_squared_error(actual, predicted),
        "MAPE (%)": mean_absolute_percentage_error(actual, predicted) * 100,
    }


def prediction_column(predictions):
    return "pred" if "pred" in predictions.columns else predictions.columns[0]


def make_lgb(params):
    return lgb.LGBMRegressor(**params)


def make_xgb(params):
    return xgb.XGBRegressor(**params)


def ews_status(persen):
    """Status Early Warning System dari persentase perubahan harga."""
    for status, batas in THRESHOLD.items():
        if persen > batas:
            return status
    return "Normal"


def print_params_block(params_store, horizons, suffix=""):
    """Cetak hyperparameter per komoditas dan horizon."""
    for commodity, params_h in params_store.items():
        print("\n" + "=" * 72)
        print(f"Nama Komoditas: {commodity}{suffix}")
        print("=" * 72)

        for h in horizons:
            print(f"\nBest parameters for horizon {h}:")
            for key, value in params_h[h]["params"].items():
                if isinstance(value, float):
                    print(f"{key:20s}: {value:.6f}")
                else:
                    print(f"{key:20s}: {value}")


# --------------------------------------------------------------------------
# data dan konfigurasi fitur
# --------------------------------------------------------------------------
@dataclass
class ResearchData:
    """Data harga yang sudah dibagi dan dikonfigurasi untuk pemodelan.

    Menyatukan state yang dipakai bersama oleh seluruh langkah evaluasi:
    split train/test, deret harga dan log harga per komoditas, serta objek
    fitur rolling/kalender yang dibagi ke semua forecaster (sama seperti
    saat GA mencari parameter).
    """

    df_raw: pd.DataFrame
    raw_train: pd.DataFrame
    raw_test: pd.DataFrame
    df_cleaned: pd.DataFrame
    df_cleaned_log: pd.DataFrame
    commodity_cols: list
    data_by_col: dict
    horizons: list = field(default_factory=lambda: list(HORIZONS))
    lags: list = field(default_factory=lambda: list(LAGS))
    differentiation: int = DIFFERENTIATION
    window_features: RollingFeatures = None
    calendar_features: CalendarFeatures = None

    # ---- konstruksi -------------------------------------------------------
    @classmethod
    def from_csv(cls, csv_path="DATASET-BERAS.csv", n_splits=5, verbose=True):
        """Muat CSV, tetapkan indeks harian, split kronologis, lalu imputasi.

        Train diimputasi interpolasi berbasis waktu; test diisi *forward fill*
        agar tidak memakai informasi masa depan.
        """
        df_raw = pd.read_csv(csv_path)
        df_raw.index = pd.DatetimeIndex(df_raw["tanggal"], yearfirst=True)
        df_raw.drop(columns=["tanggal"], inplace=True)
        df_raw = df_raw.asfreq("D")

        holdout = TimeSeriesSplit(n_splits=n_splits)
        train_idx, test_idx = list(holdout.split(df_raw))[-1]
        raw_train = df_raw.iloc[train_idx].copy()
        raw_test = df_raw.iloc[test_idx].copy()

        train_filled_interpolation = raw_train.interpolate(
            method="time", limit_direction="both"
        )
        test_filled_interpolation = (
            pd.concat([train_filled_interpolation.tail(1), raw_test]).ffill().iloc[1:]
        )
        df_cleaned = pd.concat(
            [train_filled_interpolation, test_filled_interpolation]
        ).loc[raw_train.index[0] :]

        assert df_cleaned.index.equals(df_raw.loc[raw_train.index[0] :].index)
        assert not df_cleaned.isna().any().any()
        if verbose:
            print(
                "Train:", raw_train.index.min().date(),
                "->", raw_train.index.max().date(),
            )
            print(
                "Test:", raw_test.index.min().date(),
                "->", raw_test.index.max().date(),
            )

        commodity_cols = df_cleaned.columns.tolist()
        log_transformation = FunctionTransformer(
            func=np.log1p, inverse_func=np.expm1, check_inverse=True
        )
        df_cleaned_log = pd.DataFrame(
            log_transformation.fit_transform(df_cleaned[commodity_cols]),
            index=df_cleaned.index,
            columns=commodity_cols,
        )
        data_by_col = {
            col: {
                "price_train": df_cleaned.loc[raw_train.index, col],
                "price_test": df_cleaned.loc[raw_test.index, col],
                "log_price_train": df_cleaned_log.loc[raw_train.index, col].rename(col),
                "log_price_test": df_cleaned_log.loc[raw_test.index, col].rename(col),
            }
            for col in commodity_cols
        }

        return cls(
            df_raw=df_raw,
            raw_train=raw_train,
            raw_test=raw_test,
            df_cleaned=df_cleaned,
            df_cleaned_log=df_cleaned_log,
            commodity_cols=commodity_cols,
            data_by_col=data_by_col,
        )

    def __post_init__(self):
        # satu instance fitur dibagi ke seluruh forecaster, seperti di notebook asal
        if self.window_features is None:
            self.window_features = RollingFeatures(
                stats=["mean", "mean", "std", "std", "min", "min", "max", "max"],
                window_sizes=[7, 30, 7, 30, 7, 30, 7, 30],
            )
        if self.calendar_features is None:
            self.calendar_features = CalendarFeatures(
                features=["day_of_year", "day_of_week", "day_of_month", "month"],
                features_to_encode=[
                    "day_of_year", "day_of_month", "day_of_week", "month",
                ],
                encoding="cyclical",
                max_values={
                    "day_of_year": 365,
                    "day_of_week": 6,
                    "day_of_month": 31,
                    "month": 12,
                },
            )

    # ---- forecaster -------------------------------------------------------
    def make_forecaster(self, estimator, steps):
        return ForecasterDirect(
            estimator=estimator,
            steps=steps,
            lags=self.lags,
            window_features=self.window_features,
            calendar_features=self.calendar_features,
            transformer_y=StandardScaler(),
            differentiation=self.differentiation,
        )

    def fit_forecaster(self, estimator, steps, y):
        """Bentuk `ForecasterDirect` lalu latih pada deret log harga `y`."""
        forecaster = self.make_forecaster(estimator, steps)
        forecaster.fit(y=y)
        return forecaster

    def fit_all_horizons(self, estimator_factory):
        """Latih satu forecaster per komoditas dan horizon (parameter default)."""
        return {
            col: {
                h: self.fit_forecaster(
                    estimator_factory(), h, self.data_by_col[col]["log_price_train"]
                )
                for h in self.horizons
            }
            for col in self.commodity_cols
        }

    def fit_from_params(self, params_store, estimator_factory):
        """Latih forecaster memakai hyperparameter tersimpan per komoditas/horizon."""
        return {
            col: {
                h: self.fit_forecaster(
                    estimator_factory(params_store[col][h]["params"]),
                    h,
                    self.data_by_col[col]["log_price_train"],
                )
                for h in self.horizons
            }
            for col in self.commodity_cols
        }

    # ---- evaluasi ---------------------------------------------------------
    def predict_prices(self, forecaster, steps):
        """Prediksi `steps` langkah lalu kembalikan ke skala harga."""
        return log_to_price(forecaster.predict(steps=steps))

    def test_metrics(self, forecasters_by_col, extra=None):
        """MAE/RMSE/MAPE pada h hari pertama data test untuk tiap komoditas."""
        rows = []
        for col in self.commodity_cols:
            price_test = self.data_by_col[col]["price_test"]
            for h in self.horizons:
                price_pred = self.predict_prices(forecasters_by_col[col][h], h)
                actual_price = price_test.iloc[:h].to_numpy()
                rows.append(
                    {
                        **(extra or {}),
                        "Komoditas": col,
                        "Horizon": h,
                        **price_metrics(actual_price, price_pred),
                    }
                )
        return pd.DataFrame(rows)

    def evaluate_on_test(self, params_store, estimator_factory):
        """Latih ulang dengan parameter tersimpan, lalu ukur galat pada data test."""
        forecasters = self.fit_from_params(params_store, estimator_factory)
        return forecasters, self.test_metrics(forecasters)

    def walk_forward_evaluation(self, params_store, estimator_factory):
        """Backtesting walk-forward untuk semua komoditas dan horizon.

        Galat hanya dihitung pada tanggal yang punya observasi asli
        (bukan hasil imputasi).
        """
        metric_rows = []
        prediction_rows = []

        for col in self.commodity_cols:
            log_price_train = self.data_by_col[col]["log_price_train"]
            y_walk_forward = pd.concat(
                [log_price_train, self.data_by_col[col]["log_price_test"]]
            ).asfreq("D")

            for h in self.horizons:
                cv = TimeSeriesFold(
                    steps=h,
                    initial_train_size=len(log_price_train),
                    refit=True,
                    fixed_train_size=False,
                    allow_incomplete_fold=True,
                    differentiation=self.differentiation,
                    verbose=False,
                )
                _, predictions = backtesting_forecaster(
                    forecaster=self.make_forecaster(
                        estimator_factory(params_store[col][h]["params"]), h
                    ),
                    y=y_walk_forward,
                    cv=cv,
                    metric="mean_absolute_error",
                    verbose=False,
                    show_progress=False,
                )

                idx = predictions.index
                price_predicted = log_to_price(
                    predictions[prediction_column(predictions)]
                )
                raw_actual = self.raw_test[col].reindex(idx)
                real_mask = raw_actual.notna().to_numpy()
                price_actual = raw_actual.to_numpy()[real_mask]
                price_predicted = price_predicted[real_mask]

                metric_rows.append(
                    {
                        "Komoditas": col,
                        "Horizon": h,
                        "Jumlah Observasi": int(real_mask.sum()),
                        **price_metrics(price_actual, price_predicted),
                    }
                )
                prediction_rows.extend(
                    {
                        "Tanggal": tanggal,
                        "Komoditas": col,
                        "Horizon": h,
                        "Harga Aktual": actual,
                        "Harga Prediksi": predicted,
                    }
                    for tanggal, actual, predicted in zip(
                        idx[real_mask], price_actual, price_predicted
                    )
                )

        return pd.DataFrame(metric_rows), pd.DataFrame(prediction_rows)

    def ews_table(self, forecasters_by_col, h_ews=30, model_name=None):
        """Bandingkan prediksi H+`h_ews` dengan harga terakhir pada data train."""
        rows = []
        for col in self.commodity_cols:
            price_train = self.data_by_col[col]["price_train"]
            harga_origin = float(price_train.iloc[-1])
            harga_pred = self.predict_prices(forecasters_by_col[col][h_ews], h_ews)
            harga_h30 = float(harga_pred[-1])
            persen = (harga_h30 - harga_origin) / harga_origin * 100

            rows.append(
                {
                    **({"Model": model_name} if model_name is not None else {}),
                    "Komoditas": col,
                    "Tanggal origin": price_train.index[-1].date(),
                    "Harga origin (train)": harga_origin,
                    f"Prediksi H+{h_ews}": harga_h30,
                    "Perubahan (%)": persen,
                    "Status": ews_status(persen),
                }
            )
        return pd.DataFrame(rows)

    # ---- keluaran ---------------------------------------------------------
    def plot_walkforward(self, models, suptitle, pred_linewidth=1.1):
        """Grid komoditas × horizon: harga aktual plus satu kurva per model.

        `models` memetakan label legenda ke (DataFrame prediksi, warna kurva).
        """
        fig, axes = plt.subplots(
            nrows=len(self.commodity_cols),
            ncols=len(self.horizons),
            figsize=(18, 3.2 * len(self.commodity_cols)),
            squeeze=False,
        )

        for row_idx, commodity in enumerate(self.commodity_cols):
            for col_idx, h in enumerate(self.horizons):
                ax = axes[row_idx, col_idx]
                actual_drawn = False

                for label, (df_predictions, color) in models.items():
                    model_slice = df_predictions.loc[
                        (df_predictions["Komoditas"] == commodity)
                        & (df_predictions["Horizon"] == h)
                    ].sort_values("Tanggal")

                    if model_slice.empty:
                        continue

                    if not actual_drawn:
                        ax.plot(
                            model_slice["Tanggal"],
                            model_slice["Harga Aktual"],
                            color="#355c7d",
                            linewidth=1.3,
                            label="Harga Aktual",
                        )
                        actual_drawn = True

                    ax.plot(
                        model_slice["Tanggal"],
                        model_slice["Harga Prediksi"],
                        color=color,
                        linewidth=pred_linewidth,
                        linestyle="--",
                        label=label,
                    )

                if not actual_drawn:
                    ax.text(0.5, 0.5, "Tidak ada observasi", ha="center", va="center")
                    ax.set_axis_off()
                    continue

                ax.set_title(f"{commodity} | H+{h}", fontsize=9)
                ax.grid(axis="y", alpha=0.25)
                ax.tick_params(axis="x", labelrotation=30, labelsize=8)
                ax.tick_params(axis="y", labelsize=8)
                if col_idx == 0:
                    ax.set_ylabel("Harga", fontsize=8)
                if row_idx == len(self.commodity_cols) - 1:
                    ax.set_xlabel("Tanggal", fontsize=8)

        handles, labels = axes[0, 0].get_legend_handles_labels()
        fig.legend(
            handles,
            labels,
            loc="upper center",
            ncol=len(models) + 1,
            bbox_to_anchor=(0.5, 1.0),
        )
        fig.suptitle(suptitle, y=1.015, fontsize=14)
        fig.tight_layout(rect=(0, 0, 1, 0.99))
        plt.show()

    def save_forecasters(self, forecasters, folder, prefix):
        """Simpan tiap forecaster ke `folder/prefix_<komoditas>_h<horizon>.joblib`."""
        Path(folder).mkdir(exist_ok=True)
        for col in self.commodity_cols:
            for h in self.horizons:
                save_forecaster(
                    forecasters[col][h],
                    str(Path(folder) / f"{prefix}_{col}_h{h}.joblib"),
                    save_custom_functions=False,
                )
                print("tersimpan:", col, "h=" + str(h))
