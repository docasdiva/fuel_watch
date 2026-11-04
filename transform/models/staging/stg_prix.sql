with source as (

    select * from {{ source('raw', 'raw_prix') }}

),

renamed as (

    select
        station_id,
        carburant,
        to_utc_timestamp(maj, 'Europe/Paris') as maj_utc,
        prix,
        prix not between 0.2 and 5 as est_aberrant,
        date_fichier
    from source

)

select *
from renamed
qualify row_number() over (
    partition by date_fichier, station_id, carburant
    order by maj_utc desc
) = 1