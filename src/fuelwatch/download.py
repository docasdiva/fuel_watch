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


def download_daily(day: date, raw_dir: Path = RAW_DIR, force: bool = False) -> Path:
    """Télécharge le fichier quotidien de `day` et renvoie son chemin local.

    Idempotent : si le fichier existe déjà, on ne le retélécharge pas (sauf force=True).
    """
    path = daily_path(day, raw_dir)

    if path.exists() and not force:
        return path

    response = requests.get(daily_url(day), timeout=60)
    response.raise_for_status()

    # Le site renvoie 200 + une page HTML quand le fichier n'existe pas (ou plus).
    if not response.content.startswith(b"PK"):
        raise SourceError(
            f"Pas de fichier zip pour le {day.isoformat()} "
            f"(reçu : {response.content[:40]!r})"
        )

    # Écriture atomique : un plantage ne laisse jamais de fichier partiel à `path`.
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".zip.tmp")
    tmp.write_bytes(response.content)
    tmp.replace(path)

    return path
