"""Enchaîne les étapes d'ingestion pour une journée : téléchargement -> Parquet -> Databricks."""
import sys
from datetime import date, timedelta

from fuelwatch import download, load, parse


def run_daily(day: date) -> dict[str, int]:
    """Ingestion complète d'une journée. Rejouable sans doublons."""
    download.download_daily(day)
    stations_path, _ = parse.convert_daily(day)
    load.setup()
    load.upload(stations_path.parent, day)
    return load.load(day)


if __name__ == "__main__":
    # python -m fuelwatch.pipeline [AAAA-MM-JJ]  (par défaut : hier)
    day = date.fromisoformat(sys.argv[1]) if len(sys.argv) > 1 else date.today() - timedelta(days=1)
    print(day, run_daily(day))
