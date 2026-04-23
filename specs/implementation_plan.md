# Backtest Report — Project Blueprint & Prompt Pack

> Derived from [backtest-report-spec.md](file:///home/samir/backtest-report/specs/backtest-report-spec.md)

---

## 1. Project Blueprint

### Milestone 1: Foundation — Data Models & Persistence (Local)

**Goal:** Establish the project skeleton, define all data models (Pydantic + dataclasses), and implement local filesystem persistence (Parquet-first reading/writing of experiment directories).

**Components:** `pyproject.toml`, `src/backtest_report/__init__.py`, `models.py`, `persist.py` (local only)

**Artifacts:**
- Python package skeleton with `pyproject.toml` and editable install
- Pydantic models: `BacktestConfig`, `BacktestData`, `BacktestMeta`, `InstrumentMeta`
- Dataclass: `SectionOutput`
- `persist.py`: `read_experiment_dir()`, `write_experiment_dir()` (Parquet-first strategy)
- Synthetic test data generator script (`scripts/generate_fixtures.py`)
- Unit tests for models and persistence

---

### Milestone 2: Portfolio Sections — Charts & Metrics

**Goal:** Implement all portfolio-level report sections: equity curve, drawdown, monthly returns table, key metrics table, and rolling statistics. All charts via matplotlib, metrics via `qs.stats` with manual fallbacks.

**Components:** `portfolio.py`

**Artifacts:**
- `render_portfolio_pnl()` — equity curve + drawdown matplotlib figures → base64 PNG
- `render_monthly_returns()` — year × month HTML table with conditional formatting
- `render_portfolio_stats()` — key metrics table using `qs.stats` with fallbacks
- `render_rolling_stats()` — rolling Sharpe, rolling return, optional beta charts
- Unit tests for each render function

---

### Milestone 3: Rendering Pipeline — Templates, CSS, PDF

**Goal:** Build the Jinja2 template system, CSS design system with embedded fonts, and WeasyPrint HTML→PDF conversion. The output is a self-contained, print-ready report.

**Components:** `render.py`, `templates/report.html`, `templates/style.css`, `templates/sections/*.html`, `templates/fonts/`

**Artifacts:**
- `style.css` with full design system (fonts, colours, spacing, @page rules, print rules)
- Jinja2 master template (`report.html`) with section slot injection
- Section-level HTML templates for each section type
- `assemble_html()` and `html_to_pdf()` in `render.py`
- Bundled font files (Inter, JetBrains Mono)

---

### Milestone 4: Report Orchestrator + Header/Appendix

**Goal:** Create the `BacktestReport` class that wires section renderers to the rendering pipeline. Implement the header and appendix sections. At this point, an end-to-end report (portfolio sections + header + appendix) should produce a valid PDF.

**Components:** `report.py`, `header.py`, `appendix.py`

**Artifacts:**
- `BacktestReport` class with `SECTION_REGISTRY` and `generate()` method
- `render_header()` — metadata display section
- `render_appendix()` — config dump, checksums, environment info
- Convenience functions: `generate_report()`, `from_pysystemtrade()`
- End-to-end integration test (fixture data → PDF)

---

### Milestone 5: Instrument Sections

**Goal:** Implement per-instrument analysis: small-multiples PnL grid and per-instrument statistics table.

**Components:** `instrument.py`

**Artifacts:**
- `render_instrument_pnl()` — 4-column small multiples grid with Sharpe annotations
- `render_instrument_table()` — per-instrument stats HTML table
- Unit tests for instrument section functions

---

### Milestone 6: Positions & Attribution

**Goal:** Implement the position heatmap and return attribution sections.

**Components:** `positions.py`, `attribution.py`

**Artifacts:**
- `render_position_snapshot()` — time × instrument heatmap (diverging colourmap)
- `render_attribution()` — by-instrument and by-sector stacked bar charts
- Unit tests for position and attribution functions

---

### Milestone 7: PySystemTrade Adapter

**Goal:** Build the optional adapter that converts pysystemtrade `System` objects into `BacktestData`. Include the instrument metadata YAML mapping.

**Components:** `adapters/pysystemtrade.py`, `adapters/instrument_map.yaml`

**Artifacts:**
- `extract_backtest_data()`, `extract_backtest_config()`, `load_system()` functions
- `instrument_map.yaml` with comprehensive instrument mappings
- Pickle fallback path in `persist.py`
- Unit tests with mocked `System` object

---

### Milestone 8: CLI, Remote Persistence, Tests & Docs

**Goal:** Implement the Click CLI, remote SCP operations, full test coverage, and documentation.

**Components:** `__main__.py`, `persist.py` (remote), `tests/`, `docs/`, `Makefile`

**Artifacts:**
- Click CLI with subcommands: `generate`, `upload`, `sections`, `validate`, `export-parquet`
- Remote read/write via SCP/rsync (`persist.py`)
- Config cascade for remote settings
- Full test suite with ≥80% coverage
- `README.md`, `docs/usage.md`, `docs/architecture.md`
- `Makefile` with lint/test/build targets

---

## 2. Refined Implementation Steps

### Pass 1 + Pass 2 Refinement

---

#### S1 (Milestone 1): Project Skeleton & Package Configuration

**Objective:** Create the Python package skeleton with `pyproject.toml`, directory structure, `__init__.py` (version via importlib.metadata), and an empty `Makefile`.

**Main changes:**
- Create full directory tree as specified in §2 of the spec
- `pyproject.toml` with all core + dev dependencies, entry point, and project metadata
- `__init__.py` with version detection and public API placeholders
- `Makefile` with `lint`, `test`, `install` targets
- `LICENSE` (MIT), `.gitignore`

**Dependencies:** None

---

#### S2 (Milestone 1): Pydantic Data Models

**Objective:** Implement all Pydantic models (`BacktestConfig`, `BacktestData`, `BacktestMeta`, `InstrumentMeta`) and the `SectionOutput` dataclass in `models.py`.

**Main changes:**
- `BacktestConfig` with all fields per §3.1
- `BacktestData` with `arbitrary_types_allowed`, `@field_validator` for DatetimeIndex validation per §3.2
- `InstrumentMeta` with defaulted fields per §3.2
- `BacktestMeta` with checksum format per §3.3
- `SectionOutput` as a plain dataclass per §3.4
- Unit tests: model creation, validation errors, serialisation

**Dependencies:** S1

---

#### S3 (Milestone 1): Test Fixture Generator

**Objective:** Create `scripts/generate_fixtures.py` to produce synthetic but realistic backtest data (5 years, 10 instruments, controlled correlation structure).

**Main changes:**
- Generate synthetic portfolio returns (Sharpe ~1.0, 15% vol annualised)
- Generate correlated instrument PnL and positions
- Generate `sample_meta.json`
- Save to `tests/fixtures/` as Parquet and JSON files
- Run the script to produce fixture files

**Dependencies:** S2

---

#### S4 (Milestone 1): Local Persistence Layer

**Objective:** Implement `persist.py` with `read_experiment_dir()` and `write_experiment_dir()` for local filesystem operations (Parquet-first strategy).

**Main changes:**
- `write_experiment_dir()`: write DataFrames as Parquet, metadata as JSON/YAML, compute checksums
- `read_experiment_dir()`: Parquet-first loading, pickle fallback stub (raises `ImportError`)
- SHA-256 checksum computation in `sha256:<hex>` format
- Unit tests using temp directories and fixture data

**Dependencies:** S2, S3

---

#### S5 (Milestone 2): Portfolio PnL Charts

**Objective:** Implement `portfolio.py` with `render_portfolio_pnl()` — equity curve and drawdown charts using matplotlib, returned as base64 PNG in `SectionOutput`.

**Main changes:**
- Compute cumulative returns and drawdown from `portfolio_returns`
- Generate styled matplotlib figures (consistent styling foundation for all future charts)
- Create a shared matplotlib style utility (colours, font sizes, grid, DPI=150)
- Encode figures as base64 PNG via `io.BytesIO`
- Return `SectionOutput` with `section_id="portfolio_pnl"` and figures dict
- Unit tests verifying output structure and non-empty base64 strings

**Dependencies:** S2

---

#### S6 (Milestone 2): Monthly Returns Table

**Objective:** Implement `render_monthly_returns()` — resample daily returns to monthly, pivot into year × month table, render as conditionally-formatted HTML.

**Main changes:**
- Resample using `ME` frequency
- Pivot into year rows × month columns with annual total
- Generate HTML `<table>` with inline conditional background colours (green/red intensity scaling, capped at ±10%)
- Highlight best/worst months
- Return `SectionOutput` with `section_id="monthly_returns"`
- Unit tests for resampling correctness and HTML output

**Dependencies:** S2

---

#### S7 (Milestone 2): Portfolio Stats Table

**Objective:** Implement `render_portfolio_stats()` — compute all 15 key metrics using `qs.stats` with manual fallbacks, render as an HTML table.

**Main changes:**
- Wrap each `qs.stats.*` call in try/except with manual pandas/numpy fallback per §5.4
- Format metrics with appropriate precision (percentages, ratios, days)
- Render as 2-column HTML table (metric name, value)
- Logging for QuantStats failures and fallback activation
- Unit tests for metric computation and graceful degradation

**Dependencies:** S2

---

#### S8 (Milestone 2): Rolling Stats Charts

**Objective:** Implement `render_rolling_stats()` — rolling 1-year Sharpe, rolling 3-year return, and optional beta chart.

**Main changes:**
- Rolling 252-day Sharpe ratio computation and chart
- Rolling 756-day annualised return computation and chart
- Conditional beta chart (only if `benchmark_returns` is provided)
- Short-history warning banner for backtests < 1 year
- matplotlib figures → base64 PNG
- Unit tests for both with-benchmark and without-benchmark paths

**Dependencies:** S5 (reuses matplotlib style utilities)

---

#### S9 (Milestone 3): CSS Design System & Fonts

**Objective:** Create `templates/style.css` with the full design system, @font-face declarations, @page rules, print rules, and table/figure styling. Bundle font files.

**Main changes:**
- CSS custom properties per §9.2 (colours, spacing, typography)
- `@font-face` for Inter and JetBrains Mono (woff2)
- `@page` rules with margin boxes per §9.4 (header/footer, page numbers)
- Print rules per §9.5 (page breaks, orphan prevention)
- Table styling (striped rows, `.br-instrument-table`)
- Figure/caption styling
- Download/bundle font woff2 files into `templates/fonts/`
- Font license files

**Dependencies:** S1

---

#### S10 (Milestone 3): Jinja2 Templates

**Objective:** Create the Jinja2 master template (`report.html`) and all section-level HTML templates.

**Main changes:**
- `report.html` master template with section slot injection per §8.3
- Running header/footer elements for `string-set` CSS properties
- Section templates: `header.html`, `portfolio.html`, `monthly_returns.html`, `portfolio_stats.html`, `rolling_stats.html`, `instrument_pnl.html`, `instrument_table.html`, `position_snapshot.html`, `attribution.html`, `appendix.html`
- Each section template expects variables from Jinja2 context (section HTML, figures)

**Dependencies:** S9

---

#### S11 (Milestone 3): Render Module (HTML Assembly + PDF)

**Objective:** Implement `render.py` with `assemble_html()` and `html_to_pdf()`.

**Main changes:**
- `assemble_html()`: load Jinja2 env from templates/, render master template with section outputs and meta, inject custom CSS
- `html_to_pdf()`: WeasyPrint `HTML(string=html).write_pdf()` with A4, 15mm margins, image optimisation
- Template directory resolution (package resources + override path)
- Unit tests: assemble HTML with mock section outputs, verify structure; PDF generation from sample HTML

**Dependencies:** S10

---

#### S12 (Milestone 4): Header & Appendix Sections

**Objective:** Implement `header.py` and `appendix.py` as section renderers.

**Main changes:**
- `render_header()`: extract metadata from `BacktestMeta.config`, format for display (experiment ID, strategy, dates, capital, risk target, git commit)
- `render_appendix()`: YAML config dump in `<pre>` block, checksums table, environment info
- Both return `SectionOutput` with appropriate HTML
- Unit tests

**Dependencies:** S2

---

#### S13 (Milestone 4): Report Orchestrator

**Objective:** Implement `BacktestReport` class in `report.py` — the central orchestrator that connects section renderers to the rendering pipeline.

**Main changes:**
- `BacktestReport.__init__()`: accept `BacktestData`, `BacktestMeta`, optional section filter, template dir, custom CSS
- `SECTION_REGISTRY` mapping section IDs to render functions
- `generate()` method: iterate registry → collect `SectionOutput` → `assemble_html()` → `html_to_pdf()` → write file → return Path
- Section ordering and filtering
- Timing/logging per section
- Convenience function `generate_report()` (loads experiment dir, creates report, generates)
- Stub for `from_pysystemtrade()` (full implementation in S21)

**Dependencies:** S4, S5, S6, S7, S8, S11, S12

---

#### S14 (Milestone 4): End-to-End Integration Test

**Objective:** Create an integration test that generates a complete PDF from fixture data and validates the output.

**Main changes:**
- `test_report.py::test_end_to_end_report_generation()`: load fixtures → `BacktestReport` → `generate()` → assert PDF exists, non-empty
- Assert HTML intermediate contains expected section markers
- Assert figure embeddings are present
- Assert key metric values appear in HTML
- `conftest.py` with shared pytest fixtures

**Dependencies:** S3, S13

---

#### S15 (Milestone 5): Instrument PnL Small Multiples

**Objective:** Implement `render_instrument_pnl()` — 4-column grid of per-instrument cumulative PnL curves with Sharpe annotations.

**Main changes:**
- Sort instruments by total PnL (best → worst)
- Generate matplotlib small-multiples grid (4 columns, ~3" × 2" per subplot)
- Each subplot: instrument code + name, cumulative PnL line, Sharpe annotation
- Paginate if > 20 instruments per page
- Return `SectionOutput` with figure as base64 PNG
- Unit tests

**Dependencies:** S5 (matplotlib style utilities), S2

---

#### S16 (Milestone 5): Instrument Stats Table

**Objective:** Implement `render_instrument_table()` — per-instrument statistics table.

**Main changes:**
- Compute per-instrument: Sharpe, cumulative PnL, max drawdown, avg position, turnover, win rate
- Render as HTML table with alternating row colours, sorted by PnL descending
- Apply `br-instrument-table` class
- Handle missing `instrument_returns` → compute from PnL
- Unit tests

**Dependencies:** S2

---

#### S17 (Milestone 5): Register Instrument Sections

**Objective:** Wire instrument section renderers into the `SECTION_REGISTRY` and update the integration test.

**Main changes:**
- Import instrument module in `report.py`, add to registry
- Update integration test to assert instrument sections appear in output
- Verify end-to-end with fixture data

**Dependencies:** S13, S15, S16

---

#### S18 (Milestone 6): Position Heatmap

**Objective:** Implement `render_position_snapshot()` — time × instrument heatmap with diverging colourmap.

**Main changes:**
- Sample positions at weekly or monthly frequency (auto-detect based on date range)
- Sort instruments by average absolute position (most active at top)
- Generate matplotlib heatmap (`imshow` or `pcolormesh`) with RdBu colourmap, colour bar
- Base64 PNG output
- Unit tests

**Dependencies:** S5 (matplotlib style utilities), S2

---

#### S19 (Milestone 6): Attribution Section

**Objective:** Implement `render_attribution()` — return attribution by instrument and by sector/group.

**Main changes:**
- By-instrument view: monthly P&L contribution per instrument, top 10 + "Other"
- By-sector view: aggregate by `instrument_meta.sector`, stacked bars per month
- Handle missing/unknown sector metadata (default to "Unknown")
- matplotlib stacked bar charts → base64 PNG
- Unit tests

**Dependencies:** S5, S2

---

#### S20 (Milestone 6): Register Position & Attribution Sections

**Objective:** Wire position and attribution renderers into the orchestrator and validate end-to-end.

**Main changes:**
- Import and register in `SECTION_REGISTRY`
- Update integration test
- All 10 sections now produce output

**Dependencies:** S13, S18, S19

---

#### S21 (Milestone 7): PySystemTrade Adapter

**Objective:** Implement `adapters/pysystemtrade.py` with `extract_backtest_data()`, `extract_backtest_config()`, `load_system()`, and the instrument metadata YAML map.

**Main changes:**
- `load_system()`: unpickle with compatibility handling
- `extract_backtest_data()`: extract returns, PnL, positions from System object per §6
- `extract_backtest_config()`: build config from System + external config file
- `instrument_map.yaml` with mappings for common pysystemtrade instruments
- Load mapping via `importlib.resources`
- Wire pickle fallback path in `persist.py`
- `from_pysystemtrade()` convenience function in `report.py`
- Unit tests with mocked System object

**Dependencies:** S4, S2

---

#### S22 (Milestone 8): Click CLI

**Objective:** Implement the Click CLI in `__main__.py` with all subcommands.

**Main changes:**
- `generate` command: local path or `--remote`, output format, section filtering, raw DataFrame mode
- `upload` command: push PDF to remote
- `sections` command: list available section IDs
- `validate` command: check experiment directory completeness
- `export-parquet` command: convert System pickle to Parquet
- `--verbose` flag → configure logging to DEBUG
- `--version` flag
- Config cascade for remote settings
- Error handling with clear user-facing messages
- Unit tests for CLI argument parsing

**Dependencies:** S13, S4

---

#### S23 (Milestone 8): Remote Persistence (SCP)

**Objective:** Implement remote read/write in `persist.py` using SCP/rsync via subprocess.

**Main changes:**
- `read_remote_experiment()`: SCP files to local temp dir, then `read_experiment_dir()`
- `write_remote_report()`: SCP report PDF to remote experiment directory
- Config cascade: CLI flags → `.backtest-report.yaml` → env vars → defaults
- Error handling for SSH/SCP failures with troubleshooting hints
- Unit tests (mocked subprocess)

**Dependencies:** S4, S22

---

#### S24 (Milestone 8): Full Test Suite & Coverage

**Objective:** Ensure all modules have comprehensive unit tests with ≥80% coverage. Fill any gaps from earlier steps.

**Main changes:**
- Review and fill test coverage gaps
- Add edge-case tests: short history warnings, missing data, QuantStats failures, corrupt pickle
- `pytest.ini` or `pyproject.toml` [tool.pytest] configuration
- Coverage configuration in `pyproject.toml`
- Run `pytest --cov` and verify ≥80%

**Dependencies:** All previous steps

---

#### S25 (Milestone 8): Documentation, README & CI

**Objective:** Write documentation, finalise the README, and set up GitHub Actions CI.

**Main changes:**
- `README.md` with project overview, installation, quick-start, CLI usage examples
- `docs/usage.md` with detailed usage guide
- `docs/architecture.md` — cleaned version of the spec
- GitHub Actions workflow: lint (ruff), type-check (mypy), test (pytest --cov), build
- `Makefile` targets finalised
- `.backtest-report.yaml` example file

**Dependencies:** S24

---

### Refinement Verification Checklist

- ✅ All 8 milestones are covered by S1–S25
- ✅ No large complexity jumps: each step is scoped to a single module or concern
- ✅ Dependencies form a clean DAG with no cycles
- ✅ No redundant or overlapping steps
- ✅ S1–S14 produce a working end-to-end report (portfolio sections)
- ✅ S15–S20 add instrument-level detail incrementally
- ✅ S21–S25 add integration, CLI, remote, and polish
- ✅ Every section renderer is explicitly registered in steps S13, S17, S20

---

## 3. Code-Generation Prompt Pack

### Step S1 — Project Skeleton & Package Configuration

```text
[INSTRUCTIONS FOR THE CODE-GENERATION LLM]

Context:
- We are building a Python package called "backtest-report" that generates standardised PDF backtest reports from trading system data.
- This is a brand-new project. The repo currently contains only a specs/ directory.
- The package must support Python 3.10+, use Pydantic v2 for data models, matplotlib for charts, QuantStats for metrics, Jinja2 + WeasyPrint for rendering.

Task:
Create the complete project skeleton with the following directory structure and configuration files. Do NOT create any business logic yet — only the skeleton.

Files to create:

1. `pyproject.toml`:
   - name: "backtest-report", version: "0.1.0"
   - Minimum Python 3.10
   - Core dependencies: pandas>=2.0, numpy>=1.24, matplotlib>=3.7, quantstats>=0.0.62, jinja2>=3.1, weasyprint>=60, pydantic>=2.0, pyyaml>=6.0, click>=8.0
   - Optional dependencies group "pysystemtrade": pysystemtrade>=1.8
   - Optional dependencies group "parquet": pyarrow>=12.0
   - Dev dependencies group: pytest>=7.0, pytest-cov>=4.0, ruff>=0.1, mypy>=1.5
   - Entry point: backtest-report = "backtest_report.__main__:cli"
   - [tool.ruff] and [tool.pytest.ini_options] sections
   - [tool.mypy] section

2. `src/backtest_report/__init__.py`:
   - Read version from importlib.metadata with PackageNotFoundError fallback to "0.0.0-dev"
   - Define `__all__` with placeholder names (will be filled later)
   - Set up root logger: `logging.getLogger("backtest_report")`

3. `src/backtest_report/__main__.py`:
   - Minimal Click CLI stub: a `cli` group with a `--version` option and a placeholder `generate` command that prints "Not yet implemented"

4. Empty `__init__.py` files for `src/backtest_report/adapters/`

5. `Makefile` with targets:
   - `install`: pip install -e ".[dev,parquet]"
   - `lint`: ruff check src/ tests/
   - `format`: ruff format src/ tests/
   - `typecheck`: mypy src/
   - `test`: pytest tests/ -v --cov=backtest_report
   - `clean`: remove __pycache__, .pytest_cache, dist/, etc.

6. `LICENSE` — MIT license, 2026, Samir Sheldenkar

7. `.gitignore` — Python-specific ignores (pycache, dist, eggs, .venv, *.pkl, *.parquet in root)

8. Empty directories (with .gitkeep or __init__.py where appropriate):
   - `src/backtest_report/templates/`
   - `src/backtest_report/templates/sections/`
   - `src/backtest_report/templates/fonts/`
   - `tests/`
   - `tests/fixtures/`
   - `scripts/`
   - `docs/`

Requirements:
- The package must be installable via `pip install -e .` after this step
- The CLI stub must respond to `backtest-report --version`
- All paths must match the directory structure in the spec exactly
- Do not create any data model or business logic files yet

Output:
- All files listed above, ready for editable install
- A short note listing what was created
```

---

### Step S2 — Pydantic Data Models

```text
[INSTRUCTIONS FOR THE CODE-GENERATION LLM]

Context:
- The backtest-report project skeleton exists (pyproject.toml, __init__.py, Makefile, etc.)
- We need to define all data models that the entire system will use.
- Models requiring validation/serialisation use Pydantic v2. Internal data-passing uses dataclasses.
- pandas types (Series, DataFrame) in Pydantic require `ConfigDict(arbitrary_types_allowed=True)`.

Task:
Create `src/backtest_report/models.py` with all data models, and `tests/test_models.py` with unit tests.

File: `src/backtest_report/models.py`

Define the following:

1. `InstrumentMeta(BaseModel)`:
   - Fields: code (str), name (str, default ""), sector (str, default ""), group (str, default ""), asset_class (str, default ""), exchange (str, default ""), point_value (float, default 1.0), currency (str, default "USD")

2. `BacktestConfig(BaseModel)`:
   - Fields: experiment_id (str), strategy_name (str), engine (str, default "pysystemtrade"), engine_version (str, default ""), python_version (str, default ""), git_commit (str, default ""), instrument_universe (list[str]), start_date (date), end_date (date), capital (float), currency (str, default "USD"), risk_target_annual_pct (float), data_sources (list[str], default []), config_overrides (dict[str, Any], default {})

3. `BacktestData(BaseModel)`:
   - model_config = ConfigDict(arbitrary_types_allowed=True)
   - Fields: portfolio_returns (pd.Series), instrument_pnl (pd.DataFrame), positions (pd.DataFrame), instrument_meta (dict[str, InstrumentMeta]), instrument_returns (dict[str, pd.Series], default {}), benchmark_returns (pd.Series | None, default None)
   - @field_validator("portfolio_returns"): validate DatetimeIndex and non-empty
   - @field_validator("instrument_pnl", "positions"): validate DatetimeIndex

4. `BacktestMeta(BaseModel)`:
   - Fields: config (BacktestConfig), generated_at (datetime), report_version (str), data_checksums (dict[str, str], default {}), notes (str, default "")

5. `SectionOutput` (plain dataclass, NOT Pydantic):
   - Fields: section_id (str), html (str), figures (dict[str, str], default_factory=dict), tables (dict[str, pd.DataFrame], default_factory=dict)

File: `tests/test_models.py`

Write tests:
- Create valid instances of each model with realistic data
- Test BacktestData validators: non-DatetimeIndex should raise ValueError, empty Series should raise ValueError
- Test InstrumentMeta defaults
- Test BacktestMeta serialisation (model_dump)
- Test SectionOutput creation

Requirements:
- Use `from __future__ import annotations` for clean type hints
- Import types from typing where needed
- All models must be importable from `backtest_report.models`
- Update `src/backtest_report/__init__.py` to re-export the main models in `__all__`

Output:
- `src/backtest_report/models.py`
- `tests/test_models.py`
- Updated `src/backtest_report/__init__.py`
- Short summary of what was created
```

---

### Step S3 — Test Fixture Generator

```text
[INSTRUCTIONS FOR THE CODE-GENERATION LLM]

Context:
- The backtest-report project has a package skeleton and all data models defined in `models.py`.
- Models: BacktestConfig, BacktestData, BacktestMeta, InstrumentMeta, SectionOutput.
- We need synthetic but realistic backtest data for testing throughout the project.

Task:
Create `scripts/generate_fixtures.py` that generates synthetic test data and saves it to `tests/fixtures/`. Then run the script to produce the fixture files.

File: `scripts/generate_fixtures.py`

The script should:

1. Generate 5 years of daily dates (business days only, e.g. 2020-01-02 to 2024-12-31)

2. Generate synthetic portfolio returns:
   - Daily returns from a normal distribution calibrated to ~15% annualised vol
   - Add a small positive drift to achieve ~1.0 Sharpe ratio
   - Save as `tests/fixtures/sample_portfolio_returns.parquet` (pd.Series with DatetimeIndex, named "portfolio_returns")

3. Generate 10 instruments with correlated PnL:
   - Instrument codes: ["EDOLLAR", "US10", "US5", "GOLD", "CRUDE_W", "SP500", "EUROSTX", "GAS_US", "CORN", "JPY"]
   - Instrument PnL: generate from a multivariate normal with moderate cross-correlation (~0.2–0.4), add instrument-specific drift and vol
   - Scale so total PnL roughly matches the portfolio returns curve
   - Save as `tests/fixtures/sample_instrument_returns.parquet` (DataFrame: DatetimeIndex × instrument_code → float)

4. Generate position sizes:
   - Realistic contract-level positions: each instrument between -20 and +20 contracts
   - Use a slow mean-reverting process (AR(1) with phi ~0.99) to simulate trend-following positions
   - Save as `tests/fixtures/sample_positions.parquet` (DataFrame: DatetimeIndex × instrument_code → float)

5. Generate metadata:
   - Create a `sample_meta.json` file containing a valid BacktestMeta JSON with:
     - experiment_id: "test-fixture_20240101_120000"
     - strategy_name: "Test Fixture Strategy"
     - Full BacktestConfig with the 10 instrument codes, date range, capital=1_000_000, risk_target=20.0
     - generated_at: current timestamp
     - report_version: "0.1.0"
     - data_checksums: compute SHA-256 for each generated Parquet file
   - Save as `tests/fixtures/sample_meta.json`

6. Also create `tests/conftest.py` with pytest fixtures:
   - `sample_portfolio_returns()` → load from Parquet
   - `sample_instrument_pnl()` → load from Parquet
   - `sample_positions()` → load from Parquet
   - `sample_meta()` → load from JSON, return BacktestMeta
   - `sample_backtest_data()` → construct BacktestData from above fixtures
   - `sample_instrument_meta()` → dict of InstrumentMeta for the 10 instruments

Requirements:
- Use numpy random with a fixed seed (42) for reproducibility
- All DatetimeIndex must be timezone-naive
- The script should be runnable standalone: `python scripts/generate_fixtures.py`
- Print summary statistics when done (total return, Sharpe, max DD, number of trading days)

Output:
- `scripts/generate_fixtures.py`
- `tests/conftest.py`
- Generated fixture files in `tests/fixtures/`
- Short summary of fixture characteristics
```

---

### Step S4 — Local Persistence Layer

```text
[INSTRUCTIONS FOR THE CODE-GENERATION LLM]

Context:
- The backtest-report project has models (BacktestConfig, BacktestData, BacktestMeta, InstrumentMeta) and test fixtures.
- We need a persistence layer that reads/writes experiment directories using a Parquet-first strategy.
- Remote (SCP) persistence will be added later — this step is local filesystem only.

Task:
Create `src/backtest_report/persist.py` and `tests/test_persist.py`.

File: `src/backtest_report/persist.py`

Implement:

1. `write_experiment_dir(path, data, config, data_checksums, system=None)`:
   - Create directory if it doesn't exist
   - Write `portfolio_returns.parquet` from data.portfolio_returns
   - Write `instrument_pnl.parquet` from data.instrument_pnl
   - Write `positions.parquet` from data.positions
   - Write `instrument_meta.json` from data.instrument_meta (serialise InstrumentMeta models)
   - Write `config.yaml` from config (Pydantic model_dump → YAML)
   - Write `data_checksums.json` from data_checksums dict
   - Write `meta.json` with auto-generated BacktestMeta (current timestamp, package version, config, checksums)
   - If system is not None, pickle it as `system.pkl` (log warning about pickle security)
   - Log all files written

2. `read_experiment_dir(path)` → tuple[BacktestData, BacktestMeta]:
   - Strategy 1 (Parquet-first): if portfolio_returns.parquet exists, read all Parquet + JSON files
   - Strategy 2 (Pickle fallback): if system.pkl exists but no Parquet, attempt to import pysystemtrade adapter. If not installed, raise ImportError with clear message.
   - Raise FileNotFoundError if neither strategy works, listing found vs expected files
   - Log which strategy was used

3. `compute_checksum(path)` → str:
   - Compute SHA-256 of a file, return as "sha256:<hex>"

4. `validate_experiment_dir(path)` → dict:
   - Check which expected files exist
   - Return dict with "valid" (bool), "found" (list), "missing" (list), "strategy" (str)

File: `tests/test_persist.py`

Tests:
- Write then read an experiment directory round-trip
- Verify all files are created with correct content
- Test checksum computation
- Test validate_experiment_dir with complete and incomplete directories
- Test read with missing Parquet falls back to pickle error
- Test read with nothing raises FileNotFoundError with helpful message

Requirements:
- Use tmp_path pytest fixture for temp directories
- Use the conftest.py fixtures from S3
- Handle edge cases: existing directory, missing parent dirs
- Use pathlib.Path throughout (no os.path)

Output:
- `src/backtest_report/persist.py`
- `tests/test_persist.py`
- Short summary of what was implemented
```

---

### Step S5 — Portfolio PnL Charts (Equity Curve & Drawdown)

```text
[INSTRUCTIONS FOR THE CODE-GENERATION LLM]

Context:
- The backtest-report project has models, fixtures, and persistence.
- We now begin the section renderers. Each section is a function: `render_<section_id>(data: BacktestData, meta: BacktestMeta) -> SectionOutput`.
- All charts use matplotlib (NOT QuantStats' built-in charts). QuantStats is only for metric computation.
- Charts are encoded as base64 PNG and returned in SectionOutput.figures.

Task:
Create `src/backtest_report/portfolio.py` (partial — PnL section only) and `tests/test_portfolio.py` (partial).

File: `src/backtest_report/portfolio.py`

Implement:

1. A shared matplotlib styling module at the top of the file:
   - Define a function `apply_report_style()` that sets matplotlib rcParams:
     - Font family matching the design system (sans-serif fallback since we're generating PNGs)
     - Grid: light grey, alpha 0.3
     - Figure facecolor: white
     - Axes facecolor: white
     - DPI: 150
     - Tick label size: 8pt
   - Define colour constants: POSITIVE_COLOR = "#10b981", NEGATIVE_COLOR = "#ef4444", NEUTRAL_COLOR = "#6b7280"

2. Helper function `fig_to_base64(fig) -> str`:
   - Save matplotlib figure to BytesIO as PNG (dpi=150, bbox_inches="tight")
   - Encode to base64 string
   - Close figure to free memory
   - Return the base64 string

3. `render_portfolio_pnl(data: BacktestData, meta: BacktestMeta) -> SectionOutput`:
   - Compute cumulative returns: `(1 + data.portfolio_returns).cumprod()`
   - Compute drawdown: `cumulative / cumulative.cummax() - 1`
   - Generate equity curve figure:
     - Single line plot, colour=POSITIVE_COLOR
     - Title: "Cumulative Returns"
     - Y-axis: "Growth of $1"
     - X-axis: formatted dates
     - Horizontal line at y=1.0 (dashed, grey)
   - Generate drawdown figure:
     - Fill between 0 and drawdown, colour=NEGATIVE_COLOR, alpha=0.7
     - Title: "Underwater Plot (Drawdown)"
     - Y-axis: "Drawdown %" (format as percentage)
     - Zero line
   - Both figures: 10" wide × 4" tall
   - Return SectionOutput(section_id="portfolio_pnl", html=<simple div with img tags referencing figures>, figures={"equity_curve": base64, "drawdown": base64})

File: `tests/test_portfolio.py`

Tests:
- render_portfolio_pnl returns SectionOutput with correct section_id
- SectionOutput.figures contains "equity_curve" and "drawdown" keys
- Each figure value is a non-empty base64 string
- HTML contains img tags
- Works with fixture data

Requirements:
- Use `matplotlib.use("Agg")` at module top to avoid display issues
- Close all figures after encoding to prevent memory leaks
- The HTML in SectionOutput should use inline base64 data URIs: `<img src="data:image/png;base64,{figure_data}">`
- Keep the HTML minimal — the Jinja2 section template (created later) will wrap it

Output:
- `src/backtest_report/portfolio.py` (render_portfolio_pnl + helpers)
- `tests/test_portfolio.py` (partial)
- Short summary
```

---

### Step S6 — Monthly Returns Table

```text
[INSTRUCTIONS FOR THE CODE-GENERATION LLM]

Context:
- The backtest-report project has models, fixtures, persistence, and the portfolio PnL chart renderer.
- `portfolio.py` exists with `render_portfolio_pnl()`, `fig_to_base64()`, and styling utilities.

Task:
Add `render_monthly_returns()` to `src/backtest_report/portfolio.py` and add corresponding tests to `tests/test_portfolio.py`.

Modify: `src/backtest_report/portfolio.py`

Add:

1. `render_monthly_returns(data: BacktestData, meta: BacktestMeta) -> SectionOutput`:
   - Resample daily returns to monthly: `data.portfolio_returns.resample('ME').apply(lambda x: (1 + x).prod() - 1)`
   - Pivot into a table: rows = years, columns = Jan–Dec + "Year" (annual total)
   - Annual total: compound monthly returns for that year
   - Generate HTML `<table>` with class `br-monthly-returns`:
     - Column headers: Year, Jan, Feb, ..., Dec, Year
     - Each cell: formatted as percentage (1 decimal place)
     - Conditional background colour:
       - Positive returns: green with intensity scaling (0% → white, ≥10% → full green #10b981)
       - Negative returns: red with intensity scaling (0% → white, ≤-10% → full red #ef4444)
       - Zero/NaN: light grey #f3f4f6
     - Highlight best month (bold, green border) and worst month (bold, red border)
     - Use inline styles for the conditional formatting (since this goes into a PDF)
   - Return SectionOutput(section_id="monthly_returns", html=<the table HTML>, tables={"monthly_returns": the_pivot_dataframe})

2. Helper function `_return_to_color(value: float) -> str`:
   - Map a return value to an rgba background-color string
   - Linear interpolation between white and green/red
   - Cap at ±10% for colour scaling purposes

Modify: `tests/test_portfolio.py`

Add tests:
- render_monthly_returns produces valid SectionOutput
- HTML contains '<table' and 'br-monthly-returns'
- Monthly table has correct number of rows (years) and columns (14: year + 12 months + annual)
- Conditional colouring is applied (check for 'background-color' in HTML)
- Best and worst months are highlighted
- Handles partial years (first and last year)

Requirements:
- Keep all existing code in portfolio.py intact
- Handle NaN values gracefully (months with no data → grey cell, "—")
- The table HTML must be self-contained (no external CSS dependencies except classes)

Output:
- Updated `src/backtest_report/portfolio.py`
- Updated `tests/test_portfolio.py`
- Short note on what changed
```

---

### Step S7 — Portfolio Stats Table

```text
[INSTRUCTIONS FOR THE CODE-GENERATION LLM]

Context:
- The backtest-report project has models, fixtures, persistence, portfolio PnL charts, and monthly returns table.
- `portfolio.py` has `render_portfolio_pnl()` and `render_monthly_returns()`.
- QuantStats is a dependency. We use `qs.stats` for metric computation with manual fallbacks.

Task:
Add `render_portfolio_stats()` to `src/backtest_report/portfolio.py` and tests to `tests/test_portfolio.py`.

Modify: `src/backtest_report/portfolio.py`

Add:

1. `render_portfolio_stats(data: BacktestData, meta: BacktestMeta) -> SectionOutput`:
   - Compute 15 key metrics using the following pattern for EACH metric:
     ```python
     try:
         value = qs.stats.<metric>(returns)
     except Exception as e:
         logger.warning("qs.stats.%s failed, falling back: %s", metric_name, e)
         value = <manual_computation>
     ```
   - Metrics to compute (in order):
     - Total Return: qs.stats.comp(returns) / fallback: (1+returns).prod() - 1
     - CAGR: qs.stats.cagr(returns) / fallback: manual annualisation
     - Annualised Vol: qs.stats.volatility(returns) / fallback: returns.std() * sqrt(252)
     - Sharpe Ratio: qs.stats.sharpe(returns) / fallback: annualised_return / annualised_vol
     - Sortino Ratio: qs.stats.sortino(returns) / fallback: manual downside deviation
     - Calmar Ratio: qs.stats.calmar(returns) / fallback: CAGR / abs(max_dd)
     - Max Drawdown: qs.stats.max_drawdown(returns)
     - Max DD Duration: compute longest period below peak in calendar days
     - Win Rate: qs.stats.win_rate(returns) / fallback: (returns > 0).mean()
     - Profit Factor: qs.stats.profit_factor(returns)
     - Avg Win / Avg Loss ratio: qs.stats.avg_win / abs(qs.stats.avg_loss)
     - Skewness: qs.stats.skew(returns) / fallback: returns.skew()
     - Kurtosis: qs.stats.kurtosis(returns) / fallback: returns.kurtosis()
     - Best Day: qs.stats.best(returns) / fallback: returns.max()
     - Worst Day: qs.stats.worst(returns) / fallback: returns.min()
   - If both qs.stats AND manual fallback fail, use "N/A"
   - Format values:
     - Percentages (Total Return, CAGR, Vol, Max DD, Win Rate, Best/Worst Day): "XX.XX%"
     - Ratios (Sharpe, Sortino, Calmar, Profit Factor, Win/Loss): "X.XX"
     - Days (Max DD Duration): "XXX days"
     - Skew/Kurtosis: "X.XX"
   - Render as HTML table with class `br-portfolio-stats`:
     - 2 columns: "Metric", "Value"
     - Clean typography, no background colouring
   - Return SectionOutput(section_id="portfolio_stats", html=<table>)

Modify: `tests/test_portfolio.py`

Add tests:
- render_portfolio_stats returns valid SectionOutput
- HTML contains all 15 metric names
- Metric values are reasonable for fixture data (Sharpe ~1.0, Vol ~15%, etc.)
- Test graceful degradation: mock qs.stats to raise exceptions, verify manual fallbacks work
- Test "N/A" fallback when both methods fail

Requirements:
- Import quantstats as qs at module level; use qs.stats for computations
- ALL qs.stats calls must be wrapped in try/except
- Use the existing `logger = logging.getLogger("backtest_report")` for warnings
- Do not modify existing functions in portfolio.py

Output:
- Updated `src/backtest_report/portfolio.py`
- Updated `tests/test_portfolio.py`
- Short note on changes
```

---

### Step S8 — Rolling Stats Charts

```text
[INSTRUCTIONS FOR THE CODE-GENERATION LLM]

Context:
- `portfolio.py` now has: render_portfolio_pnl, render_monthly_returns, render_portfolio_stats, plus helpers (fig_to_base64, apply_report_style, colour constants).
- We need the final portfolio section: rolling statistics charts.

Task:
Add `render_rolling_stats()` to `src/backtest_report/portfolio.py` and tests to `tests/test_portfolio.py`.

Modify: `src/backtest_report/portfolio.py`

Add:

1. `render_rolling_stats(data: BacktestData, meta: BacktestMeta) -> SectionOutput`:
   - Check if backtest period < 252 days. If so, return SectionOutput with HTML containing a warning banner: "⚠ Insufficient history for rolling statistics (minimum 1 year required)"
   - Rolling 252-day (1-year) Sharpe ratio:
     - rolling_return = data.portfolio_returns.rolling(252).mean() * 252
     - rolling_vol = data.portfolio_returns.rolling(252).std() * sqrt(252)
     - rolling_sharpe = rolling_return / rolling_vol
     - Plot as line chart, horizontal line at 0 (dashed grey)
     - Title: "Rolling 1-Year Sharpe Ratio"
   - Rolling 756-day (3-year) annualised return:
     - rolling_3y = data.portfolio_returns.rolling(756).apply(lambda x: (1+x).prod()**(252/len(x)) - 1)
     - Plot as line chart
     - Title: "Rolling 3-Year Annualised Return"
     - Only show if backtest period >= 756 days; otherwise show warning for this subplot
   - Beta to benchmark (CONDITIONAL):
     - ONLY if data.benchmark_returns is not None
     - Rolling 252-day beta: cov(portfolio, benchmark) / var(benchmark)
     - Plot as line chart, horizontal line at 0
     - Title: "Rolling 1-Year Beta"
     - If benchmark_returns is None, omit this chart entirely (do not show empty plot)
   - Each chart: 10" × 3" figure
   - Combine into SectionOutput with figures dict
   - Generate HTML with img tags for each available figure

Modify: `tests/test_portfolio.py`

Add tests:
- render_rolling_stats with sufficient history returns expected figures
- With < 252 days of data, returns warning HTML instead of charts
- Without benchmark_returns, beta chart is omitted
- With benchmark_returns, beta chart is included
- Figure base64 strings are valid

Requirements:
- Reuse existing matplotlib helpers (fig_to_base64, apply_report_style, colour constants)
- Do not modify existing functions
- Handle NaN values in rolling computations (dropna before plotting)

Output:
- Updated `src/backtest_report/portfolio.py`
- Updated `tests/test_portfolio.py`
- Short note
```

---

### Step S9 — CSS Design System & Fonts

```text
[INSTRUCTIONS FOR THE CODE-GENERATION LLM]

Context:
- The backtest-report project has models, fixtures, persistence, and all portfolio section renderers.
- We need to create the CSS design system for the PDF report. This CSS is used by WeasyPrint to render HTML → PDF.
- WeasyPrint supports CSS Paged Media (@page rules, margin boxes, page counters).
- Fonts (Inter, JetBrains Mono) must be bundled as woff2 files in templates/fonts/.

Task:
Create the complete CSS design system and acquire font files.

File: `src/backtest_report/templates/style.css`

Create the CSS file with ALL of the following:

1. @font-face declarations:
   - Inter Regular (400) and SemiBold (600) — woff2 format, relative path fonts/
   - JetBrains Mono Regular (400) — woff2 format
   - Fallback: system font stack

2. CSS custom properties (:root) — exact values from the spec:
   - --br-font-body, --br-font-mono, --br-font-data
   - Colours: --br-col-bg (#ffffff), --br-col-text (#1a1a1a), --br-col-muted (#6b7280), --br-col-border (#e5e7eb), --br-col-positive (#10b981), --br-col-negative (#ef4444), --br-col-neutral (#6b7280), --br-col-header (#111827), --br-col-header-text (#f9fafb), --br-col-table-stripe (#f9fafb), --br-col-table-hover (#f3f4f6)
   - Spacing: --br-spacing-xs (4px) through --br-spacing-xl (32px)
   - Page: --br-page-width (210mm), --br-page-margin (15mm)

3. @page rules:
   - size: A4, margin: 15mm
   - @top-right: experiment ID + page N of M (7pt, muted colour)
   - @bottom-center: "Generated by backtest-report v{version} | {date}" (6.5pt, muted)
   - @page :first — suppress top-right header

4. Base styles:
   - body: font-family var(--br-font-body), 10pt, line-height 1.5, colour/bg per design system
   - h1, h2, h3: Inter SemiBold, appropriate sizes
   - code, pre: JetBrains Mono, 7.5pt

5. Print rules:
   - .br-page-break: page-break-after: always
   - h2, h3: page-break-after: avoid
   - table, figure, .br-figure: page-break-inside: avoid
   - figcaption, .br-figure-caption: centered, 8pt, muted colour

6. Component styles:
   - .br-header: full-width dark banner, white text
   - .br-monthly-returns table: compact layout, 8pt text
   - .br-portfolio-stats table: clean 2-column layout
   - .br-instrument-table table: alternating row stripes, 8pt
   - .br-heatmap: full-width figure
   - .br-attribution: chart container
   - .br-appendix pre: monospace config dump, light grey background, padding
   - .br-warning-banner: yellow background, warning icon

7. Utility classes:
   - .br-metric-value: right-aligned, tabular-nums
   - .br-positive: green text
   - .br-negative: red text
   - .br-muted: grey text, smaller font

Font files:
- Download Inter Regular and SemiBold woff2 from Google Fonts CDN
- Download JetBrains Mono Regular woff2 from JetBrains CDN
- Save to `src/backtest_report/templates/fonts/`
- Create `OFL.txt` license file for the fonts

Requirements:
- CSS must work with WeasyPrint (no flexbox gaps, limited grid support — use float/table layouts)
- All font references must use relative paths (fonts/filename.woff2)
- Test that the CSS is valid by parsing it (no syntax errors)

Output:
- `src/backtest_report/templates/style.css`
- Font files in `src/backtest_report/templates/fonts/`
- `src/backtest_report/templates/fonts/OFL.txt`
- Short note on design system
```

---

### Step S10 — Jinja2 Templates

```text
[INSTRUCTIONS FOR THE CODE-GENERATION LLM]

Context:
- The project has CSS design system (style.css) with all component classes defined.
- Section renderers produce SectionOutput objects containing HTML fragments and base64 figures.
- We need Jinja2 templates that assemble these fragments into a complete HTML document.

Task:
Create the Jinja2 master template and all section-level templates.

File: `src/backtest_report/templates/report.html`

The master template:
- DOCTYPE html, charset utf-8
- <title> using meta.config.experiment_id
- Inline the style.css via {% include "style.css" %} in a <style> block
- Optional custom_css injection
- Running elements div (.br-running-header) with string-set spans for experiment-id, report-version, generated-at
- Section blocks with .br-page-break dividers between sections
- Sections: header, portfolio_pnl, monthly_returns, portfolio_stats, rolling_stats, instrument_pnl, instrument_table, position_snapshot, attribution, appendix
- Each section wrapped in {% if sections.<id> %}{{ sections.<id>.html | safe }}{% endif %}
- Match the exact template structure from spec §8.3

Section templates in `src/backtest_report/templates/sections/`:

1. `header.html` — expects: config object with experiment_id, strategy_name, engine, dates, capital, risk_target, git_commit, generated_at. Renders as a dark banner with metadata fields.

2. `portfolio.html` — expects: figures dict with equity_curve and drawdown base64 strings. Wraps in .br-portfolio-pnl div with img tags and captions.

3. `monthly_returns.html` — expects: table_html (pre-rendered HTML table string). Wraps with section heading.

4. `portfolio_stats.html` — expects: stats_html (pre-rendered stats table). Wraps with section heading.

5. `rolling_stats.html` — expects: figures dict with available rolling charts. Wraps each in figure with caption.

6. `instrument_pnl.html` — expects: figure base64 for small multiples grid. Wraps in section.

7. `instrument_table.html` — expects: table_html (pre-rendered instrument stats table). Wraps in section.

8. `position_snapshot.html` — expects: heatmap figure base64. Wraps in section.

9. `attribution.html` — expects: figures dict with attribution charts. Wraps each in figure.

10. `appendix.html` — expects: config_yaml (string), checksums (dict), environment info. Renders config in <pre>, checksums as table.

Requirements:
- Each section template should be a FRAGMENT (no <html>, <head>, <body> tags) — they're included in the master template
- Use Jinja2 best practices: filters (safe, e), macros where reuse makes sense
- All img tags should use data URIs: src="data:image/png;base64,{{ figure }}"
- Section templates should be standalone and not depend on each other
- Include section headings (h2) in each section template

Output:
- `src/backtest_report/templates/report.html`
- All 10 section templates in `src/backtest_report/templates/sections/`
- Short summary
```

---

### Step S11 — Render Module (HTML Assembly + PDF)

```text
[INSTRUCTIONS FOR THE CODE-GENERATION LLM]

Context:
- The project has: models, fixtures, persistence, all portfolio section renderers, CSS design system, and Jinja2 templates (master + section templates).
- We need the render module that assembles section outputs into complete HTML and converts to PDF.

Task:
Create `src/backtest_report/render.py` and `tests/test_render.py`.

File: `src/backtest_report/render.py`

Implement:

1. `assemble_html(sections, meta, template_dir=None, custom_css=None) -> str`:
   - `sections`: dict[str, SectionOutput] — mapping section_id to SectionOutput
   - `meta`: BacktestMeta
   - Load Jinja2 Environment with FileSystemLoader pointing to templates directory
   - Default template_dir: use importlib.resources to locate the package's templates/ directory
   - Allow template_dir override for testing
   - Build template context:
     - meta: the BacktestMeta object
     - sections: the sections dict (templates access .html and .figures attributes)
     - custom_css: optional additional CSS string
   - Render the master report.html template
   - Return the complete HTML string

2. `html_to_pdf(html, output_path) -> Path`:
   - Convert HTML string to PDF using WeasyPrint
   - Settings: optimize_images=True, jpeg_quality=85
   - Set base_url to template directory (for font file resolution)
   - Write to output_path
   - Return the Path object
   - Log rendering time

3. `get_template_dir() -> Path`:
   - Return the path to the package's templates/ directory
   - Use importlib.resources for package-relative path resolution
   - Fallback: relative path from this file's location

File: `tests/test_render.py`

Tests:
- assemble_html with mock SectionOutput objects produces valid HTML
- HTML contains DOCTYPE, <html>, <head>, <body>
- HTML includes the style.css content
- HTML contains section HTML fragments in correct order
- Custom CSS is injected after main styles
- Sections dict filtering works (missing sections are skipped)
- html_to_pdf produces a file (basic smoke test — requires WeasyPrint)
- Integration: assemble_html → html_to_pdf round-trip produces non-empty PDF
- get_template_dir returns a valid directory containing report.html

Requirements:
- Handle missing sections gracefully (the template already uses {% if %} guards)
- Use logging for timing and errors
- WeasyPrint may emit warnings about CSS features — filter/suppress known benign warnings
- Import WeasyPrint lazily if possible (it's a heavy import)

Output:
- `src/backtest_report/render.py`
- `tests/test_render.py`
- Short note on implementation
```

---

### Step S12 — Header & Appendix Sections

```text
[INSTRUCTIONS FOR THE CODE-GENERATION LLM]

Context:
- The project has models, fixtures, persistence, portfolio renderers, templates, CSS, and the render module.
- We need the header and appendix section renderers. These are simpler sections that display metadata rather than charts.

Task:
Create `src/backtest_report/header.py`, `src/backtest_report/appendix.py`, and their tests.

File: `src/backtest_report/header.py`

Implement:

1. `render_header(data: BacktestData, meta: BacktestMeta) -> SectionOutput`:
   - Render the header/title page section
   - HTML output should include:
     - Experiment ID (large, prominent — h1)
     - Strategy name (subtitle — h2)
     - Engine + version (small, muted text)
     - Date range: "start_date → end_date" with duration in years
     - Capital: formatted with currency symbol (e.g., "$1,000,000")
     - Risk target: "XX% annual"
     - Generated at: timestamp, small muted text
     - Git commit: short hash (first 7 chars), monospace font
     - Number of instruments in universe
   - Use div with class `br-header` for the dark banner styling
   - Return SectionOutput(section_id="header", html=...)

File: `src/backtest_report/appendix.py`

Implement:

1. `render_appendix(data: BacktestData, meta: BacktestMeta) -> SectionOutput`:
   - Render the appendix section with:
     - Full config as YAML dump in a <pre> block with class `br-appendix` and monospace styling
     - Data checksums table: filename → SHA-256 hash
     - Environment info: python_version, engine_version, report_version
     - Git commit (full hash if available, short hash in parentheses)
   - Use yaml.dump() for config serialisation (from meta.config.model_dump())
   - Return SectionOutput(section_id="appendix", html=...)

Files: `tests/test_header.py`, `tests/test_appendix.py` (new test files, or add to existing)

Tests for header:
- Renders SectionOutput with section_id "header"
- HTML contains experiment_id, strategy_name
- HTML contains formatted capital with currency
- HTML contains risk target percentage

Tests for appendix:
- Renders SectionOutput with section_id "appendix"
- HTML contains YAML config dump
- HTML contains checksums
- HTML contains version info

Requirements:
- Use the conftest.py fixtures
- Format currency using locale-aware formatting or manual comma separation
- Escape any HTML-special characters in config values
- Both modules should be importable without any heavy dependencies

Output:
- `src/backtest_report/header.py`
- `src/backtest_report/appendix.py`
- Test files
- Short note
```

---

### Step S13 — Report Orchestrator

```text
[INSTRUCTIONS FOR THE CODE-GENERATION LLM]

Context:
- The project now has ALL portfolio-level section renderers (portfolio_pnl, monthly_returns, portfolio_stats, rolling_stats), header, appendix, the render module (assemble_html, html_to_pdf), templates, CSS, models, fixtures, and persistence.
- We need the central orchestrator that wires everything together.

Task:
Create `src/backtest_report/report.py` with the BacktestReport class and convenience functions.

File: `src/backtest_report/report.py`

Implement:

1. `BacktestReport` class:
   ```python
   class BacktestReport:
       SECTION_REGISTRY = {
           "header": header.render_header,
           "portfolio_pnl": portfolio.render_portfolio_pnl,
           "monthly_returns": portfolio.render_monthly_returns,
           "portfolio_stats": portfolio.render_portfolio_stats,
           "rolling_stats": portfolio.render_rolling_stats,
           # instrument, position, attribution will be added in later steps
           "appendix": appendix.render_appendix,
       }
   ```
   - `__init__(self, data, meta, sections=None, template_dir=None, custom_css=None)`:
     - Store all parameters
     - If sections is None, use all keys from SECTION_REGISTRY
     - Validate that all requested section IDs exist in the registry
   - `generate(self, output_dir=None, fmt="pdf", filename=None) -> Path`:
     - Default output_dir: current working directory
     - Default filename: f"{meta.config.experiment_id}_report.{fmt}"
     - Run each section: iterate over the requested sections in registry order, call the render function, collect SectionOutput objects. Time each section.
     - Call assemble_html(sections_dict, self.meta, self.template_dir, self.custom_css)
     - If fmt="html": write HTML to output path, return path
     - If fmt="pdf": call html_to_pdf(html, output_path), return path
     - Log total generation time
   - `available_sections(cls) -> list[str]`: class method returning registered section IDs

2. Convenience function `generate_report(experiment_dir, sections=None, fmt="pdf") -> Path`:
   - Load data and meta from experiment_dir using `persist.read_experiment_dir()`
   - Create BacktestReport with loaded data
   - Call generate(output_dir=experiment_dir, fmt=fmt)
   - Return the output path

3. Stub for `from_pysystemtrade(system_path, config_path, meta_path, sections=None) -> BacktestReport`:
   - For now, raise NotImplementedError("pysystemtrade adapter not yet implemented")
   - Will be completed in step S21

Update: `src/backtest_report/__init__.py`
- Re-export: BacktestReport, BacktestData, BacktestMeta, BacktestConfig, InstrumentMeta, SectionOutput, generate_report
- Update __all__

Requirements:
- Import section modules at module level (header, portfolio, appendix)
- Use the existing render module (assemble_html, html_to_pdf)
- Handle section generation errors gracefully: if a section fails, log the error and continue with remaining sections (don't crash the whole report)
- Include comprehensive logging (section timing, total time, output path)

Output:
- `src/backtest_report/report.py`
- Updated `src/backtest_report/__init__.py`
- Short summary
```

---

### Step S14 — End-to-End Integration Test

```text
[INSTRUCTIONS FOR THE CODE-GENERATION LLM]

Context:
- The backtest-report project now has a complete pipeline from BacktestData → sections → HTML → PDF.
- Available sections: header, portfolio_pnl, monthly_returns, portfolio_stats, rolling_stats, appendix.
- Test fixtures exist in tests/fixtures/ and conftest.py.

Task:
Create `tests/test_report.py` with end-to-end integration tests.

File: `tests/test_report.py`

Implement:

1. `test_end_to_end_pdf_generation(sample_backtest_data, sample_meta, tmp_path)`:
   - Create BacktestReport with fixture data
   - Call generate(output_dir=tmp_path, fmt="pdf")
   - Assert: PDF file exists at returned path
   - Assert: PDF file size > 0 (at least 10KB for a real report)
   - Assert: filename matches expected pattern

2. `test_end_to_end_html_generation(sample_backtest_data, sample_meta, tmp_path)`:
   - Create BacktestReport with fixture data
   - Call generate(output_dir=tmp_path, fmt="html")
   - Assert: HTML file exists
   - Read HTML content and assert:
     - Contains "<!DOCTYPE html>"
     - Contains experiment_id
     - Contains "data:image/png;base64," (at least one embedded figure)
     - Contains "Cumulative Returns" (portfolio PnL section)
     - Contains "Monthly Returns" or table structure
     - Contains strategy_name
     - Contains config YAML dump (appendix)

3. `test_section_filtering(sample_backtest_data, sample_meta, tmp_path)`:
   - Create BacktestReport with sections=["header", "portfolio_pnl"]
   - Generate HTML
   - Assert: header and portfolio_pnl content appear
   - Assert: appendix content does NOT appear

4. `test_invalid_section_raises(sample_backtest_data, sample_meta)`:
   - Attempt to create BacktestReport with sections=["nonexistent"]
   - Assert: raises ValueError or KeyError

5. `test_generate_report_from_experiment_dir(sample_backtest_data, sample_meta, tmp_path)`:
   - Use persist.write_experiment_dir() to write fixture data to tmp_path
   - Call generate_report(tmp_path, fmt="html")
   - Assert: report file is created

6. `test_available_sections()`:
   - Call BacktestReport.available_sections()
   - Assert: returns list containing "header", "portfolio_pnl", etc.

Requirements:
- Use tmp_path fixture for all file output
- Use conftest.py fixtures for data
- Mark WeasyPrint PDF tests with @pytest.mark.slow if desired (they take a few seconds)
- Ensure tests work in CI (no display/GUI required — matplotlib Agg backend)

Output:
- `tests/test_report.py`
- Any updates to `tests/conftest.py` if new fixtures are needed
- Short note on test results
```

---

### Step S15 — Instrument PnL Small Multiples

```text
[INSTRUCTIONS FOR THE CODE-GENERATION LLM]

Context:
- The project has a working end-to-end pipeline with portfolio sections, header, and appendix.
- BacktestReport.SECTION_REGISTRY currently has: header, portfolio_pnl, monthly_returns, portfolio_stats, rolling_stats, appendix.
- We now add instrument-level analysis sections.

Task:
Create `src/backtest_report/instrument.py` (partial) and `tests/test_instrument.py` (partial).

File: `src/backtest_report/instrument.py`

Implement:

1. `render_instrument_pnl(data: BacktestData, meta: BacktestMeta) -> SectionOutput`:
   - Get instrument list from data.instrument_pnl.columns
   - Compute cumulative PnL for each instrument
   - Sort instruments by total PnL (best → worst)
   - Compute Sharpe ratio for each instrument (if instrument_returns available, use those; otherwise approximate from PnL)
   - Generate a matplotlib figure with small multiples layout:
     - 4 columns
     - Rows: ceil(n_instruments / 4)
     - Each subplot ~3" wide × 2" tall
     - Each subplot shows: cumulative PnL line, title = "CODE (Name)" or just "CODE", Sharpe annotation in corner
     - Consistent y-axis formatting (currency)
   - If more than 20 instruments: generate multiple figures (paginated)
   - Encode as base64 PNG
   - Generate HTML with img tags for each page figure
   - Return SectionOutput(section_id="instrument_pnl", figures={"instrument_pnl_p1": ..., ...}, html=...)

File: `tests/test_instrument.py`

Tests:
- render_instrument_pnl with 10 instruments (fixture data) produces valid SectionOutput
- Figure is present in SectionOutput.figures
- HTML contains img tag
- Works with missing instrument_meta (defaults to code-only labels)
- Works with fewer than 4 instruments (partial last row)

Requirements:
- Reuse matplotlib helpers from portfolio.py (fig_to_base64, apply_report_style, colour constants)
- Import these shared utilities — do NOT duplicate them
- Handle instruments with all-zero PnL gracefully (flat line, Sharpe = "N/A")
- Use tight_layout() or constrained_layout for the grid

Output:
- `src/backtest_report/instrument.py`
- `tests/test_instrument.py`
- Short note
```

---

### Step S16 — Instrument Stats Table

```text
[INSTRUCTIONS FOR THE CODE-GENERATION LLM]

Context:
- `instrument.py` exists with `render_instrument_pnl()`.
- We need the per-instrument statistics table.

Task:
Add `render_instrument_table()` to `src/backtest_report/instrument.py` and tests to `tests/test_instrument.py`.

Modify: `src/backtest_report/instrument.py`

Add:

1. `render_instrument_table(data: BacktestData, meta: BacktestMeta) -> SectionOutput`:
   - Compute per-instrument metrics:
     - Instrument name: code (name from instrument_meta if available)
     - Sharpe: annualised return / annualised vol (from instrument_returns or derived from PnL)
     - P&L: cumulative sum of instrument PnL
     - Max DD: maximum drawdown on the cumulative PnL curve
     - Avg Position: mean absolute position from data.positions
     - Turnover: positions.diff().abs().sum() / len(positions)
     - Win Rate: % of days with positive PnL
   - Sort by P&L descending
   - Render as HTML table with class `br-instrument-table`:
     - Column headers: Instrument, Sharpe, P&L, Max DD, Avg Position, Turnover, Win Rate
     - Alternating row background colours
     - Numeric formatting: Sharpe (2dp), P&L (currency with commas), Max DD (%), Avg Position (1dp), Turnover (2dp), Win Rate (%)
   - Return SectionOutput(section_id="instrument_table", html=..., tables={"instrument_table": df})

Modify: `tests/test_instrument.py`

Add tests:
- render_instrument_table returns valid SectionOutput
- HTML table contains expected column headers
- All instruments from fixture data appear
- Values are reasonable (Sharpe between -3 and 5, win rates between 0% and 100%)
- Handles missing instrument_returns (derives from PnL)
- Handles instruments not in positions DataFrame

Requirements:
- Keep existing render_instrument_pnl() intact
- Handle edge cases: instruments with no trades (all-zero PnL), instruments in PnL but not in positions
- Format currency values with commas and appropriate decimal places

Output:
- Updated `src/backtest_report/instrument.py`
- Updated `tests/test_instrument.py`
```

---

### Step S17 — Register Instrument Sections in Orchestrator

```text
[INSTRUCTIONS FOR THE CODE-GENERATION LLM]

Context:
- `instrument.py` now has render_instrument_pnl() and render_instrument_table().
- BacktestReport.SECTION_REGISTRY in report.py needs to include these.
- The integration test should verify these sections appear in the output.

Task:
Update `src/backtest_report/report.py` and `tests/test_report.py` to include instrument sections.

Modify: `src/backtest_report/report.py`

- Import the instrument module
- Add to SECTION_REGISTRY:
  - "instrument_pnl": instrument.render_instrument_pnl
  - "instrument_table": instrument.render_instrument_table
- Ensure registry order matches the template order (header → portfolio sections → instrument sections → appendix)

Modify: `tests/test_report.py`

- Update test_end_to_end_html_generation to also assert:
  - HTML contains instrument PnL figure (data:image/png;base64)
  - HTML contains instrument table headers (Instrument, Sharpe, P&L)
- Add test_instrument_sections_in_registry:
  - Verify "instrument_pnl" and "instrument_table" are in available_sections()

Requirements:
- Keep all existing tests passing
- The registry order should be: header, portfolio_pnl, monthly_returns, portfolio_stats, rolling_stats, instrument_pnl, instrument_table, appendix

Output:
- Updated `src/backtest_report/report.py`
- Updated `tests/test_report.py`
- Short note on changes
```

---

### Step S18 — Position Heatmap

```text
[INSTRUCTIONS FOR THE CODE-GENERATION LLM]

Context:
- The project has models, all portfolio sections, instrument sections, header/appendix, render pipeline, and orchestrator.
- We now add the position heatmap section.

Task:
Create `src/backtest_report/positions.py` and `tests/test_positions.py`.

File: `src/backtest_report/positions.py`

Implement:

1. `render_position_snapshot(data: BacktestData, meta: BacktestMeta) -> SectionOutput`:
   - Determine sampling frequency based on date range:
     - If range > 2 years: sample monthly ('ME')
     - Else: sample weekly ('W')
   - Resample positions DataFrame to chosen frequency (use last value per period)
   - Sort instruments (y-axis) by average absolute position size (most active at top)
   - Generate matplotlib heatmap:
     - Use imshow() or pcolormesh()
     - Diverging colourmap: RdBu_r (red = short, white = flat, blue = long)
     - Centre colourmap at 0
     - X-axis: time labels (formatted dates, rotated 45°)
     - Y-axis: instrument codes
     - Colour bar on the right with label "Position Size (contracts)"
     - Figure size: 12" wide × max(4, n_instruments * 0.4)" tall
     - Title: "Position Snapshot — {frequency} Sampling"
   - Handle edge cases:
     - If positions DataFrame is empty, return warning HTML
     - If > 30 instruments, paginate (show top 30 by activity)
   - Encode as base64 PNG
   - Return SectionOutput(section_id="position_snapshot", figures={"position_heatmap": base64}, html=...)

File: `tests/test_positions.py`

Tests:
- render_position_snapshot returns valid SectionOutput
- Heatmap figure is present and non-empty
- Monthly sampling used for >2 year range
- Weekly sampling used for <2 year range
- Empty positions DataFrame returns warning
- Works with fixture data (10 instruments, 5 years)

Requirements:
- Reuse fig_to_base64() and apply_report_style() from portfolio.py
- Use TwoSlopeNorm or DivergingNorm to centre the colourmap at 0
- Ensure instrument labels are readable (not overlapping)
- Handle NaN positions (treat as flat/zero)

Output:
- `src/backtest_report/positions.py`
- `tests/test_positions.py`
- Short note
```

---

### Step S19 — Attribution Section

```text
[INSTRUCTIONS FOR THE CODE-GENERATION LLM]

Context:
- The project has all sections except attribution. positions.py was just created.
- We need return attribution charts: by instrument and by sector/group.

Task:
Create `src/backtest_report/attribution.py` and `tests/test_attribution.py`.

File: `src/backtest_report/attribution.py`

Implement:

1. `render_attribution(data: BacktestData, meta: BacktestMeta) -> SectionOutput`:
   - **By-instrument attribution:**
     - Resample instrument_pnl to monthly (sum daily PnL per month)
     - Compute per-instrument monthly contribution
     - Identify top 10 instruments by total absolute PnL
     - Group remaining as "Other"
     - Generate stacked bar chart (monthly):
       - X-axis: months
       - Y-axis: P&L contribution (currency)
       - Coloured by instrument (use a qualitative colourmap, e.g., tab10 or Set3)
       - Legend outside plot
       - Title: "Monthly P&L Attribution — By Instrument"
     - Figure size: 12" × 5"
   
   - **By-sector attribution:**
     - Map instruments to sectors using data.instrument_meta
     - If instrument_meta is missing or sector is empty, use "Unknown"
     - Sum PnL by sector per month
     - Generate stacked bar chart (monthly):
       - X-axis: months
       - Y-axis: P&L contribution
       - Coloured by sector
       - Legend
       - Title: "Monthly P&L Attribution — By Sector"
     - Figure size: 12" × 5"
   
   - Encode both as base64 PNG
   - Generate HTML with both figures
   - Return SectionOutput(section_id="attribution", figures={"by_instrument": ..., "by_sector": ...}, html=...)

File: `tests/test_attribution.py`

Tests:
- render_attribution returns valid SectionOutput with both figures
- By-instrument figure groups correctly (top 10 + Other)
- By-sector figure handles missing sector metadata ("Unknown" grouping)
- Works with fixture data
- Handles case where all instruments have same sector
- Handles case where instrument_meta is empty

Requirements:
- Reuse fig_to_base64() and apply_report_style() from portfolio.py
- Handle instruments not in instrument_meta gracefully (default to "Unknown" sector)
- Stacked bars should handle negative values correctly (below zero line)
- Use different colormaps for instrument vs sector charts to visually distinguish them

Output:
- `src/backtest_report/attribution.py`
- `tests/test_attribution.py`
- Short note
```

---

### Step S20 — Register Position & Attribution Sections

```text
[INSTRUCTIONS FOR THE CODE-GENERATION LLM]

Context:
- positions.py has render_position_snapshot() and attribution.py has render_attribution().
- BacktestReport.SECTION_REGISTRY needs these final sections. After this step, all 10 sections are registered.
- The integration test should verify the complete report.

Task:
Update `src/backtest_report/report.py` and `tests/test_report.py`.

Modify: `src/backtest_report/report.py`

- Import positions and attribution modules
- Add to SECTION_REGISTRY:
  - "position_snapshot": positions.render_position_snapshot
  - "attribution": attribution.render_attribution
- Final registry order: header, portfolio_pnl, monthly_returns, portfolio_stats, rolling_stats, instrument_pnl, instrument_table, position_snapshot, attribution, appendix

Modify: `tests/test_report.py`

- Update test_end_to_end_html_generation:
  - Assert HTML contains position heatmap figure
  - Assert HTML contains attribution figures
- Add test_all_sections_registered:
  - Verify all 10 section IDs are in available_sections()
  - Assert: ["header", "portfolio_pnl", "monthly_returns", "portfolio_stats", "rolling_stats", "instrument_pnl", "instrument_table", "position_snapshot", "attribution", "appendix"]
- Add test_complete_pdf_all_sections:
  - Generate a PDF with ALL sections from fixture data
  - Assert PDF file is ≥ 50KB (reasonable minimum for a complete report)

Requirements:
- All existing tests must still pass
- The complete 10-section report should generate without errors from fixture data

Output:
- Updated `src/backtest_report/report.py`
- Updated `tests/test_report.py`
- Short note confirming all 10 sections are wired
```

---

### Step S21 — PySystemTrade Adapter

```text
[INSTRUCTIONS FOR THE CODE-GENERATION LLM]

Context:
- The project has a complete 10-section report pipeline that works with BacktestData (engine-agnostic).
- We now need the optional adapter that converts pysystemtrade System objects into BacktestData.
- pysystemtrade is an OPTIONAL dependency — the rest of the package must work without it.

Task:
Create `src/backtest_report/adapters/pysystemtrade.py`, `src/backtest_report/adapters/instrument_map.yaml`, and `tests/test_pysystemtrade_adapter.py`.

File: `src/backtest_report/adapters/pysystemtrade.py`

Implement:

1. `load_system(pickle_path: Path) -> "System"`:
   - Import pysystemtrade lazily (at function call, not module level)
   - Unpickle the System object
   - Handle version mismatch warnings (log but don't crash)
   - Handle ImportError: raise with clear message about installing pysystemtrade

2. `extract_backtest_data(system: "System") -> BacktestData`:
   - Get instrument list: system.get_instrument_list()
   - Get portfolio returns: system.accounts.portfolio().percent (convert to decimal)
   - For each instrument:
     - PnL: system.accounts.pandl_for_subsystem(instrument)
     - Positions: system.portfolio.get_notional_position(instrument)
     - Returns: derive from PnL / notional exposure (if available)
   - Load instrument metadata from instrument_map.yaml
   - Default to InstrumentMeta(code=code) for unmapped instruments
   - Build and return BacktestData

3. `extract_backtest_config(system: "System", config_path: Path) -> BacktestConfig`:
   - Extract instrument_universe, start/end dates from system
   - Read additional config from config_path (YAML)
   - Build BacktestConfig

4. `load_instrument_map() -> dict[str, InstrumentMeta]`:
   - Load instrument_map.yaml from package resources (importlib.resources)
   - Parse into dict of InstrumentMeta
   - Handle missing file gracefully (return empty dict with warning)

File: `src/backtest_report/adapters/instrument_map.yaml`

Create with mappings for at least these instruments (from the spec and the user's SG Trend Proxy universe):
EDOLLAR, US10, US5, US2, US30, GOLD, SILVER, CRUDE_W, BRENT, GAS_US, SP500, EUROSTX, NIKKEI, CORN, SOYBEAN, WHEAT, JPY, EUR, GBP, AUD, CAD, CHF, COPPER, COTTON, COFFEE, SUGAR, COCOA, PALLAD, PLAT, NASDAQ, RUSSELL, VIX, BOBL, BUND, BTP, OAT, GILT

Include for each: name, sector, group, asset_class, exchange, point_value, currency.

File: `tests/test_pysystemtrade_adapter.py`

Tests (use mocked System object — do NOT depend on actual pysystemtrade):
- Mock System with get_instrument_list(), accounts.portfolio(), accounts.pandl_for_subsystem(), portfolio.get_notional_position()
- extract_backtest_data returns valid BacktestData with correct instruments
- extract_backtest_config returns valid BacktestConfig
- load_instrument_map returns dict with expected keys
- Unmapped instruments default to InstrumentMeta(code=code)
- ImportError handling when pysystemtrade is not installed

Also update: `src/backtest_report/persist.py`
- In read_experiment_dir(), implement the pickle fallback path (Strategy 2):
  - If Parquet files not found but system.pkl exists
  - Import load_system and extract_backtest_data from adapters
  - Handle ImportError with clear message

Also update: `src/backtest_report/report.py`
- Implement from_pysystemtrade() convenience function (replace the NotImplementedError stub)

Requirements:
- ALL pysystemtrade imports must be inside function bodies, never at module level
- The adapter module itself should only fail when its functions are called without pysystemtrade, not on import
- Type hints use string literals for pysystemtrade types: "System"
- Include docstring notes about verifying API compatibility with pysystemtrade versions

Output:
- `src/backtest_report/adapters/pysystemtrade.py`
- `src/backtest_report/adapters/instrument_map.yaml`
- `tests/test_pysystemtrade_adapter.py`
- Updated `src/backtest_report/persist.py`
- Updated `src/backtest_report/report.py`
- Short summary
```

---

### Step S22 — Click CLI

```text
[INSTRUCTIONS FOR THE CODE-GENERATION LLM]

Context:
- The backtest-report project has a complete 10-section pipeline, persistence layer (local + pickle fallback), pysystemtrade adapter, and the BacktestReport orchestrator.
- We need the Click CLI that exposes all functionality to the command line.
- The CLI entry point is defined in pyproject.toml: backtest-report = "backtest_report.__main__:cli"

Task:
Rewrite `src/backtest_report/__main__.py` (replacing the stub) with the full CLI implementation.

File: `src/backtest_report/__main__.py`

Implement using Click (≥8.0):

1. `cli` — the main Click group:
   - `--version` option showing package version
   - `--verbose` flag that sets logging to DEBUG level

2. `generate` command:
   - Argument: PATH (optional) — local experiment directory
   - Options:
     - `--remote EXPERIMENT_ID` — pull from remote server (mutually exclusive with PATH)
     - `--host TEXT` — remote host override
     - `--remote-base TEXT` — remote base path override
     - `--sections TEXT` — comma-separated section IDs (default: all)
     - `--format` — pdf or html (default: pdf)
     - `--output-dir PATH` — output directory (default: experiment dir or cwd)
     - `--filename TEXT` — custom output filename
   - Raw DataFrame options (mutually exclusive with PATH and --remote):
     - `--portfolio-returns PATH`
     - `--instrument-pnl PATH`
     - `--positions PATH`
     - `--meta PATH`
   - Logic:
     - If PATH: load from local experiment dir
     - If --remote: load from remote (persist.read_remote_experiment)
     - If raw DataFrame options: load individual files and construct BacktestData
     - Create BacktestReport and generate
     - Print output path to stdout
   - Error handling: catch exceptions with click.echo + sys.exit(1)

3. `upload` command:
   - Argument: PDF_PATH — path to report PDF
   - Options: --experiment-id (required), --host, --remote-base
   - Logic: call persist.write_remote_report()

4. `sections` command:
   - No arguments
   - List all available section IDs from BacktestReport.SECTION_REGISTRY

5. `validate` command:
   - Argument: PATH — experiment directory
   - Logic: call persist.validate_experiment_dir(), print results

6. `export-parquet` command:
   - Argument: PATH — experiment directory containing system.pkl
   - Logic: load system via adapter, extract data, write Parquet exports

File: `tests/test_cli.py`

Tests using Click's CliRunner:
- `backtest-report --version` shows version string
- `backtest-report sections` lists expected section IDs
- `backtest-report validate <dir>` shows validation results
- `backtest-report generate <dir>` with fixture experiment dir produces output
- `backtest-report generate` with raw DataFrame options works
- Invalid section ID in --sections produces error
- Mutually exclusive options (PATH + --remote) produce error

Requirements:
- Use click.group(), @cli.command(), click.argument(), click.option()
- Configure logging in the cli group callback (--verbose → DEBUG, default → WARNING)
- Use click.echo() for user-facing output, logger for internal progress
- Handle missing files with clear error messages (not tracebacks)
- Sections option parsing: split on comma, strip whitespace

Output:
- `src/backtest_report/__main__.py` (complete rewrite)
- `tests/test_cli.py`
- Short note
```

---

### Step S23 — Remote Persistence (SCP)

```text
[INSTRUCTIONS FOR THE CODE-GENERATION LLM]

Context:
- The project has local persistence, the complete report pipeline, CLI, and pysystemtrade adapter.
- We need remote read/write for the hc4t server using SCP/rsync via subprocess.
- Remote settings use a config cascade: CLI flags → .backtest-report.yaml → env vars → defaults.

Task:
Add remote persistence functions to `src/backtest_report/persist.py` and create `tests/test_remote_persist.py`.

Modify: `src/backtest_report/persist.py`

Add:

1. `resolve_remote_config(host=None, remote_base=None) -> tuple[str, str]`:
   - Config cascade (highest to lowest priority):
     1. Explicit parameters (host, remote_base)
     2. Config file: look for `.backtest-report.yaml` in CWD, then home directory. Parse `remote.host` and `remote.base_path` keys
     3. Environment variables: `BACKTEST_REPORT_HOST`, `BACKTEST_REPORT_REMOTE_BASE`
     4. Defaults: host="quant@hc4t.sheldenkar.com", remote_base="/store/backtests"
   - Return (host, remote_base)

2. `read_remote_experiment(experiment_id, host=None, remote_base=None) -> tuple[BacktestData, BacktestMeta]`:
   - Resolve remote config
   - Create temp directory
   - Construct remote path: f"{remote_base}/{experiment_id}/"
   - SCP the entire experiment directory from remote to local temp:
     `subprocess.run(["scp", "-r", f"{host}:{remote_path}", str(local_tmp)], check=True, capture_output=True, text=True)`
   - Call read_experiment_dir(local_tmp / experiment_id) on the local copy
   - Return result
   - Handle subprocess.CalledProcessError with clear error message and SSH troubleshooting hints
   - Log SCP operations (start, success, failure)

3. `write_remote_report(pdf_path, experiment_id, host=None, remote_base=None) -> None`:
   - Resolve remote config
   - SCP the PDF to remote: f"{host}:{remote_base}/{experiment_id}/report.pdf"
   - Handle errors with clear messages

File: `tests/test_remote_persist.py`

Tests (ALL using mocked subprocess — do NOT make real SSH connections):
- resolve_remote_config with explicit params returns those params
- resolve_remote_config reads from .backtest-report.yaml
- resolve_remote_config reads from env vars
- resolve_remote_config falls back to defaults
- read_remote_experiment calls subprocess with correct SCP command
- read_remote_experiment handles SCP failure with clear error
- write_remote_report calls subprocess with correct SCP command
- write_remote_report handles SCP failure

Also update `tests/test_cli.py`:
- Add test for `backtest-report generate --remote <id>` (mocked)
- Add test for `backtest-report upload` command (mocked)

Requirements:
- Use subprocess.run with check=True, capture_output=True, text=True, timeout=120
- Handle CalledProcessError, TimeoutExpired, FileNotFoundError (scp not installed)
- Use tempfile.mkdtemp() for temp directories, clean up on success
- Config file parsing: use yaml.safe_load, handle missing file gracefully

Output:
- Updated `src/backtest_report/persist.py`
- `tests/test_remote_persist.py`
- Updated `tests/test_cli.py`
- Short note
```

---

### Step S24 — Full Test Suite & Coverage

```text
[INSTRUCTIONS FOR THE CODE-GENERATION LLM]

Context:
- The backtest-report project is feature-complete. All modules are implemented:
  models.py, persist.py, portfolio.py, instrument.py, positions.py, attribution.py,
  header.py, appendix.py, render.py, report.py, __main__.py, adapters/pysystemtrade.py.
- Tests exist for each module but may have gaps.
- Target: ≥80% test coverage.

Task:
Review all existing tests, fill coverage gaps, add edge-case tests, and configure coverage.

Modify: `pyproject.toml`

Add/update:
```toml
[tool.pytest.ini_options]
testpaths = ["tests"]
addopts = "--cov=backtest_report --cov-report=term-missing --cov-report=html -v"
markers = [
    "slow: marks tests as slow (deselect with '-m \"not slow\"')",
]

[tool.coverage.run]
source = ["src/backtest_report"]
omit = ["src/backtest_report/adapters/pysystemtrade.py"]

[tool.coverage.report]
fail_under = 80
show_missing = true
```

Review and add tests in ALL test files for the following edge cases:

1. `tests/test_models.py`:
   - BacktestData with non-DatetimeIndex raises ValueError
   - BacktestData with empty portfolio_returns raises ValueError
   - InstrumentMeta with all defaults
   - BacktestConfig model_dump() and JSON serialisation
   - SectionOutput with figures and tables populated

2. `tests/test_portfolio.py`:
   - Very short history (< 30 days)
   - Single-day returns
   - All-zero returns
   - All-negative returns (ensure no division by zero in Sharpe)
   - Missing QuantStats dependency (mock import failure)

3. `tests/test_instrument.py`:
   - Single instrument
   - >20 instruments (pagination)
   - Instruments with all-zero PnL
   - Missing instrument_meta for some instruments

4. `tests/test_positions.py`:
   - Very few dates (< 4 weeks)
   - All-flat positions (zero everywhere)
   - Large position values (test colourmap scaling)

5. `tests/test_attribution.py`:
   - No instrument_meta provided (all "Unknown" sectors)
   - Single sector (no stacking needed)
   - All negative PnL

6. `tests/test_render.py`:
   - Template not found (invalid template_dir)
   - Empty sections dict
   - Custom CSS injection

7. `tests/test_persist.py`:
   - Read from directory with only some files
   - Write then read round-trip with verified checksums
   - Validate directory with various states

8. `tests/test_report.py`:
   - Section generation failure (one section throws) — report still generates with others
   - Custom section ordering
   - generate_report from a complete experiment directory
   - Report with only header section

Requirements:
- Run `pytest --cov` and ensure ≥80% coverage
- Mark slow tests (PDF generation) with @pytest.mark.slow
- All tests must pass in a headless CI environment
- Use mocks/patches where appropriate to isolate units

Output:
- Updated test files (list all modified files)
- Coverage report summary
- Note on any remaining gaps
```

---

### Step S25 — Documentation, README & CI

```text
[INSTRUCTIONS FOR THE CODE-GENERATION LLM]

Context:
- The backtest-report project is feature-complete and tested (≥80% coverage).
- All modules, tests, CLI, and remote persistence are implemented.
- We need documentation and CI configuration.

Task:
Create documentation files, finalise the README, and set up GitHub Actions CI.

File: `README.md`

Create a comprehensive README with:
- Project title and one-line description
- Badges: Python version, license, tests status
- Overview (2–3 paragraphs explaining what the package does)
- Features list (bulleted)
- Installation instructions:
  - `pip install .` (from source)
  - `pip install ".[parquet]"` (with Parquet support)
  - `pip install ".[pysystemtrade]"` (with pysystemtrade adapter)
  - Dev install: `pip install -e ".[dev,parquet]"`
- Quick Start:
  - Python API example (BacktestData → BacktestReport → generate)
  - CLI example (backtest-report generate /path/to/experiment)
- CLI Reference (all subcommands with brief descriptions)
- Report Sections (list all 10 with 1-line descriptions)
- Configuration (.backtest-report.yaml example)
- Development section (make lint, make test, etc.)
- License (MIT)

File: `docs/usage.md`

Detailed usage guide:
- Preparing experiment data (Parquet + config + meta)
- Generating reports from pysystemtrade System objects
- Generating reports from raw DataFrames
- Customising sections
- Remote server integration (hc4t)
- Configuration override reference
- Troubleshooting (common errors and solutions)

File: `docs/architecture.md`

Architecture overview:
- Design principles (engine-agnostic, composable, reproducible)
- Data flow diagram (System → Adapter → BacktestData → Sections → HTML → PDF)
- Module overview with responsibilities
- Adding a custom section (how to write and register)
- Adding a new adapter (QuantConnect example)

File: `.github/workflows/ci.yml`

GitHub Actions workflow:
- Trigger: push to main, pull requests to main
- Matrix: Python 3.10, 3.11, 3.12
- Steps:
  1. Checkout
  2. Set up Python
  3. Install system dependencies (WeasyPrint requires libpango, libcairo, etc.)
  4. Install package: pip install -e ".[dev,parquet]"
  5. Lint: ruff check src/ tests/
  6. Type check: mypy src/
  7. Test: pytest tests/ -v --cov=backtest_report --cov-report=xml
  8. Upload coverage report

Finalise: `Makefile`

Ensure all targets work:
- install, lint, format, typecheck, test, clean, build, docs

File: `.backtest-report.yaml.example`

Example configuration file with all options commented with descriptions.

Requirements:
- README should be thorough but scannable (headers, code blocks, tables)
- CI workflow must install WeasyPrint system dependencies on Ubuntu
- Docs should cross-reference each other where relevant
- Include a note about font licensing (OFL) in the README

Output:
- `README.md`
- `docs/usage.md`
- `docs/architecture.md`
- `.github/workflows/ci.yml`
- `.backtest-report.yaml.example`
- Updated `Makefile`
- Short note summarising the documentation
```

---

*End of Prompt Pack — 25 steps covering the complete backtest-report implementation.*
