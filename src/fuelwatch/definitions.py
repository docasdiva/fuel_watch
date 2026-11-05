"""Orchestration Dagster de FuelWatch.

Lancement de l'interface : dagster dev -m fuelwatch.definitions
"""
from datetime import date

import dagster as dg

from fuelwatch.pipeline import run_daily

# Une partition par jour. Le site ne garde qu'environ 1 mois de fichiers quotidiens.
partitions_quotidiennes = dg.DailyPartitionsDefinition(
    start_date="2026-10-10",
    timezone="Europe/Paris",
)


@dg.asset(
    partitions_def=partitions_quotidiennes,
    group_name="ingestion",
    retry_policy=dg.RetryPolicy(max_retries=3, delay=600),
    description="Fichier quotidien téléchargé, converti en Parquet et chargé dans "
    "raw_stations et raw_prix (Databricks).",
)
def raw_quotidien(context: dg.AssetExecutionContext) -> dg.MaterializeResult:
    day = date.fromisoformat(context.partition_key)
    counts = run_daily(day)
    context.log.info(f"{day} : {counts}")
    return dg.MaterializeResult(
        metadata={
            "nb_stations": counts["raw_stations"],
            "nb_prix": counts["raw_prix"],
        }
    )


defs = dg.Definitions(assets=[raw_quotidien])