create table customers (
    customer_id bigint generated always as identity primary key,
    name varchar(200) not null,
    email varchar(200) not null unique,
    country_code char(2) not null,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now()
);

create table orders (
    order_id bigint generated always as identity primary key,
    customer_id bigint not null references customers(customer_id),
    order_date timestamptz not null default now(),
    amount numeric(12, 2) not null,
    status varchar(20) not null
        check (status in ('pending', 'paid', 'cancelled', 'refunded')),
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now(),
    deleted_at timestamptz null
);

insert into customers
    (name, email, country_code)
values
    ('Ana Silva', 'ana@example.com', 'BR'),
    ('Bruno Costa', 'bruno@example.com', 'BR'),
    ('Carla Mendes', 'carla@example.com', 'DE'),
    ('Daniel Souza', 'daniel@example.com', 'US'),
    ('Emma Fischer', 'emma@example.com', 'DE'),
    ('Felipe Rocha', 'felipe@example.com', 'BR'),
    ('Grace Miller', 'grace@example.com', 'US'),
    ('Helena Martins', 'helena@example.com', 'BR');

insert into orders
    (customer_id, order_date, amount, status)
values
    (1, '2026-08-20 10:15:00', 120.50, 'paid'),
    (2, '2026-08-20 11:30:00', 89.90, 'paid'),
    (1, '2026-08-21 09:00:00', 45.00, 'cancelled'),
    (3, '2026-08-21 15:10:00', 230.00, 'paid'),
    (4, '2026-08-22 14:20:00', 59.99, 'refunded'),
    (5, '2026-08-23 17:30:00', 310.40, 'paid'),
    (2, '2026-08-24 08:45:00', 75.50, 'paid'),
    (6, '2026-08-25 13:00:00', 150.00, 'paid'),
    (7, '2026-08-26 16:20:00', 42.75, 'cancelled'),
    (8, '2026-08-27 10:10:00', 199.90, 'paid');

