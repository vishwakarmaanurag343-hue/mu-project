"""Precomputed quantitative factor engine and score retriever."""

from typing import Any

from pydantic import BaseModel, ConfigDict
from sqlalchemy.orm import Session

from alphalens.db.models import PredictionLog, User

# Fixed model version for Phase 0 / Week 1
MODEL_VERSION = "v1.0.0-quant"


class ConfidenceInterval(BaseModel):
    """Lower and upper confidence intervals."""

    model_config = ConfigDict(extra="forbid")

    lower: float
    upper: float


class FactorContribution(BaseModel):
    """Contribution of an individual quant factor."""

    model_config = ConfigDict(extra="forbid")

    factor: str
    contribution: float
    score: float


class ScenarioDetail(BaseModel):
    """Scenario return expectation and thesis statement."""

    model_config = ConfigDict(extra="forbid")

    return_pct: float
    description: str


class QuantReportResponse(BaseModel):
    """Complete Tier 1 quantitative evaluation response."""

    model_config = ConfigDict(extra="forbid")

    ticker: str
    probability: float
    confidence_interval: ConfidenceInterval
    decision_label: str
    as_of: str
    factor_contributions: list[FactorContribution]
    scenarios: dict[str, ScenarioDetail]
    model_version: str


# Precomputed fixtures table for Nifty 100 constituents
_PRECOMPUTED_SCORES: dict[str, dict[str, Any]] = {
    "RELIANCE.NS": {
        "probability": 0.68,
        "ci": (0.61, 0.74),
        "label": "Overweight",
        "as_of": "2026-11-13",
        "factors": [
            {"factor": "Value", "contribution": 0.08, "score": 1.2},
            {"factor": "Quality", "contribution": 0.12, "score": 2.1},
            {"factor": "Momentum", "contribution": -0.04, "score": -0.6},
            {"factor": "Low Volatility", "contribution": 0.02, "score": 0.4},
        ],
        "scenarios": {
            "bull": {
                "return_pct": 24.5,
                "description": "Accelerated retail margin expansion & 5G monetization",
            },
            "base": {
                "return_pct": 14.2,
                "description": "Steady refining margins with moderate capex execution",
            },
            "bear": {
                "return_pct": -6.8,
                "description": "Sharp drop in global refining cracks and higher interest costs",
            },
        },
    },
    "TCS.NS": {
        "probability": 0.61,
        "ci": (0.55, 0.67),
        "label": "Overweight",
        "as_of": "2026-11-13",
        "factors": [
            {"factor": "Value", "contribution": -0.02, "score": -0.3},
            {"factor": "Quality", "contribution": 0.16, "score": 2.8},
            {"factor": "Momentum", "contribution": 0.05, "score": 0.9},
            {"factor": "Low Volatility", "contribution": 0.04, "score": 0.8},
        ],
        "scenarios": {
            "bull": {
                "return_pct": 19.8,
                "description": "Major BFSI discretionary tech spending rebound",
            },
            "base": {
                "return_pct": 11.5,
                "description": "Enterprise digital transformations with margin resilience",
            },
            "bear": {
                "return_pct": -4.2,
                "description": "Delayed North American contract renewals and currency headwinds",
            },
        },
    },
    "HDFCBANK.NS": {
        "probability": 0.54,
        "ci": (0.48, 0.60),
        "label": "Neutral",
        "as_of": "2026-11-13",
        "factors": [
            {"factor": "Value", "contribution": 0.09, "score": 1.4},
            {"factor": "Quality", "contribution": 0.08, "score": 1.5},
            {"factor": "Momentum", "contribution": -0.07, "score": -1.1},
            {"factor": "Low Volatility", "contribution": 0.02, "score": 0.3},
        ],
        "scenarios": {
            "bull": {
                "return_pct": 16.5,
                "description": "Rapid deposit accretion and merger cost synergies",
            },
            "base": {
                "return_pct": 8.0,
                "description": "Gradual credit-to-deposit ratio normalization",
            },
            "bear": {
                "return_pct": -8.5,
                "description": "Margin pressure from elevated deposit competition",
            },
        },
    },
}

_DEFAULT_PRECOMPUTE: dict[str, Any] = {
    "probability": 0.50,
    "ci": (0.43, 0.57),
    "label": "Neutral",
    "as_of": "2026-11-13",
    "factors": [
        {"factor": "Value", "contribution": 0.01, "score": 0.1},
        {"factor": "Quality", "contribution": 0.03, "score": 0.5},
        {"factor": "Momentum", "contribution": -0.02, "score": -0.3},
        {"factor": "Low Volatility", "contribution": 0.01, "score": 0.2},
    ],
    "scenarios": {
        "bull": {
            "return_pct": 15.0,
            "description": "Macroeconomic acceleration across Indian enterprise sectors",
        },
        "base": {
            "return_pct": 7.5,
            "description": "Broadly in line with historical GDP growth pace",
        },
        "bear": {
            "return_pct": -10.0,
            "description": "External global shocks and rising raw material inflation",
        },
    },
}


def get_precomputed_quant_score(
    ticker: str,
    user: User,
    db: Session,
) -> QuantReportResponse:
    """Retrieve precomputed quantitative metrics and record prediction in append-only log."""
    data = _PRECOMPUTED_SCORES.get(ticker, _DEFAULT_PRECOMPUTE)

    # Decision threshold applied strictly to label (never altering underlying probability)
    prob = float(data["probability"])
    lower, upper = data["ci"]

    # Append to append-only prediction audit table
    log_entry = PredictionLog(
        user_id=user.id,
        ticker=ticker,
        probability=prob,
        decision_label=data["label"],
        model_version=MODEL_VERSION,
    )
    db.add(log_entry)
    db.commit()

    return QuantReportResponse(
        ticker=ticker,
        probability=prob,
        confidence_interval=ConfidenceInterval(lower=lower, upper=upper),
        decision_label=data["label"],
        as_of=data["as_of"],
        factor_contributions=[FactorContribution(**fc) for fc in data["factors"]],
        scenarios={k: ScenarioDetail(**v) for k, v in data["scenarios"].items()},
        model_version=MODEL_VERSION,
    )
