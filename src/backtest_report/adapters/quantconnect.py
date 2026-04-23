"""QuantConnect adapter — fetch cloud backtest results and convert to BacktestData.

This module provides functions to extract backtest data and configuration
from QuantConnect cloud backtests via the QC API v2.

Usage:
    from backtest_report.adapters.quantconnect import fetch_backtest

    data, config = fetch_backtest(
        project_id=30522360,
        backtest_id="283c46d6a20c169a7a75e3a9a371a68d",
    )

    # Then write to experiment directory:
    from backtest_report.persist import write_experiment_dir
    write_experiment_dir(Path("/store/backtests/my_experiment"), data, config, {})
"""
from __future__ import annotations

import logging
from base64 import b64encode
from datetime import date, datetime, timezone
from hashlib import sha256
from pathlib import Path
from time import time
from typing import Any

import pandas as pd
import requests

logger = logging.getLogger("backtest_report")

QC_BASE_URL = "https://www.quantconnect.com/api/v2"


class QuantConnectAuthError(Exception):
    """Raised when QC API authentication fails."""
    pass


class QuantConnectAPIError(Exception):
    """Raised when a QC API request fails."""
    pass


class QuantConnectNotFoundError(Exception):
    """Raised when a backtest or project is not found."""
    pass


def _get_headers(user_id: str, api_token: str) -> dict[str, str]:
    """Generate authenticated headers for QC API v2.

    QC API v2 uses a timestamped SHA-256 hash of the API token,
    NOT plain Basic auth.
    """
    timestamp = f"{int(time())}"
    time_stamped_token = f"{api_token}:{timestamp}".encode("utf-8")
    hashed_token = sha256(time_stamped_token).hexdigest()
    authentication = f"{user_id}:{hashed_token}".encode("utf-8")
    authentication = b64encode(authentication).decode("ascii")
    return {
        "Authorization": f"Basic {authentication}",
        "Timestamp": timestamp,
    }


def _api_post(
    endpoint: str,
    user_id: str,
    api_token: str,
    data: dict[str, Any] | None = None,
    timeout: int = 60,
) -> dict[str, Any]:
    """Make an authenticated POST request to QC API v2."""
    url = f"{QC_BASE_URL}/{endpoint}"
    resp = requests.post(
        url,
        headers=_get_headers(user_id, api_token),
        json=data or {},
        timeout=timeout,
    )
    resp.raise_for_status()
    return resp.json()


def authenticate(user_id: str, api_token: str) -> bool:
    """Verify QC API credentials.

    Returns:
        True if authentication succeeds

    Raises:
        QuantConnectAuthError: if authentication fails
    """
    resp = _api_post("authenticate", user_id, api_token)
    if not resp.get("success"):
        raise QuantConnectAuthError(f"QC API authentication failed: {resp}")
    return True


def list_backtests(
    user_id: str,
    api_token: str,
    project_id: int,
) -> list[dict[str, Any]]:
    """List backtests for a project.

    Returns:
        list of backtest summary dicts (id, name, status, etc.)
    """
    resp = _api_post("backtests/read", user_id, api_token, {
        "projectId": project_id,
    })
    if not resp.get("success"):
        raise QuantConnectAPIError(f"Failed to list backtests: {resp.get('errors')}")
    return resp.get("backtests", [])


def get_backtest_info(
    user_id: str,
    api_token: str,
    project_id: int,
    backtest_id: str,
) -> dict[str, Any]:
    """Fetch backtest metadata and statistics.

    Returns:
        dict with keys: name, backtestId, backtestStart, backtestEnd,
        statistics, tradeableDates, etc.
    """
    resp = _api_post("backtests/read", user_id, api_token, {
        "projectId": project_id,
        "backtestId": backtest_id,
    })
    if not resp.get("success"):
        errors = resp.get("errors", [])
        raise QuantConnectAPIError(f"Failed to read backtest: {errors}")

    bt = resp.get("backtest", {})
    if not bt:
        raise QuantConnectNotFoundError(
            f"Backtest {backtest_id} not found in project {project_id}"
        )
    return bt


