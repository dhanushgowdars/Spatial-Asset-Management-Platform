"""Deterministic Aereo-only test defaults.

This fixture applies only to the isolated `aereo_tests` collection.  It deliberately
uses pytest's monkeypatch fixture so caller shell settings are restored outside
each test, and individual tests can override any value after this fixture runs.
Never use this fixture to configure the running GeoInsight/FaultWeave servers.
"""
from __future__ import annotations

import pytest


# These are application-documented development defaults, not production policy.
# Deliberate invalid-setting tests override these through their own monkeypatch.
AEREO_TEST_DEFAULTS = {
    'AEREO_MAX_CONCURRENT_UPLOADS': '4',
    'AEREO_MAX_CONCURRENT_ANALYSES': '4',
    'AEREO_UPLOAD_REQUESTS_PER_WINDOW': '120',
    'AEREO_UPLOAD_RATE_WINDOW_SECONDS': '60',
    'AEREO_RESPONSE_CACHE_MAX_ENTRIES': '32',
    'AEREO_RESPONSE_CACHE_MAX_BYTES': '33554432',
    'AEREO_RESPONSE_CACHE_MAX_ITEM_BYTES': '4194304',
    'AEREO_RESPONSE_CACHE_TTL_SECONDS': '60',
}


@pytest.fixture(autouse=True)
def stable_aereo_test_settings(monkeypatch):
    """Normalize this test's app settings without affecting the parent shell."""
    for name, value in AEREO_TEST_DEFAULTS.items():
        monkeypatch.setenv(name, value)
    yield
