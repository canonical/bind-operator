#!/usr/bin/env python3
# Copyright 2024 Canonical Ltd.
# See LICENSE file for licensing details.

"""Integration tests."""

import logging
import time

import ops
import pytest
from pytest_operator.plugin import Model, OpsTest

import constants
import models
import tests.integration.helpers

logger = logging.getLogger(__name__)


@pytest.mark.asyncio
@pytest.mark.abort_on_fail
async def test_lifecycle(app: ops.model.Application, ops_test: OpsTest):
    """
    arrange: build and deploy the charm.
    act: nothing.
    assert: that the charm ends up in an active state.
    """
    # Application actually does have units
    unit = app.units[0]  # type: ignore

    # Mypy has difficulty with ActiveStatus
    assert unit.workload_status == ops.model.ActiveStatus.name  # type: ignore

    await tests.integration.helpers.dispatch_to_unit(ops_test, unit, "stop")
    time.sleep(5)
    _, service_status, _ = await ops_test.juju(
        "exec", "--unit", unit.name, "snap services charmed-bind"
    )
    logger.info(service_status)
    assert "inactive" in service_status

    # Wait a bit and retest the status.
    # This is done to make sure that bind-reload doesn't restart the service
    time.sleep(70)
    logger.info(service_status)
    assert "inactive" in service_status

    await tests.integration.helpers.dispatch_to_unit(ops_test, unit, "start")
    time.sleep(5)
    _, service_status, _ = await ops_test.juju(
        "exec", "--unit", unit.name, "snap services charmed-bind"
    )
    logger.info(service_status)
    assert "active" in service_status


@pytest.mark.asyncio
@pytest.mark.abort_on_fail
async def test_basic_dns_config(app: ops.model.Application, ops_test: OpsTest):
    """
    arrange: build, deploy the charm and change its configuration.
    act: request the test domain.
    assert: the output of the dig command is the expected one
    """
    # Application actually does have units
    unit = app.units[0]  # type: ignore

    test_zone_def = f"""zone "dns.test" IN {{
    type primary;
    file "{constants.DNS_CONFIG_DIR}/db.dns.test";
    allow-update {{ none; }};
}};
    """
    # We need to stop the dispatch-reload-bind timer for this test
    stop_timer_cmd = "sudo systemctl stop dispatch-reload-bind.timer"
    await tests.integration.helpers.run_on_unit(ops_test, unit.name, stop_timer_cmd)

    await tests.integration.helpers.push_to_unit(
        ops_test, unit, test_zone_def, f"{constants.DNS_CONFIG_DIR}/named.conf.local"
    )

    test_zone = """$TTL    604800
@       IN      SOA     dns.test. admin.dns.test. (
                              1         ; Serial
                         604800         ; Refresh
                          86400         ; Retry
                        2419200         ; Expire
                         604800 )       ; Negative Cache TTL
;
@       IN      NS      localhost.
@       IN      A       127.0.0.1
@       IN      TXT     "this-is-a-test"
    """
    await tests.integration.helpers.push_to_unit(
        ops_test, unit, test_zone, f"{constants.DNS_CONFIG_DIR}/db.dns.test"
    )

    restart_cmd = f"sudo snap restart --reload {constants.DNS_SNAP_NAME}"
    await tests.integration.helpers.run_on_unit(ops_test, unit.name, restart_cmd)

    assert (
        await tests.integration.helpers.run_on_unit(
            ops_test, f"{app.name}/{0}", "dig @127.0.0.1 dns.test TXT +short"
        )
    ).strip() == '"this-is-a-test"'

    # Restart the timer for the subsequent tests
    start_timer_cmd = "sudo systemctl start dispatch-reload-bind.timer"
    await tests.integration.helpers.run_on_unit(ops_test, unit.name, start_timer_cmd)


