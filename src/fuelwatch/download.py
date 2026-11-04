"""Téléchargement des fichiers bruts depuis donnees.roulez-eco.fr."""
from datetime import date
from pathlib import Path

import requests

BASE_URL = "https://donnees.roulez-eco.fr/opendata"
RAW_DIR = Path("data/raw")


class SourceError(RuntimeError):
    """La source n'a pas renvoyé le fichier attendu."""


def daily_url(day: date) -> str:
    return f"{BASE_URL}/jour/{day.strftime('%Y%m%d')}"


def daily_path(day: date, raw_dir: Path = RAW_DIR) -> Path:
    return raw_dir / "quotidien" / f"{day.isoformat()}.zip"


def annual_url(year: int) -> str:
    return f"{BASE_URL}/annee/{year}"


def annual_path(year: int, raw_dir: Path = RAW_DIR) -> Path:
    return raw_dir / "annuel" / f"{year}.zip"


def _download(url: str, path: Path, label: str, force: bool, timeout: int) -> Path:
    """Télécharge `url` vers `path`. Idempotent : ne refait rien si le fichier existe (sauf force)."""
    if path.exists() and not force:
        return path

    response = requests.get(url, timeout=timeout)
    response.raise_for_status()

    # Le site renvoie 200 + une page HTML quand le fichier n'existe pas (ou plus).
    if not response.content.startswith(b"PK"):
        raise SourceError(f"Pas de fichier zip pour {label} (reçu : {response.content[:40]!r})")

    # Écriture atomique : un plantage ne laisse jamais de fichier partiel à `path`.
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".zip.tmp")
    tmp.write_bytes(response.content)
    tmp.replace(path)

    return path


def download_daily(day: date, raw_dir: Path = RAW_DIR, force: bool = False) -> Path:
    """Télécharge le fichier quotidien de `day` et renvoie son chemin local."""
    return _download(
        daily_url(day), daily_path(day, raw_dir), f"le {day.isoformat()}", force, timeout=60
    )


def download_annual(year: int, raw_dir: Path = RAW_DIR, force: bool | None = None) -> Path:
    """Télécharge l'archive annuelle de `year` (~30 Mo) et renvoie son chemin local.

    Par défaut, l'année en cours est toujours retéléchargée (le fichier grossit chaque jour),
    les années passées ne le sont jamais (le fichier est figé).
    """
    if force is None:
        force = year == date.today().year
    return _download(
        annual_url(year), annual_path(year, raw_dir), f"l'année {year}", force, timeout=300
    )
