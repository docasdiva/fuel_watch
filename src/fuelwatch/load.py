"""Chargement des Parquet dans Databricks : Volume (fichiers) puis tables Delta (raw)."""
from datetime import date
from pathlib import Path

from fuelwatch.databricks import sql_connection, workspace_client

CATALOG = "workspace"
SCHEMA = "fuelwatch_raw"
VOLUME = "fichiers"
VOLUME_PATH = f"/Volumes/{CATALOG}/{SCHEMA}/{VOLUME}"

SETUP_SQL = [
    f"CREATE SCHEMA IF NOT EXISTS {CATALOG}.{SCHEMA}",
    f"CREATE VOLUME IF NOT EXISTS {CATALOG}.{SCHEMA}.{VOLUME}",
    f"""CREATE TABLE IF NOT EXISTS {CATALOG}.{SCHEMA}.raw_stations (
        station_id BIGINT,
        latitude DOUBLE,
        longitude DOUBLE,
        code_postal STRING,
        type_route STRING,
        adresse STRING,
        ville STRING,
        services ARRAY<STRING>,
        automate_24_24 BOOLEAN,
        date_fichier DATE,
        charge_le TIMESTAMP
    )""",
    f"""CREATE TABLE IF NOT EXISTS {CATALOG}.{SCHEMA}.raw_prix (
        station_id BIGINT,
        carburant STRING,
        maj TIMESTAMP,
        prix DOUBLE,
        date_fichier DATE,
        charge_le TIMESTAMP
    )""",
]

# Colonnes lues dans le Parquet, avec conversion explicite vers le type de la table.
COLUMNS = {
    "raw_stations": "station_id, latitude, longitude, code_postal, type_route, adresse, ville, "
                    "services, automate_24_24",
    "raw_prix": "station_id, carburant, CAST(maj AS TIMESTAMP) AS maj, prix",
}
FILES = {"raw_stations": "stations.parquet", "raw_prix": "prix.parquet"}


def setup() -> None:
    """Crée le schéma, le Volume et les tables s'ils n'existent pas (rejouable)."""
    with sql_connection() as conn, conn.cursor() as cur:
        for statement in SETUP_SQL:
            cur.execute(statement)


def volume_dir(day: date) -> str:
    return f"{VOLUME_PATH}/quotidien/{day.isoformat()}"


def upload(local_dir: Path, day: date) -> None:
    """Envoie stations.parquet et prix.parquet dans le Volume (écrase si déjà présents)."""
    client = workspace_client()
    for filename in FILES.values():
        with open(local_dir / filename, "rb") as f:
            client.files.upload(f"{volume_dir(day)}/{filename}", f, overwrite=True)


def load(day: date) -> dict[str, int]:
    """Charge les fichiers de `day` dans les tables raw. Idempotent.

    REPLACE WHERE remplace, en une seule transaction, les lignes de cette date :
    relancer la même journée ne crée pas de doublons.
    """
    counts = {}
    with sql_connection() as conn, conn.cursor() as cur:
        for table, filename in FILES.items():
            cur.execute(
                f"""INSERT INTO {CATALOG}.{SCHEMA}.{table}
                REPLACE WHERE date_fichier = DATE'{day.isoformat()}'
                SELECT {COLUMNS[table]},
                       DATE'{day.isoformat()}' AS date_fichier,
                       current_timestamp() AS charge_le
                FROM read_files('{volume_dir(day)}/{filename}', format => 'parquet')"""
            )
            cur.execute(
                f"SELECT count(*) FROM {CATALOG}.{SCHEMA}.{table} "
                f"WHERE date_fichier = DATE'{day.isoformat()}'"
            )
            counts[table] = cur.fetchone()[0]
    return counts
