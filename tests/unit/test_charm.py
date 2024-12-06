# Copyright 2024 Canonical Ltd.
# See LICENSE file for licensing details.

"""Unit tests for the bind module."""

import json
import logging
from unittest.mock import patch

import ops
import pytest
import scenario
from scenario.context import _Event  # needed for custom events for now

import tests.unit.helpers

logger = logging.getLogger(__name__)


@pytest.mark.usefixtures("context")
@pytest.mark.usefixtures("base_state")
def test_start_wo_peer_relation(context, base_state):
    """
    arrange: prepare some state
    act: run start
    assert: status is peer not available
    """
    base_state["relations"] = []
    state = ops.testing.State(**base_state)
    out = context.run(context.on.start(), state)
    assert out.unit_status == ops.testing.WaitingStatus("Peer relation is not available")


@pytest.mark.usefixtures("context")
@pytest.mark.usefixtures("base_state")
def test_start(context, base_state):
    """
    arrange: prepare some state with peer relation
    act: run start
    assert: status is active
    """
    state = ops.testing.State(**base_state)
    out = context.run(context.on.start(), state)
    assert out.unit_status == ops.testing.ActiveStatus()


@pytest.mark.usefixtures("context")
@pytest.mark.usefixtures("base_state")
def test_stop(context, base_state):
    """
    arrange: prepare some state with peer relation
    act: run stop
    assert: status is active
    """
    state = ops.testing.State(**base_state)
    out = context.run(context.on.stop(), state)
    assert out.unit_status == ops.testing.ActiveStatus()


@pytest.mark.usefixtures("context")
@pytest.mark.usefixtures("base_state")
def test_install(context, base_state):
    """
    arrange: prepare some state with peer relation
    act: run install
    assert: status is active
    """
    state = ops.testing.State(**base_state)
    out = context.run(context.on.install(), state)
    assert out.unit_status == ops.testing.ActiveStatus()


@pytest.mark.usefixtures("context")
@pytest.mark.usefixtures("base_state")
def test_config_changed(context, base_state):
    """
    arrange: prepare some state with peer relation
    act: run config_changed
    assert: status is active
    """
    state = ops.testing.State(**base_state)
    out = context.run(context.on.config_changed(), state)
    assert out.unit_status == ops.testing.ActiveStatus()


@pytest.mark.usefixtures("context")
@pytest.mark.usefixtures("base_state")
def test_leader_elected_changed_while_leader_not_active(context, base_state):
    """
    arrange: prepare some state with peer relation
    act: run leader_elected
    assert: status is active
    """
    base_state["leader"] = True
    state = ops.testing.State(**base_state)
    out = context.run(context.on.leader_elected(), state)
    assert out.unit_status == ops.testing.ActiveStatus("active")


@pytest.mark.usefixtures("context")
@pytest.mark.usefixtures("base_state")
def test_leader_elected_changed_while_leader_not_active_dig_timeout(context, base_state):
    """
    arrange: be leader not active and dig timeout
    act: run leader_elected
    assert: status is active
    """
    base_state["leader"] = True
    databag = {"active-unit": "1.2.99.4"}
    peer_relation = scenario.PeerRelation(
        endpoint="bind-peers",
        local_app_data=databag,
    )
    base_state["relations"][0] = peer_relation
    with patch("src.charm.BindCharm._dig_query") as dig_query:
        dig_query.return_value = ""
        state = ops.testing.State(**base_state)
        out = context.run(context.on.leader_elected(), state)
        assert out.unit_status == ops.testing.ActiveStatus("active")