def get_chart(
    user_id: str,
    api_token: str,
    project_id: int,
    backtest_id: str,
    chart_name: str,
    start: int | None = None,
    end: int | None = None,
    count: int = 50000,
) -> dict[str, Any]:
    """Fetch chart data from a backtest via /backtests/chart/read.

    Common chart names: "Strategy Equity", "Benchmark", "Drawdown",
    "Portfolio Margin", "Assets Sales Volume", "Exposure", "Capacity".

    Args:
        start/end: Unix timestamps in SECONDS (not ms)
        count: max data points to return

    Returns:
        chart dict with 'name', 'chartType', 'series' keys
    """
    payload: dict[str, Any] = {
        "projectId": project_id,
        "backtestId": backtest_id,
        "name": chart_name,
        "count": count,
    }
    if start is not None:
        payload["start"] = start
    if end is not None:
        payload["end"] = end

    resp = _api_post("backtests/chart/read", user_id, api_token, payload)
    if not resp.get("success"):
        raise QuantConnectAPIError(
            f"Failed to read chart '{chart_name}': {resp.get('errors')}"
        )
    return resp["chart"]


# ── Parsing helpers ──────────────────────────────────────────────────


def parse_equity_chart(chart: dict[str, Any]) -> pd.Series:
    """Parse Strategy Equity chart into a daily equity Series.

    QC returns equity as [timestamp_seconds, open, high, low, close].
    We extract the daily close to build the equity curve.

    Returns:
        pd.Series with DatetimeIndex (UTC), values = daily close equity

    Raises:
        ValueError: if no equity values found
    """
    series = chart.get("series", {})
    equity_data = series.get("Equity", series.get("equity", {}))
    values = equity_data.get("values", [])

    if not values:
        raise ValueError("No equity values found in Strategy Equity chart")

    daily_close: dict[pd.Timestamp, float] = {}
    for v in values:
        if isinstance(v, (list, tuple)) and len(v) >= 5:
            # [timestamp_seconds, open, high, low, close]
            ts = pd.Timestamp(v[0], unit="s", tz="UTC")
            close = v[4]
            daily_close[ts.normalize()] = close
        elif isinstance(v, dict):
            ts = pd.Timestamp(v.get("x", v.get("time", 0)), unit="s", tz="UTC")
            close = v.get("y", v.get("close", v.get("value", 0)))
            daily_close[ts.normalize()] = close

    if not daily_close:
        raise ValueError("No parseable equity values found")

    equity = pd.Series(daily_close).sort_index()
    equity.index = pd.DatetimeIndex(equity.index, name="date")
    equity.name = "equity"
    return equity


def parse_returns_series(chart: dict[str, Any]) -> pd.Series | None:
    """Parse daily return series from chart if available.

    QC provides a "Return" series with [timestamp_seconds, return_pct].
    Returns may be in percentage (e.g. 2.5) or decimal (e.g. 0.025) form.
    We detect and normalise to decimal.

    Returns:
        pd.Series with DatetimeIndex, or None if not available
    """
    series = chart.get("series", {})
    for key in ("Return", "Daily Return", "return"):
        if key in series:
            values = series[key].get("values", [])
            if not values:
                continue

            returns: dict[pd.Timestamp, float] = {}
            for v in values:
                if isinstance(v, (list, tuple)) and len(v) >= 2:
                    ts = pd.Timestamp(v[0], unit="s", tz="UTC")
                    ret = v[1]
                    # QC returns percentages for this series (e.g. 2.5 = 2.5%)
                    if abs(ret) > 1:
                        ret = ret / 100
                    returns[ts.normalize()] = ret
                elif isinstance(v, dict):
                    ts = pd.Timestamp(v.get("x", 0), unit="s", tz="UTC")
                    ret = v.get("y", v.get("value", 0))
                    if abs(ret) > 1:
                        ret = ret / 100
                    returns[ts.normalize()] = ret

            if returns:
                s = pd.Series(returns).sort_index()
                s.index = pd.DatetimeIndex(s.index, name="date")
                s.name = "returns"
                return s
    return None


