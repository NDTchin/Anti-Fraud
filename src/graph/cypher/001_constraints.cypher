CREATE CONSTRAINT customer_id IF NOT EXISTS
FOR (n:Customer) REQUIRE n.customer_id IS UNIQUE;

CREATE CONSTRAINT driver_id IF NOT EXISTS
FOR (n:Driver) REQUIRE n.driver_id IS UNIQUE;

CREATE CONSTRAINT merchant_id IF NOT EXISTS
FOR (n:Merchant) REQUIRE n.merchant_id IS UNIQUE;

CREATE CONSTRAINT order_id IF NOT EXISTS
FOR (n:Order) REQUIRE n.order_id IS UNIQUE;

CREATE CONSTRAINT address_key IF NOT EXISTS
FOR (n:Address) REQUIRE n.address_key IS UNIQUE;

CREATE CONSTRAINT payment_method_name IF NOT EXISTS
FOR (n:PaymentMethod) REQUIRE n.name IS UNIQUE;

CREATE CONSTRAINT promotion_code IF NOT EXISTS
FOR (n:PromotionCode) REQUIRE n.code IS UNIQUE;

CREATE CONSTRAINT promotion_campaign_code IF NOT EXISTS
FOR (n:PromotionCampaign) REQUIRE n.code IS UNIQUE;

CREATE CONSTRAINT cancel_actor_name IF NOT EXISTS
FOR (n:CancelActor) REQUIRE n.name IS UNIQUE;

CREATE CONSTRAINT cancel_reason_text IF NOT EXISTS
FOR (n:CancelReason) REQUIRE n.reason IS UNIQUE;

CREATE CONSTRAINT dropoff_fail_actor_name IF NOT EXISTS
FOR (n:DropoffFailActor) REQUIRE n.name IS UNIQUE;

CREATE CONSTRAINT dropoff_fail_code_value IF NOT EXISTS
FOR (n:DropoffFailCode) REQUIRE n.code IS UNIQUE;

CREATE CONSTRAINT ride_service_name IF NOT EXISTS
FOR (n:RideService) REQUIRE n.name IS UNIQUE;

CREATE CONSTRAINT service_type_name IF NOT EXISTS
FOR (n:ServiceType) REQUIRE n.name IS UNIQUE;

CREATE CONSTRAINT sub_vertical_name IF NOT EXISTS
FOR (n:SubVertical) REQUIRE n.name IS UNIQUE;

CREATE CONSTRAINT travel_mode_name IF NOT EXISTS
FOR (n:TravelMode) REQUIRE n.name IS UNIQUE;

CREATE CONSTRAINT channel_type_name IF NOT EXISTS
FOR (n:ChannelType) REQUIRE n.name IS UNIQUE;

CREATE INDEX order_time IF NOT EXISTS
FOR (n:Order) ON (n.order_time);

CREATE INDEX order_domain IF NOT EXISTS
FOR (n:Order) ON (n.domain);

CREATE INDEX order_status IF NOT EXISTS
FOR (n:Order) ON (n.status);

