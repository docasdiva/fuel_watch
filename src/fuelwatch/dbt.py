"""Lance dbt avec les variables du fichier .env (dbt ne lit pas .env tout seul).

Utilisation : python -m fuelwatch.dbt debug | build | run | test | source freshness ...
"""

import sys
from pathlib import Path

from dbt.cli.main import dbtRunner
from dotenv import load_dotenv

PROJECT_DIR = Path(__file__).resolve().parents[2] / "transform"


def run_dbt(args: list[str]) -> bool:
    load_dotenv()
    result = dbtRunner().invoke(
        [*args, "--project-dir", str(PROJECT_DIR), "--profiles-dir", str(PROJECT_DIR)]
    )
    return result.success


if __name__ == "__main__":
    sys.exit(0 if run_dbt(sys.argv[1:]) else 1)
