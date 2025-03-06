# Copyright 2025 Canonical Ltd.
# See LICENSE file for licensing details.

"""Fixtures for charm tests."""

import json
import logging
from unittest.mock import patch

import ops.testing
import pytest
import scenario

from src.charm import DnsPolicyCharm

logger = logging.getLogger(__name__)


@pytest.fixture(name="api_root_token")
def api_root_token_fixture():
    """API root token fixture."""
    yield "SomeTestApiRootToken"


@pytest.fixture(name="context")
def context_fixture(api_root_token):
    """Context fixture."""
    with (
        patch("timer.TimerService.start"),
        patch("dns_policy.DnsPolicyService.setup"),
        patch("dns_policy.DnsPolicyService.status") as dns_policy_status,
        patch("dns_policy.DnsPolicyService.configure"),
        patch("dns_policy.DnsPolicyService.get_approved_requests"),
        patch("dns_policy.DnsPolicyService.get_api_root_token") as dns_policy_get_api_root_token,
    ):
        dns_policy_status.return_value = True
        dns_policy_get_api_root_token.return_value = api_root_token
        yield ops.testing.Context(
            charm_type=DnsPolicyCharm,
        )


@pytest.fixture(name="base_state")
def base_state_fixture():
    """Base state fixture."""
    input_state: dict = {"leader": True}
    input_state["relations"] = [
        scenario.SubordinateRelation(
            endpoint="dns-record-requirer",
            interface="dns_record",
            remote_app_name="bind",
            remote_app_data={},
            local_unit_data={},
        )
    ]
    yield input_state


@pytest.fixture(name="database_relation")
def database_relation_fixture():
    """Database relation data fixture."""
    data = {
        "database": "somedb",
        "endpoints": "1.2.3.4:5432",
        "password": "bar",
        "username": "foo",
    }
    return scenario.Relation(
        endpoint="database",
        interface="database",
        remote_app_name="postgresql",
        remote_app_data=data,
        local_unit_data=data,
    )


@pytest.fixture(name="record_request")
def record_request_fixture():
    """Record request fixture."""
    yield {
        "domain": "canonical.com",
        "host_label": "admin",
        "ttl": 3600,
        "record_class": "IN",
        "record_type": "A",
        "record_data": "204.45.64.14",
        "uuid": "2c210a7c-55fe-52e1-a14b-2268bd8f4669",
    }


@pytest.fixture(name="requirer_relation")
def requirer_relation_fixture(record_request):
    """Requirer relation data fixture."""
    data = {"dns_entries": json.dumps([record_request])}
    return scenario.Relation(
        endpoint="dns-record-provider",
        interface="dns_record",
        remote_app_name="dns-integrator",
        remote_app_data=data,
        local_unit_data=data,
    )
