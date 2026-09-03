# scripts/mutate.py

import argparse
from datetime import datetime, timedelta
import random

import os
import psycopg
from dotenv import load_dotenv

load_dotenv()

POSTGRES_HOST=os.getenv('POSTGRES_HOST')
POSTGRES_PORT=os.getenv('POSTGRES_PORT')
POSTGRES_USER=os.getenv('POSTGRES_USER')
POSTGRES_PASSWORD=os.getenv('POSTGRES_PASSWORD')
POSTGRES_DB=os.getenv('POSTGRES_DB')


DSN = f"postgresql://{POSTGRES_USER}:{POSTGRES_PASSWORD}@{POSTGRES_HOST}:{POSTGRES_PORT}/{POSTGRES_DB}"
SAFE_DSN = f"postgresql://{POSTGRES_USER}:***@{POSTGRES_HOST}:{POSTGRES_PORT}/{POSTGRES_DB}"
print(SAFE_DSN)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _random_customer_id(cur):
    """
    Returns a random existing customer_id, or None if the
    customers table is empty.
    """
    cur.execute("select customer_id from customers order by random() limit 1")
    row = cur.fetchone()
    return row[0] if row else None


def _random_order_id(cur):
    """
    Returns a random existing order_id, or None if the
    orders table is empty.
    """
    cur.execute("select order_id from orders order by random() limit 1")
    row = cur.fetchone()
    return row[0] if row else None


# Valid values used by the "normal" (non-buggy) mutations.
VALID_COUNTRY_CODES = ["BR", "DE", "US"]
VALID_ORDER_STATUSES = ["pending", "paid", "cancelled", "refunded"]

# Range used when generating a random order amount.
ORDER_AMOUNT_MIN = 10.00
ORDER_AMOUNT_MAX = 500.00


def _random_amount(min_value=ORDER_AMOUNT_MIN, max_value=ORDER_AMOUNT_MAX):
    return round(random.uniform(min_value, max_value), 2)


# ---------------------------------------------------------------------------
# Normal mutations
# ---------------------------------------------------------------------------


def insert_customer(conn):
    with conn.cursor() as cur:
        cur.execute(
            """
            insert into customers (
                name,
                email,
                country_code
            )
            values (%s, %s, %s)
            returning customer_id
            """,
            (
                "João Santos",
                f"joao.{datetime.now().timestamp()}@example.com",
                "BR",
            ),
        )

        customer_id = cur.fetchone()[0]

    print(f"Created customer {customer_id}")


def insert_order(conn):
    with conn.cursor() as cur:
        customer_id = _random_customer_id(cur)

        if customer_id is None:
            print("No customer found, skipping insert_order")
            return

        amount = _random_amount()

        cur.execute(
            """
            insert into orders (
                customer_id,
                amount,
                status
            )
            values (%s, %s, %s)
            returning order_id
            """,
            (customer_id, amount, "paid"),
        )

        order_id = cur.fetchone()[0]

    print(
        f"Created order {order_id} for customer {customer_id} "
        f"with amount={amount}"
    )


def update_customer(conn):
    with conn.cursor() as cur:
        customer_id = _random_customer_id(cur)

        if customer_id is None:
            print("No customer found, skipping update_customer")
            return

        cur.execute(
            "select country_code from customers where customer_id = %s",
            (customer_id,),
        )
        current_country = cur.fetchone()[0]

        # Pick a different valid country so the mutation is visible.
        candidates = [
            c for c in VALID_COUNTRY_CODES if c != current_country
        ]
        new_country = random.choice(candidates)

        cur.execute(
            """
            update customers
            set
                country_code = %s,
                updated_at = now()
            where customer_id = %s
            """,
            (new_country, customer_id),
        )

    print(
        f"Customer {customer_id} moved from "
        f"{current_country} to {new_country}"
    )


def update_order(conn):
    with conn.cursor() as cur:
        order_id = _random_order_id(cur)

        if order_id is None:
            print("No order found, skipping update_order")
            return

        cur.execute(
            "select status from orders where order_id = %s",
            (order_id,),
        )
        current_status = cur.fetchone()[0]

        # Pick a different valid status so the mutation is visible.
        candidates = [
            s for s in VALID_ORDER_STATUSES if s != current_status
        ]
        new_status = random.choice(candidates)

        cur.execute(
            """
            update orders
            set
                status = %s,
                updated_at = now()
            where order_id = %s
            """,
            (new_status, order_id),
        )

    print(
        f"Order {order_id} changed from "
        f"{current_status} to {new_status}"
    )


