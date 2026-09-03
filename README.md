# dbt Essentials — Pipeline Analítico com PostgreSQL

Este projeto foi criado como material prático para um curso de **dbt (Data Build Tool)** focado em padrões de produção.

A proposta é simular um pipeline analítico realista, partindo de um banco transacional PostgreSQL com suporte a soft deletes, aplicando transformações avançadas com dbt (incremental models, snapshots, contracts, semantic models) e chegando a modelos analíticos organizados em camadas de staging, intermediate e marts.

O ambiente permite alterar os dados transacionais durante a execução do curso, incluindo a injeção intencional de problemas de qualidade para demonstrar testes do dbt em funcionamento.

---

## Objetivos

Ao longo do projeto são demonstrados os fundamentos e padrões avançados de dbt:

### Conceitos Fundamentais
* criação e configuração de um projeto dbt;
* definição de `sources` e `seeds`;
* uso de `ref()` e `source()`;
* organização de modelos em camadas;
* criação de modelos SQL;
* materializações (view, table, ephemeral);
* testes genéricos e SQL customizados;
* macros com Jinja;
* documentação e lineage;
* execução com `dbt run`, `dbt test`, `dbt build`.

### Padrões de Produção
* **soft deletes**: manutenção de histórico com coluna `deleted_at`;
* **incremental models**: atualização eficiente com merge strategy;
* **snapshots**: histórico dimensional (SCD Type 2);
* **model contracts**: garantia de contrato com tipos PostgreSQL enforçados;
* **generic tests com severity**: testes que avisamem vez de falhar a build;
* **tags e selectors**: seleção granular de modelos por atributos;
* **macros avançadas**: reutilização com Jinja loops;
* **semantic models**: definição de métrica com MetricFlow;
* **CI/CD**: validação automática via GitHub Actions.

---

## Arquitetura

O projeto utiliza um pequeno banco PostgreSQL para representar o sistema OLTP com suporte a histórico via soft deletes.

```text
PostgreSQL OLTP (com histórico de soft-deletes)
│
├── customers
└── orders (com deleted_at)
        │
        ▼
      dbt
        │
        ├── staging (propagação de deleted_at)
        │
        ├── intermediate (filtro de histórico)
        │
        ├── snapshots (SCD Type 2)
        │
        └── marts (contratos, métricas)
                │
                ▼
        modelos analíticos
```

Também utilizamos:

```text
country_codes.csv (seed de referência)
```

O fluxo completo é aproximadamente:

```text
customers source
      │
      ▼
stg_customers
      │
      ▼
int_customers_enriched ◄──── country_codes seed
      │
      ▼
dim_customers ◄── customers_snapshot (SCD Type 2)


orders source (deleted_at)
      │
      ▼
stg_orders (expõe deleted_at)
      │
      ▼
fct_orders (incremental, merge, retém deleted_at)
      │
      ▼
int_orders_by_customer (filtra deleted_at)
      │
      ▼
mart_customer_sales
      ▲
      │
dim_customers
```

---

## Estrutura do projeto

```text
.
├── .gitattributes                    # Normalização LF
├── docker-compose.yml
│
├── oltp/
│   └── init.sql                      # Schema com soft-delete support
│
├── scripts/
│   └── mutate.py                     # Simulação de alterações OLTP
│
├── .github/workflows/
│   └── dbt-ci.yml                    # CI com PostgreSQL service
│
├── ecommerce/
│   ├── dbt_project.yml               # Config com tags por folder
│   ├── selectors.yml                 # Seletores nomeados (finance, orders_pipeline)
│   ├── .gitignore
│   │
│   ├── seeds/
│   │   └── country_codes.csv
│   │
│   ├── macros/
│   │   ├── normalize_email.sql
│   │   ├── amount_for_status.sql
│   │   ├── status_count.sql          # Macro avançada com Jinja
│   │   └── tests/
│   │       └── positive_values.sql   # Generic test reusável
│   │
│   ├── tests/
│   │   ├── assert_positive_order_amount.sql
│   │   ├── assert_no_future_orders.sql
│   │   ├── assert_known_country_codes.sql
│   │   └── assert_order_timestamps_consistent.sql
│   │
│   ├── snapshots/
│   │   └── customers_snapshot.yml    # SCD Type 2 snapshot
│   │
│   ├── models/
│   │   ├── staging/
│   │   │   ├── sources.yml
│   │   │   ├── schema.yml
│   │   │   ├── stg_customers.sql
│   │   │   └── stg_orders.sql        # Propaga deleted_at
│   │   │
│   │   ├── intermediate/
│   │   │   ├── schema.yml
│   │   │   ├── int_customers_enriched.sql
│   │   │   └── int_orders_by_customer.sql  # Filtra deleted_at
│   │   │
│   │   ├── mart/
│   │   │   ├── schema.yml            # Contrato enforçado (fct_orders)
│   │   │   ├── dim_customers.sql
│   │   │   ├── fct_orders.sql        # Incremental com merge strategy
│   │   │   └── mart_customer_sales.sql
│   │   │
│   │   └── semantic/
│   │       └── semantic_orders.yml   # MetricFlow metrics
│   │
│   ├── analyses/
│   └── README.md
│
└── logs/
    └── query_log.sql
```

