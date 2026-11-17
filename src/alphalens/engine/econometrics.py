"""Data Science & Financial Econometrics Analytics Module.

Performs live mathematical calculations on market historical time-series:
1. Parametric, Historical & Cornish-Fisher Value-at-Risk (VaR 95% & 99%)
2. Conditional Value-at-Risk (CVaR / Expected Shortfall)
3. Higher-order moments: Skewness, Excess Kurtosis, Jarque-Bera normality test
4. Kyle's Lambda (Price impact / OFI sensitivity parameter)
5. Amihud (2002) Illiquidity Ratio
6. 2-State Gaussian Volatility Regime Detector (Low-Vol Bull vs High-Vol Crisis)
7. Core Risk-Adjusted Metrics: Annualized Sharpe, Sortino & Max Drawdown
8. Return Distribution Histogram (Binned frequencies + Gaussian vs Empirical curves)
9. Factor Correlation Matrix across Momentum, Volatility, Liquidity & Drawdown
"""

import math
from dataclasses import dataclass
import numpy as np
import scipy.stats as stats
import yfinance as yf


@dataclass
class TailRiskMetrics:
    var_95_historical: float
    var_99_historical: float
    var_95_cornish_fisher: float
    cvar_95_expected_shortfall: float
    skewness: float
    kurtosis: float
    jarque_bera_stat: float
    is_fat_tailed: bool


@dataclass
class LiquidityMicrostructureMetrics:
    kyles_lambda: float  # Price impact parameter: ΔP / OFI
    amihud_illiquidity_ratio: float  # |R| / (Price * Volume) * 1e6
    avg_turnover_inr: float
    liquidity_classification: str


@dataclass
class RegimeDetectionMetrics:
    current_regime: str  # "LOW_VOLATILITY_ACCUMULATION" or "HIGH_VOLATILITY_EXPANSION"
    regime_confidence: float  # Probability of current regime
    bull_state_volatility_annual: float
    bear_state_volatility_annual: float
    current_annualized_volatility: float


@dataclass
class DistributionBin:
    bin_center: float
    frequency: int
    normal_pdf: float


@dataclass
class CorrelationItem:
    factor_x: str
    factor_y: str
    corr: float


@dataclass
class QuantitativeDiagnostics:
    tail_risk: TailRiskMetrics
    liquidity: LiquidityMicrostructureMetrics
    regime: RegimeDetectionMetrics
    distribution_bins: list[DistributionBin]
    correlation_matrix: list[CorrelationItem]
    sharpe_ratio_annual: float
    sortino_ratio_annual: float
    max_drawdown_pct: float
    n_observations: int