@pytest.mark.usefixtures("context")
@pytest.mark.usefixtures("base_state")
def test_leader_elected_changed_while_leader_not_active_dig_ok(context, base_state):
    """
    arrange: be leader not active and dig successful
    act: run leader_elected
    assert: status is active
    """
    base_state["leader"] = True
    databag = {"active-unit": "1.2.99.4"}
    peer_relation = scenario.PeerRelation(
        endpoint="bind-peers",
        local_app_data=databag,
    )
    base_state["relations"][0] = peer_relation
    with patch("src.charm.BindCharm._dig_query") as dig_query:
        dig_query.return_value = "ok"
        state = ops.testing.State(**base_state)
        out = context.run(context.on.leader_elected(), state)
        assert out.unit_status == ops.testing.ActiveStatus()


@pytest.mark.usefixtures("context")
@pytest.mark.usefixtures("base_state")
def test_leader_elected_changed_while_not_leader(context, base_state):
    """
    arrange: not leader
    act: run leader_elected
    assert: status is active
    """
    base_state["leader"] = False
    state = ops.testing.State(**base_state)
    out = context.run(context.on.leader_elected(), state)
    assert out.unit_status == ops.testing.ActiveStatus()


@pytest.mark.usefixtures("context")
@pytest.mark.usefixtures("base_state")
@pytest.mark.usefixtures("peer_relation")
def test_peer_relation_departed_while_leader(context, base_state, peer_relation):
    """
    arrange: while leader
    act: run peer relation departed
    assert: status is active
    """
    base_state["leader"] = True
    state = ops.testing.State(**base_state)
    peer_relation_departed_event = _Event(
        f"{peer_relation.endpoint}_relation_departed", relation=peer_relation
    )
    out = context.run(peer_relation_departed_event, state)
    assert out.unit_status == ops.testing.ActiveStatus("active")


@pytest.mark.usefixtures("context")
@pytest.mark.usefixtures("base_state")
@pytest.mark.usefixtures("peer_relation")
def test_peer_relation_departed_while_not_leader(context, base_state, peer_relation):
    """
    arrange: while not leader
    act: run peer relation departed
    assert: status is active
    """
    base_state["leader"] = False
    state = ops.testing.State(**base_state)
    peer_relation_departed_event = _Event(
        f"{peer_relation.endpoint}_relation_departed", relation=peer_relation
    )
    out = context.run(peer_relation_departed_event, state)
    assert out.unit_status == ops.testing.ActiveStatus()


@pytest.mark.usefixtures("context")
@pytest.mark.usefixtures("base_state")
@pytest.mark.usefixtures("peer_relation")
def test_peer_relation_joined(context, base_state, peer_relation):
    """
    arrange: while not leader
    act: run peer relation joined
    assert: status is active
    """
    state = ops.testing.State(**base_state)
    peer_relation_joined_event = _Event(
        f"{peer_relation.endpoint}_relation_joined", relation=peer_relation
    )
    out = context.run(peer_relation_joined_event, state)
    assert out.unit_status == ops.testing.ActiveStatus()


@pytest.mark.usefixtures("context")
@pytest.mark.usefixtures("base_state")
def test_reload_bind(context, base_state):
    """
    arrange: base state
    act: run reload bind
    assert: status is active
    """
    state = ops.testing.State(**base_state)
    reload_bind_event = _Event("reload_bind")
    out = context.run(reload_bind_event, state)
    assert out.unit_status == ops.testing.ActiveStatus()


@pytest.mark.usefixtures("context")
@pytest.mark.usefixtures("base_state")
def test_dns_record_relation_changed_wo_conflict(context, base_state):
    """
    arrange: base state with some relation
    act: run dns record relation changed
    assert: status is active
    """
    record_requirers_data = tests.unit.helpers.dns_record_requirers_data_from_integration_datasets(
        [
            [
                tests.unit.helpers.RECORDS["admin.dns.test_42"],
                tests.unit.helpers.RECORDS["admin.dns.test_42"],
            ],
        ],
    )
    dumped_model = record_requirers_data[0].model_dump(exclude_unset=True)
    dumped_data = {
        "dns_entries": json.dumps(dumped_model["dns_entries"], default=str),
    }

    dns_record_relation = scenario.Relation(
        endpoint="dns-record",
        remote_app_data=dumped_data,
    )
    base_state["relations"].append(dns_record_relation)
    base_state["leader"] = True
    state = ops.testing.State(**base_state)
    dns_record_relation_changed_event = _Event(
        "dns_record_relation_changed", relation=dns_record_relation
    )
    out = context.run(dns_record_relation_changed_event, state)
    in_uuids = {str(x["uuid"]) for x in dumped_model["dns_entries"]}
    for relation in out.relations:
        if relation.endpoint == "dns-record":
            data = json.loads(relation.local_app_data["dns_entries"])
            out_uuids = {x["uuid"] for x in data}
            # check that all the records from the requirer data are approved
            assert out_uuids == in_uuids
    assert out.unit_status == ops.testing.ActiveStatus()