---

## Banco transacional

O PostgreSQL representa uma aplicação operacional simples com suporte a soft deletes.

### `customers`

```sql
customer_id BIGINT PRIMARY KEY
name TEXT
email TEXT UNIQUE
country_code TEXT
created_at TIMESTAMP WITH TIME ZONE
updated_at TIMESTAMP WITH TIME ZONE
```

### `orders`

```sql
order_id BIGINT PRIMARY KEY
customer_id BIGINT REFERENCES customers
order_date DATE
amount NUMERIC
status TEXT
created_at TIMESTAMP WITH TIME ZONE
updated_at TIMESTAMP WITH TIME ZONE
deleted_at TIMESTAMP WITH TIME ZONE  -- Soft delete indicator
```

A coluna `deleted_at`:
* `NULL` = registro ativo
* `NOT NULL` = registro logicamente deletado

Isso permite recuperar histórico sem perder referências transacionais.

---

## Camadas do dbt

### Staging

Os modelos de staging representam os dados de origem de forma limpa e consistente.

Responsabilidades:

* renomear colunas;
* aplicar casts;
* normalizar strings;
* padronizar valores;
* **propagar `deleted_at` sem filtro** (decisão fica com camadas posteriores);
* manter granularidade próxima da origem.

Modelos: `stg_customers`, `stg_orders`

**Importante:** `stg_orders` expõe a coluna `deleted_at`. Nenhum filtro é aplicado aqui.

```sql
select
    order_id,
    customer_id,
    order_date,
    amount,
    status,
    created_at,
    updated_at,
    deleted_at  -- Propagado, não filtrado
from {{ source('shop', 'orders') }}
```

---

### Intermediate

A camada intermediate contém transformações auxiliares com lógica de negócio.

#### `int_customers_enriched`

Combina clientes com o seed `country_codes`.

Atributos: customer_id, customer_name, email, country_code, country_name, region, currency, created_at, updated_at

#### `int_orders_by_customer`

Agrega informações de pedidos **ativos** por cliente.

Grão: 1 linha = 1 cliente

**Filtra:** `where deleted_at is null` (exclui pedidos soft-deletados)

Usa macro avançada `status_count()` em loop Jinja:

```sql
{% set order_statuses = ['paid', 'cancelled', 'refunded'] %}
select customer_id, count(*) as total_orders,
  {% for s in order_statuses -%}
  {{ status_count('status', s) }} as {{ s }}_orders,
  {% endfor -%}
  ...
from {{ ref('fct_orders') }}
where deleted_at is null
group by customer_id
```

Atributos: customer_id, total_orders, paid_orders, cancelled_orders, refunded_orders, revenue, refunded_amount, average_paid_order_value, first_order_date, last_order_date

---

### Marts

Os marts representam contratos analíticos destinados ao consumo.

#### `dim_customers`

Dimensão de clientes com histórico (via snapshot).

Grão: 1 linha = 1 cliente

Atributos: customer_id, customer_name, email, country_code, country_name, region, currency, created_at, updated_at

#### `fct_orders` ⭐ Incremental com Merge

Tabela fato de pedidos **incremental** com contrato enforçado.

Grão: 1 linha = 1 pedido (inclui soft-deletados)

**Configuração:**
```yaml
config:
  materialized: 'incremental'
  unique_key: 'order_id'
  incremental_strategy: 'merge'
```

**Predicado Incremental:**
```sql
{% if is_incremental() %}
where updated_at > (select coalesce(max(updated_at), '1900-01-01'::timestamptz) from {{ this }})
{% endif %}
```

**Contrato (enforçado):** Todos os 13 atributos com tipos PostgreSQL validados:
- order_id: bigint (not_null, unique)
- customer_id: bigint (not_null, relationships)
- order_date: date (not_null)
- amount: numeric (not_null, positive_values com severity: warn)
- status: text (not_null)
- is_paid, is_cancelled, is_refunded: integer
- recognized_revenue, refunded_amount: numeric (not_null)
- created_at, updated_at: timestamp with time zone (not_null)
- **deleted_at: timestamp with time zone (nullable)** ← Retém histórico

