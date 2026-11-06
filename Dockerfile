FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    DAGSTER_HOME=/opt/dagster/home

WORKDIR /app

# Code Python et dépendances (installation « éditable » : le code reste dans /app/src,
# ce qui permet à definitions.py de retrouver /app/transform).
COPY pyproject.toml ./
COPY src ./src
RUN pip install --no-cache-dir -e . && mkdir -p "$DAGSTER_HOME"

# Projet dbt et dashboard
COPY transform ./transform
COPY dashboard ./dashboard

# Paquets dbt et manifest.json générés à la construction.
# Identifiants factices : dbt parse ne se connecte pas à Databricks.
RUN export DATABRICKS_HOST=build DATABRICKS_HTTP_PATH=build DATABRICKS_TOKEN=build \
    && dbt deps --project-dir transform --profiles-dir transform \
    && dbt parse --project-dir transform --profiles-dir transform

EXPOSE 3000 8501