---
title: Backtest Report — Implementation Specification
domain: trading
type: infra
created: 2026-04-19
updated: 2026-04-19 23:57:00
sources:
  - wiki/trading/infra/backtest-reporting.md
  - wiki/trading/infra/pysystemtrade.md
tags: [reporting, backtest, pdf, quantstats, specification, implementation]
status: draft
---

# Backtest Report — Implementation Specification

> **Repo**: `backtest-report` (to be created on Forgejo)
> **Language**: Python 3.10+
> **License**: MIT
> **Status**: Draft — ready for implementation

## 1. Overview

A standalone Python package that generates standardised, reproducible PDF backtest reports from persisted pysystemtrade `System` objects (or plain pandas DataFrames for engine-agnostic use). Combines QuantStats portfolio-level analytics with custom per-instrument attribution, producing self-contained tear sheets.

**Design principles:**

1. **Engine-agnostic core** — the reporting pipeline does not import pysystemtrade at runtime. It accepts pre-extracted DataFrames (returns, positions, instruments) as its primary input. A thin adapter layer converts pysystemtrade `System` objects into these DataFrames.
2. **Reproducible** — every report embeds its config snapshot, data checksums, and git commit so any historical report can be regenerated.
3. **Composable sections** — each report section is a self-contained module that produces an HTML fragment. Sections can be added, removed, or reordered without touching others.
4. **No data in git** — `System` pickles and Parquet archives live on the hc4t server only. The repo contains code and templates.

---

## 2. Repository Structure

```
backtest-report/
├── pyproject.toml
├── README.md
├── LICENSE                          # MIT
├── Makefile                         # lint, test, build, install
├── src/
│   └── backtest_report/
│       ├── __init__.py              # version, public API re-exports
│       ├── report.py                # BacktestReport orchestrator
│       ├── models.py                # Pydantic data models (config, metadata, sections)
│       ├── portfolio.py             # QuantStats integration → HTML fragment
│       ├── instrument.py            # Per-instrument analysis → HTML fragment
│       ├── attribution.py           # Return attribution (by instrument, sector, group)
│       ├── positions.py             # Position heatmap + snapshot tables
│       ├── render.py                # Jinja2 template assembly → full HTML → PDF via WeasyPrint
│       ├── persist.py               # Read/write experiment directories on hc4t
│       ├── adapters/
│       │   ├── __init__.py
│       │   └── pysystemtrade.py     # System → BacktestData adapter (optional dependency)
│       └── templates/
│           ├── report.html          # Jinja2 master template
│           ├── sections/
│           │   ├── header.html
│           │   ├── portfolio.html
│           │   ├── monthly_returns.html
│           │   ├── portfolio_stats.html
│           │   ├── rolling_stats.html
│           │   ├── instrument_pnl.html
│           │   ├── instrument_table.html
│           │   ├── position_snapshot.html
│           │   ├── attribution.html
│           │   └── appendix.html
│           └── style.css
├── tests/
│   ├── conftest.py                  # Fixtures: sample BacktestData, mock System
│   ├── test_report.py
│   ├── test_portfolio.py
│   ├── test_instrument.py
│   ├── test_attribution.py
│   ├── test_positions.py
│   ├── test_render.py
│   ├── test_persist.py
│   ├── test_pysystemtrade_adapter.py
│   └── fixtures/
│       ├── sample_portfolio_returns.parquet
│       ├── sample_instrument_returns.parquet
│       ├── sample_positions.parquet
│       └── sample_meta.json
└── docs/
    ├── architecture.md               # This spec (checked in as docs, not as wiki)
    └── usage.md                      # Quick-start guide
```

---

## 3. Data Models (`models.py`)

All data models use **Pydantic v2** for validation and serialisation.

### 3.1 `BacktestConfig`

```python
class BacktestConfig(BaseModel):
    experiment_id: str                # e.g. "sg-trend-proxy_20260419_153000"
    strategy_name: str                 # e.g. "SG Trend Proxy"
    engine: str = "pysystemtrade"      # or "quantconnect", "custom"
    engine_version: str = ""           # e.g. "1.8.0"
    python_version: str = ""
    git_commit: str = ""
    instrument_universe: list[str]     # e.g. ["EDOLLAR", "US10", "GOLD", ...]
    start_date: date
    end_date: date
    capital: float                     # initial capital in account currency
    currency: str = "USD"
    risk_target_annual_pct: float      # e.g. 20.0
    data_sources: list[str] = []       # e.g. ["pysystemtrade-csv", "eodhd"]
    config_overrides: dict = {}        # any non-default config values
```

