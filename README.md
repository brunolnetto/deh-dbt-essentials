# dbt Fundamentos — Pipeline Analítico com PostgreSQL

Este projeto foi criado como material prático para um curso introdutório de **dbt (Data Build Tool)**.

A proposta é simular um pipeline analítico pequeno, mas realista, partindo de um banco transacional PostgreSQL, aplicando transformações com dbt e chegando a modelos analíticos organizados em camadas de staging, intermediate e marts.

O ambiente também permite alterar os dados transacionais durante a execução do curso, incluindo a injeção intencional de problemas de qualidade para demonstrar testes do dbt em funcionamento.

---

## Objetivos

Ao longo do projeto são demonstrados os principais fundamentos do dbt:

* criação e configuração de um projeto dbt;
* definição de `sources`;
* uso de `ref()` e `source()`;
* organização de modelos em camadas;
* criação de modelos SQL;
* uso de seeds;
* materializações;
* testes genéricos;
* testes SQL customizados;
* macros com Jinja;
* documentação;
* lineage;
* execução com `dbt run`, `dbt test` e `dbt build`;
* comportamento do pipeline após alterações no banco transacional.

---

# Arquitetura

O projeto utiliza um pequeno banco PostgreSQL para representar o sistema OLTP.

```text
PostgreSQL OLTP
│
├── customers
└── orders
        │
        ▼
      dbt
        │
        ├── staging
        │
        ├── intermediate
        │
        └── marts
                │
                ▼
        modelos analíticos
```

Também utilizamos um seed com dados de referência:

```text
country_codes.csv
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
dim_customers


orders source
      │
      ▼
stg_orders
      │
      ▼
fct_orders
      │
      ▼
int_orders_by_customer
      │
      ▼
mart_customer_sales
      ▲
      │
dim_customers
```

---

# Estrutura do projeto

```text
.
├── docker-compose.yml
│
├── oltp/
│   └── init.sql
│
├── scripts/
│   └── mutate.py
│
├── seeds/
│   └── country_codes.csv
│
├── macros/
│   ├── normalize_email.sql
│   └── amount_for_status.sql
│
├── tests/
│   ├── assert_positive_order_amount.sql
│   ├── assert_no_future_orders.sql
│   ├── assert_known_country_codes.sql
│   └── assert_order_timestamps_consistent.sql
│
└── models/
    ├── staging/
    │   ├── sources.yml
    │   ├── schema.yml
    │   ├── stg_customers.sql
    │   └── stg_orders.sql
    │
    ├── intermediate/
    │   ├── schema.yml
    │   ├── int_customers_enriched.sql
    │   └── int_orders_by_customer.sql
    │
    └── marts/
        ├── schema.yml
        ├── dim_customers.sql
        ├── fct_orders.sql
        └── mart_customer_sales.sql
```

---

# Banco transacional

O PostgreSQL representa uma aplicação operacional simples.

As principais tabelas são:

## `customers`

```text
customer_id
name
email
country_code
created_at
updated_at
```

## `orders`

```text
order_id
customer_id
order_date
amount
status
created_at
updated_at
```

O banco mantém restrições transacionais como:

* chave primária;
* chave estrangeira;
* campos obrigatórios;
* unicidade de email;
* valores válidos para status.

Essas restrições protegem o sistema operacional.

Elas não substituem, porém, testes analíticos e regras de qualidade de dados.

---

# Camadas do dbt

## Staging

Os modelos de staging representam os dados de origem de forma limpa e consistente.

Responsabilidades típicas:

* renomear colunas;
* aplicar casts;
* normalizar strings;
* padronizar valores;
* manter granularidade próxima da origem.

Modelos:

```text
stg_customers
stg_orders
```

Exemplo:

```sql
select
    customer_id,
    trim(name) as customer_name,
    {{ normalize_email('email') }} as email,
    upper(trim(country_code)) as country_code,
    created_at,
    updated_at

from {{ source('shop', 'customers') }}
```

A ideia é manter a camada de staging simples.

Regras de negócio complexas não devem ser escondidas aqui.

---

## Intermediate

A camada intermediate contém transformações auxiliares utilizadas por modelos posteriores.

Modelos:

```text
int_customers_enriched
int_orders_by_customer
```

### `int_customers_enriched`

Combina clientes com o seed `country_codes`.

```text
customer
+
country_code
+
country_name
+
region
+
currency
```

### `int_orders_by_customer`

Agrega informações de pedidos por cliente.

Grão:

```text
1 linha = 1 cliente
```

Exemplos de atributos:

```text
total_orders
paid_orders
cancelled_orders
refunded_orders
revenue
refunded_amount
average_paid_order_value
first_order_date
last_order_date
```

