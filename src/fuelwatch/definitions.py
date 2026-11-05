"""Orchestration Dagster de FuelWatch.

Lancement de l'interface : dagster dev -m fuelwatch.definitions
"""
from datetime import date
from pathlib import Path

import dagster as dg
from dagster_dbt import DbtCliResource, DbtProject, dbt_assets

from fuelwatch.pipeline import run_daily

# ---------- Ingestion ----------

# Une partition par jour. Le site ne garde qu'environ 1 mois de fichiers quotidiens.
partitions_quotidiennes = dg.DailyPartitionsDefinition(
    start_date="2026-10-10",
    timezone="Europe/Paris",
)

# Mêmes noms que les sources dbt (source « raw », tables raw_stations et raw_prix) :
# Dagster relie ainsi automatiquement l'ingestion aux modèles dbt.
RAW_STATIONS = dg.AssetKey(["raw", "raw_stations"])
RAW_PRIX = dg.AssetKey(["raw", "raw_prix"])


@dg.multi_asset(
    specs=[
        dg.AssetSpec(RAW_STATIONS, group_name="ingestion",
                     description="Stations du fichier quotidien, dans Databricks."),
        dg.AssetSpec(RAW_PRIX, group_name="ingestion",
                     description="Prix du fichier quotidien, dans Databricks."),
    ],
    partitions_def=partitions_quotidiennes,
    retry_policy=dg.RetryPolicy(max_retries=3, delay=600),
)
def ingestion_quotidienne(context: dg.AssetExecutionContext):
    """Télécharge le fichier du jour, le convertit en Parquet et le charge dans Databricks."""
    day = date.fromisoformat(context.partition_key)
    counts = run_daily(day)
    context.log.info(f"{day} : {counts}")
    yield dg.MaterializeResult(asset_key=RAW_STATIONS,
                               metadata={"nb_lignes": counts["raw_stations"]})
    yield dg.MaterializeResult(asset_key=RAW_PRIX,
                               metadata={"nb_lignes": counts["raw_prix"]})


# ---------- Transformation (dbt) ----------

TRANSFORM_DIR = Path(__file__).resolve().parents[2] / "transform"

dbt_project = DbtProject(project_dir=TRANSFORM_DIR, profiles_dir=TRANSFORM_DIR)
dbt_project.prepare_if_dev()  # régénère manifest.json quand on lance « dagster dev »


@dbt_assets(manifest=dbt_project.manifest_path)
def fuelwatch_dbt(context: dg.AssetExecutionContext, dbt: DbtCliResource):
    yield from dbt.cli(["build"], context=context).stream()


# ---------- Définitions ----------

defs = dg.Definitions(
    assets=[ingestion_quotidienne, fuelwatch_dbt],
    resources={"dbt": DbtCliResource(project_dir=dbt_project)},
)