### 3.2 `BacktestData`

The engine-agnostic input to the report pipeline. This is what `BacktestReport` actually consumes — no pysystemtrade imports required.

```python
class BacktestData(BaseModel):
    # Portfolio-level daily returns, zero-indexed by date
    portfolio_returns: pd.Series       # DateIndex → float (daily % returns)

    # Per-instrument daily P&L in account currency
    instrument_pnl: pd.DataFrame       # DateIndex × instrument_code → float

    # Per-instrument position sizes (number of contracts or notional)
    positions: pd.DataFrame             # DateIndex × instrument_code → float

    # Instrument metadata (sector, group, asset class for attribution)
    instrument_meta: dict[str, InstrumentMeta]

    # Optional: per-instrument daily returns (for Sharpe/DD per instrument)
    instrument_returns: dict[str, pd.Series] = {}

class InstrumentMeta(BaseModel):
    code: str                           # e.g. "EDOLLAR"
    name: str = ""                      # e.g. "Eurodollar"
    sector: str = ""                    # e.g. "Rates"
    group: str = ""                     # e.g. "STIR"
    asset_class: str = ""               # e.g. "Fixed Income"
    exchange: str = ""                   # e.g. "CME"
    point_value: float = 1.0
    currency: str = "USD"
```

### 3.3 `BacktestMeta`

```python
class BacktestMeta(BaseModel):
    config: BacktestConfig
    generated_at: datetime
    report_version: str                 # backtest_report package version
    data_checksums: dict[str, str] = {} # filename → MD5
    notes: str = ""
```

### 3.4 Section Output

Each section module returns a `SectionOutput`:

```python
class SectionOutput(BaseModel):
    section_id: str                     # e.g. "portfolio_pnl"
    html: str                           # rendered HTML fragment
    figures: dict[str, str] = {}        # figure_id → base64-encoded PNG
    tables: dict[str, pd.DataFrame] = {} # table_id → DataFrame (for appendix export)
```

---

## 4. Core API (`report.py`)

### 4.1 `BacktestReport` class

```python
class BacktestReport:
    """
    Main entry point. Orchestrates section generation and PDF rendering.

    Usage:
        data = BacktestData(...)
        meta = BacktestMeta(...)
        report = BacktestReport(data=data, meta=meta)
        pdf_path = report.generate()          # → Path to PDF
        html_path = report.generate(fmt="html") # → Path to HTML
        report.generate(output_dir="/store/backtests/sg-trend-proxy_20260419_153000/")
    """

    def __init__(
        self,
        data: BacktestData,
        meta: BacktestMeta,
        sections: list[str] | None = None,    # None = all sections
        template_dir: Path | None = None,     # override template lookup
    ): ...

    def generate(
        self,
        output_dir: Path | str | None = None,
        fmt: str = "pdf",                     # "pdf" or "html"
        filename: str | None = None,          # default: f"{meta.config.experiment_id}_report.{fmt}"
    ) -> Path:
        """
        Generate the report.

        1. Run each section module to get SectionOutput.
        2. Assemble all HTML fragments + figures into the master template.
        3. Render Jinja2 template with all context.
        4. If fmt="pdf", convert HTML → PDF via WeasyPrint.
        5. Write to output_dir / filename.
        6. If output_dir is on hc4t (starts with /store/ or ssh path), persist via persist.py.
        7. Return Path to generated file.
        """
        ...

    # Section registry — maps section_id to callable
    SECTION_REGISTRY: dict[str, Callable] = {
        "header": sections.render_header,
        "portfolio_pnl": portfolio.render_portfolio_pnl,
        "monthly_returns": portfolio.render_monthly_returns,
        "portfolio_stats": portfolio.render_portfolio_stats,
        "rolling_stats": portfolio.render_rolling_stats,
        "instrument_pnl": instrument.render_instrument_pnl,
        "instrument_table": instrument.render_instrument_table,
        "position_snapshot": positions.render_position_snapshot,
        "attribution": attribution.render_attribution,
        "appendix": sections.render_appendix,
    }
```

