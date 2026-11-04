with source as (

    select * from {{ source('raw', 'raw_prix_annuel') }}

),

renamed as (

    select
        station_id,
        carburant,
        to_utc_timestamp(maj, 'Europe/Paris') as maj_utc,
        prix,
        prix not between 0.2 and 5 as est_aberrant,
        annee
    from source

)

select *
from renamed
qualify row_number() over (
    partition by station_id, carburant, maj_utc
    order by prix
) = 1                