---

# Marts

Os marts representam contratos analíticos destinados ao consumo.

## `dim_customers`

Dimensão de clientes.

Grão:

```text
1 linha = 1 cliente
```

Inclui informações como:

```text
customer_id
customer_name
email
country
region
currency
```

---

## `fct_orders`

Tabela fato de pedidos.

Grão:

```text
1 linha = 1 pedido
```

Além dos atributos do pedido, o modelo cria medidas auxiliares como:

```text
is_paid
is_cancelled
is_refunded
recognized_revenue
refunded_amount
```

Essas colunas permitem que agregações posteriores sejam construídas sem repetir regras de negócio.

---

## `mart_customer_sales`

Modelo analítico final com visão de vendas por cliente.

Exemplo:

```text
customer_id
customer_name
country_name
region
currency
total_orders
paid_orders
cancelled_orders
refunded_orders
revenue
refunded_amount
average_paid_order_value
first_order_date
last_order_date
```

Grão:

```text
1 linha = 1 cliente
```

---

# Seed

O projeto utiliza:

```text
seeds/country_codes.csv
```

Exemplo:

```csv
country_code,country_name,region,currency
BR,Brazil,South America,BRL
DE,Germany,Europe,EUR
US,United States,North America,USD
```

O seed representa dados pequenos, controlados e versionados junto com o projeto.

Isso permite diferenciar claramente:

```text
customers / orders
→ dados operacionais mutáveis
→ source()

country_codes
→ dado de referência controlado
→ ref()
```

Para carregar o seed:

```bash
dbt seed
```

---

# Macros

Macros permitem reutilizar lógica SQL usando Jinja.

## Normalização de email

```sql
{% macro normalize_email(column_name) %}

    lower(trim({{ column_name }}))

{% endmacro %}
```

Uso:

```sql
{{ normalize_email('email') }}
```

---

## Valores condicionais por status

```sql
{% macro amount_for_status(amount_column, status_column, expected_status) %}

    case
        when {{ status_column }} = '{{ expected_status }}'
        then {{ amount_column }}
        else 0
    end

{% endmacro %}
```

Exemplo:

```sql
{{ amount_for_status('amount', 'status', 'paid') }}
    as recognized_revenue
```

---

# Testes

O projeto utiliza diferentes níveis de validação.

## Restrições do PostgreSQL

Protegem a integridade transacional.

Exemplos:

```text
PRIMARY KEY
FOREIGN KEY
NOT NULL
UNIQUE
CHECK
```

---

## Testes genéricos do dbt

Exemplos:

```yaml
data_tests:
  - not_null
  - unique
```

Também são utilizados:

```text
accepted_values
relationships
```

Por exemplo:

```yaml
- name: status
  data_tests:
    - accepted_values:
        arguments:
          values:
            - pending
            - paid
            - cancelled
            - refunded
```

---

# Testes SQL customizados

Além dos testes genéricos, o projeto possui testes SQL para regras de negócio.

Um teste singular deve retornar:

```text
0 linhas → PASS
1 ou mais linhas → FAIL
```

## Valores negativos

```sql
select *
from {{ ref('stg_orders') }}
where amount <= 0
```

---

## Pedidos no futuro

```sql
select *
from {{ ref('stg_orders') }}
where order_date > current_date
```

---

## País inexistente

```sql
select
    c.customer_id,
    c.customer_name,
    c.country_code

from {{ ref('stg_customers') }} as c

left join {{ ref('country_codes') }} as cc
    on c.country_code = cc.country_code

where cc.country_code is null
```

---

## Inconsistência temporal

```sql
select
    order_id,
    created_at,
    updated_at

from {{ ref('stg_orders') }}

where updated_at < created_at
```

---

# Simulação de alterações

O script:

```text
scripts/mutate.py
```

permite modificar o banco OLTP durante a execução do projeto.

Por exemplo:

```bash
python scripts/mutate.py insert-customer
```

```bash
python scripts/mutate.py insert-order
```

```bash
python scripts/mutate.py update-customer
```

```bash
python scripts/mutate.py update-order
```

```bash
python scripts/mutate.py delete-order
```

Também é possível executar uma alteração aleatória:

```bash
python scripts/mutate.py simulate
```

Depois da alteração:

```bash
dbt build
```

Isso permite observar o dado percorrendo o pipeline:

```text
OLTP
 ↓
source
 ↓
staging
 ↓
intermediate
 ↓
fact / dimension
 ↓
mart
```

---

# Injeção de problemas de qualidade

O script também permite criar dados propositalmente problemáticos.

## Country code inválido

