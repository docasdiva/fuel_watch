with quotidien as (

    select
        station_id, latitude, longitude, code_postal, departement,
        type_route, adresse, ville, services, automate_24_24,
        date_fichier as date_reference
    from {{ ref('stg_stations') }}

),

annuel as (

    select
        station_id, latitude, longitude, code_postal, departement,
        type_route, adresse, ville, services, automate_24_24,
        make_date(annee, 1, 1) as date_reference
    from {{ ref('stg_stations_annuel') }}

),

empile as (

    select * from quotidien
    union all
    select * from annuel

),

derniere_version as (

    select *
    from empile
    qualify row_number() over (
        partition by station_id
        order by date_reference desc
    ) = 1

),

actives as (

    select station_id
    from {{ ref('stg_stations') }}
    where date_fichier = (select max(date_fichier) from {{ ref('stg_stations') }})

)

select
    d.station_id,
    d.latitude,
    d.longitude,
    d.code_postal,
    d.departement,
    d.type_route,
    d.adresse,
    d.ville,
    d.services,
    d.automate_24_24,
    d.date_reference as derniere_observation,
    a.station_id is not null as est_active
from derniere_version d
left join actives a on d.station_id = a.station_id