def delete_order(conn):
    with conn.cursor() as cur:
        cur.execute(
            """
            delete from orders
            where order_id = (
                select max(order_id)
                from orders
            )
            returning order_id
            """
        )

        row = cur.fetchone()

    if row:
        print(f"Deleted order {row[0]}")
    else:
        print("No order found")


def delete_customer_cascade(conn):
    """
    Deletes a random customer that has at least one order, removing
    their orders first since orders.customer_id has no ON DELETE
    CASCADE in the schema. Simulates a churn / GDPR-style delete.
    """
    with conn.cursor() as cur:
        cur.execute(
            """
            select c.customer_id
            from customers c
            join orders o on o.customer_id = c.customer_id
            group by c.customer_id
            order by random()
            limit 1
            """
        )

        row = cur.fetchone()

        if not row:
            print("No customer with orders found")
            return

        customer_id = row[0]

        cur.execute(
            "delete from orders where customer_id = %s",
            (customer_id,),
        )
        deleted_orders = cur.rowcount

        cur.execute(
            "delete from customers where customer_id = %s",
            (customer_id,),
        )

    print(
        f"Deleted customer {customer_id} "
        f"and {deleted_orders} associated order(s)"
    )

def backdate_update(conn):
    stale_date = datetime.now() - timedelta(days=7)

    with conn.cursor() as cur:
        cur.execute(
            """
            update orders
            set updated_at = %s
            where order_id = (
                select order_id
                from orders
                where deleted_at is null
                order by order_id
                limit 1
            )
            returning order_id
            """,
            (stale_date,),
        )
        row = cur.fetchone()

    if row:
        print(
            f"Backdated order {row[0]}: "
            f"updated_at set to {stale_date.date()} "
            "(will be missed by naive updated_at > max predicate)"
        )
    else:
        print("No active order found")


def soft_delete_order(conn):
    with conn.cursor() as cur:
        cur.execute(
            """
            update orders
            set
                deleted_at = now(),
                updated_at = now()
            where order_id = (
                select max(order_id)
                from orders
                where deleted_at is null
            )
            returning order_id
            """
        )

        row = cur.fetchone()

    if row:
        print(f"Soft deleted order {row[0]}")

def restore_order(conn):
    with conn.cursor() as cur:
        cur.execute(
            """
            update orders
            set
                deleted_at = null,
                updated_at = now()
            where order_id = (
                select max(order_id)
                from orders
                where deleted_at is not null
            )
            returning order_id
            """
        )

        row = cur.fetchone()

    if row:
        print(f"Restored order {row[0]}")

def late_arriving_order(conn):
    old_date = datetime.now() - timedelta(days=30)

    with conn.cursor() as cur:
        cur.execute(
            """
            insert into orders (
                customer_id,
                order_date,
                amount,
                status,
                created_at,
                updated_at
            )
            values (%s, %s, %s, %s, now(), now())
            returning order_id
            """,
            (
                1,
                old_date,
                250.00,
                "paid",
            ),
        )

        order_id = cur.fetchone()[0]

    print(
        f"Created late-arriving order {order_id} "
        f"with order_date={old_date.date()}"
    )

# ---------------------------------------------------------------------------
# Bad data mutations
# ---------------------------------------------------------------------------


def bug_invalid_country(conn):
    """
    Creates a customer whose country code does not exist
    in the country_codes seed.
    """
    with conn.cursor() as cur:
        cur.execute(
            """
            insert into customers (
                name,
                email,
                country_code
            )
            values (%s, %s, %s)
            returning customer_id
            """,
            (
                "Invalid Country",
                f"invalid-country.{datetime.now().timestamp()}@example.com",
                "XX",
            ),
        )

        customer_id = cur.fetchone()[0]

    print(
        f"BUG injected: customer {customer_id} "
        "has unknown country_code='XX'"
    )


def bug_negative_amount(conn):
    """
    Inserts an economically invalid order.
    PostgreSQL accepts it because the schema does not impose
    amount > 0.
    """
    with conn.cursor() as cur:
        customer_id = _random_customer_id(cur)

        cur.execute(
            """
            insert into orders (
                customer_id,
                amount,
                status
            )
            values (%s, %s, %s)
            returning order_id
            """,
            (customer_id, -150.00, "paid"),
        )

        order_id = cur.fetchone()[0]

    print(
        f"BUG injected: order {order_id} "
        "has negative amount=-150.00"
    )


def bug_zero_amount(conn):
    with conn.cursor() as cur:
        customer_id = _random_customer_id(cur)

        cur.execute(
            """
            insert into orders (
                customer_id,
                amount,
                status
            )
            values (%s, %s, %s)
            returning order_id
            """,
            (customer_id, 0, "paid"),
        )

        order_id = cur.fetchone()[0]

    print(
        f"BUG injected: order {order_id} "
        "has amount=0"
    )


