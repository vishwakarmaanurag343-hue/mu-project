"""Precompute canonical quantitative predictions and store them in the database.

Latest month-end factors for the universe -> CanonicalPrediction rows (model_version "1.0", outcome None)
with contributions and scenarios. Idempotent.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd
from sqlalchemy import delete

from alphalens.db.models import CanonicalPrediction
from alphalens.db.session import SessionLocal
from alphalens.engine.quant import (
    MODEL_VERSION,
    QuantModel,
)

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATASET_PATH = PROJECT_ROOT / "data" / "processed" / "dataset.csv"
MODEL_JSON_PATH = PROJECT_ROOT / "models" / "model-1.0.json"


def precompute_latest_predictions(
    dataset_path: Path = DATASET_PATH,
    model_path: Path = MODEL_JSON_PATH,
    model_version: str = MODEL_VERSION,
) -> int:
    """Read latest month-end slice from dataset.csv and generate CanonicalPrediction rows."""
    if not dataset_path.exists():
        raise FileNotFoundError(
            f"Dataset file {dataset_path} does not exist. Run scripts/build_dataset.py first."
        )

    if not model_path.exists():
        raise FileNotFoundError(
            f"Model file {model_path} does not exist. Run scripts/run_backtest.py first."
        )

    model = QuantModel(model_path=model_path)
    df = pd.read_csv(dataset_path)

    latest_date = str(df["date"].max())
    latest_slice = df[df["date"] == latest_date].copy()

    predictions: list[CanonicalPrediction] = []

    for row in latest_slice.itertuples():
        ticker = str(row.ticker)
        z_scores = {feat: float(getattr(row, feat, 0.0)) for feat in model.features}
        prob, _ = model.predict_probability(z_scores)

        pred_record = CanonicalPrediction(
            ticker=ticker,
            as_of=latest_date,
            probability=round(prob, 4),
            outcome=None,
            model_version=model_version,
        )
        predictions.append(pred_record)

    # Idempotent write to CanonicalPrediction table
    with SessionLocal() as db:
        # Delete existing rows with this model_version
        db.execute(
            delete(CanonicalPrediction).where(CanonicalPrediction.model_version == model_version)
        )
        db.commit()

        db.add_all(predictions)
        db.commit()

    return len(predictions)


def main() -> None:
    """Run precomputation job."""
    print("=== AlphaLens Precompute Job ===")
    count = precompute_latest_predictions()
    print(f"Precomputed and stored {count} predictions with model_version='{MODEL_VERSION}'.")


if __name__ == "__main__":
    main()
