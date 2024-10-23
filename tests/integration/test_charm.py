#!/usr/bin/env python3
# Copyright 2024 Canonical Ltd.
# See LICENSE file for licensing details.

"""Integration tests."""

import logging
import time

import juju
import ops
import pytest
import requests
from juju.action import Action
from pytest_operator.plugin import Model, OpsTest

import constants
import models
import tests.integration.helpers

logger = logging.getLogger(__name__)


@pytest.mark.asyncio
@pytest.mark.abort_on_fail
async def test_admin_reachable(app: juju.application.Application, ops_test: OpsTest):
    """
    arrange: build and deploy the charm.
    act: nothing.
    assert: that the admin of the API is reachable.
    """
    unit = app.units[0]

    # Mypy has difficulty with ActiveStatus
    assert unit.workload_status == ops.model.ActiveStatus.name

    await app.set_config({"django_allowed_hosts": ""})
    time.sleep(10)

    # Test that the admin is not reachable
    for _, unit_ip in enumerate(await tests.integration.helpers.get_unit_ips(ops_test, unit)):
        url = f"http://{unit_ip}:8080/admin/"
        try:
            response = requests.head(url, timeout=5)
            response.raise_for_status()
            assert False, f"Asset unexpectedly accessible at {url} after config change"
            # Consider using assert False here instead of logger.error
        except requests.exceptions.HTTPError:
            logger.info("Asset inaccessible at %s as expected after config change", url)
        except requests.RequestException as e:
            logger.error("Unexpected error after config change: %s", e)

    await app.set_config({"django_allowed_hosts": "*"})
    time.sleep(10)

    # Test that the admin is reachable
    for _, unit_ip in enumerate(await tests.integration.helpers.get_unit_ips(ops_test, unit)):
        url = f"http://{unit_ip}:8080/admin/"
        response = requests.head(url, timeout=5)
        response.raise_for_status()
        logger.info("File found at %s", url)


@pytest.mark.asyncio
@pytest.mark.abort_on_fail
async def test_acl_actions(app: juju.application.Application):
    """
    arrange: build and deploy the charm.
    act: nothing.
    assert: that the acl actions do the right thing.
    """
    unit = app.units[0]

    assert unit.workload_status == ops.model.ActiveStatus.name

    zone = "test-zone"

    action_create_acl: Action = await unit.run_action(
        "create-acl",
        **{"service-account": "test-service-account", "zone": zone},
    )
    await action_create_acl.wait()
    assert action_create_acl.status == "completed"
    assert "ACL created successfully" in action_create_acl.results["result"]

    action_check_acl: Action = await unit.run_action(
        "check-acl",
        **{"service-account": "test-service-account", "zone": zone},
    )
    await action_check_acl.wait()
    assert action_check_acl.status == "completed"
    assert "ACL exists" in action_check_acl.results["result"]

    action_list_acl: Action = await unit.run_action(
        "list-acl",
    )
    await action_list_acl.wait()
    assert action_list_acl.status == "completed"
    assert f"test-service-account - {zone}" in action_list_acl.results["result"]

    action_delete_acl: Action = await unit.run_action(
        "delete-acl",
        **{"service-account": "test-service-account", "zone": zone},
    )
    await action_delete_acl.wait()
    assert action_delete_acl.status == "completed"
    assert "ACL deleted successfully" in action_delete_acl.results["result"]

    action_check_acl = await unit.run_action(
        "check-acl",
        **{"service-account": "test-service-account", "zone": zone},
    )
    await action_check_acl.wait()
    assert action_check_acl.status == "completed"
    assert "ACL does not exist" in action_check_acl.results["result"]


@pytest.mark.asyncio
@pytest.mark.abort_on_fail
async def test_lifecycle(app: juju.application.Application, ops_test: OpsTest):
    """
    arrange: build and deploy the charm.
    act: nothing.
    assert: that the charm ends up in an active state.
    """
    unit = app.units[0]

    assert unit.workload_status == ops.model.ActiveStatus.name

    status = await tests.integration.helpers.dig_query(
        ops_test,
        unit,
        f"@127.0.0.1 status.{constants.ZONE_SERVICE_NAME} TXT +short",
        retry=True,
        wait=5,
    )
    assert status == '"ok"'

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
async def test_basic_dns_config(app: juju.application.Application, ops_test: OpsTest):
    """
    arrange: build, deploy the charm and change its configuration.
    act: request the test domain.
    assert: the output of the dig command is the expected one
    """
    unit = app.units[0]

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
        ops_test=ops_test,
        unit=unit,
        source=test_zone_def,
        destination=f"{constants.DNS_CONFIG_DIR}/named.conf.local",
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
        ops_test=ops_test,
        unit=unit,
        source=test_zone,
        destination=f"{constants.DNS_CONFIG_DIR}/db.dns.test",
    )

    restart_cmd = f"sudo snap restart --reload {constants.DNS_SNAP_NAME}"
    await tests.integration.helpers.run_on_unit(ops_test, unit.name, restart_cmd)

    assert (
        await tests.integration.helpers.run_on_unit(
            ops_test, unit.name, "dig @127.0.0.1 dns.test TXT +short"
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
    app: juju.application.Application,
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
            None,
        )
        any_app_number += 1

    await model.wait_for_idle()

    await tests.integration.helpers.force_reload_bind(ops_test, app.units[0])
    await model.wait_for_idle()

    # Test the status of the bind-operator instance
    assert app.units[0].workload_status == status.name

    # Test if the records give the correct results
    # Do that only if we have an active status
    if status == ops.model.ActiveStatus:
        for integration_data in integration_datasets:
            for entry in integration_data:

                result = await tests.integration.helpers.dig_query(
                    ops_test,
                    app.units[0],
                    f"@127.0.0.1 {entry.host_label}.{entry.domain} {entry.record_type} +short",
                    retry=True,
                    wait=5,
                )
                assert result == str(entry.record_data), (
                    f"{entry.host_label}.{entry.domain}"
                    f" {entry.record_type} {entry.record_data}"
                )
