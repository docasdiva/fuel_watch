with prix as (

    select * from {{ ref('int_prix_historique') }}
    where not est_aberrant

),

dernier_prix as (

    select station_id, carburant, prix, maj_utc
    from prix
    qualify row_number() over (
        partition by station_id, carburant
        order by maj_utc desc
    ) = 1

),

stations_actives as (

    select * from {{ ref('dim_stations') }}
    where est_active

)

select
    s.station_id,
    s.adresse,
    s.ville,
    s.departement,
    s.latitude,
    s.longitude,
    p.carburant,
    p.prix,
    from_utc_timestamp(p.maj_utc, 'Europe/Paris') as maj_paris
from dernier_prix p
join stations_actives s on p.station_id = s.station_id
-- On écarte les prix figés depuis plus de 30 jours (carburant plus vendu dans la station).
where p.maj_utc >= (select max(maj_utc) from prix) - interval 30 days