"""Enable real Home Assistant integration loading."""

import pytest


@pytest.fixture(autouse=True)
def custom_integrations(enable_custom_integrations):
    yield
