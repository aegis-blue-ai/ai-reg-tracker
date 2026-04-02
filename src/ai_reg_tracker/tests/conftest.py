# ABOUTME: Shared pytest fixtures for the packaged test suite.
# ABOUTME: Provides a live API client when AI_REG_TRACKER_API_KEY is available.

import os

import pytest

from ai_reg_tracker.client import RegulationTrackerClient


@pytest.fixture
def live_client() -> RegulationTrackerClient:
    """Provide a live API client when an API key is available."""
    api_key = os.environ.get('AI_REG_TRACKER_API_KEY')
    if not api_key:
        pytest.skip('AI_REG_TRACKER_API_KEY is not set')
    return RegulationTrackerClient(api_key=api_key)