Atributos: order_id, customer_id, order_date, amount, status, is_paid, is_cancelled, is_refunded, recognized_revenue, refunded_amount, created_at, updated_at, deleted_at

#### `mart_customer_sales`

Modelo analítico final com visão de vendas por cliente.

Grão: 1 linha = 1 cliente

Atributos: customer_id, customer_name, email, country_name, region, currency, total_orders, paid_orders, cancelled_orders, refunded_orders, revenue, refunded_amount, average_paid_order_value, first_order_date, last_order_date

---

## Snapshots (SCD Type 2)

O projeto inclui um snapshot YAML para rastrear mudanças em clientes:

```yaml
snapshots:
  - name: customers_snapshot
    relation: source('shop', 'customers')
    config:
      unique_key: customer_id
      strategy: timestamp
      updated_at: updated_at
```

Cria histórico com:
- `dbt_scd_id`: ID único do registro histórico
- `dbt_valid_from`: Quando o registro começou a valer
- `dbt_valid_to`: Quando o registro expirou (NULL = atual)
- `dbt_updated_at`: Timestamp da mudança

Execute:
```bash
dbt snapshot
```

---

## Macros

### Normalização de email

```sql
{% macro normalize_email(column_name) %}
    lower(trim({{ column_name }}))
{% endmacro %}
```

### Valor para status

```sql
{% macro amount_for_status(amount_column, status_column, expected_status) %}
    case
        when {{ status_column }} = '{{ expected_status }}'
        then {{ amount_column }}
        else 0
    end
{% endmacro %}
```

### Status count ⭐ (Avançada)

```sql
{% macro status_count(status_column, expected_status) %}
    sum(case when {{ status_column }} = '{{ expected_status }}' then 1 else 0 end)
{% endmacro %}
```

Usada com Jinja loops em `int_orders_by_customer`.

---

## Testes

### Restrições do PostgreSQL

Protegem integridade transacional: PRIMARY KEY, FOREIGN KEY, NOT NULL, UNIQUE, CHECK.

### Generic tests do dbt

Reutilizáveis com YAML:
- `not_null`
- `unique`
- `accepted_values`
- `relationships`
- **`positive_values`** ⭐ (custom, definido em `macros/tests/positive_values.sql`)

Exemplo com severity:
```yaml
- name: amount
  data_tests:
    - positive_values:
        severity: warn  # Aviso em vez de falha
```

### Testes SQL customizados (singular)

Retornam 0 linhas = PASS, 1+ linhas = FAIL:
- `assert_positive_order_amount`
- `assert_no_future_orders`
- `assert_known_country_codes`
- `assert_order_timestamps_consistent`

---

## Tags e Seletores

### Tags por folder (dbt_project.yml)

```yaml
models:
  ecommerce:
    staging: +tags: [staging]
    intermediate: +tags: [intermediate]
    mart: +tags: [marts]
```

Além disso:
- `fct_orders`: tags [marts, finance, incremental]
- `mart_customer_sales`: tags [marts, finance]

### Seletores nomeados (selectors.yml)

```yaml
selectors:
  - name: finance
    definition:
      method: tag
      value: finance
```

Uso:
```bash
dbt build --selector finance      # Apenas fct_orders + mart_customer_sales
dbt ls --selector orders_pipeline  # DAG completo de fct_orders
```

---

## Semantic Models e Métricas

O projeto inclui definição de métricas via MetricFlow (v0.212.0):

```yaml
semantic_models:
  - name: orders
    model: ref('fct_orders')
    entities:
      - name: order
        type: primary
        expr: order_id
      - name: customer
        type: foreign
        expr: customer_id
    dimensions:
      - name: order_date
        type: time
        time_granularity: day
      - name: status
        type: categorical
    measures:
      - name: order_count
        agg: count_distinct
        expr: order_id
      - name: paid_order_count
        agg: sum
        expr: is_paid
      - name: recognized_revenue
        agg: sum
        expr: recognized_revenue

metrics:
  - name: revenue
    type: simple
    expr: {{ Measure('recognized_revenue') }}
  
  - name: paid_orders
    type: simple
    expr: {{ Measure('paid_order_count') }}
  
  - name: average_order_value
    type: ratio
    numerator:
      name: total_revenue
      expr: {{ Measure('recognized_revenue') }}
    denominator:
      name: order_count
      expr: {{ Measure('order_count') }}
```

---

## CI/CD com GitHub Actions

O projeto inclui workflow `.github/workflows/dbt-ci.yml`:

