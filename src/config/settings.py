"""Environment-backed application settings."""

from pathlib import Path
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    neo4j_domain: Literal["food", "ride"] = "ride"
    neo4j_food_uri: str = "bolt://localhost:7687"
    neo4j_ride_uri: str = "bolt://localhost:7688"
    neo4j_food_browser_url: str = "http://localhost:7474/browser/"
    neo4j_ride_browser_url: str = "http://localhost:7475/browser/"
    neo4j_uri: str = "bolt://localhost:7687"
    neo4j_browser_url: str = "http://localhost:7474/browser/"
    neo4j_username: str = "neo4j"
    neo4j_password: str = "change-me"
    neo4j_database: str = "neo4j"
    raw_data_path: Path = Path("data/handoff/ride/cleaned_orders/orders_ride_masked_2026-07-29.parquet")
    processed_data_dir: Path = Path("data/processed")

    @property
    def active_neo4j_uri(self) -> str:
        return self.neo4j_ride_uri if self.neo4j_domain == "ride" else self.neo4j_food_uri

    @property
    def active_neo4j_browser_url(self) -> str:
        return self.neo4j_ride_browser_url if self.neo4j_domain == "ride" else self.neo4j_food_browser_url

    def model_post_init(self, __context: object) -> None:
        # Keep legacy callers working while letting .env store both domains.
        self.neo4j_uri = self.active_neo4j_uri
        self.neo4j_browser_url = self.active_neo4j_browser_url


settings = Settings()

