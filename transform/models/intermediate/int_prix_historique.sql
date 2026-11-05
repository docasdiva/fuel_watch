{{ config(materialized='table') }}

with annuel as (

    select
        station_id,
        carburant,
        maj_utc,
        prix,
        est_aberrant,
        'annuel' as source
    from {{ ref('stg_prix_annuel') }}

),

quotidien as (

    select
        station_id,
        carburant,
        maj_utc,
        prix,
        est_aberrant,
        'quotidien' as source
    from {{ ref('stg_prix') }}

),

empile as (

    select * from annuel
    union all
    select * from quotidien

)

select *
from empile
qualify row_number() over (
    partition by station_id, carburant, maj_utc
    order by case source when 'annuel' then 1 else 2 end
) = 1