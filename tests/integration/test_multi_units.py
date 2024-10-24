#!/usr/bin/env python3
# Copyright 2024 Canonical Ltd.
# See LICENSE file for licensing details.

"""Integration tests for multiple units."""

import logging

import juju.application
import pytest
from pytest_operator.plugin import Model, OpsTest

import models
import tests.integration.helpers

logger = logging.getLogger(__name__)


@pytest.mark.asyncio
@pytest.mark.abort_on_fail
async def test_multi_units(
    app: juju.application.Application,
    ops_test: OpsTest,
    model: Model,
):
    """
    arrange: given deployed bind-operator
    act: change the number of units
    assert: there always is an active unit
    """
    # Remove previously deployed instances of any-app
    for any_app_number in range(10):
        anyapp_name = f"anyapp-t{any_app_number}"
        if anyapp_name in model.applications:
            await model.remove_application(anyapp_name, block_until_done=True)

    # Start by deploying the any-app instance with the domain to check
    await tests.integration.helpers.generate_anycharm_relation(
        app,
        ops_test,
        "anyapp-t1",
        [
            models.DnsEntry(
                domain="dns.test",
                host_label="admin",
                ttl=5,
                record_class="IN",
                record_type="A",
                record_data="42.42.42.42",
            ),
        ],
        None,
    )
    await model.wait_for_idle()

    # Start by testing that everything is fine
    assert await tests.integration.helpers.check_if_active_unit_exists(app, ops_test)
    for unit in app.units:
        await tests.integration.helpers.force_reload_bind(ops_test, unit)
        await model.wait_for_idle()
        assert (
            await tests.integration.helpers.dig_query(
                ops_test,
                unit,
                "@127.0.0.1 admin.dns.test A +short",
                retry=True,
                wait=5,
            )
            == "42.42.42.42"
        ), "Initial test failed"

    # add a unit and verify that everything goes well
    assert ops_test.model is not None
    add_unit_cmd = f"add-unit {app.name} --model={ops_test.model.info.name}"
    await ops_test.juju(*(add_unit_cmd.split(" ")))
    await model.wait_for_idle()
    assert await tests.integration.helpers.check_if_active_unit_exists(app, ops_test)
    for unit in app.units:
        await tests.integration.helpers.force_reload_bind(ops_test, unit)
        await model.wait_for_idle()
        assert (
            await tests.integration.helpers.dig_query(
                ops_test,
                unit,
                "@127.0.0.1 admin.dns.test A +short",
                retry=True,
                wait=5,
            )
            == "42.42.42.42"
        ), "Failed after adding one unit"

    # Change the domain requested by any-app
    anyapp_name = "anyapp-t1"
    anyapp = model.applications[anyapp_name]
    await tests.integration.helpers.change_anycharm_relation(
        ops_test,
        anyapp.units[0],
        [
            models.DnsEntry(
                domain="dns.test",
                host_label="admin",
                ttl=5,
                record_class="IN",
                record_type="A",
                record_data="43.43.43.43",
            ),
        ],
    )
    await model.wait_for_idle()
    for unit in app.units:
        await tests.integration.helpers.force_reload_bind(ops_test, unit)
        await model.wait_for_idle()
        assert (
            await tests.integration.helpers.dig_query(
                ops_test,
                unit,
                "@127.0.0.1 admin.dns.test A +short",
                retry=True,
                wait=5,
            )
            == "43.43.43.43"
        ), "Failed after changing DNS request"

    # remove the active unit and check that we're still all right
    active_unit = await tests.integration.helpers.get_active_unit(app, ops_test)
    assert active_unit is not None
    remove_unit_cmd = (
        f"remove-unit {active_unit.name} --model={ops_test.model.info.name} --no-prompt"
    )
    await ops_test.juju(*(remove_unit_cmd.split(" ")))
    await model.wait_for_idle()
    assert await tests.integration.helpers.check_if_active_unit_exists(app, ops_test)
    for unit in app.units:
        await tests.integration.helpers.force_reload_bind(ops_test, unit)
        await model.wait_for_idle()
        assert (
            await tests.integration.helpers.dig_query(
                ops_test,
                unit,
                "@127.0.0.1 admin.dns.test A +short",
                retry=True,
                wait=5,
            )
            == "43.43.43.43"
        ), "Failed after removing one bind unit"
