{% macro normalize_email(column_name) %}

    lower(trim({{ column_name }}))

{% endmacro %}