### 4.2 Convenience Functions

```python
def generate_report(
    experiment_dir: Path | str,
    sections: list[str] | None = None,
    fmt: str = "pdf",
) -> Path:
    """
    Load data from an experiment directory and generate report.

    Reads: experiment_dir/system.pkl (via adapter), experiment_dir/config.yaml,
           experiment_dir/meta.json
    Writes: experiment_dir/report.pdf (or .html)
    """

def from_pysystemtrade(
    system_path: Path | str,   # path to system.pkl
    config_path: Path | str,   # path to config.yaml
    meta_path: Path | str,     # path to meta.json
    sections: list[str] | None = None,
) -> BacktestReport:
    """
    High-level: load a persisted pysystemtrade System object and return
    a ready-to-generate BacktestReport.

    This is the only code path that imports pysystemtrade (optional dep).
    """
```

---

## 5. Section Specifications

Each section is a pure function with signature:

```python
def render_<section_id>(data: BacktestData, meta: BacktestMeta) -> SectionOutput
```

### 5.1 Header (`sections/header.html`)

**Data source:** `meta.config`

| Field | Display |
|-------|---------|
| experiment_id | Large, top-left |
| strategy_name | Subtitle |
| engine + version | Small grey text |
| Date range | `start_date → end_date` |
| Capital | Formatted with currency symbol |
| Risk target | `XX% annual` |
| Generated at | Timestamp, small grey |
| Git commit | Short hash, monospace |

### 5.2 Portfolio PnL (`portfolio.py` → `sections/portfolio.html`)

**Data source:** `data.portfolio_returns`

- Cumulative return curve (equity curve starting at 1.0)
- Underwater drawdown plot (percentage drawdown from peak)
- Both plots generated by QuantStats `qs.reports.html()`, but we extract only the relevant HTML fragments and embed in our template (not the full QuantStats page)

**Implementation:**
1. Call `qs.reports.html(returns, output=None, title="Portfolio")` with `data.portfolio_returns`
2. Parse the returned HTML to extract: cumulative return chart, drawdown chart
3. Apply custom CSS class `br-portfolio-pnl` and `br-portfolio-drawdown`
4. Return as base64-encoded PNG images in `SectionOutput.figures`

**Custom styling override:** QuantStats default dark theme → override to light background, consistent font stack (`Inter, -apple-system, sans-serif`), muted grid lines.

### 5.3 Monthly Returns (`portfolio.py` → `sections/monthly_returns.html`)

**Data source:** `data.portfolio_returns`

- Monthly return table: rows = years, columns = months + full-year total
- Cells coloured: green (positive, intensity by magnitude), red (negative, intensity by magnitude), grey (zero)
- Worst month highlighted; best month highlighted
- Generated by QuantStats, extracted and re-styled

### 5.4 Portfolio Stats (`portfolio.py` → `sections/portfolio_stats.html`)

**Data source:** `data.portfolio_returns`

Key metrics table (2 columns: metric, value):

| Metric | Computation |
|--------|-------------|
| Total Return | `cumulative_returns[-1] - 1` |
| CAGR | `((1 + total_return) ** (252/n_days) - 1)` |
| Annualised Vol | `returns.std() * sqrt(252)` |
| Sharpe Ratio | `annualised_return / annualised_vol` |
| Sortino Ratio | `annualised_return / downside_deviation` |
| Calmar Ratio | `CAGR / abs(max_drawdown)` |
| Max Drawdown | `min(cumulative_returns / cumulative_max - 1)` |
| Max DD Duration | longest period below peak (calendar days) |
| Win Rate | `% of positive return days` |
| Profit Factor | `sum(positive_returns) / abs(sum(negative_returns))` |
| Avg Win / Avg Loss | `mean(positive) / abs(mean(negative))` |
| Skewness | `returns.skew()` |
| Kurtosis | `returns.kurtosis()` |
| Best Day | `returns.max()` |
| Worst Day | `returns.min()` |

### 5.5 Rolling Stats (`portfolio.py` → `sections/rolling_stats.html`)

**Data source:** `data.portfolio_returns`

- Rolling 1-year Sharpe ratio (252-day window)
- Rolling 3-year annualised return (756-day window)
- Beta to benchmark (if benchmark provided in config; otherwise SPY buy-and-hold)

Plots as matplotlib figures → base64 PNG.