1. **PostgreSQL Service:** Container 17 com schema OLTP pré-carregado
2. **dbt parse:** Validação de sintaxe
3. **dbt build:** Execução completa (models, seeds, tests)

Executa automaticamente em PRs para validação antes do merge.

---

## Simulação de alterações

O script `scripts/mutate.py` permite modificar o banco OLTP:

### Operações normais

```bash
python scripts/mutate.py insert-customer
python scripts/mutate.py insert-order
python scripts/mutate.py update-customer
python scripts/mutate.py update-order
python scripts/mutate.py delete-order          # Delete permanente
python scripts/mutate.py soft-delete-order     # Soft delete (deleted_at)
python scripts/mutate.py restore-order         # Limpa deleted_at
python scripts/mutate.py late-arriving-order   # Insere com order_date antiga
python scripts/mutate.py backdate-update       # Atualiza updated_at para past
```

### Injeção de problemas

```bash
python scripts/mutate.py bug-negative-amount
python scripts/mutate.py bug-future-order
python scripts/mutate.py bug-invalid-country
python scripts/mutate.py bug-duplicate-email
```

Após alteração, execute:
```bash
dbt build
```

---

## Executando o projeto

### Subir PostgreSQL

```bash
docker compose up -d
```

### Validar configuração

```bash
dbt debug
```

### Carregar seeds

```bash
dbt seed
```

### Executar modelos

```bash
dbt run
```

### Executar testes

```bash
dbt test
```

### Snapshot (SCD Type 2)

```bash
dbt snapshot
```

### Construir tudo (models + seeds + tests)

```bash
dbt build
```

### Compilação

Para ver SQL gerado:

```bash
dbt compile
```

Arquivos em `target/compiled/`.

### Documentação

Gerar:
```bash
dbt docs generate
```

Servir:
```bash
dbt docs serve
```

Explore modelos, colunas, descrições, dependências, sources, testes, lineage.

---

## Seleção de modelos

### Por tag

```bash
dbt build --tag finance
dbt build --tag incremental
dbt build --tag marts
```

### Por seletor nomeado

```bash
dbt build --selector finance
dbt ls --selector orders_pipeline
```

### Por DAG

```bash
dbt build --select fct_orders              # Apenas fct_orders
dbt build --select +fct_orders             # fct_orders + ancestors
dbt build --select fct_orders+             # fct_orders + descendants
dbt build --select +fct_orders+            # DAG completo
```

### Estado

```bash
dbt build --select state:modified+         # Modelos modificados + downstream
```

---

## Padrões-chave demonstrados

### Soft Deletes

Coluna `deleted_at` em vez de DELETE:
- Preserva referências transacionais
- Permite recuperação
- Histórico para análise
- Staging propaga, camadas posteriores filtram

### Incremental Models

`fct_orders` com merge strategy:
- Detecta inserções/atualizações via `updated_at`
- Eficiência em grandes volumes
- Mantém histórico com `deleted_at`

### Snapshots (SCD Type 2)

Rastreamento de dimensões mutáveis:
- Histórico completo de mudanças
- Valid from/to timestamps
- Múltiplos registros por entidade

### Contracts

`fct_orders` enforça contrato:
- Tipos PostgreSQL explícitos
- Detecção de breaking changes
- Integração com `dbt parse`

### Generic Tests com Severity

Não bloqueia build:
```yaml
severity: warn  # Aviso em vez de erro
```

### Tags e Selectors

Organização granular:
- Por funcionalidade (finance, incremental)
- Por layer (staging, intermediate, marts)
- Seletores nomeados para workflows comuns

### Semantic Models

Definição métrica única, múltiplas queries:
- MetricFlow resolve a métrica
- Independente de model específico
- Suporte a dimensões, filtros

---

## Comandos principais

```bash
dbt debug
dbt seed
dbt snapshot
dbt run
dbt test
dbt build
dbt compile
dbt docs generate
dbt docs serve
dbt parse
python scripts/mutate.py simulate
```

---

## Resultado esperado

Ao final, compreender:

```text
Dados transacionais (com soft-delete)
        ↓
      source (deleted_at propagado)
        ↓
     staging (sem filtro, apenas limpeza)
        ↓
   intermediate (lógica de negócio, filtra soft-deletes)
        ↓
facts / dimensions (contratos, incremental, snapshot)
        ↓
       marts (consumo, métricas semânticas)
        ↓
   BI / Analytics
```

Além de compreender:
- Diferença entre integridade transacional e qualidade analítica
- Como manter histórico com soft deletes
- Eficiência com incremental models
- Tradeoffs de merge vs outros strategies
- Validação com contracts
- Seleção de recursos com tags/selectors
# dbt Essentials — Pipeline Analítico com PostgreSQL

