# Copyright 2025 Canonical Ltd.
# See LICENSE file for licensing details.

"""Unit tests for the bind module."""

import logging
from unittest.mock import patch

import ops
import ops.testing
import pytest
from charms.bind.v0.dns_record import RequirerEntry
from scenario.context import _Event  # needed for custom events for now

logger = logging.getLogger(__name__)


@pytest.mark.usefixtures("context")
@pytest.mark.usefixtures("base_state")
def test_start(context, base_state):
    """
    arrange: prepare some state
    act: run start
    assert: status is waiting
    """
    base_state["relations"] = []
    state = ops.testing.State(**base_state)

    out = context.run(context.on.start(), state)
    assert out.unit_status == ops.WaitingStatus("Waiting for a database integration.")


@pytest.mark.usefixtures("context")
@pytest.mark.usefixtures("base_state")
@pytest.mark.usefixtures("database_relation")
def test_start_with_database(context, base_state, database_relation):
    """
    arrange: prepare some state
    act: run start
    assert: status is active
    """
    base_state["relations"].append(database_relation)
    state = ops.testing.State(**base_state)

    out = context.run(context.on.start(), state)
    assert out.unit_status == ops.ActiveStatus("")


@pytest.mark.usefixtures("context")
@pytest.mark.usefixtures("base_state")
@pytest.mark.usefixtures("database_relation")
@pytest.mark.usefixtures("requirer_relation")
@pytest.mark.usefixtures("api_root_token")
@pytest.mark.usefixtures("record_request")
# This is a complex state that needs 6 arguments. Sorry pylint !
# pylint: disable=too-many-positional-arguments
def test_reconcile(
    context, base_state, database_relation, requirer_relation, api_root_token, record_request
):
    """
    arrange: prepare some state
    act: run reconcile
    assert: status is active and requests were send to the API
    """
    base_state["relations"].extend([database_relation, requirer_relation])
    state = ops.testing.State(**base_state)

    with (patch("dns_policy.DnsPolicyService.send_requests") as dns_policy_send_requests,):
        reconcile_event = _Event("reconcile")
        out = context.run(reconcile_event, state)
        assert out.unit_status == ops.ActiveStatus("")
        dns_policy_send_requests.assert_called()
        assert dns_policy_send_requests.call_args[0] == (
            api_root_token,
            [RequirerEntry.model_validate(record_request)],
        )