### 5.6 Instrument PnL (`instrument.py` → `sections/instrument_pnl.html`)

**Data source:** `data.instrument_pnl`

- **Small multiples grid**: 4-column layout of per-instrument cumulative PnL curves
- Each subplot: instrument code + name, cumulative PnL line, Sharpe annotation
- Instruments sorted by total PnL (best → worst)
- Grid fills left→right, top→bottom
- Matplotlib figure → base64 PNG

**Sizing:** Each subplot approximately 3" wide × 2" tall. Max 20 instruments per page; paginate if more.

### 5.7 Instrument Table (`instrument.py` → `sections/instrument_table.html`)

**Data source:** `data.instrument_pnl`, `data.positions`, `data.instrument_returns`

Per-instrument statistics table (sortable by any column):

| Column | Computation |
|--------|-------------|
| Instrument | code (name) |
| Sharpe | `annualised_return / annualised_vol` per instrument |
| P&L | cumulative PnL in account currency |
| Max DD | max drawdown for that instrument's PnL curve |
| Avg Position | `positions[instrument].mean()` (absolute value) |
| Turnover | `positions[instrument].diff().abs().sum() / len(positions)` |
| Win Rate | `% of days with positive PnL` |

Rendered as an HTML `<table>` with `br-instrument-table` class. Alternating row colours. Column headers clickable for sort (static PDF → pre-sorted by P&L descending).

### 5.8 Position Snapshot (`positions.py` → `sections/position_snapshot.html`)

**Data source:** `data.positions`

- **Heatmap**: x-axis = time (sampled at weekly or monthly frequency depending on date range), y-axis = instruments, colour = position size (diverging colourmap: red = short, white = flat, blue = long)
- Matplotlib `imshow` or `pcolormesh` → base64 PNG
- Colour bar legend on the right
- Instruments on y-axis sorted by average absolute position size (most active at top)

### 5.9 Attribution (`attribution.py` → `sections/attribution.html`)

**Data source:** `data.instrument_pnl`, `data.instrument_meta`

**Two views:**

1. **By instrument**: Stacked bar chart (or horizontal bars) showing each instrument's contribution to portfolio return per period (monthly). Top 10 instruments individually, rest grouped as "Other".
2. **By sector/group**: Aggregate P&L by `instrument_meta.sector` and `instrument_meta.group`. Stacked bars by sector per month.

Charts as matplotlib → base64 PNG.

### 5.10 Appendix (`sections/appendix.html`)

**Data source:** `meta.config`, `meta.data_checksums`

- Full config YAML dump (syntax-highlighted in a `<pre>` block with monospace font)
- Data checksums table (filename → MD5)
- Python environment: `python_version`, `engine_version`, package versions
- Git commit short hash

---

## 6. PySystemTrade Adapter (`adapters/pysystemtrade.py`)

This is the **only** module that imports pysystemtrade. It is an **optional dependency** — the rest of the package works without it.

```python
def extract_backtest_data(system: "System") -> BacktestData:
    """
    Extract all data from a pysystemtrade System object into
    engine-agnostic BacktestData.

    Steps:
    1. Get instrument list from system.get_instrument_list()
    2. Get portfolio returns from system.accounts.portfolio().returns()
    3. For each instrument:
       a. PnL: system.accounts.get_instrument_pnl(instrument)
       b. Positions: system.positionSize.get_positions(instrument)
       c. Returns: system.accounts.get_instrument_returns(instrument)
    4. Get instrument metadata from system.config or external mapping
    5. Return BacktestData with all fields populated
    """

def extract_backtest_config(system: "System", config_path: Path) -> BacktestConfig:
    """
    Build BacktestConfig from System config + external config file.

    Reads: instrument_universe, start/end dates, capital, risk target,
           data sources, config overrides.
    """

def load_system(pickle_path: Path) -> "System":
    """
    Load a pickled System object. Handles pysystemtrade version
    compatibility warnings and deserialisation.
    """
```

**Instrument metadata mapping:** pysystemtrade uses instrument codes like `"EDOLLAR"`, `"US10"`, `"GOLD"`. The adapter includes a built-in mapping file (`instrument_map.yaml`) that maps codes to `InstrumentMeta` (name, sector, group, asset_class). This file is maintained in the repo and can be overridden by the user.