Este projeto foi criado como material prático para um curso de **dbt (Data Build Tool)** focado em padrões de produção.

A proposta é simular um pipeline analítico realista, partindo de um banco transacional PostgreSQL com suporte a soft deletes, aplicando transformações avançadas com dbt (incremental models, snapshots, contracts, semantic models) e chegando a modelos analíticos organizados em camadas de staging, intermediate e marts.

O ambiente permite alterar os dados transacionais durante a execução do curso, incluindo a injeção intencional de problemas de qualidade para demonstrar testes do dbt em funcionamento.

---

## Objetivos

Ao longo do projeto são demonstrados os fundamentos e padrões avançados de dbt:

### Conceitos Fundamentais
* criação e configuração de um projeto dbt;
* definição de `sources` e `seeds`;
* uso de `ref()` e `source()`;
* organização de modelos em camadas;
* criação de modelos SQL;
* materializações (view, table, ephemeral);
* testes genéricos e SQL customizados;
* macros com Jinja;
* documentação e lineage;
* execução com `dbt run`, `dbt test`, `dbt build`.

### Padrões de Produção
* **soft deletes**: manutenção de histórico com coluna `deleted_at`;
* **incremental models**: atualização eficiente com merge strategy;
* **snapshots**: histórico dimensional (SCD Type 2);
* **model contracts**: garantia de contrato com tipos PostgreSQL enforçados;
* **generic tests com severity**: testes que avisamem vez de falhar a build;
* **tags e selectors**: seleção granular de modelos por atributos;
* **macros avançadas**: reutilização com Jinja loops;
* **semantic models**: definição de métrica com MetricFlow;
* **CI/CD**: validação automática via GitHub Actions.

---

## Arquitetura

O projeto utiliza um pequeno banco PostgreSQL para representar o sistema OLTP com suporte a histórico via soft deletes.

```text
PostgreSQL OLTP (com histórico de soft-deletes)
│
├── customers
└── orders (com deleted_at)
        │
        ▼
      dbt
        │
        ├── staging (propagação de deleted_at)
        │
        ├── intermediate (filtro de histórico)
        │
        ├── snapshots (SCD Type 2)
        │
        └── marts (contratos, métricas)
                │
                ▼
        modelos analíticos
```

Também utilizamos:

```text
country_codes.csv (seed de referência)
```

O fluxo completo é aproximadamente:

```text
customers source
      │
      ▼
stg_customers
      │
      ▼
int_customers_enriched ◄──── country_codes seed
      │
      ▼
dim_customers ◄── customers_snapshot (SCD Type 2)


orders source (deleted_at)
      │
      ▼
stg_orders (expõe deleted_at)
      │
      ▼
fct_orders (incremental, merge, retém deleted_at)
      │
      ▼
int_orders_by_customer (filtra deleted_at)
      │
      ▼
mart_customer_sales
      ▲
      │
dim_customers
```

---

## Estrutura do projeto

```text
.
├── .gitattributes                    # Normalização LF
├── docker-compose.yml
│
├── oltp/
│   └── init.sql                      # Schema com soft-delete support
│
├── scripts/
│   └── mutate.py                     # Simulação de alterações OLTP
│
├── .github/workflows/
│   └── dbt-ci.yml                    # CI com PostgreSQL service
│
├── ecommerce/
│   ├── dbt_project.yml               # Config com tags por folder
│   ├── selectors.yml                 # Seletores nomeados (finance, orders_pipeline)
│   ├── .gitignore
│   │
│   ├── seeds/
│   │   └── country_codes.csv
│   │
│   ├── macros/
│   │   ├── normalize_email.sql
│   │   ├── amount_for_status.sql
│   │   ├── status_count.sql          # Macro avançada com Jinja
│   │   └── tests/
│   │       └── positive_values.sql   # Generic test reusável
│   │
│   ├── tests/
│   │   ├── assert_positive_order_amount.sql
│   │   ├── assert_no_future_orders.sql
│   │   ├── assert_known_country_codes.sql
│   │   └── assert_order_timestamps_consistent.sql
│   │
│   ├── snapshots/
│   │   └── customers_snapshot.yml    # SCD Type 2 snapshot
│   │
│   ├── models/
│   │   ├── staging/
│   │   │   ├── sources.yml
│   │   │   ├── schema.yml
│   │   │   ├── stg_customers.sql
│   │   │   └── stg_orders.sql        # Propaga deleted_at
│   │   │
│   │   ├── intermediate/
│   │   │   ├── schema.yml
│   │   │   ├── int_customers_enriched.sql
│   │   │   └── int_orders_by_customer.sql  # Filtra deleted_at
│   │   │
│   │   ├── mart/
│   │   │   ├── schema.yml            # Contrato enforçado (fct_orders)
│   │   │   ├── dim_customers.sql
│   │   │   ├── fct_orders.sql        # Incremental com merge strategy
│   │   │   └── mart_customer_sales.sql
│   │   │
│   │   └── semantic/
│   │       └── semantic_orders.yml   # MetricFlow metrics
│   │
│   ├── analyses/
│   └── README.md
│
└── logs/
    └── query_log.sql
```

