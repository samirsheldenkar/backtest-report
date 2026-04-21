import importlib.metadata
import logging

try:
    __version__ = importlib.metadata.version("backtest-report")
except importlib.metadata.PackageNotFoundError:
    __version__ = "0.0.0-dev"

__all__ = [
    "cli",
    "report",
    "models",
    "adapters",
    "templates",
]

logger = logging.getLogger("backtest_report")