def parse_benchmark_chart(chart: dict[str, Any]) -> pd.Series | None:
    """Parse Benchmark chart into a daily benchmark returns Series."""
    series = chart.get("series", {})
    for skey, sdata in series.items():
        values = sdata.get("values", [])
        if not values:
            continue

        daily_vals: dict[pd.Timestamp, float] = {}
        for v in values:
            if isinstance(v, (list, tuple)) and len(v) >= 2:
                ts = pd.Timestamp(v[0], unit="s", tz="UTC")
                val = v[1] if len(v) == 2 else v[4]  # close for OHLC
                daily_vals[ts.normalize()] = val
            elif isinstance(v, dict):
                ts = pd.Timestamp(v.get("x", 0), unit="s", tz="UTC")
                daily_vals[ts.normalize()] = v.get("y", v.get("value", 0))

        if daily_vals:
            benchmark = pd.Series(daily_vals).sort_index()
            benchmark.index = pd.DatetimeIndex(benchmark.index, name="date")
            returns = benchmark.pct_change().dropna()
            returns.name = "benchmark_returns"
            return returns
    return None


# ── Main entry points ────────────────────────────────────────────────


def fetch_backtest(
    project_id: int,
    backtest_id: str,
    user_id: str | None = None,
    api_token: str | None = None,
    strategy_name: str | None = None,
    risk_target_annual_pct: float = 20.0,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, dict[str, Any], dict[str, Any]]:
    """Fetch a QC cloud backtest and extract all data.

    This is the low-level fetch that returns raw DataFrames and dicts,
    suitable for further processing or direct use.

    Args:
        project_id: QC project ID
        backtest_id: QC backtest ID
        user_id: QC user ID (or set env QC_USER_ID)
        api_token: QC API token (or set env QC_API_TOKEN)
        strategy_name: override strategy name (default: QC project name)
        risk_target_annual_pct: annual risk target for config

    Returns:
        tuple of:
            - portfolio_returns (Series)
            - instrument_pnl (DataFrame)
            - positions (DataFrame)
            - instrument_meta (dict[str, dict])
            - config_dict (dict for BacktestConfig)
    """
    from os import environ

    uid = user_id or environ.get("QC_USER_ID", "")
    token = api_token or environ.get("QC_API_TOKEN", "")

    if not uid or not token:
        raise ValueError(
            "QC credentials required. Pass user_id/api_token or set "
            "QC_USER_ID and QC_API_TOKEN environment variables."
        )

    # 1. Authenticate
    authenticate(uid, token)
    logger.info("QC API authenticated for user %s", uid)

    # 2. Fetch backtest metadata
    bt_info = get_backtest_info(uid, token, project_id, backtest_id)
    stats = bt_info.get("statistics", {})
    bt_name = bt_info.get("name", "unknown")
    name = strategy_name or bt_name

    logger.info(
        "Backtest: %s (%s to %s)",
        bt_name,
        bt_info.get("backtestStart"),
        bt_info.get("backtestEnd"),
    )

    # 3. Fetch equity chart
    equity_chart = get_chart(uid, token, project_id, backtest_id, "Strategy Equity")
    equity = parse_equity_chart(equity_chart)
    logger.info("Equity curve: %d days", len(equity))

    # Try to use the daily return series if available
    returns = parse_returns_series(equity_chart)
    if returns is not None and len(returns) > 1:
        portfolio_returns = returns
    else:
        # Compute from equity
        portfolio_returns = equity.pct_change().dropna()
        portfolio_returns.name = "returns"
        portfolio_returns.index.name = "date"

    # 4. Determine instruments
    # For single-instrument strategies, we infer from the algorithm
    # Multi-instrument would need per-instrument data from QC (future work)
    instruments = _infer_instruments(bt_info, stats)
    logger.info("Instruments: %s", instruments)

    # 5. Build instrument PnL
    # Without per-instrument data from QC, we proxy with equal-weight allocation
    n_instr = len(instruments)
    pnl_data = {instr: portfolio_returns.values / n_instr for instr in instruments}
    instrument_pnl = pd.DataFrame(pnl_data, index=portfolio_returns.index)
    instrument_pnl.index = pd.DatetimeIndex(instrument_pnl.index, name="date")

    # 6. Build positions (equal weight, always invested)
    pos_data = {instr: 1.0 / n_instr for instr in instruments}
    positions = pd.DataFrame(
        pos_data,
        index=pd.Index([0]),  # single row — constant allocation
    )
    # Expand to match returns dates
    positions = pd.DataFrame(
        {instr: [pos_data[instr]] * len(portfolio_returns) for instr in instruments},
        index=portfolio_returns.index,
    )
    positions.index = pd.DatetimeIndex(positions.index, name="date")

    # 7. Instrument metadata
    instrument_meta = {
        instr: {"code": instr, "asset_class": _guess_asset_class(instr)}
        for instr in instruments
    }

    # 8. Config
    start_equity = _parse_float(
        stats.get("Start Equity", stats.get("Starting Equity", "100000"))
    )
    start_date = portfolio_returns.index[0].date()
    end_date = portfolio_returns.index[-1].date()

    config_dict = {
        "experiment_id": f"qc-{name.lower().replace(' ', '-')}_{project_id}",
        "strategy_name": name,
        "engine": "quantconnect-lean",
        "instrument_universe": instruments,
        "start_date": start_date,
        "end_date": end_date,
        "capital": start_equity,
        "risk_target_annual_pct": risk_target_annual_pct,
        "data_sources": ["quantconnect-cloud"],
        "config_overrides": {
            "project_id": project_id,
            "backtest_id": backtest_id,
            "qc_statistics": {
                k: stats[k]
                for k in [
                    "Net Profit", "Sharpe Ratio", "Sortino Ratio", "Drawdown",
                    "Compounding Annual Return", "Total Orders", "Win Rate",
                    "Alpha", "Beta", "Annual Standard Deviation",
                    "Total Fees", "Probabilistic Sharpe Ratio",
                ]
                if k in stats
            },
        },
    }

    return portfolio_returns, instrument_pnl, positions, instrument_meta, config_dict