### 6.1 `instrument_map.yaml`

```yaml
# Maps pysystemtrade instrument codes to metadata
EDOLLAR:
  name: Eurodollar
  sector: Rates
  group: STIR
  asset_class: Fixed Income
  exchange: CME
  point_value: 25.0
  currency: USD

US10:
  name: US 10-Year Note
  sector: Rates
  group: Bonds
  asset_class: Fixed Income
  exchange: CBOT
  point_value: 1000.0
  currency: USD

GOLD:
  name: Gold
  sector: Commodities
  group: Metals
  asset_class: Commodities
  exchange: COMEX
  point_value: 100.0
  currency: USD

# ... extended as universe grows
```

---

## 7. Persistence Layer (`persist.py`)

Handles reading and writing experiment directories. Works both locally and via SSH to hc4t.

### 7.1 Local filesystem

```python
def read_experiment_dir(path: Path) -> tuple[BacktestData, BacktestMeta]:
    """
    Read a local experiment directory:
      - system.pkl → BacktestData (via adapter)
      - config.yaml → BacktestConfig
      - meta.json → BacktestMeta supplement
      - data_checksums.json → included in meta
    """

def write_experiment_dir(
    path: Path,
    system: "System",
    config: BacktestConfig,
    data_checksums: dict[str, str],
) -> None:
    """
    Write experiment directory:
      - system.pkl
      - config.yaml
      - data_checksums.json
      - meta.json (auto-generated)
    """
```

### 7.2 Remote (hc4t server)

```python
def read_remote_experiment(
    experiment_id: str,
    host: str = "quant@hc4t.sheldenkar.com",
    remote_base: str = "/store/backtests",
) -> tuple[BacktestData, BacktestMeta]:
    """
    SCP experiment files from remote server to a local temp directory,
    then read locally. Uses subprocess + scp for simplicity.
    """

def write_remote_report(
    pdf_path: Path,
    experiment_id: str,
    host: str = "quant@hc4t.sheldenkar.com",
    remote_base: str = "/store/backtests",
) -> None:
    """
    SCP generated report.pdf to remote experiment directory.
    """
```

### 7.3 Naming Convention

```
<strategy_slug>_<YYYYMMDD_HHMMSS>

Examples:
  sg-trend-proxy_20260419_153000
  ewmac-trend_20260420_090000
  carry-standalone_20260421_110000
```

### 7.4 Directory Structure (on hc4t)

```
/store/backtests/
├── sg-trend-proxy_20260419_153000/
│   ├── system.pkl
│   ├── config.yaml
│   ├── data_checksums.json
│   ├── meta.json
│   └── report.pdf
├── ewmac-trend_20260420_090000/
│   ├── system.pkl
│   ├── config.yaml
│   ├── data_checksums.json
│   ├── meta.json
│   └── report.pdf
└── ...
```

**Parquet export (optional):** When `--export-parquet` flag is used, also write:
```
├── portfolio_returns.parquet
├── instrument_pnl.parquet
├── positions.parquet
└── instrument_meta.json
```

---

## 8. Rendering Pipeline (`render.py`)

### 8.1 Template Assembly

```python
def assemble_html(
    sections: dict[str, SectionOutput],
    meta: BacktestMeta,
    template_dir: Path | None = None,
) -> str:
    """
    1. Load Jinja2 environment from templates/
    2. Render report.html with:
       - meta (config, timestamps, etc.)
       - sections (dict of section_id → html fragment)
       - figures (dict of figure_id → base64 PNG data URIs)
    3. Return complete HTML string
    """
```

### 8.2 PDF Generation

```python
def html_to_pdf(html: str, output_path: Path) -> Path:
    """
    Convert HTML to PDF using WeasyPrint.

    Settings:
    - Page size: A4
    - Margins: 15mm all sides
    - Header: experiment_id + page number (right-aligned)
    - Footer: "Generated by backtest-report v{version} | {timestamp}"
    - CSS: load from templates/style.css, embed all fonts and images
    - DPI: 150 for rasterised matplotlib figures
    """
```

### 8.3 Template Structure

`report.html` is a Jinja2 master template:

