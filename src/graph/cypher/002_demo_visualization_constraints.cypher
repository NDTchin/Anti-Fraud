CREATE CONSTRAINT demo_order_id IF NOT EXISTS
FOR (n:Order) REQUIRE n.order_id IS UNIQUE;

CREATE CONSTRAINT demo_driver_id IF NOT EXISTS
FOR (n:Driver) REQUIRE n.driver_id IS UNIQUE;

CREATE CONSTRAINT demo_customer_id IF NOT EXISTS
FOR (n:Customer) REQUIRE n.customer_id IS UNIQUE;

CREATE INDEX demo_order_is_flagged IF NOT EXISTS
FOR (n:Order) ON (n.is_flagged);

CREATE INDEX demo_order_date IF NOT EXISTS
FOR (n:Order) ON (n.order_date);

CREATE INDEX demo_driver_is_flagged IF NOT EXISTS
FOR (n:Driver) ON (n.is_flagged);

CREATE INDEX demo_customer_is_flagged IF NOT EXISTS
FOR (n:Customer) ON (n.is_flagged);
