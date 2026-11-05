with source as (

    select * from {{ source('raw', 'raw_stations_annuel') }}

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
        annee
    from source

)

select *
from renamed
qualify row_number() over (
    partition by annee, station_id
    order by station_id
) = 1       