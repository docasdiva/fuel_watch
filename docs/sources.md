# Sources de données

## Vue d'ensemble

Les prix des carburants en France sont publiés par le Ministère de l'Économie (système « Prix Carburants »).
Chaque station-service est légalement tenue de déclarer ses prix. Les données sont diffusées en open data
sous **Licence Ouverte / Open Licence 2.0 (Etalab)** : réutilisation libre, y compris commerciale, avec mention de la source.

- Source d'origine : <https://donnees.roulez-eco.fr/opendata>
- Copie sur data.gouv.fr (mêmes données, converties en CSV/JSON) :
  <https://www.data.gouv.fr/datasets/prix-des-carburants-en-france-flux-quotidien-1>

Le projet utilise la **source d'origine** : elle propose des fichiers datés (indispensables pour l'idempotence
et le backfill), alors que data.gouv.fr ne fournit que le fichier du jour, écrasé quotidiennement.

## Les fichiers disponibles

| Flux | URL | Contenu | Fréquence | Taille (zip / XML) | Historique |
|---|---|---|---|---|---|
| Instantané | `/opendata/instantane` | État actuel : dernier prix connu par station et carburant | ~10 min | 0,9 Mo / 12 Mo | Aucun |
| Quotidien | `/opendata/jour/AAAAMMJJ` | État en fin de journée J | 1 / jour | 1,1 Mo / 15 Mo | ~1 mois glissant |
| Annuel | `/opendata/annee/AAAA` | **Tous** les changements de prix de l'année | 1 / jour (année en cours) | ~30 Mo / ~350 Mo | Depuis 2007 |

Volumes observés (octobre 2026) :

| Fichier | Stations | Lignes de prix |
|---|---|---|
| Instantané | 9 818 | 31 772 |
| Quotidien 14/10/2026 | 9 945 | 31 476 |
| Annuel 2026 (au 14/10) | 14 902 | 4 360 073 |

L'annuel contient plus de stations car il inclut celles fermées au cours de l'année.

## Structure des données

Format : **XML**, encodé en **ISO-8859-1**, dans une archive zip. Un élément `<pdv>` (point de vente) par station :

```xml
<pdv id="1000001" latitude="4620100" longitude="519800" cp="01000" pop="R">
  <adresse>596 AVENUE DE TREVOUX</adresse>
  <ville>SAINT-DENIS-LÈS-BOURG</ville>
  <horaires automate-24-24="">
    <jour id="1" nom="Lundi" ferme="">
      <horaire ouverture="08.30" fermeture="19.00"/>
    </jour>
    ...
  </horaires>
  <services>
    <service>Station de gonflage</service>
    <service>DAB (Distributeur automatique de billets)</service>
  </services>
  <prix nom="Gazole" id="1" maj="2026-10-14T00:46:00" valeur="2.417"/>
  <rupture id="4" nom="GPLc" debut="2017-09-16T09:50:23" fin="" type="definitive"/>
</pdv>
```

| Élément | Description |
|---|---|
| `pdv@id` | **Clé unique de la station** |
| `latitude`, `longitude` | Coordonnées × 100 000 (`4620100` = 46,201°) |
| `cp` | Code postal |
| `pop` | Type d'implantation : `R` = route, `A` = autoroute |
| `adresse`, `ville` | Adresse postale |
| `horaires` | Horaires par jour, indicateur automate 24h/24 |
| `services` | Liste des services proposés |
| `prix` | Un prix par carburant : `nom`, `id`, `maj` (date de mise à jour du prix), `valeur` (€/L) |
| `rupture` | Carburant indisponible : `debut`, `fin`, `type` (`temporaire` / `definitive`) |

Carburants : Gazole (1), SP95 (2), E85 (3), GPLc (4), E10 (5), SP98 (6).

### Ce qui change dans le temps

| Donnée | Fréquence de changement | Traitement prévu |
|---|---|---|
| Prix | Plusieurs fois par semaine | Table de faits (une ligne par changement de prix) |
| Ruptures | Ponctuel | Table de faits |
| Adresse, horaires, services | Rare | Dimension station historisée en **SCD type 2** |

## Pièges identifiés

1. **Encodage ISO-8859-1** : lu en UTF-8, les accents sont cassés.
2. **Coordonnées entières** : à diviser par 100 000.
3. **Réponse 200 OK sans fichier** : une date quotidienne trop ancienne renvoie une page HTML avec le code 200.
   Il faut vérifier que la réponse est bien un zip, pas seulement le code HTTP.
4. **Rétention d'environ 1 mois** des fichiers quotidiens : au-delà, seule l'archive annuelle permet de récupérer les données.
   Le pipeline doit donc **conserver une copie brute** de chaque fichier téléchargé.
5. **« Quotidien » ≠ « prix du jour »** : le fichier du 14/10 contient le dernier prix connu de chaque station,
   dont seulement 12 445 sur 31 476 ont été mis à jour ce jour-là. La date de référence d'un prix est `maj`,
   pas la date du fichier.
6. **Pas d'enseigne** (Total, Leclerc…) dans le XML : à chercher dans une source complémentaire si nécessaire.
7. **Fichiers annuels volumineux** (~350 Mo de XML) : parsing en flux obligatoire, sans tout charger en mémoire.
8. **Doublons possibles dans l'annuel** : un même prix peut apparaître plusieurs fois avec des `maj` différents
   mais la même `valeur`. Il faut dédupliquer sur (station, carburant, `maj`).

## Choix pour le projet

| Besoin | Source retenue | Raison |
|---|---|---|
| Ingestion quotidienne | `/opendata/jour/AAAAMMJJ` | Fichier daté → téléchargement rejouable, donc idempotent |
| Rattrapage < 1 mois | `/opendata/jour/AAAAMMJJ` | Même mécanisme, en boucle sur les jours manquants |
| Backfill historique | `/opendata/annee/AAAA` | Seule source contenant l'historique complet des prix |
| Contrôle de fraîcheur | `/opendata/instantane` (optionnel) | Vérifier que la source répond et que les `maj` sont récentes |

Périmètre initial du backfill : **2022 à aujourd'hui** (extensible jusqu'à 2007).
