with prix as (

    select * from {{ ref('int_prix_historique') }}
    where not est_aberrant

),

stations as (

    select station_id, departement from {{ ref('dim_stations') }}

)

select
    to_date(from_utc_timestamp(p.maj_utc, 'Europe/Paris')) as jour,
    p.carburant,
    s.departement,
    round(avg(p.prix), 3) as prix_moyen,
    min(p.prix) as prix_min,
    max(p.prix) as prix_max,
    count(*) as nb_releves,
    count(distinct p.station_id) as nb_stations
from prix p
join stations s on p.station_id = s.station_id
group by 1, 2, 3