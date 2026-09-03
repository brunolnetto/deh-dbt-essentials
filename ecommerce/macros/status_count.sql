{% macro status_count(status_column, expected_status) %}

    sum(
        case
            when {{ status_column }} = '{{ expected_status }}'
            then 1
            else 0
        end
    )

{% endmacro %}
