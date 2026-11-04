"""Enchaîne les étapes d'ingestion : téléchargement -> Parquet -> Databricks.

Utilisation :
    python -m fuelwatch.pipeline                    # journée d'hier
    python -m fuelwatch.pipeline 2026-11-03         # une journée précise
    python -m fuelwatch.pipeline backfill 2022 2026 # archives annuelles (années incluses)
"""
import sys
import time
from datetime import date, timedelta

from fuelwatch import download, load, parse
from fuelwatch.parse import PARQUET_DIR


def run_daily(day: date) -> dict[str, int]:
    """Ingestion complète d'une journée. Rejouable sans doublons."""
    download.download_daily(day)
    stations_path, _ = parse.convert_daily(day)
    load.setup()
    load.upload(stations_path.parent, load.daily_volume_dir(day))
    return load.load_daily(day)


def run_annual(year: int) -> dict[str, int]:
    """Ingestion complète d'une archive annuelle. Rejouable sans doublons."""
    zip_path = download.download_annual(year)
    out_dir = PARQUET_DIR / "annuel" / str(year)
    parse.convert_zip(zip_path, out_dir)
    load.setup()
    load.upload(out_dir, load.annual_volume_dir(year))
    return load.load_annual(year)


def backfill(first_year: int, last_year: int) -> None:
    """Rejoue les archives annuelles de first_year à last_year (incluses), une par une."""
    for year in range(first_year, last_year + 1):
        start = time.time()
        counts = run_annual(year)
        print(f"{year} : {counts} ({time.time() - start:.0f} s)")


if __name__ == "__main__":
    args = sys.argv[1:]
    if args and args[0] == "backfill":
        backfill(int(args[1]), int(args[2]))
    else:
        day = date.fromisoformat(args[0]) if args else date.today() - timedelta(days=1)
        print(day, run_daily(day))