```html
<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <title>{{ meta.config.experiment_id }} — Backtest Report</title>
    <style>{% include "style.css" %}</style>
</head>
<body>
    {% if sections.header %}{{ sections.header.html | safe }}{% endif %}

    <div class="br-page-break"></div>
    {% if sections.portfolio_pnl %}{{ sections.portfolio_pnl.html | safe }}{% endif %}

    <div class="br-page-break"></div>
    {% if sections.monthly_returns %}{{ sections.monthly_returns.html | safe }}{% endif %}

    <div class="br-page-break"></div>
    {% if sections.portfolio_stats %}{{ sections.portfolio_stats.html | safe }}{% endif %}

    <div class="br-page-break"></div>
    {% if sections.rolling_stats %}{{ sections.rolling_stats.html | safe }}{% endif %}

    <div class="br-page-break"></div>
    {% if sections.instrument_pnl %}{{ sections.instrument_pnl.html | safe }}{% endif %}

    <div class="br-page-break"></div>
    {% if sections.instrument_table %}{{ sections.instrument_table.html | safe }}{% endif %}

    <div class="br-page-break"></div>
    {% if sections.position_snapshot %}{{ sections.position_snapshot.html | safe }}{% endif %}

    <div class="br-page-break"></div>
    {% if sections.attribution %}{{ sections.attribution.html | safe }}{% endif %}

    <div class="br-page-break"></div>
    {% if sections.appendix %}{{ sections.appendix.html | safe }}{% endif %}
</body>
</html>
```

Each section partial (e.g. `sections/portfolio.html`) receives its data and figures via Jinja2 context variables.

---

## 9. Styling (`templates/style.css`)

### 9.1 Design System

```css
:root {
    --br-font-body: 'Inter', -apple-system, 'Segoe UI', sans-serif;
    --br-font-mono: 'JetBrains Mono', 'Fira Code', monospace;
    --br-font-data: 'Inter', -apple-system, sans-serif;

    --br-col-bg: #ffffff;
    --br-col-text: #1a1a1a;
    --br-col-muted: #6b7280;
    --br-col-border: #e5e7eb;

    --br-col-positive: #10b981;    /* green - positive returns */
    --br-col-negative: #ef4444;    /* red - negative returns */
    --br-col-neutral: #6b7280;    /* grey - zero/flat */

    --br-col-header: #111827;      /* dark header bar */
    --br-col-header-text: #f9fafb;

    --br-col-table-stripe: #f9fafb;
    --br-col-table-hover: #f3f4f6;

    --br-spacing-xs: 4px;
    --br-spacing-sm: 8px;
    --br-spacing-md: 16px;
    --br-spacing-lg: 24px;
    --br-spacing-xl: 32px;

    --br-page-width: 210mm;        /* A4 */
    --br-page-margin: 15mm;
}
```

### 9.2 Typography

- **Headers**: Inter, 600 weight
- **Body**: Inter, 400 weight, 10pt, line-height 1.5
- **Data tables**: Inter, 400 weight, 8pt, line-height 1.3
- **Code/config dumps**: JetBrains Mono, 400 weight, 7.5pt

### 9.3 Print Rules

- Page breaks between major sections (`br-page-break`)
- No orphan headers (keep with next content)
- Figure captions below figures
- Tables don't split across pages when possible (`page-break-inside: avoid`)

---

## 10. CLI Interface

The package installs a `backtest-report` CLI command:

```bash
# Generate report from a local experiment directory
backtest-report generate /path/to/experiment_dir

# Generate from a remote experiment on hc4t
backtest-report generate --remote sg-trend-proxy_20260419_153000

# Specify output format
backtest-report generate /path/to/experiment_dir --format html

# Generate from raw DataFrames (no System object)
backtest-report generate \
    --portfolio-returns returns.parquet \
    --instrument-pnl pnl.parquet \
    --positions positions.parquet \
    --meta meta.json \
    --output-dir ./reports/

# List available sections
backtest-report sections

# Validate an experiment directory
backtest-report validate /path/to/experiment_dir

# Export System object to Parquet (for archival)
backtest-report export-parquet /path/to/experiment_dir
```

### 10.1 Argument Details