---

## Banco transacional

O PostgreSQL representa uma aplicação operacional simples com suporte a soft deletes.

### `customers`

```sql
customer_id BIGINT PRIMARY KEY
name TEXT
email TEXT UNIQUE
country_code TEXT
created_at TIMESTAMP WITH TIME ZONE
updated_at TIMESTAMP WITH TIME ZONE
```

### `orders`

```sql
order_id BIGINT PRIMARY KEY
customer_id BIGINT REFERENCES customers
order_date DATE
amount NUMERIC
status TEXT
created_at TIMESTAMP WITH TIME ZONE
updated_at TIMESTAMP WITH TIME ZONE
deleted_at TIMESTAMP WITH TIME ZONE  -- Soft delete indicator
```

A coluna `deleted_at`:
* `NULL` = registro ativo
* `NOT NULL` = registro logicamente deletado

Isso permite recuperar histórico sem perder referências transacionais.

---

## Camadas do dbt

### Staging

Os modelos de staging representam os dados de origem de forma limpa e consistente.

Responsabilidades:

* renomear colunas;
* aplicar casts;
* normalizar strings;
* padronizar valores;
* **propagar `deleted_at` sem filtro** (decisão fica com camadas posteriores);
* manter granularidade próxima da origem.

Modelos: `stg_customers`, `stg_orders`

**Importante:** `stg_orders` expõe a coluna `deleted_at`. Nenhum filtro é aplicado aqui.

```sql
select
    order_id,
    customer_id,
    order_date,
    amount,
    status,
    created_at,
    updated_at,
    deleted_at  -- Propagado, não filtrado
from {{ source('shop', 'orders') }}
```

---

### Intermediate

A camada intermediate contém transformações auxiliares com lógica de negócio.

#### `int_customers_enriched`

Combina clientes com o seed `country_codes`.

Atributos: customer_id, customer_name, email, country_code, country_name, region, currency, created_at, updated_at

#### `int_orders_by_customer`

Agrega informações de pedidos **ativos** por cliente.

Grão: 1 linha = 1 cliente

**Filtra:** `where deleted_at is null` (exclui pedidos soft-deletados)

Usa macro avançada `status_count()` em loop Jinja:

```sql
{% set order_statuses = ['paid', 'cancelled', 'refunded'] %}
select customer_id, count(*) as total_orders,
  {% for s in order_statuses -%}
  {{ status_count('status', s) }} as {{ s }}_orders,
  {% endfor -%}
  ...
from {{ ref('fct_orders') }}
where deleted_at is null
group by customer_id
```

Atributos: customer_id, total_orders, paid_orders, cancelled_orders, refunded_orders, revenue, refunded_amount, average_paid_order_value, first_order_date, last_order_date

---

### Marts

Os marts representam contratos analíticos destinados ao consumo.

#### `dim_customers`

Dimensão de clientes com histórico (via snapshot).

Grão: 1 linha = 1 cliente

Atributos: customer_id, customer_name, email, country_code, country_name, region, currency, created_at, updated_at

#### `fct_orders` ⭐ Incremental com Merge

Tabela fato de pedidos **incremental** com contrato enforçado.

Grão: 1 linha = 1 pedido (inclui soft-deletados)

**Configuração:**
```yaml
config:
  materialized: 'incremental'
  unique_key: 'order_id'
  incremental_strategy: 'merge'
```

**Predicado Incremental:**
```sql
{% if is_incremental() %}
where updated_at > (select coalesce(max(updated_at), '1900-01-01'::timestamptz) from {{ this }})
{% endif %}
```

**Contrato (enforçado):** Todos os 13 atributos com tipos PostgreSQL validados:
- order_id: bigint (not_null, unique)
- customer_id: bigint (not_null, relationships)
- order_date: date (not_null)
- amount: numeric (not_null, positive_values com severity: warn)
- status: text (not_null)
- is_paid, is_cancelled, is_refunded: integer
- recognized_revenue, refunded_amount: numeric (not_null)
- created_at, updated_at: timestamp with time zone (not_null)
- **deleted_at: timestamp with time zone (nullable)** ← Retém histórico

