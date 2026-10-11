"""Builds a small e-commerce star schema in DuckDB so you can run the agent today.
Later you can point agent.py at your Databricks tables instead."""
import random, datetime as dt, duckdb

random.seed(7)
con = duckdb.connect("ecommerce.duckdb")
for t in ("fact_orders", "dim_product", "dim_customer"):
    con.execute(f"DROP TABLE IF EXISTS {t}")

con.execute("CREATE TABLE dim_customer(customer_id INT, region VARCHAR, signup_date DATE)")
con.execute("CREATE TABLE dim_product(product_id INT, product_name VARCHAR, category VARCHAR, brand VARCHAR, unit_price DOUBLE)")
con.execute("""CREATE TABLE fact_orders(order_id INT, customer_id INT, product_id INT,
               order_date DATE, quantity INT, discount_pct INT, revenue DOUBLE)""")

regions = ["North", "South", "East", "West", "Central"]
catalog = {
    "Electronics": [("Phone", 18000), ("Laptop", 52000), ("Earbuds", 2500), ("Smartwatch", 6500)],
    "Fashion": [("Sneakers", 3200), ("Jacket", 4100), ("Jeans", 2200), ("Backpack", 1800)],
    "Home": [("Mixer", 3500), ("Lamp", 1200), ("Cookware Set", 4800), ("Air Purifier", 9500)],
    "Beauty": [("Face Wash", 450), ("Perfume", 2800), ("Hair Dryer", 1900)],
}
brands = ["Zenith", "Orbit", "Nova", "Kite", "Lumen"]

customers = [(i, random.choice(regions), dt.date(2022, 1, 1) + dt.timedelta(days=random.randint(0, 900)))
             for i in range(1, 2001)]
products, pid = [], 1
for cat, items in catalog.items():
    for name, price in items:
        products.append((pid, name, cat, random.choice(brands), float(price)))
        pid += 1

price_of = {p[0]: p[4] for p in products}
orders = []
for oid in range(1, 20001):
    p = random.choice(products)[0]
    qty = random.randint(1, 4)
    disc = random.choice([0, 0, 5, 10, 15, 20])
    day = dt.date(2024, 1, 1) + dt.timedelta(days=random.randint(0, 700))
    orders.append((oid, random.randint(1, 2000), p, day, qty, disc,
                   round(price_of[p] * qty * (1 - disc / 100), 2)))

con.executemany("INSERT INTO dim_customer VALUES (?,?,?)", customers)
con.executemany("INSERT INTO dim_product VALUES (?,?,?,?,?)", products)
con.executemany("INSERT INTO fact_orders VALUES (?,?,?,?,?,?,?)", orders)
print("Created ecommerce.duckdb with", len(orders), "orders")
