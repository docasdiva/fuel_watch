"""Parsing des fichiers XML Prix Carburants vers Parquet."""
import zipfile
from datetime import date, datetime
from pathlib import Path

import pyarrow as pa
import pyarrow.parquet as pq
from lxml import etree

from fuelwatch.download import RAW_DIR, daily_path

PARQUET_DIR = Path("data/parquet")
COORD_FACTOR = 100_000  # les coordonnées sont stockées x 100 000

# Schémas explicites : les types ne dépendent pas du contenu du fichier
# (sinon une colonne entièrement vide serait typée "null").
STATIONS_SCHEMA = pa.schema([
    ("station_id", pa.int64()),
    ("latitude", pa.float64()),
    ("longitude", pa.float64()),
    ("code_postal", pa.string()),
    ("type_route", pa.string()),
    ("adresse", pa.string()),
    ("ville", pa.string()),
    ("services", pa.list_(pa.string())),
    ("automate_24_24", pa.bool_()),
])

PRICES_SCHEMA = pa.schema([
    ("station_id", pa.int64()),
    ("carburant", pa.string()),
    ("maj", pa.timestamp("s")),
    ("prix", pa.float64()),
])


def _coord(value: str | None) -> float | None:
    return float(value) / COORD_FACTOR if value else None


def _timestamp(value: str | None) -> datetime | None:
    return datetime.fromisoformat(value) if value else None


def parse_station(pdv) -> dict:
    """Transforme un élément <pdv> en dictionnaire (une ligne de la table stations)."""
    horaires = pdv.find("horaires")
    return {
        "station_id": int(pdv.get("id")),
        "latitude": _coord(pdv.get("latitude")),
        "longitude": _coord(pdv.get("longitude")),
        "code_postal": pdv.get("cp"),
        "type_route": pdv.get("pop"),
        "adresse": pdv.findtext("adresse"),
        "ville": pdv.findtext("ville"),
        "services": [s.text for s in pdv.iterfind("services/service") if s.text],
        "automate_24_24": horaires is not None and horaires.get("automate-24-24") == "1",
    }


def parse_prices(pdv) -> list[dict]:
    """Une ligne par élément <prix> de la station."""
    station_id = int(pdv.get("id"))
    return [
        {
            "station_id": station_id,
            "carburant": p.get("nom"),
            "maj": _timestamp(p.get("maj")),
            "prix": float(p.get("valeur")),
        }
        for p in pdv.iterfind("prix")
        if p.get("valeur")
    ]


def iter_pdv(zip_path: Path):
    """Parcourt les <pdv> du XML contenu dans le zip, un par un, sans tout charger."""
    with zipfile.ZipFile(zip_path) as zf:
        xml_name = zf.namelist()[0]
        with zf.open(xml_name) as f:  # f est lu en octets -> lxml gère l'encodage
            for _, pdv in etree.iterparse(f, tag="pdv"):
                yield pdv
                # Libère la mémoire : la station traitée et celles d'avant.
                pdv.clear()
                while pdv.getprevious() is not None:
                    del pdv.getparent()[0]


def write_parquet(table: pa.Table, path: Path) -> None:
    """Écriture atomique, comme dans download.py."""
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".parquet.tmp")
    pq.write_table(table, tmp, compression="zstd")
    tmp.replace(path)


def convert_zip(zip_path: Path, out_dir: Path, batch_size: int = 200_000) -> tuple[Path, Path]:
    """Zip XML -> out_dir/stations.parquet + out_dir/prix.parquet.

    Les prix sont écrits par lots de `batch_size` lignes : la mémoire reste stable,
    même pour un fichier annuel (plusieurs millions de prix).
    Écriture atomique : fichiers .tmp renommés à la fin seulement.
    """
    out_dir.mkdir(parents=True, exist_ok=True)
    stations_path, prices_path = out_dir / "stations.parquet", out_dir / "prix.parquet"
    prices_tmp = prices_path.with_suffix(".parquet.tmp")

    stations, batch = [], []
    with pq.ParquetWriter(prices_tmp, PRICES_SCHEMA, compression="zstd") as writer:
        for pdv in iter_pdv(zip_path):
            stations.append(parse_station(pdv))
            batch.extend(parse_prices(pdv))
            if len(batch) >= batch_size:
                writer.write_table(pa.Table.from_pylist(batch, schema=PRICES_SCHEMA))
                batch = []
        if batch:
            writer.write_table(pa.Table.from_pylist(batch, schema=PRICES_SCHEMA))

    write_parquet(pa.Table.from_pylist(stations, schema=STATIONS_SCHEMA), stations_path)
    prices_tmp.replace(prices_path)
    return stations_path, prices_path


def convert_daily(
    day: date, raw_dir: Path = RAW_DIR, parquet_dir: Path = PARQUET_DIR
) -> tuple[Path, Path]:
    """Zip quotidien -> Parquet. Rejouable : la sortie est écrasée."""
    return convert_zip(daily_path(day, raw_dir), parquet_dir / "quotidien" / day.isoformat())