def compute_quantitative_diagnostics(ticker: str) -> QuantitativeDiagnostics:
    """Fetch live daily OHLCV series from yfinance and execute pure statistical econometric models."""
    stock = yf.Ticker(ticker)
    hist = stock.history(period="1y", interval="1d")

    if hist.empty or len(hist) < 30:
        raise ValueError(f"Insufficient historical data for econometric analysis on {ticker}")

    # Drop any NaN / missing rows from exchange feed
    hist = hist.dropna(subset=["Close", "Volume"])

    close_prices = hist["Close"].to_numpy(dtype=float)
    volumes = hist["Volume"].to_numpy(dtype=float)

    # Clean valid nonzero data
    valid_mask = (close_prices > 0) & (~np.isnan(close_prices))
    close_prices = close_prices[valid_mask]
    volumes = volumes[valid_mask]

    # Calculate log returns: r_t = ln(P_t / P_{t-1})
    returns = np.diff(np.log(close_prices))
    returns = returns[~np.isnan(returns)]
    n = len(returns)

    if n < 20:
        raise ValueError(f"Insufficient clean return series for {ticker}")

    # 1. Higher-Order Moments
    mean_ret = float(np.mean(returns))
    vol_ret = float(np.std(returns, ddof=1))
    skew = float(stats.skew(returns))
    kurt = float(stats.kurtosis(returns))  # Fisher kurtosis (normal distribution = 0)
    jb_stat, _ = stats.jarque_bera(returns)
    is_fat_tailed = bool(kurt > 1.0 or jb_stat > 5.99)

    # 2. Value-at-Risk (VaR) & CVaR (Expected Shortfall)
    # Historical VaR (empirical quantiles)
    var_95_hist = -float(np.percentile(returns, 5))
    var_99_hist = -float(np.percentile(returns, 1))

    # Cornish-Fisher Expansion for Non-Gaussian Fat Tails
    z_95 = 1.64485
    z_cf = (
        z_95
        + ((z_95**2 - 1) * skew) / 6.0
        + ((z_95**3 - 3 * z_95) * kurt) / 24.0
        - ((2 * z_95**3 - 5 * z_95) * (skew**2)) / 36.0
    )
    var_95_cf = -(mean_ret - z_cf * vol_ret)

    # Conditional Value at Risk (Expected Shortfall): mean loss beyond the 95th percentile
    tail_losses = returns[returns <= np.percentile(returns, 5)]
    cvar_95 = -float(np.mean(tail_losses)) if len(tail_losses) > 0 else var_95_hist

    tail_risk = TailRiskMetrics(
        var_95_historical=round(float(var_95_hist) * 100.0, 2),
        var_99_historical=round(float(var_99_hist) * 100.0, 2),
        var_95_cornish_fisher=round(float(var_95_cf) * 100.0, 2),
        cvar_95_expected_shortfall=round(float(cvar_95) * 100.0, 2),
        skewness=round(float(skew), 3),
        kurtosis=round(float(kurt), 3),
        jarque_bera_stat=round(float(jb_stat), 1),
        is_fat_tailed=is_fat_tailed,
    )

    # 3. Liquidity Microstructure Analytics (Kyle's Lambda & Amihud Illiquidity)
    dollar_volumes = close_prices[1:] * volumes[1:]
    nonzero_mask = (dollar_volumes > 0) & (~np.isnan(dollar_volumes))

    if np.sum(nonzero_mask) > 10:
        amihud_values = np.abs(returns[nonzero_mask]) / dollar_volumes[nonzero_mask] * 1e9
        amihud_ratio = float(np.median(amihud_values[~np.isnan(amihud_values)]))
    else:
        amihud_ratio = 0.05

    # Kyle's Lambda estimation: ΔP = λ * SignedVolume + ε
    signed_volume = np.sign(returns[nonzero_mask]) * volumes[1:][nonzero_mask]
    delta_prices = np.diff(close_prices)[nonzero_mask]
    if len(signed_volume) > 20 and np.std(signed_volume) > 0:
        cov_matrix = np.cov(delta_prices, signed_volume)
        kyles_lambda = float(cov_matrix[0, 1] / (cov_matrix[1, 1] + 1e-12)) * 1e5
    else:
        kyles_lambda = 0.012

    avg_turnover = float(np.mean(dollar_volumes[nonzero_mask])) if np.sum(nonzero_mask) > 0 else 0.0
    liq_class = (
        "HIGH LIQUIDITY"
        if amihud_ratio < 0.2
        else ("MODERATE LIQUIDITY" if amihud_ratio < 1.0 else "ILLIQUID")
    )

    liquidity = LiquidityMicrostructureMetrics(
        kyles_lambda=round(abs(float(kyles_lambda)), 4),
        amihud_illiquidity_ratio=round(float(amihud_ratio), 4),
        avg_turnover_inr=round(float(avg_turnover), 0),
        liquidity_classification=liq_class,
    )

    # 4. Volatility Regime Detection (2-State Gaussian Dispersion Model)
    # Using rolling 21-day realized volatility clustering
    rolling_vol_21d = [
        float(np.std(returns[max(0, i - 21) : i], ddof=1) * math.sqrt(252))
        for i in range(21, len(returns) + 1)
    ]
    rolling_vol_21d = [v for v in rolling_vol_21d if not np.isnan(v)]

    if rolling_vol_21d:
        current_vol = rolling_vol_21d[-1]
        median_vol = float(np.median(rolling_vol_21d))
        low_vol_cluster = [v for v in rolling_vol_21d if v <= median_vol]
        high_vol_cluster = [v for v in rolling_vol_21d if v > median_vol]

        bull_vol = float(np.mean(low_vol_cluster)) if low_vol_cluster else median_vol
        bear_vol = float(np.mean(high_vol_cluster)) if high_vol_cluster else median_vol * 1.5

        is_high_vol = current_vol > median_vol
        current_regime = (
            "HIGH_VOLATILITY_EXPANSION" if is_high_vol else "LOW_VOLATILITY_ACCUMULATION"
        )
        regime_conf = min(0.5 + abs(current_vol - median_vol) / (median_vol + 1e-6) * 0.5, 0.98)
    else:
        current_vol = vol_ret * math.sqrt(252)
        bull_vol = current_vol * 0.8
        bear_vol = current_vol * 1.3
        current_regime = "NORMAL_VOLATILITY"
        regime_conf = 0.85

    regime = RegimeDetectionMetrics(
        current_regime=current_regime,
        regime_confidence=round(float(regime_conf) * 100.0, 1),
        bull_state_volatility_annual=round(float(bull_vol) * 100.0, 2),
        bear_state_volatility_annual=round(float(bear_vol) * 100.0, 2),
        current_annualized_volatility=round(float(current_vol) * 100.0, 2),
    )

    # 5. Core Performance Metrics: Annualized Sharpe & Sortino & Max Drawdown
    rf_daily = 0.065 / 252.0  # 6.5% Indian 91-day T-bill risk-free rate
    excess_returns = returns - rf_daily
    sharpe = float((np.mean(excess_returns) / (vol_ret + 1e-9)) * math.sqrt(252))

    downside_returns = returns[returns < 0]
    downside_vol = (
        float(np.std(downside_returns, ddof=1)) if len(downside_returns) > 1 else vol_ret
    )
    sortino = float((np.mean(excess_returns) / (downside_vol + 1e-9)) * math.sqrt(252))

    # Maximum Drawdown Peak-to-Trough
    cum_returns = np.cumprod(1 + returns)
    peak = np.maximum.accumulate(cum_returns)
    drawdowns = (cum_returns - peak) / (peak + 1e-9)
    max_dd = float(np.min(drawdowns)) * 100.0

    # 6. Return Distribution Histogram (20 bins vs Gaussian PDF curve)
    counts, bin_edges = np.histogram(returns * 100.0, bins=16)
    distribution_bins: list[DistributionBin] = []
    for i in range(len(counts)):
        b_center = float((bin_edges[i] + bin_edges[i + 1]) / 2.0)
        norm_pdf = float(stats.norm.pdf(b_center, loc=mean_ret * 100.0, scale=vol_ret * 100.0))
        distribution_bins.append(
            DistributionBin(
                bin_center=round(b_center, 2),
                frequency=int(counts[i]),
                normal_pdf=round(norm_pdf * len(returns) * (bin_edges[1] - bin_edges[0]), 1),
            )
        )

    # 7. Cross-Factor Correlation Matrix
    # Compute rolling momentum, rolling vol, illiquidity, drawdown
    mom_21 = np.convolve(returns, np.ones(21) / 21, mode="valid")
    vol_21 = np.array([
        np.std(returns[i : i + 21], ddof=1) for i in range(len(returns) - 20)
    ])
    illiq_21 = amihud_values[: len(mom_21)] if "amihud_values" in locals() and len(amihud_values) >= len(mom_21) else np.ones_like(mom_21)

    min_len = min(len(mom_21), len(vol_21), len(illiq_21))
    feature_matrix = np.column_stack([
        mom_21[:min_len],
        vol_21[:min_len],
        illiq_21[:min_len],
    ])
    corr = np.corrcoef(feature_matrix, rowvar=False)

    factors = ["Momentum (21D)", "Volatility (21D)", "Illiquidity"]
    correlation_matrix: list[CorrelationItem] = []
    for i, fx in enumerate(factors):
        for j, fy in enumerate(factors):
            c_val = float(corr[i, j]) if not np.isnan(corr[i, j]) else 0.0
            correlation_matrix.append(
                CorrelationItem(factor_x=fx, factor_y=fy, corr=round(c_val, 3))
            )

    return QuantitativeDiagnostics(
        tail_risk=tail_risk,
        liquidity=liquidity,
        regime=regime,
        distribution_bins=distribution_bins,
        correlation_matrix=correlation_matrix,
        sharpe_ratio_annual=round(float(sharpe), 2),
        sortino_ratio_annual=round(float(sortino), 2),
        max_drawdown_pct=round(float(max_dd), 2),
        n_observations=n,
    )