def bug_future_order(conn):
    future_date = datetime.now() + timedelta(days=30)

    with conn.cursor() as cur:
        customer_id = _random_customer_id(cur)

        cur.execute(
            """
            insert into orders (
                customer_id,
                order_date,
                amount,
                status
            )
            values (%s, %s, %s, %s)
            returning order_id
            """,
            (
                customer_id,
                future_date,
                199.90,
                "paid",
            ),
        )

        order_id = cur.fetchone()[0]

    print(
        f"BUG injected: order {order_id} (customer {customer_id}) "
        f"has future date {future_date.date()}"
    )


def bug_dirty_customer_name(conn):
    """
    Creates data that is structurally valid but poorly normalized.
    """
    with conn.cursor() as cur:
        cur.execute(
            """
            insert into customers (
                name,
                email,
                country_code
            )
            values (%s, %s, %s)
            returning customer_id
            """,
            (
                "   MARIA DA SILVA   ",
                f"dirty-name.{datetime.now().timestamp()}@example.com",
                "BR",
            ),
        )

        customer_id = cur.fetchone()[0]

    print(
        f"BUG injected: customer {customer_id} "
        "has badly formatted name"
    )


def bug_duplicate_logical_email(conn):
    """
    PostgreSQL VARCHAR uniqueness is case-sensitive.

    Therefore these can coexist:

        ana@example.com
        ANA@EXAMPLE.COM

    A dbt model that normalizes emails with lower()
    can expose the logical duplicate.
    """
    with conn.cursor() as cur:
        cur.execute(
            """
            select email
            from customers
            order by customer_id
            limit 1
            """
        )

        email = cur.fetchone()[0]
        duplicate_email = email.upper()

        cur.execute(
            """
            insert into customers (
                name,
                email,
                country_code
            )
            values (%s, %s, %s)
            returning customer_id
            """,
            (
                "Duplicate Customer",
                duplicate_email,
                "BR",
            ),
        )

        customer_id = cur.fetchone()[0]

    print(
        f"BUG injected: customer {customer_id} "
        f"has logical duplicate email '{duplicate_email}'"
    )


def bug_stale_record(conn):
    stale_date = datetime.now() - timedelta(days=365)

    with conn.cursor() as cur:
        cur.execute(
            """
            update customers
            set updated_at = %s
            where customer_id = 1
            """,
            (stale_date,),
        )

    print(
        "BUG injected: customer 1 has "
        f"stale updated_at={stale_date.date()}"
    )


# ---------------------------------------------------------------------------
# Simulation
# ---------------------------------------------------------------------------


NORMAL_ACTIONS = [
    insert_order,
    update_order,
    insert_customer,
    update_customer,
    delete_order,
    delete_customer_cascade,
    soft_delete_order,
    restore_order,
    late_arriving_order,
    backdate_update,
]


BUG_ACTIONS = [
    bug_invalid_country,
    bug_negative_amount,
    bug_zero_amount,
    bug_future_order,
    bug_dirty_customer_name,
    bug_duplicate_logical_email,
    bug_stale_record,
]


def simulate(conn):
    action = random.choice(NORMAL_ACTIONS)

    print(f"Executing: {action.__name__}")

    action(conn)


def simulate_bug(conn):
    action = random.choice(BUG_ACTIONS)

    print(f"Injecting: {action.__name__}")

    action(conn)


ACTIONS = {
    "insert-customer": insert_customer,
    "insert-order": insert_order,
    "update-customer": update_customer,
    "update-order": update_order,
    "delete-order": delete_order,
    "delete-customer-cascade": delete_customer_cascade,
    "soft-delete-order": soft_delete_order,
    "restore-order": restore_order,
    "late-arriving-order": late_arriving_order,
    "backdate-update": backdate_update,

    "bug-invalid-country": bug_invalid_country,
    "bug-negative-amount": bug_negative_amount,
    "bug-zero-amount": bug_zero_amount,
    "bug-future-order": bug_future_order,
    "bug-dirty-name": bug_dirty_customer_name,
    "bug-duplicate-email": bug_duplicate_logical_email,
    "bug-stale-record": bug_stale_record,

    "simulate": simulate,
    "simulate-bug": simulate_bug,
}


def main():
    parser = argparse.ArgumentParser()

    parser.add_argument(
        "action",
        choices=ACTIONS,
    )

    args = parser.parse_args()

    with psycopg.connect(DSN) as conn:
        ACTIONS[args.action](conn)
        conn.commit()


if __name__ == "__main__":
    main()
