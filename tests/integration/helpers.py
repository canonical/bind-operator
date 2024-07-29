#!/usr/bin/env python3
# Copyright 2024 Canonical Ltd.
# See LICENSE file for licensing details.

"""Helper functions for the integration tests."""

# Ignore duplicate code from the helpers (they can be in the charm also)
# pylint: disable=duplicate-code

import json
import pathlib
import random
import string
import tempfile
import time

import ops
from pytest_operator.plugin import OpsTest

import constants
import models


class ExecutionError(Exception):
    """Exception raised when execution fails.

    Attributes:
        msg (str): Explanation of the error.
    """

    def __init__(self, msg: str):
        """Initialize a new instance of the ExecutionError exception.

        Args:
            msg (str): Explanation of the error.
        """
        self.msg = msg


def _generate_random_filename(length: int = 24, extension: str = "") -> str:
    """Generate a random filename.

    Args:
        length: length of the generated name
        extension: extension of the generated name

    Returns:
        the generated name
    """
    characters = string.ascii_letters + string.digits
    # Disabling sec checking here since we're not looking
    # to generate something cryptographically secure
    random_string = "".join(random.choice(characters) for _ in range(length))  # nosec
    if extension:
        if "." in extension:
            pieces = extension.split(".")
            last_extension = pieces[-1]
            extension = last_extension
        return f"{random_string}.{extension}"
    return random_string


async def run_on_unit(ops_test: OpsTest, unit_name: str, command: str) -> str:
    """Run a command on a specific unit.

    Args:
        ops_test: The ops test framework instance
        unit_name: The name of the unit to run the command on
        command: The command to run

    Returns:
        the command output if it succeeds, otherwise raises an exception.

    Raises:
        ExecutionError: if the command was not successful
    """
    complete_command = ["exec", "--unit", unit_name, "--", *command.split()]
    return_code, stdout, stderr = await ops_test.juju(*complete_command)
    if return_code != 0:
        raise ExecutionError(f"Command {command} failed with code {return_code}: {stderr}")
    return stdout


# pylint: disable=too-many-arguments
async def push_to_unit(
    ops_test: OpsTest,
    unit: ops.model.Unit,
    source: str,
    destination: str,
    user: str = "root",
    group: str = "root",
    mode: str = "644",
) -> None:
    """Push a source file to the chosen unit

    Args:
        ops_test: The ops test framework instance
        unit: The unit to push the file to
        source: the content of the file
        destination: the path of the file on the unit
        user: the user that owns the file
        group: the group that owns the file
        mode: the mode of the file
    """
    _, temp_path = tempfile.mkstemp()
    with open(temp_path, "w", encoding="utf-8") as fd:
        fd.writelines(source)

    temp_filename_on_workload = _generate_random_filename()
    # unit does have scp_to
    await unit.scp_to(source=temp_path, destination=temp_filename_on_workload)  # type: ignore
    mv_cmd = f"mv /home/ubuntu/{temp_filename_on_workload} {destination}"
    await run_on_unit(ops_test, unit.name, mv_cmd)
    chown_cmd = f"chown {user}:{group} {destination}"
    await run_on_unit(ops_test, unit.name, chown_cmd)
    chmod_cmd = f"chmod {mode} {destination}"
    await run_on_unit(ops_test, unit.name, chmod_cmd)


async def dispatch_to_unit(
    ops_test: OpsTest,
    unit: ops.model.Unit,
    hook_name: str,
):
    """Dispatch a hook to the chosen unit.

    Args:
        ops_test: The ops test framework instance
        unit: The unit to push the file to
        hook_name: the hook name
    """
    await ops_test.juju(
        "exec",
        "--unit",
        unit.name,
        "--",
        f"export JUJU_DISPATCH_PATH=hooks/{hook_name}; ./dispatch",
    )


