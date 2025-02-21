# Copyright 2025 Canonical Ltd.
# See LICENSE file for licensing details.

"""Fixtures for charm tests."""

import logging
from unittest.mock import Mock

import pytest

from src.charm import DnsIntegratorCharm

logger = logging.getLogger(__name__)


@pytest.fixture
def mock_self():
    """Create a mock self object since we don't need real instance."""
    return Mock(spec=DnsIntegratorCharm)


@pytest.fixture(name="base_state")
def base_state_fixture():
    """Base state fixture."""
    input_state: dict = {}
    yield input_state
