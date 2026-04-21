"""CLI entry point for backtest-report."""
import click

from backtest_report import __version__


@click.group()
@click.version_option(version=__version__)
def cli() -> None:
    """Generate PDF backtest reports from trading system data."""
    pass


@cli.command()
def generate() -> None:
    """Generate a backtest report."""
    print("Not yet implemented")


if __name__ == "__main__":
    cli()