```
backtest-report generate [PATH] [OPTIONS]

Arguments:
  PATH                    Local experiment directory containing
                          system.pkl, config.yaml, meta.json

Options:
  --remote EXPERIMENT_ID  Pull from hc4t server instead of local path
  --host TEXT             Remote host (default: quant@hc4t.sheldenkar.com)
  --remote-base TEXT      Remote base path (default: /store/backtests)
  --sections TEXT         Comma-separated section IDs to include
                          (default: all)
  --format TEXT           Output format: pdf, html (default: pdf)
  --output-dir PATH       Output directory (default: experiment directory)
  --filename TEXT         Output filename (default: auto-generated)
  --export-parquet        Also export DataFrames as Parquet files
  --verbose               Log section generation progress

Raw DataFrame options (mutually exclusive with PATH):
  --portfolio-returns PATH   Parquet/CSV file with portfolio returns series
  --instrument-pnl PATH     Parquet/CSV file with instrument PnL DataFrame
  --positions PATH           Parquet/CSV file with positions DataFrame
  --meta PATH                JSON file with BacktestMeta
```

---

## 11. Dependencies

### 11.1 Core (required)

| Package | Version | Purpose |
|---------|---------|---------|
| python | ≥3.10 | Minimum runtime |
| pandas | ≥2.0 | DataFrame handling |
| numpy | ≥1.24 | Numerical computation |
| matplotlib | ≥3.7 | Figure generation |
| quantstats | ≥0.0.62 | Portfolio analytics |
| jinja2 | ≥3.1 | Template rendering |
| weasyprint | ≥60 | HTML → PDF |
| pydantic | ≥2.0 | Data model validation |
| pyyaml | ≥6.0 | Config file handling |

### 11.2 Optional

| Package | Version | Purpose |
|---------|---------|---------|
| pysystemtrade | ≥1.8 | System object adapter (optional) |
| paramiko | ≥3.0 | SSH/SCP for remote experiments (optional) |
| pyarrow | ≥12.0 | Parquet read/write (optional, faster than CSV) |

### 11.3 Dev dependencies

| Package | Version | Purpose |
|---------|---------|---------|
| pytest | ≥7.0 | Testing |
| pytest-cov | ≥4.0 | Coverage |
| ruff | ≥0.1 | Linting + formatting |
| mypy | ≥1.5 | Type checking |

---

## 12. Testing Strategy

### 12.1 Unit Tests

Each module has corresponding unit tests in `tests/`:

- `test_portfolio.py` — portfolio metrics computation, QuantStats fragment extraction
- `test_instrument.py` — per-instrument PnL curves, small multiples layout
- `test_attribution.py` — sector/group aggregation, top-N + "Other" grouping
- `test_positions.py` — heatmap generation, sampling frequency
- `test_render.py` — template assembly, PDF generation (snapshot testing)
- `test_persist.py` — experiment directory read/write, naming validation
- `test_pysystemtrade_adapter.py` — System → BacktestData extraction (mocked System)
- `test_report.py` — end-to-end: BacktestReport with sample data → PDF file

### 12.2 Test Fixtures

`tests/fixtures/` contains:

- `sample_portfolio_returns.parquet` — 5 years of synthetic daily returns (Sharpe ~1.0, 15% vol)
- `sample_instrument_returns.parquet` — 10 instruments, correlated with portfolio
- `sample_positions.parquet` — realistic position sizes
- `sample_meta.json` — complete BacktestMeta example

**How to generate fixtures:** A `scripts/generate_fixtures.py` script creates synthetic but realistic backtest data using numpy (random walk with drift, controlled correlation structure).

### 12.3 Integration Test

```python
def test_end_to_end_report_generation():
    """Generate a complete PDF from fixture data and verify:
    1. PDF file is created and non-empty
    2. PDF contains expected section headers
    3. All figures are embedded
    4. Config appendix is included
    """
```

### 12.4 Snapshot Testing

For PDF output, we don't binary-diff. Instead:
1. Generate HTML output
2. Assert HTML contains expected section markers
3. Assert all `data:image/png;base64,...` figure embeddings exist
4. Assert key metric values appear in the HTML (Sharpe, MaxDD, etc.)

---

## 13. Error Handling

### 13.1 Missing Data

- If an instrument has no position data, the instrument PnL and position sections skip it gracefully
- If `instrument_meta` is incomplete, default sector/group to `"Unknown"`
- If `instrument_returns` dict is empty, compute approximate returns from PnL

### 13.2 Short History

- If backtest period < 1 year: rolling stats sections show a warning banner instead of a chart
- If < 30 days: report still generates but header shows `"⚠ Short history (N days)"`

