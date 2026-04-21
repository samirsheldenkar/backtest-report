"""Generate synthetic backtest fixture data for testing.

Run standalone: python scripts/generate_fixtures.py
"""
from __future__ import annotations

import hashlib
import json
from datetime import date, datetime
from pathlib import Path

import numpy as np
import pandas as pd

# Fixed seed for reproducibility
RNG = np.random.default_rng(42)

SCRIPT_DIR = Path(__file__).parent
FIXTURES_DIR = SCRIPT_DIR.parent / "tests" / "fixtures"
FIXTURES_DIR.mkdir(parents=True, exist_ok=True)

INSTRUMENTS = [
    "EDOLLAR",
    "US10",
    "US5",
    "GOLD",
    "CRUDE_W",
    "SP500",
    "EUROSTX",
    "GAS_US",
    "CORN",
    "JPY",
]

INSTRUMENT_NAMES = {
    "EDOLLAR": "Eurodollar",
    "US10": "US 10-Year Note",
    "US5": "US 5-Year Note",
    "GOLD": "Gold",
    "CRUDE_W": "WTI Crude Oil",
    "SP500": "S&P 500",
    "EUROSTX": "Euro Stoxx 50",
    "GAS_US": "Henry Hub Natural Gas",
    "CORN": "Corn",
    "JPY": "Japanese Yen",
}


def compute_checksum(path: Path) -> str:
    """Compute SHA-256 checksum of a file."""
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    return f"sha256:{digest}"


def generate_dates(start: str, end: str, freq: str = "B") -> pd.DatetimeIndex:
    """Generate business day date range, timezone-naive."""
    return pd.date_range(start=start, end=end, freq=freq, tz=None)


def generate_portfolio_returns(dates: pd.DatetimeIndex) -> pd.Series:
    """Generate daily portfolio returns: ~15% vol annualised, Sharpe ~1.0."""
    n = len(dates)
    annual_vol = 0.15
    daily_vol = annual_vol / np.sqrt(252)

    # Target Sharpe 1.0: annualised return ≈ annualised vol
    # Total return over 5 years ≈ (1.15)^5 - 1 ≈ 101%
    # Per-day compounding factor: (1 + target_total)^^(1/n)
    # We add noise on top of a fixed drift so results are deterministic
    years = 5.0
    target_total = (1 + annual_vol) ** years - 1  # ≈ 101%
    daily_drift = (1 + target_total) ** (1 / n) - 1

    returns = RNG.normal(daily_drift, daily_vol, size=n)
    return pd.Series(returns, index=dates, name="portfolio_returns")


def generate_instrument_pnl(dates: pd.DatetimeIndex) -> pd.DataFrame:
    """Generate correlated instrument PnL (10 instruments).

    Uses a multivariate normal with moderate cross-correlation (~0.2–0.4).
    Each instrument has individual drift and vol, plus shared market factor.
    """
    n = len(dates)
    k = len(INSTRUMENTS)

    # Shared market factor
    market = RNG.normal(0, 1, size=n)

    # Instrument-specific vol and drift
    inst_vol = RNG.uniform(0.005, 0.02, size=k)
    inst_drift = RNG.uniform(0.0001, 0.0005, size=k)

    # Build correlation matrix: moderate positive correlation
    base = RNG.uniform(-0.1, 0.1, size=(k, k))
    corr_matrix = np.eye(k) * 0.5 + 0.5 * base
    corr_matrix = np.clip(corr_matrix, -1, 1)
    np.fill_diagonal(corr_matrix, 1.0)

    # Ensure positive semi-definite: symmetrize + small diagonal perturbation
    corr_matrix = 0.5 * (corr_matrix + corr_matrix.T)
    corr_matrix = corr_matrix + 0.001 * np.eye(k)

    try:
        chol = np.linalg.cholesky(corr_matrix)
    except np.linalg.LinAlgError:
        corr_matrix = np.eye(k)
        chol = np.linalg.cholesky(corr_matrix)

    # Generate correlated factor returns
    factor_returns = RNG.standard_normal((n, k))
    correlated = factor_returns @ chol.T

    # Build PnL
    pnl = np.zeros((n, k))
    for i in range(k):
        pnl[:, i] = (
            correlated[:, i] * inst_vol[i]
            + inst_drift[i]
            + 0.3 * market * inst_vol[i]
        )

    df = pd.DataFrame(pnl, index=dates, columns=INSTRUMENTS)
    return df


def generate_positions(dates: pd.DatetimeIndex, n_instruments: int = 10) -> pd.DataFrame:
    """Generate slow mean-reverting positions using AR(1) process.

    Simulates trend-following position sizing: phi ~0.99, Gaussian noise.
    Positions range roughly -20 to +20.
    """
    n = len(dates)
    phi = 0.99
    sigma = 2.0

    positions = np.zeros((n, n_instruments))
    for i in range(n_instruments):
        pos = RNG.normal(0, 5)
        for t in range(n):
            positions[t, i] = pos
            pos = phi * pos + RNG.normal(0, sigma)

    # Clip to realistic contract range
    positions = np.clip(positions, -20, 20)

    return pd.DataFrame(positions, index=dates, columns=INSTRUMENTS)


