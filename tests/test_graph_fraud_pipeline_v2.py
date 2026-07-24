import pytest

from src.algorithms.graph_fraud_pipeline_v2 import FraudPipelineConfig


def config(**overrides: object) -> FraudPipelineConfig:
    values = {
        "from_time": "2026-07-14T07:00:00",
        "to_time": "2026-07-15T07:00:00",
        **overrides,
    }
    return FraudPipelineConfig(**values)


def test_v2_defaults_match_audited_dataset() -> None:
    pipeline_config = config()

    assert pipeline_config.driver_max_degree == 30
    assert pipeline_config.merchant_max_degree == 80
    assert pipeline_config.rare_address_max_degree == 10
    assert pipeline_config.address_max_degree == 50
    assert pipeline_config.payment_max_degree == 150
    assert pipeline_config.promo_max_degree == 200
    assert pipeline_config.similarity_cutoff == 0.6
    assert pipeline_config.split_min_size == 6
    assert pipeline_config.component_max_size == 50


def test_v2_parameters_include_stable_run_id() -> None:
    parameters = config().parameters()

    assert parameters["run_id"] == (
        "2026-07-14T07:00:00__2026-07-15T07:00:00"
    )


@pytest.mark.parametrize(
    "pipeline_config",
    [
        config(to_time="2026-07-14T07:00:00"),
        config(driver_min_degree=31, driver_max_degree=30),
        config(rare_address_max_degree=51),
        config(payment_min_degree=151, payment_max_degree=150),
        config(similarity_cutoff=0.0),
        config(ring_density=0.6, split_density=0.5),
        config(component_min_size=1),
        config(component_min_avg_score=1.1),
        config(driver_weight=0.0),
    ],
)
def test_v2_rejects_invalid_configuration(
    pipeline_config: FraudPipelineConfig,
) -> None:
    with pytest.raises(ValueError):
        pipeline_config.validate()
