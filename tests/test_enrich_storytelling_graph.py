from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

from scripts.enrich_storytelling_graph import (
    load_anomaly_scores,
    load_flagged_orders,
    parse_feature_list,
    parse_json_text,
)


def test_parse_json_text_handles_empty_values() -> None:
    assert parse_json_text(None) == {}
    assert parse_json_text('') == {}


def test_parse_json_text_parses_payload() -> None:
    payload = parse_json_text('{"merchant_id":"m1","order_count":3}')

    assert payload["merchant_id"] == "m1"
    assert payload["order_count"] == 3


def test_parse_feature_list_splits_features() -> None:
    features = parse_feature_list('discount, food_total_paid, merchant_order_frequency')

    assert features == ['discount', 'food_total_paid', 'merchant_order_frequency']


def test_load_flagged_orders_builds_storytelling_rule_rows() -> None:
    path = Path('D:/VSF/tmp_storytelling_flagged.csv')
    pd.DataFrame(
        [
            {
                'domain': 'food',
                'order_id': 'o1',
                'customer_id': 'c1',
                'rule_name': 'PROMO_ENTITY_CONCENTRATION',
                'rule_version': 'v1',
                'flag_reason': 'shared promo pattern',
                'rule_score': 82,
                'risk_level': 'HIGH',
                'flagged_at': '2026-07-21T09:00:00',
                'evidence_json': json.dumps({'merchant_id': 'm1'}),
            }
        ]
    ).to_csv(path, index=False)

    rows = load_flagged_orders(path)

    assert rows[0]['rule_key'] == 'food|PROMO_ENTITY_CONCENTRATION|v1'
    assert rows[0]['evidence_type'] == 'RULE_HIT'
    assert json.loads(rows[0]['raw_payload_json'])['merchant_id'] == 'm1'


def test_load_anomaly_scores_builds_storytelling_model_rows() -> None:
    path = Path('D:/VSF/tmp_storytelling_scores.csv')
    pd.DataFrame(
        [
            {
                'domain': 'food',
                'order_id': 'o1',
                'customer_id': 'c1',
                'model_name': 'isolation_forest',
                'model_version': 'v1',
                'anomaly_score': 96.4,
                'is_model_anomaly': True,
                'score_threshold': 95.0,
                'scored_at': '2026-07-21T09:10:00',
                'top_features': 'discount,food_total_paid',
            }
        ]
    ).to_csv(path, index=False)

    rows = load_anomaly_scores(path)

    assert rows[0]['model_key'] == 'food|isolation_forest|v1'
    assert rows[0]['evidence_type'] == 'MODEL_SCORE'
    assert json.loads(rows[0]['raw_payload_json'])['top_features'] == ['discount', 'food_total_paid']