def generate_instrument_meta() -> dict:
    """Generate instrument metadata for the 10 instruments."""
    from backtest_report.models import InstrumentMeta

    meta = {}
    for code in INSTRUMENTS:
        meta[code] = InstrumentMeta(
            code=code,
            name=INSTRUMENT_NAMES.get(code, code),
            sector=_sector_for(code),
            group="Futures",
            asset_class=_asset_class_for(code),
            exchange=_exchange_for(code),
            point_value=1.0,
            currency="USD",
        )
    return meta


def _sector_for(code: str) -> str:
    sectors = {
        "EDOLLAR": "Interest Rate",
        "US10": "Interest Rate",
        "US5": "Interest Rate",
        "GOLD": "Metals",
        "CRUDE_W": "Energy",
        "SP500": "Equity Index",
        "EUROSTX": "Equity Index",
        "GAS_US": "Energy",
        "CORN": "Agriculture",
        "JPY": "FX",
    }
    return sectors.get(code, "Unknown")


def _asset_class_for(code: str) -> str:
    if code in ("EDOLLAR", "US10", "US5"):
        return "Interest Rate"
    if code in ("GOLD", "CRUDE_W", "GAS_US", "CORN"):
        return "Commodity"
    if code in ("SP500", "EUROSTX"):
        return "Equity Index"
    return "FX"


def _exchange_for(code: str) -> str:
    exchanges = {
        "EDOLLAR": "CME",
        "US10": "CBOT",
        "US5": "CBOT",
        "GOLD": "COMEX",
        "CRUDE_W": "NYMEX",
        "SP500": "CME",
        "EUROSTX": "EUREX",
        "GAS_US": "NYMEX",
        "CORN": "CBOT",
        "JPY": "CME",
    }
    return exchanges.get(code, "UNKNOWN")


def compute_stats(returns: pd.Series) -> dict:
    """Compute summary statistics for portfolio returns."""
    total_return = (1 + returns).prod() - 1
    annual_return = (1 + total_return) ** (252 / len(returns)) - 1
    annual_vol = returns.std() * np.sqrt(252)
    sharpe = annual_return / annual_vol if annual_vol > 0 else 0.0
    cummax = (1 + returns).cumprod().cummax()
    drawdown = (1 + returns).cumprod() / cummax - 1
    max_dd = drawdown.min()

    return {
        "total_return": f"{total_return:.2%}",
        "annualised_return": f"{annual_return:.2%}",
        "annualised_vol": f"{annual_vol:.2%}",
        "sharpe_ratio": f"{sharpe:.2f}",
        "max_drawdown": f"{max_dd:.2%}",
        "trading_days": len(returns),
    }


def main() -> None:
    print("Generating fixture data...")

    dates = generate_dates("2020-01-02", "2024-12-31")

    # Portfolio returns
    portfolio_returns = generate_portfolio_returns(dates)
    returns_path = FIXTURES_DIR / "sample_portfolio_returns.parquet"
    portfolio_returns.to_frame().to_parquet(returns_path)
    print(f"  Written: {returns_path}")

    # Instrument PnL
    instrument_pnl = generate_instrument_pnl(dates)
    pnl_path = FIXTURES_DIR / "sample_instrument_pnl.parquet"
    instrument_pnl.to_parquet(pnl_path)
    print(f"  Written: {pnl_path}")

    # Positions
    positions = generate_positions(dates)
    pos_path = FIXTURES_DIR / "sample_positions.parquet"
    positions.to_parquet(pos_path)
    print(f"  Written: {pos_path}")

    # Instrument metadata
    inst_meta = generate_instrument_meta()
    checksums = {
        "portfolio_returns": compute_checksum(returns_path),
        "instrument_pnl": compute_checksum(pnl_path),
        "positions": compute_checksum(pos_path),
    }

    # BacktestMeta JSON
    from backtest_report.models import BacktestConfig, BacktestMeta

    config = BacktestConfig(
        experiment_id="test-fixture_20240101_120000",
        strategy_name="Test Fixture Strategy",
        engine="backtest-report",
        engine_version="0.1.0",
        instrument_universe=INSTRUMENTS,
        start_date=date(2020, 1, 2),
        end_date=date(2024, 12, 31),
        capital=1_000_000.0,
        currency="USD",
        risk_target_annual_pct=20.0,
        data_sources=["synthetic"],
    )

    meta = BacktestMeta(
        config=config,
        generated_at=datetime(2024, 1, 1, 12, 0, 0),
        report_version="0.1.0",
        data_checksums=checksums,
        notes="Synthetic fixture data for testing",
    )

    meta_path = FIXTURES_DIR / "sample_meta.json"
    meta_path.write_text(json.dumps(meta.model_dump(), indent=2, default=str))
    print(f"  Written: {meta_path}")

    # Print summary stats
    stats = compute_stats(portfolio_returns)
    print("\n=== Portfolio Returns Summary ===")
    for k, v in stats.items():
        print(f"  {k}: {v}")

    print(f"\nInstruments: {INSTRUMENTS}")
    print(f"Trading days: {len(dates)}")
    print("\nFixture generation complete.")


if __name__ == "__main__":
    main()