with source as (

    select * from {{ source('raw', 'raw_stations') }}

),

renamed as (

    select
        station_id,
        latitude,
        longitude,
        code_postal,
        left(code_postal, 2) as departement,
        case type_route
            when 'R' then 'route'
            when 'A' then 'autoroute'
        end as type_route,
        trim(adresse) as adresse,
        trim(ville) as ville,
        services,
        automate_24_24,
        date_fichier
    from source

)

select *
from renamed
qualify row_number() over (
    partition by date_fichier, station_id
    order by station_id
) = 1       