### 13.3 QuantStats Failures

- Wrap QuantStats calls in try/except
- On failure: generate a minimal text-based section with the error message
- Never let a QuantStats failure prevent the entire report from generating

### 13.4 Remote Access Failures

- If SCP to hc4t fails: clear error message with connection troubleshooting hints
- If `system.pkl` is corrupt or incompatible pysystemtrade version: error message with version info
- If required file is missing from experiment directory: list which files were found vs expected

---

## 14. Configuration Override

Users can override report behaviour via a `.backtest-report.yaml` file or CLI flags:

```yaml
# .backtest-report.yaml (in experiment directory or home directory)
report:
  sections:
    - header
    - portfolio_pnl
    - portfolio_stats
    - instrument_pnl
    - instrument_table
    - attribution
    - appendix
    # Omit sections to exclude them

  style:
    theme: light          # light | dark
    font_scale: 1.0
    color_positive: "#10b981"
    color_negative: "#ef4444"

  heatmap:
    max_instruments: 30    # paginate if more
    sample_freq: W         # W=weekly, M=monthly

  attribution:
    top_n: 10              # top N instruments shown individually
    group_other: true      # group remaining as "Other"

  output:
    format: pdf            # pdf | html | both
    dpi: 150
    page_size: A4
    margins_mm: 15
```

---

## 15. QuantConnect / LEAN Adapter (Future)

The architecture explicitly supports future adapters. When QuantConnect backtests are needed:

```python
# adapters/quantconnect.py (future)
def extract_backtest_data(lean_result: "LeanResult") -> BacktestData:
    """Convert LEAN backtest results to BacktestData."""
    ...
```

This requires no changes to any other module — `BacktestReport` only sees `BacktestData`.

---

## 16. Implementation Order

| Phase | Items | Description |
|-------|-------|-------------|
| **P1** | `models.py`, `persist.py` (local only) | Data models + experiment directory read/write |
| **P2** | `portfolio.py` | QuantStats integration — portfolio PnL, monthly returns, stats, rolling stats |
| **P3** | `render.py` + templates | Jinja2 template assembly + WeasyPrint PDF generation |
| **P4** | `report.py` | BacktestReport orchestrator that wires sections together |
| **P5** | `instrument.py` | Per-instrument PnL curves, instrument stats table |
| **P6** | `positions.py` | Position heatmap |
| **P7** | `attribution.py` | Return attribution by instrument and sector |
| **P8** | `adapters/pysystemtrade.py` | System → BacktestData adapter |
| **P9** | CLI (`__main__.py`) | Click/argparse CLI interface |
| **P10** | `persist.py` (remote) | SCP read/write for hc4t |
| **P11** | Tests, docs, CI | Full test coverage, README, GitHub Actions |

Each phase should produce a working, testable increment. P1–P4 produce a minimal end-to-end report (portfolio sections only). P5–P7 add instrument-level detail. P8–P10 add integration with pysystemtrade and remote server.

---

## 17. Acceptance Criteria

The implementation is complete when:

1. ✅ `backtest-report generate /path/to/experiment_dir` produces a valid PDF from a local experiment directory containing `system.pkl`, `config.yaml`, and `meta.json`
2. ✅ `backtest-report generate --portfolio-returns returns.parquet --instrument-pnl pnl.parquet --positions positions.parquet --meta meta.json` produces a PDF from raw DataFrames (no pysystemtrade)
3. ✅ All 10 report sections render correctly with fixture data
4. ✅ PDF contains: header with metadata, equity curve, drawdown, monthly returns, portfolio stats, rolling Sharpe, instrument small multiples, instrument table, position heatmap, attribution, appendix
5. ✅ Report page breaks are correct (no orphan headers, no mid-table splits)
6. ✅ Report styling is consistent (fonts, colours, spacing per design system)
7. ✅ Remote experiment loading via `--remote` works against hc4t
8. ✅ `backtest-report validate <dir>` checks experiment directory completeness
9. ✅ `backtest-report sections` lists available section IDs
10. ✅ Test coverage ≥ 80% for all modules
11. ✅ Short history (< 30 days, < 1 year) handled gracefully with warnings
12. ✅ Missing instrument metadata defaults to "Unknown" sector/group without crashing
13. ✅ QuantStats failures are caught and reported; report still generates with partial content