@pytest.mark.usefixtures("context")
@pytest.mark.usefixtures("base_state")
def test_dns_record_relation_changed_wo_conflict_not_leader(context, base_state):
    """
    arrange: base state with some relation not leader
    act: run dns record relation changed
    assert: status is active
    """
    record_requirers_data = tests.unit.helpers.dns_record_requirers_data_from_integration_datasets(
        [
            [
                tests.unit.helpers.RECORDS["admin.dns.test_42"],
                tests.unit.helpers.RECORDS["admin.dns.test_42"],
            ],
        ],
    )
    dumped_model = record_requirers_data[0].model_dump(exclude_unset=True)
    dumped_data = {
        "dns_entries": json.dumps(dumped_model["dns_entries"], default=str),
    }

    dns_record_relation = scenario.Relation(
        endpoint="dns-record",
        remote_app_data=dumped_data,
    )
    base_state["relations"].append(dns_record_relation)
    base_state["leader"] = False
    state = ops.testing.State(**base_state)
    dns_record_relation_changed_event = _Event(
        "dns_record_relation_changed", relation=dns_record_relation
    )
    out = context.run(dns_record_relation_changed_event, state)
    for relation in out.relations:
        if relation.endpoint == "dns-record":
            # As we are not the leader, we do not update the databag of the relation
            assert "dns_entries" not in relation.local_app_data
    assert out.unit_status == ops.testing.ActiveStatus()


@pytest.mark.skip(reason="TODO: Status is not currently correctly computed.")
@pytest.mark.usefixtures("context")
@pytest.mark.usefixtures("base_state")
def test_dns_record_relation_changed_w_conflict(context, base_state):
    """
    arrange: base state with some relation with conflicts
    act: run dns record relation changed
    assert: status is blocked
    """
    record_requirers_data = tests.unit.helpers.dns_record_requirers_data_from_integration_datasets(
        [
            [
                tests.unit.helpers.RECORDS["admin.dns.test_42"],
            ],
            [
                tests.unit.helpers.RECORDS["admin.dns.test_42"],
            ],
        ],
    )
    for record_requirer_data in record_requirers_data:
        dumped_model = record_requirer_data.model_dump(exclude_unset=True)
        dumped_data = {
            "dns_entries": json.dumps(dumped_model["dns_entries"], default=str),
        }
        dns_record_relation = scenario.Relation(
            endpoint="dns-record",
            remote_app_data=dumped_data,
        )
        base_state["relations"].append(dns_record_relation)
    base_state["leader"] = True
    state = ops.testing.State(**base_state)
    dns_record_relation_changed_event = _Event(
        "dns_record_relation_changed", relation=dns_record_relation
    )
    out = context.run(dns_record_relation_changed_event, state)
    # in_uuids = {str(x["uuid"]) for x in dumped_model["dns_entries"]}
    for relation in out.relations:
        if relation.endpoint == "dns-record" and relation.local_app_data:
            logger.debug("relation data: '%s'", relation.local_app_data)
            requests_data = json.loads(relation.local_app_data["dns_entries"])
            for request in requests_data:
                assert request["status"] == "conflict"
    assert out.unit_status == ops.testing.BlockedStatus("Conflicting requests")
