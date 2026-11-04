"""Chargement des Parquet dans Databricks : Volume (fichiers) puis tables Delta (raw).

Deux familles de tables, car les deux sources n'ont pas le même sens :
- quotidien : photo de la fin de journée (dernier prix connu)   -> partition date_fichier
- annuel    : journal de tous les changements de prix de l'année -> partition annee
"""
from datetime import date
from pathlib import Path

from fuelwatch.databricks import sql_connection, workspace_client

CATALOG = "workspace"
SCHEMA = "fuelwatch_raw"
VOLUME = "fichiers"
VOLUME_PATH = f"/Volumes/{CATALOG}/{SCHEMA}/{VOLUME}"

STATIONS_COLUMNS = """
    station_id BIGINT,
    latitude DOUBLE,
    longitude DOUBLE,
    code_postal STRING,
    type_route STRING,
    adresse STRING,
    ville STRING,
    services ARRAY<STRING>,
    automate_24_24 BOOLEAN"""

PRIX_COLUMNS = """
    station_id BIGINT,
    carburant STRING,
    maj TIMESTAMP,
    prix DOUBLE"""

def _create_table(name: str, columns: str, partition: str) -> str:
    return (
        f"CREATE TABLE IF NOT EXISTS {CATALOG}.{SCHEMA}.{name} "
        f"({columns}, {partition}, charge_le TIMESTAMP)"
    )


SETUP_SQL = [
    f"CREATE SCHEMA IF NOT EXISTS {CATALOG}.{SCHEMA}",
    f"CREATE VOLUME IF NOT EXISTS {CATALOG}.{SCHEMA}.{VOLUME}",
    _create_table("raw_stations", STATIONS_COLUMNS, "date_fichier DATE"),
    _create_table("raw_prix", PRIX_COLUMNS, "date_fichier DATE"),
    _create_table("raw_stations_annuel", STATIONS_COLUMNS, "annee INT"),
    _create_table("raw_prix_annuel", PRIX_COLUMNS, "annee INT"),
]

# Colonnes lues dans le Parquet, avec conversion explicite vers le type de la table.
SELECT_STATIONS = (
    "station_id, latitude, longitude, code_postal, type_route, adresse, ville, "
    "services, automate_24_24"
)
SELECT_PRIX = "station_id, carburant, CAST(maj AS TIMESTAMP) AS maj, prix"


def setup() -> None:
    """Crée le schéma, le Volume et les tables s'ils n'existent pas (rejouable)."""
    with sql_connection() as conn, conn.cursor() as cur:
        for statement in SETUP_SQL:
            cur.execute(statement)


def daily_volume_dir(day: date) -> str:
    return f"{VOLUME_PATH}/quotidien/{day.isoformat()}"


def annual_volume_dir(year: int) -> str:
    return f"{VOLUME_PATH}/annuel/{year}"


def upload(local_dir: Path, volume_dir: str) -> None:
    """Envoie stations.parquet et prix.parquet dans le Volume (écrase si déjà présents)."""
    client = workspace_client()
    for filename in ("stations.parquet", "prix.parquet"):
        with open(local_dir / filename, "rb") as f:
            client.files.upload(f"{volume_dir}/{filename}", f, overwrite=True)


def _replace(cur, table: str, select: str, partition: str, value: str, file: str) -> int:
    """Remplace, en une transaction Delta, les lignes de la partition par le contenu du fichier.

    C'est ce qui rend le chargement idempotent : relancer ne crée pas de doublons.
    """
    full_name = f"{CATALOG}.{SCHEMA}.{table}"
    cur.execute(
        f"""INSERT INTO {full_name}
        REPLACE WHERE {partition} = {value}
        SELECT {select}, {value} AS {partition}, current_timestamp() AS charge_le
        FROM read_files('{file}', format => 'parquet')"""
    )
    cur.execute(f"SELECT count(*) FROM {full_name} WHERE {partition} = {value}")
    return cur.fetchone()[0]


def load_daily(day: date) -> dict[str, int]:
    """Charge les fichiers quotidiens de `day` dans raw_stations et raw_prix."""
    folder, value = daily_volume_dir(day), f"DATE'{day.isoformat()}'"
    with sql_connection() as conn, conn.cursor() as cur:
        return {
            "raw_stations": _replace(cur, "raw_stations", SELECT_STATIONS, "date_fichier",
                                     value, f"{folder}/stations.parquet"),
            "raw_prix": _replace(cur, "raw_prix", SELECT_PRIX, "date_fichier",
                                 value, f"{folder}/prix.parquet"),
        }


def load_annual(year: int) -> dict[str, int]:
    """Charge l'archive de `year` dans raw_stations_annuel et raw_prix_annuel."""
    folder, value = annual_volume_dir(year), str(int(year))
    with sql_connection() as conn, conn.cursor() as cur:
        return {
            "raw_stations_annuel": _replace(cur, "raw_stations_annuel", SELECT_STATIONS, "annee",
                                            value, f"{folder}/stations.parquet"),
            "raw_prix_annuel": _replace(cur, "raw_prix_annuel", SELECT_PRIX, "annee",
                                        value, f"{folder}/prix.parquet"),
        }