async def generate_anycharm_relation(
    app: ops.model.Application,
    ops_test: OpsTest,
    any_charm_name: str,
    dns_entries: list[models.DnsEntry],
):
    """Deploy any-charm with a wanted DNS entries config and integrate it to the bind app.

    Args:
        app: Deployed bind-operator app
        ops_test: The ops test framework instance
        any_charm_name: Name of the to be deployed any-charm
        dns_entries: List of DNS entries for any-charm
    """
    any_app_name = any_charm_name
    any_charm_content = pathlib.Path("tests/integration/any_charm.py").read_text(encoding="utf-8")
    dns_record_content = pathlib.Path("lib/charms/bind/v0/dns_record.py").read_text(
        encoding="utf-8"
    )

    any_charm_src_overwrite = {
        "any_charm.py": any_charm_content,
        "dns_record.py": dns_record_content,
        # It's okay to write to /tmp for these tests, so # nosec is used
        "/tmp/dns_entries.json": json.dumps(
            [e.model_dump(mode="json") for e in dns_entries]
        ),  # nosec
    }

    # We deploy https://charmhub.io/any-charm and inject the any_charm.py behavior
    # See https://github.com/canonical/any-charm on how to use any-charm
    assert ops_test.model
    any_charm = await ops_test.model.deploy(
        "any-charm",
        application_name=any_app_name,
        channel="beta",
        config={
            "src-overwrite": json.dumps(any_charm_src_overwrite),
            "python-packages": "pydantic==2.7.1\n",
        },
    )
    await ops_test.model.add_relation(f"{any_charm.name}", f"{app.name}")


async def dig_query(
    ops_test: OpsTest, app: ops.model.Application, cmd: str, retry: bool = False, wait: int = 5
) -> str:
    """Query a DnsEntry with dig.

    Args:
        ops_test: The ops test framework instance
        app: Application to be used to launch the command
        cmd: Dig command to perform
        retry: If the dig request should be retried
        wait: duration in seconds to wait between retries

    Returns: the result of the DNS query
    """
    result: str = ""
    # Application actually does have units
    unit = app.units[0]  # type: ignore
    for _ in range(5):
        result = (await run_on_unit(ops_test, unit.name, f"dig {cmd}")).strip()
        if (result.strip() != "" and "timed out" not in result) or not retry:
            break
        time.sleep(wait)

    return result


async def get_active_unit(app: ops.model.Application, ops_test: OpsTest) -> ops.model.Unit | None:
    """Get the current active unit if it exists

    Args:
        app: Application to search for an active unit
        ops_test: The ops test framework instance

    Returns:
        The current active unit if it exists, None otherwise
    """
    for unit in app.units:  # type: ignore
        data = json.loads((await ops_test.juju("show-unit", unit.name, "--format", "json"))[1])
        relations = data[unit.name]["relation-info"]
        for relation in relations:
            if relation["endpoint"] == "bind-peers":
                peer_relation = relation
                break
        if peer_relation is None:
            continue
        if "active-unit" not in peer_relation["application-data"]:
            continue
        if (
            peer_relation["local-unit"]["data"]["ingress-address"]
            == peer_relation["application-data"]["active-unit"]
        ):
            return unit
    return None


async def check_if_active_unit_exists(app: ops.model.Application, ops_test: OpsTest) -> bool:
    """Check if an active unit exists and is reachable

    Args:
        app: Application to search for an active unit
        ops_test: The ops test framework instance

    Returns:
        The current active unit if it exists, None otherwise
    """
    # Application actually does have units
    unit = app.units[0]  # type: ignore
    data = json.loads((await ops_test.juju("show-unit", unit.name, "--format", "json"))[1])
    relations = data[unit.name]["relation-info"]
    for relation in relations:
        if relation["endpoint"] == "bind-peers":
            peer_relation = relation
            break
    if peer_relation is None:
        return False
    if "active-unit" not in peer_relation["application-data"]:
        return False
    active_unit = peer_relation["application-data"]["active-unit"]
    if not active_unit:
        return False

    status = await dig_query(
        ops_test,
        app,
        f"@{active_unit} status.{constants.ZONE_SERVICE_NAME} TXT +short",
        retry=True,
        wait=5,
    )
    if status != '"ok"':
        return False
    return True
