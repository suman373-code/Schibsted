-- Custom schema macro: use the schema name exactly as defined in dbt_project.yml
-- Without this, dbt would create RAW_STAGING, RAW_BUSINESS (prepending the default schema)

{% macro generate_schema_name(custom_schema_name, node) -%}
    {%- if custom_schema_name is none -%}
        {{ default_schema }}
    {%- else -%}
        {{ custom_schema_name | trim }}
    {%- endif -%}
{%- endmacro %}
