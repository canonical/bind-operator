#!/usr/bin/env python3

# Copyright 2024 Canonical Ltd.
# See LICENSE file for licensing details.

"""Integration tests."""

import pytest


@pytest.mark.abort_on_fail
async def test_nothing():
    """
    arrange: nothing.
    act: nothing.
    assert: True.
    """
    assert True