"""Small Neo4j driver wrapper shared by scripts and services."""

from collections.abc import Iterator
from contextlib import contextmanager

from neo4j import Driver, GraphDatabase

from src.config.settings import settings


@contextmanager
def neo4j_driver() -> Iterator[Driver]:
    driver = GraphDatabase.driver(
        settings.neo4j_uri,
        auth=(settings.neo4j_username, settings.neo4j_password),
    )
    try:
        driver.verify_connectivity()
        yield driver
    finally:
        driver.close()