def fetch_backtest_data(
    project_id: int,
    backtest_id: str,
    user_id: str | None = None,
    api_token: str | None = None,
    strategy_name: str | None = None,
    risk_target_annual_pct: float = 20.0,
) -> tuple[Any, Any]:
    """Fetch a QC cloud backtest and return BacktestData + BacktestConfig.

    This is the high-level entry point that returns validated model objects,
    ready for write_experiment_dir() or BacktestReport.generate().

    Args:
        project_id: QC project ID
        backtest_id: QC backtest ID
        user_id: QC user ID (or set env QC_USER_ID)
        api_token: QC API token (or set env QC_API_TOKEN)
        strategy_name: override strategy name
        risk_target_annual_pct: annual risk target for config

    Returns:
        tuple of (BacktestData, BacktestConfig)

    Example:
        data, config = fetch_backtest_data(30522360, "abc123...")
        write_experiment_dir(Path("/store/backtests/my_exp"), data, config, {})
    """
    from backtest_report.models import BacktestConfig, BacktestData, InstrumentMeta

    (
        portfolio_returns,
        instrument_pnl,
        positions,
        instrument_meta_raw,
        config_dict,
    ) = fetch_backtest(
        project_id=project_id,
        backtest_id=backtest_id,
        user_id=user_id,
        api_token=api_token,
        strategy_name=strategy_name,
        risk_target_annual_pct=risk_target_annual_pct,
    )

    # Build validated model objects
    config = BacktestConfig.model_validate(config_dict)

    instrument_meta = {
        code: InstrumentMeta.model_validate(meta)
        for code, meta in instrument_meta_raw.items()
    }

    # Try to fetch benchmark
    uid = user_id or __import__("os").environ.get("QC_USER_ID", "")
    token = api_token or __import__("os").environ.get("QC_API_TOKEN", "")
    benchmark_returns = None
    try:
        bench_chart = get_chart(uid, token, project_id, backtest_id, "Benchmark")
        benchmark_returns = parse_benchmark_chart(bench_chart)
        if benchmark_returns is not None:
            logger.info("Benchmark: %d days", len(benchmark_returns))
    except Exception as e:
        logger.warning("Could not fetch benchmark: %s", e)

    data = BacktestData(
        portfolio_returns=portfolio_returns,
        instrument_pnl=instrument_pnl,
        positions=positions,
        instrument_meta=instrument_meta,
        benchmark_returns=benchmark_returns,
    )

    return data, config