```bash
python scripts/mutate.py bug-invalid-country
```

Cria, por exemplo:

```text
country_code = XX
```

O código é válido para o PostgreSQL, mas não existe no seed de países.

O teste de relacionamento deve falhar.

---

## Valor negativo

```bash
python scripts/mutate.py bug-negative-amount
```

Exemplo:

```text
amount = -150.00
```

O PostgreSQL aceita o valor porque essa regra não faz parte do contrato transacional.

O teste analítico deve detectar o problema.

---

## Pedido no futuro

```bash
python scripts/mutate.py bug-future-order
```

Cria um pedido com data futura.

O teste:

```text
assert_no_future_orders
```

deve falhar.

---

## Email logicamente duplicado

```bash
python scripts/mutate.py bug-duplicate-email
```

O banco pode conter:

```text
ana@example.com
ANA@EXAMPLE.COM
```

Depois da normalização no staging:

```text
ana@example.com
ana@example.com
```

O teste `unique` passa então a detectar a duplicidade lógica.

Esse exemplo demonstra que:

```text
integridade transacional
!=
qualidade analítica
```

---

# Executando o projeto

## Subir PostgreSQL

```bash
docker compose up -d
```

Verifique os containers:

```bash
docker compose ps
```

---

## Validar configuração do dbt

```bash
dbt debug
```

---

## Carregar seeds

```bash
dbt seed
```

---

## Executar modelos

```bash
dbt run
```

---

## Executar testes

```bash
dbt test
```

---

## Construir todo o projeto

```bash
dbt build
```

O `dbt build` executa os recursos respeitando o DAG de dependências e inclui modelos, seeds e testes.

---

# Compilação

Para observar como o dbt transforma Jinja em SQL executável:

```bash
dbt compile
```

Os arquivos compilados podem ser encontrados dentro de:

```text
target/
```

Essa é uma forma útil de entender que dbt não executa uma linguagem SQL própria.

Ele gera SQL para o banco de dados de destino.

---

# Documentação

Gerar documentação:

```bash
dbt docs generate
```

Abrir interface local:

```bash
dbt docs serve
```

A documentação permite explorar:

* modelos;
* colunas;
* descrições;
* dependências;
* sources;
* testes;
* lineage.

---

# Lineage

Uma das principais vantagens do uso de `ref()` e `source()` é a construção automática do DAG.

Exemplo:

```text
source(customers)
       │
       ▼
stg_customers
       │
       ▼
int_customers_enriched
       │
       ▼
dim_customers
       │
       ▼
mart_customer_sales
```

Se um modelo depende de outro:

```sql
from {{ ref('dim_customers') }}
```

o dbt passa a conhecer essa dependência.

Isso permite:

* ordenar execuções;
* construir lineage;
* selecionar modelos relacionados;
* executar apenas partes específicas do DAG.

---

# Conceitos principais

O projeto busca reforçar algumas distinções importantes.

## `source()` vs `ref()`

Use:

```text
source()
```

para tabelas externas ao dbt.

Use:

```text
ref()
```

para recursos gerenciados pelo projeto dbt.

---

## OLTP vs OLAP

O banco operacional é orientado a transações:

```text
OLTP
normalized
mutable
application-oriented
```

Os modelos finais são orientados a análise:

```text
OLAP
analytical
business-oriented
optimized for consumption
```

O dbt atua entre esses dois mundos.

---

## Banco válido não significa dado correto

Um registro pode satisfazer todas as constraints do PostgreSQL e ainda ser incorreto para análise.

Por exemplo:

```text
amount = -150
```

pode ser tecnicamente armazenável.

Mas pode violar uma regra de negócio.

Por isso:

```text
database constraints
+
dbt tests
+
business tests
```

resolvem problemas diferentes.

---

# Comandos utilizados

```bash
dbt debug
dbt seed
dbt run
dbt test
dbt build
dbt compile
dbt docs generate
dbt docs serve
```

Para simular alterações:

```bash
python scripts/mutate.py simulate
```

Para injetar um problema:

```bash
python scripts/mutate.py simulate-bug
```

---

# Resultado esperado

Ao final do projeto, deve ser possível compreender o fluxo:

```text
Dados transacionais
        ↓
      source
        ↓
     staging
        ↓
   intermediate
        ↓
facts / dimensions
        ↓
       marts
        ↓
consumo analítico
```

Mais importante que conhecer comandos específicos, o objetivo é entender dbt como uma forma de transformar SQL em um projeto de engenharia com:

* dependências explícitas;
* contratos;
* testes;
* documentação;
* reutilização;
* versionamento;
* lineage;
* modelos analíticos organizados.