Atributos: order_id, customer_id, order_date, amount, status, is_paid, is_cancelled, is_refunded, recognized_revenue, refunded_amount, created_at, updated_at, deleted_at

#### `mart_customer_sales`

Modelo analítico final com visão de vendas por cliente.

Grão: 1 linha = 1 cliente

Atributos: customer_id, customer_name, email, country_name, region, currency, total_orders, paid_orders, cancelled_orders, refunded_orders, revenue, refunded_amount, average_paid_order_value, first_order_date, last_order_date

---

## Snapshots (SCD Type 2)

O projeto inclui um snapshot YAML para rastrear mudanças em clientes:

```yaml
snapshots:
  - name: customers_snapshot
    relation: source('shop', 'customers')
    config:
      unique_key: customer_id
      strategy: timestamp
      updated_at: updated_at
```

Cria histórico com:
- `dbt_scd_id`: ID único do registro histórico
- `dbt_valid_from`: Quando o registro começou a valer
- `dbt_valid_to`: Quando o registro expirou (NULL = atual)
- `dbt_updated_at`: Timestamp da mudança

Execute:
```bash
dbt snapshot
```

---

## Macros

### Normalização de email

```sql
{% macro normalize_email(column_name) %}
    lower(trim({{ column_name }}))
{% endmacro %}
```

### Valor para status

```sql
{% macro amount_for_status(amount_column, status_column, expected_status) %}
    case
        when {{ status_column }} = '{{ expected_status }}'
        then {{ amount_column }}
        else 0
    end
{% endmacro %}
```

### Status count ⭐ (Avançada)

```sql
{% macro status_count(status_column, expected_status) %}
    sum(case when {{ status_column }} = '{{ expected_status }}' then 1 else 0 end)
{% endmacro %}
```

Usada com Jinja loops em `int_orders_by_customer`.

---

## Testes

### Restrições do PostgreSQL

Protegem integridade transacional: PRIMARY KEY, FOREIGN KEY, NOT NULL, UNIQUE, CHECK.

### Generic tests do dbt

Reutilizáveis com YAML:
- `not_null`
- `unique`
- `accepted_values`
- `relationships`
- **`positive_values`** ⭐ (custom, definido em `macros/tests/positive_values.sql`)

Exemplo com severity:
```yaml
- name: amount
  data_tests:
    - positive_values:
        severity: warn  # Aviso em vez de falha
```

### Testes SQL customizados (singular)

Retornam 0 linhas = PASS, 1+ linhas = FAIL:
- `assert_positive_order_amount`
- `assert_no_future_orders`
- `assert_known_country_codes`
- `assert_order_timestamps_consistent`

---

## Tags e Seletores

### Tags por folder (dbt_project.yml)

```yaml
models:
  ecommerce:
    staging: +tags: [staging]
    intermediate: +tags: [intermediate]
    mart: +tags: [marts]
```

Além disso:
- `fct_orders`: tags [marts, finance, incremental]
- `mart_customer_sales`: tags [marts, finance]

### Seletores nomeados (selectors.yml)

```yaml
selectors:
  - name: finance
    definition:
      method: tag
      value: finance
```

Uso:
```bash
dbt build --selector finance      # Apenas fct_orders + mart_customer_sales
dbt ls --selector orders_pipeline  # DAG completo de fct_orders
```

---

## Semantic Models e Métricas

O projeto inclui definição de métricas via MetricFlow (v0.212.0):

```yaml
semantic_models:
  - name: orders
    model: ref('fct_orders')
    entities:
      - name: order
        type: primary
        expr: order_id
      - name: customer
        type: foreign
        expr: customer_id
    dimensions:
      - name: order_date
        type: time
        time_granularity: day
      - name: status
        type: categorical
    measures:
      - name: order_count
        agg: count_distinct
        expr: order_id
      - name: paid_order_count
        agg: sum
        expr: is_paid
      - name: recognized_revenue
        agg: sum
        expr: recognized_revenue

metrics:
  - name: revenue
    type: simple
    expr: {{ Measure('recognized_revenue') }}
  
  - name: paid_orders
    type: simple
    expr: {{ Measure('paid_order_count') }}
  
  - name: average_order_value
    type: ratio
    numerator:
      name: total_revenue
      expr: {{ Measure('recognized_revenue') }}
    denominator:
      name: order_count
      expr: {{ Measure('order_count') }}
```

---

## CI/CD com GitHub Actions

O projeto inclui workflow `.github/workflows/dbt-ci.yml`:

1. **PostgreSQL Service:** Container 17 com schema OLTP pré-carregado
2. **dbt parse:** Validação de sintaxe
3. **dbt build:** Execução completa (models, seeds, tests)

Executa automaticamente em PRs para validação antes do merge.

---

## Simulação de alterações

O script `scripts/mutate.py` permite modificar o banco OLTP:

### Operações normais

```bash
python scripts/mutate.py insert-customer
python scripts/mutate.py insert-order
python scripts/mutate.py update-customer
python scripts/mutate.py update-order
python scripts/mutate.py delete-order          # Delete permanente
python scripts/mutate.py soft-delete-order     # Soft delete (deleted_at)
python scripts/mutate.py restore-order         # Limpa deleted_at
python scripts/mutate.py late-arriving-order   # Insere com order_date antiga
python scripts/mutate.py backdate-update       # Atualiza updated_at para past
```

### Injeção de problemas

```bash
python scripts/mutate.py bug-negative-amount
python scripts/mutate.py bug-future-order
python scripts/mutate.py bug-invalid-country
python scripts/mutate.py bug-duplicate-email
```

Após alteração, execute:
```bash
dbt build
```

---

## Executando o projeto

### Subir PostgreSQL

```bash
docker compose up -d
```

### Validar configuração

```bash
dbt debug
```

### Carregar seeds

```bash
dbt seed
```

### Executar modelos

```bash
dbt run
```

### Executar testes

```bash
dbt test
```

### Snapshot (SCD Type 2)

```bash
dbt snapshot
```

### Construir tudo (models + seeds + tests)

```bash
dbt build
```

### Compilação

Para ver SQL gerado:

```bash
dbt compile
```

Arquivos em `target/compiled/`.

### Documentação

Gerar:
```bash
dbt docs generate
```

Servir:
```bash
dbt docs serve
```

Explore modelos, colunas, descrições, dependências, sources, testes, lineage.

---

## Seleção de modelos

### Por tag

```bash
dbt build --tag finance
dbt build --tag incremental
dbt build --tag marts
```

### Por seletor nomeado

```bash
dbt build --selector finance
dbt ls --selector orders_pipeline
```

### Por DAG

```bash
dbt build --select fct_orders              # Apenas fct_orders
dbt build --select +fct_orders             # fct_orders + ancestors
dbt build --select fct_orders+             # fct_orders + descendants
dbt build --select +fct_orders+            # DAG completo
```

### Estado

```bash
dbt build --select state:modified+         # Modelos modificados + downstream
```

---

## Padrões-chave demonstrados

### Soft Deletes

Coluna `deleted_at` em vez de DELETE:
- Preserva referências transacionais
- Permite recuperação
- Histórico para análise
- Staging propaga, camadas posteriores filtram

### Incremental Models

`fct_orders` com merge strategy:
- Detecta inserções/atualizações via `updated_at`
- Eficiência em grandes volumes
- Mantém histórico com `deleted_at`

### Snapshots (SCD Type 2)

Rastreamento de dimensões mutáveis:
- Histórico completo de mudanças
- Valid from/to timestamps
- Múltiplos registros por entidade

### Contracts

`fct_orders` enforça contrato:
- Tipos PostgreSQL explícitos
- Detecção de breaking changes
- Integração com `dbt parse`

### Generic Tests com Severity

Não bloqueia build:
```yaml
severity: warn  # Aviso em vez de erro
```

### Tags e Selectors

Organização granular:
- Por funcionalidade (finance, incremental)
- Por layer (staging, intermediate, marts)
- Seletores nomeados para workflows comuns

### Semantic Models

Definição métrica única, múltiplas queries:
- MetricFlow resolve a métrica
- Independente de model específico
- Suporte a dimensões, filtros

---

## Comandos principais

```bash
dbt debug
dbt seed
dbt snapshot
dbt run
dbt test
dbt build
dbt compile
dbt docs generate
dbt docs serve
dbt parse
python scripts/mutate.py simulate
```

---

## Resultado esperado

Ao final, compreender:

```text
Dados transacionais (com soft-delete)
        ↓
      source (deleted_at propagado)
        ↓
     staging (sem filtro, apenas limpeza)
        ↓
   intermediate (lógica de negócio, filtra soft-deletes)
        ↓
facts / dimensions (contratos, incremental, snapshot)
        ↓
       marts (consumo, métricas semânticas)
        ↓
   BI / Analytics
```

Além de compreender:
- Diferença entre integridade transacional e qualidade analítica
- Como manter histórico com soft deletes
- Eficiência com incremental models
- Tradeoffs de merge vs outros strategies
- Validação com contracts
- Seleção de recursos com tags/selectors