@pytest.mark.parametrize(
    "integration_datasets, status",
    (
        (
            (
                [
                    models.DnsEntry(
                        domain="dns.test",
                        host_label="admin",
                        ttl=600,
                        record_class="IN",
                        record_type="A",
                        record_data="42.42.42.42",
                    ),
                    models.DnsEntry(
                        domain="dns.test",
                        host_label="admin2",
                        ttl=600,
                        record_class="IN",
                        record_type="A",
                        record_data="42.42.42.43",
                    ),
                    models.DnsEntry(
                        domain="dns2.test",
                        host_label="admin",
                        ttl=600,
                        record_class="IN",
                        record_type="A",
                        record_data="42.42.44.44",
                    ),
                ],
            ),
            ops.model.ActiveStatus,
        ),
        (
            (
                [
                    models.DnsEntry(
                        domain="dns.test",
                        host_label="admin",
                        ttl=600,
                        record_class="IN",
                        record_type="A",
                        record_data="42.42.42.42",
                    ),
                ],
                [
                    models.DnsEntry(
                        domain="dns-app-2.test",
                        host_label="somehost",
                        ttl=600,
                        record_class="IN",
                        record_type="A",
                        record_data="41.41.41.41",
                    ),
                ],
                [
                    models.DnsEntry(
                        domain="dns-app-3.test",
                        host_label="somehost",
                        ttl=600,
                        record_class="IN",
                        record_type="A",
                        record_data="40.40.40.40",
                    ),
                ],
            ),
            ops.model.ActiveStatus,
        ),
        (
            (
                [
                    models.DnsEntry(
                        domain="dns.test",
                        host_label="admin",
                        ttl=600,
                        record_class="IN",
                        record_type="A",
                        record_data="42.42.42.42",
                    ),
                ],
                [
                    models.DnsEntry(
                        domain="dns.test",
                        host_label="admin",
                        ttl=600,
                        record_class="IN",
                        record_type="A",
                        record_data="41.41.41.41",
                    ),
                ],
            ),
            ops.model.BlockedStatus,
        ),
    ),
)
@pytest.mark.asyncio
@pytest.mark.abort_on_fail
async def test_dns_record_relation(
    app: ops.model.Application,
    ops_test: OpsTest,
    model: Model,
    status: ops.model.StatusBase,
    integration_datasets: tuple[list[models.DnsEntry]],
):
    """
    arrange: given deployed bind-operator
    act: integrate any-charm instances to the deployed app
    assert: bind-operator should have the correct status and respond to dig queries
    """
    # Remove previously deployed instances of any-app
    for any_app_number in range(10):
        anyapp_name = f"anyapp-t{any_app_number}"
        if anyapp_name in model.applications:
            await model.remove_application(anyapp_name, block_until_done=True)
    # Start by deploying the any-app instances and integrate them with the bind charm
    any_app_number = 0
    for integration_data in integration_datasets:
        anyapp_name = f"anyapp-t{any_app_number}"
        await tests.integration.helpers.generate_anycharm_relation(
            app,
            ops_test,
            anyapp_name,
            integration_data,
        )
        any_app_number += 1

    await model.wait_for_idle()

    # wait for the bind-reload event to happen
    restart_cmd = f"sudo snap restart --reload {constants.DNS_SNAP_NAME}"
    # Application actually does have units
    unit = app.units[0]  # type: ignore
    await tests.integration.helpers.run_on_unit(ops_test, unit.name, restart_cmd)
    await model.wait_for_idle()

    # Test the status of the bind-operator instance
    # Application actually does have units
    unit = app.units[0]  # type: ignore
    assert unit.workload_status == status.name

    # Test if the records give the correct results
    # Do that only if we have an active status
    if status == ops.model.ActiveStatus:
        for integration_data in integration_datasets:
            for entry in integration_data:

                result = await tests.integration.helpers.dig_query(ops_test, app.name, entry)
                assert result == str(entry.record_data), (
                    f"{entry.host_label}.{entry.domain}"
                    f" {entry.record_type} {entry.record_data}"
                )
