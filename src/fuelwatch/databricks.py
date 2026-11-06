"""Connexion à Databricks (SQL Warehouse + API fichiers), configurée par le fichier .env."""

import os

from databricks import sql
from databricks.sdk import WorkspaceClient
from dotenv import load_dotenv

load_dotenv()


def _env(name: str) -> str:
    value = os.environ.get(name)
    if not value:
        raise RuntimeError(f"Variable {name} manquante : remplissez le fichier .env")
    return value


def sql_connection():
    """Connexion SQL au warehouse. À utiliser avec `with sql_connection() as conn:`."""
    return sql.connect(
        server_hostname=_env("DATABRICKS_HOST"),
        http_path=_env("DATABRICKS_HTTP_PATH"),
        access_token=_env("DATABRICKS_TOKEN"),
    )


def workspace_client() -> WorkspaceClient:
    """Client de l'API Databricks (envoi de fichiers dans les Volumes)."""
    return WorkspaceClient(
        host=f"https://{_env('DATABRICKS_HOST')}", token=_env("DATABRICKS_TOKEN")
    )


def check_connection() -> None:
    """Affiche l'utilisateur, le catalogue et la version : vérifie que tout est bien configuré."""
    with sql_connection() as conn, conn.cursor() as cur:
        cur.execute("SELECT current_user(), current_catalog(), current_schema(), current_version()")
        user, catalog, schema, version = cur.fetchone()
    print(f"Connecté en tant que {user}")
    print(f"Catalogue : {catalog} / schéma : {schema}")
    print(f"Version : {version}")


if __name__ == "__main__":
    check_connection()
