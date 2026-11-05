with stations as (

    select * from {{ ref('stg_stations') }}

)

select
    *,
    cast(date_fichier as timestamp) as photo_le
from stations
{% if var('date_photo', none) %}
where date_fichier = '{{ var("date_photo") }}'
{% else %}
where date_fichier = (select max(date_fichier) from stations)
{% endif %}