{{
    config(
        materialized='table',
        tags=['intermediate', 'time_spine']
    )
}}

-- Generate a time spine from 2020-01-01 to today + 1 year
with dates as (
    select generate_series(
        '2020-01-01'::date,
        current_date + interval '1 year',
        interval '1 day'
    )::date as date_day
),

spine as (
    select
        date_day,
        date_day::date as date_spine,
        extract(year from date_day)::int as year_number,
        extract(month from date_day)::int as month_number,
        extract(day from date_day)::int as day_number,
        date_trunc('week', date_day)::date as week_start_date,
        date_trunc('month', date_day)::date as month_start_date,
        date_trunc('quarter', date_day)::date as quarter_start_date,
        date_trunc('year', date_day)::date as year_start_date
    from dates
)

select * from spine
