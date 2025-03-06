#!/usr/bin/env python3
# Copyright 2025 Canonical Ltd.
# See LICENSE file for licensing details.

"""Integration tests."""

import logging

import juju.application
import ops
import pytest

logger = logging.getLogger(__name__)


@pytest.mark.asyncio
@pytest.mark.abort_on_fail
async def test_active(full_deployment: dict[str, juju.application.Application]):
    """
    arrange: build and deploy the charm.
    act: nothing.
    assert: that the charm ends up in an active state.
    """
    unit = full_deployment["dns-policy"].units[0]
    assert unit.workload_status == ops.model.ActiveStatus.name
