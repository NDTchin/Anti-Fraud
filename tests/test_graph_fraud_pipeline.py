import pytest

from src.algorithms.graph_fraud_pipeline import FraudPipelineConfig


def test_default_thresholds_match_dataset_profile() -> None:
    config = FraudPipelineConfig()

    assert config.driver_max_degree == 30
    assert config.address_max_degree == 50
    assert config.promo_max_degree == 200
    assert config.repeated_driver_orders == 3
    assert config.similarity_cutoff == 0.5


@pytest.mark.parametrize(
    "config",
    [
        FraudPipelineConfig(driver_min_degree=4, driver_max_degree=3),
        FraudPipelineConfig(similarity_cutoff=0.0),
        FraudPipelineConfig(repeated_driver_ratio=1.1),
        FraudPipelineConfig(similarity_top_k=0),
    ],
)
def test_invalid_thresholds_are_rejected(config: FraudPipelineConfig) -> None:
    with pytest.raises(ValueError):
        config.validate()
