"""Orchestration Dagster de FuelWatch.

Lancement de l'interface : dagster dev -m fuelwatch.definitions
"""
from collections.abc import Mapping
from datetime import date
from pathlib import Path
from typing import Any

import dagster as dg
from dagster_dbt import DagsterDbtTranslator, DbtCliResource, DbtProject, dbt_assets

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


class FuelwatchDbtTranslator(DagsterDbtTranslator):
    """Range tous les modèles dbt dans le groupe « transformation »."""

    def get_group_name(self, dbt_resource_props: Mapping[str, Any]) -> str:
        return "transformation"


@dbt_assets(
    manifest=dbt_project.manifest_path,
    dagster_dbt_translator=FuelwatchDbtTranslator(),
)
def fuelwatch_dbt(context: dg.AssetExecutionContext, dbt: DbtCliResource):
    yield from dbt.cli(["build"], context=context).stream()


# ---------- Planification ----------

# Ingestion de la veille, puis dbt build : tout le graphe en une exécution.
job_quotidien = dg.define_asset_job("job_quotidien", selection=dg.AssetSelection.all())

# Chaque jour à 8 h (heure de Paris), pour la dernière journée complète.
planning_quotidien = dg.build_schedule_from_partitioned_job(
    job_quotidien,
    hour_of_day=8,
    default_status=dg.DefaultScheduleStatus.RUNNING,
)


# ---------- Définitions ----------

defs = dg.Definitions(
    assets=[ingestion_quotidienne, fuelwatch_dbt],
    jobs=[job_quotidien],
    schedules=[planning_quotidien],
    resources={"dbt": DbtCliResource(project_dir=dbt_project)},
)