# ── CLI convenience ──────────────────────────────────────────────────


def fetch_and_write(
    project_id: int,
    backtest_id: str,
    output_dir: Path,
    user_id: str | None = None,
    api_token: str | None = None,
    strategy_name: str | None = None,
) -> Path:
    """Fetch a QC backtest and write to an experiment directory.

    Combines fetch_backtest_data() + write_experiment_dir() + checksums.

    Args:
        project_id: QC project ID
        backtest_id: QC backtest ID
        output_dir: base directory (experiment dir created inside)
        user_id: QC user ID
        api_token: QC API token
        strategy_name: strategy name override

    Returns:
        Path to the created experiment directory
    """
    from backtest_report.persist import compute_checksum, write_experiment_dir

    data, config = fetch_backtest_data(
        project_id=project_id,
        backtest_id=backtest_id,
        user_id=user_id,
        api_token=api_token,
        strategy_name=strategy_name,
    )

    # Create experiment dir
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    slug = config.strategy_name.lower().replace(" ", "-")
    experiment_id = f"{slug}_{timestamp}"
    exp_dir = Path(output_dir) / experiment_id

    # Write first, then compute checksums
    write_experiment_dir(exp_dir, data, config, data_checksums={})

    # Compute checksums and re-write
    checksums = {}
    for fname in ["portfolio_returns.parquet", "instrument_pnl.parquet", "positions.parquet"]:
        fpath = exp_dir / fname
        if fpath.exists():
            checksums[fname] = compute_checksum(fpath)

    write_experiment_dir(exp_dir, data, config, data_checksums=checksums)
    logger.info("Experiment written to: %s", exp_dir)

    return exp_dir


# ── Helpers ──────────────────────────────────────────────────────────


_ASSET_CLASS_MAP: dict[str, str] = {
    "equity": "equity",
    "future": "future",
    "forex": "fx",
    "crypto": "crypto",
    "option": "option",
    "index": "index",
    "cfd": "cfd",
}


def _guess_asset_class(symbol: str) -> str:
    """Guess asset class from a QC symbol or security type hint."""
    s = symbol.upper()
    if s in ("SPY", "QQQ", "IWM", "AAPL", "MSFT", "GOOG"):
        return "equity"
    # Common futures patterns
    for prefix in ("ES", "NQ", "CL", "GC", "ZB", "ZN", "ZF", "ZW", "ZC", "ZS"):
        if s.startswith(prefix):
            return "future"
    # FX pairs
    for pair in ("EURUSD", "GBPUSD", "USDJPY", "AUDUSD"):
        if s.startswith(pair[:3]):
            return "fx"
    return "equity"  # default


def _infer_instruments(bt_info: dict, stats: dict) -> list[str]:
    """Infer traded instruments from backtest metadata.

    QC API doesn't always provide a clean instrument list in the backtest
    summary. We try several approaches.
    """
    # Try from statistics
    lowest = stats.get("Lowest Capacity Asset", "")
    if isinstance(lowest, str) and lowest.strip():
        # e.g. "SPY R735QTJ8XC9X" → extract the symbol
        parts = lowest.strip().split()
        if parts:
            return [parts[0]]

    # Try from orders (if available)
    orders = bt_info.get("orders", [])
    if orders:
        symbols = set()
        for order in orders:
            sym = order.get("symbol", {}).get("value", "")
            if sym:
                symbols.add(sym)
        if symbols:
            return sorted(symbols)

    # Default: return generic
    return ["UNKNOWN"]


def _parse_float(value: str | float) -> float:
    """Parse a string value to float, stripping currency symbols and commas."""
    if isinstance(value, (int, float)):
        return float(value)
    return float(str(value).replace(",", "").replace("$", "").strip())
