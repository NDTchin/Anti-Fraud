CREATE CONSTRAINT rule_key IF NOT EXISTS
FOR (n:Rule) REQUIRE n.rule_key IS UNIQUE;

CREATE CONSTRAINT model_version_key IF NOT EXISTS
FOR (n:ModelVersion) REQUIRE n.model_key IS UNIQUE;

CREATE CONSTRAINT fraud_evidence_key IF NOT EXISTS
FOR (n:FraudEvidence) REQUIRE n.evidence_key IS UNIQUE;

CREATE CONSTRAINT order_reference_key IF NOT EXISTS
FOR (n:OrderReference) REQUIRE n.ref_key IS UNIQUE;

CREATE CONSTRAINT customer_reference_key IF NOT EXISTS
FOR (n:CustomerReference) REQUIRE n.ref_key IS UNIQUE;

CREATE CONSTRAINT timeline_event_key IF NOT EXISTS
FOR (n:TimelineEvent) REQUIRE n.event_key IS UNIQUE;

CREATE INDEX fraud_evidence_type IF NOT EXISTS
FOR (n:FraudEvidence) ON (n.evidence_type);

CREATE INDEX fraud_evidence_domain IF NOT EXISTS
FOR (n:FraudEvidence) ON (n.domain);

CREATE INDEX timeline_event_order IF NOT EXISTS
FOR (n:TimelineEvent) ON (n.order_id);
