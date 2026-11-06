"""Dashboard FuelWatch : prix des carburants en France.

Lancement : streamlit run dashboard/app.py
"""

import pandas as pd
import streamlit as st

from fuelwatch.databricks import sql_connection

MARTS = "workspace.fuelwatch_marts"
CARBURANTS = ["Gazole", "SP95", "SP98", "E10", "E85", "GPLc"]

st.set_page_config(page_title="FuelWatch", page_icon="⛽", layout="wide")


# ---------- Lecture des données (marts uniquement) ----------


@st.cache_data(ttl=3600, show_spinner="Lecture des données dans Databricks…")
def lire(sql: str) -> pd.DataFrame:
    """Exécute une requête dans Databricks. Le résultat est gardé en cache 1 heure."""
    with sql_connection() as conn, conn.cursor() as cur:
        cur.execute(sql)
        return cur.fetchall_arrow().to_pandas()


def prix_nationaux() -> pd.DataFrame:
    """Prix moyen national par jour et carburant (moyenne pondérée par le nombre de relevés)."""
    df = lire(f"""
        select jour, carburant,
               sum(prix_moyen * nb_releves) / sum(nb_releves) as prix_moyen
        from {MARTS}.fct_prix_journaliers
        where jour >= '2022-01-01'
        group by jour, carburant
    """)
    df["jour"] = pd.to_datetime(df["jour"])
    return df


def prix_actuels() -> pd.DataFrame:
    """Dernier prix connu de chaque station active, par carburant."""
    df = lire(f"select * from {MARTS}.fct_prix_actuels")
    # Les heures sont déjà en heure de Paris : on retire juste l'étiquette de fuseau.
    df["maj_paris"] = pd.to_datetime(df["maj_paris"]).dt.tz_localize(None)
    return df


def couleur_prix(prix: pd.Series) -> list[str]:
    """Du vert (moins cher) au rouge (plus cher), sur la plage 5 %-95 % des prix."""
    bas, haut = prix.quantile(0.05), prix.quantile(0.95)
    t = ((prix - bas) / max(haut - bas, 0.001)).clip(0, 1)
    return [f"#{int(255 * x):02x}{int(200 * (1 - x)):02x}40b0" for x in t]


nationaux = prix_nationaux()
actuels = prix_actuels()

# ---------- En-tête ----------

st.title("⛽ FuelWatch : les prix des carburants en France")
derniere_maj = actuels["maj_paris"].max()
st.caption(
    f"Source : données ouvertes prix-carburants (data.gouv.fr) · "
    f"Dernière mise à jour : {derniere_maj:%d/%m/%Y %H:%M} · "
    f"{actuels['station_id'].nunique():,} stations actives".replace(",", " ")
)

# ---------- Indicateurs : moyenne des 7 derniers jours, comparée à la semaine d'avant ----------

serie = nationaux.pivot_table(index="jour", columns="carburant", values="prix_moyen").sort_index()
fin = serie.index.max()
semaine = serie[serie.index > fin - pd.Timedelta(days=7)].mean()
semaine_avant = serie[
    (serie.index <= fin - pd.Timedelta(days=7)) & (serie.index > fin - pd.Timedelta(days=14))
].mean()

st.subheader("Prix moyen national (7 derniers jours)")
colonnes = st.columns(len(CARBURANTS))
for colonne, carburant in zip(colonnes, CARBURANTS, strict=True):
    ecart = semaine[carburant] - semaine_avant[carburant]
    colonne.metric(
        carburant,
        f"{semaine[carburant]:.3f} €",
        f"{ecart * 100:+.1f} cts sur 7 j",
        delta_color="inverse",  # une baisse de prix est une bonne nouvelle : en vert
    )

# ---------- Évolution ----------

st.subheader("Évolution depuis 2022")
choix = st.multiselect("Carburants", CARBURANTS, default=["Gazole", "SP98", "E10"])
if choix:
    hebdo = serie[choix].resample("W").mean()  # moyenne par semaine : courbe plus lisible
    st.line_chart(hebdo, y_label="€ / litre", x_label="")

# ---------- Choix du carburant pour la suite ----------

st.divider()
carburant = st.selectbox("Carburant pour la carte et les départements", CARBURANTS)
stations = actuels[actuels["carburant"] == carburant].copy()

# ---------- Départements ----------

par_dep = (
    stations.groupby("departement")
    .agg(prix_moyen=("prix", "mean"), nb_stations=("station_id", "count"))
    .query("nb_stations >= 5")  # on écarte les départements avec trop peu de stations
    .sort_values("prix_moyen")
)

gauche, droite = st.columns(2)
with gauche:
    st.subheader("Les 10 départements les moins chers")
    st.bar_chart(
        par_dep.head(10)["prix_moyen"],
        horizontal=True,
        x_label="€ / litre",
        y_label="",
        color="#2e9e5b",
    )
with droite:
    st.subheader("Les 10 départements les plus chers")
    st.bar_chart(
        par_dep.tail(10)["prix_moyen"],
        horizontal=True,
        x_label="€ / litre",
        y_label="",
        color="#d1495b",
    )

# ---------- Carte ----------

st.subheader(f"Carte des stations : {carburant}")
st.caption("Vert : parmi les moins chères · Rouge : parmi les plus chères")
stations["couleur"] = couleur_prix(stations["prix"])
st.map(stations, latitude="latitude", longitude="longitude", color="couleur", size=400)

# ---------- Stations les moins chères ----------

st.subheader(f"Les 10 stations les moins chères : {carburant}")
st.dataframe(
    stations.nsmallest(10, "prix")[["ville", "adresse", "departement", "prix", "maj_paris"]],
    hide_index=True,
    column_config={
        "ville": "Ville",
        "adresse": "Adresse",
        "departement": "Dép.",
        "prix": st.column_config.NumberColumn("Prix", format="%.3f €"),
        "maj_paris": st.column_config.DatetimeColumn("Mis à jour", format="DD/MM HH:mm"),
    },
)
