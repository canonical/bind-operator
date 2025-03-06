# Copyright 2025 Canonical Ltd.
# See LICENSE file for licensing details.

"""Integration tests fixtures."""

import asyncio
from pathlib import Path

import pytest_asyncio
import yaml
from pytest import Config, fixture
from pytest_operator.plugin import Model, OpsTest


@fixture(scope="module", name="dns_policy_metadata")
def dns_policy_metadata_fixture():
    """Provide charm metadata."""
    yield yaml.safe_load(Path("./charmcraft.yaml").read_text(encoding="UTF-8"))


@fixture(scope="module", name="dns_policy_name")
def fixture_dns_policy_name(dns_policy_metadata):
    """Provide charm name from the metadata."""
    yield dns_policy_metadata["name"]


@fixture(scope="module", name="bind_metadata")
def bind_metadata_fixture():
    """Provide charm metadata."""
    yield yaml.safe_load(Path("../bind-operator/metadata.yaml").read_text(encoding="UTF-8"))


@fixture(scope="module", name="bind_name")
def fixture_bind_name(bind_metadata):
    """Provide charm name from the metadata."""
    yield bind_metadata["name"]


@fixture(scope="module", name="model")
def model_fixture(ops_test: OpsTest) -> Model:
    """Juju model API client."""
    assert ops_test.model
    return ops_test.model


@pytest_asyncio.fixture(scope="module", name="dns_policy")
async def dns_policy_fixture(
    ops_test: OpsTest,
    dns_policy_name: str,
    pytestconfig: Config,
    model: Model,
):
    """Build the charm and deploys it."""
    use_existing = pytestconfig.getoption("--use-existing", default=False)
    if use_existing:
        yield model.applications[dns_policy_name]
        return

    resources: dict = {}

    if charm := pytestconfig.getoption("--dns-policy-charm-file"):
        application = await model.deploy(
            f"./{charm}",
            application_name=dns_policy_name,
            resources=resources,
            num_units=0,  # subordinate charm
        )
    else:
        charm = await ops_test.build_charm(".")
        application = await model.deploy(
            charm, application_name=dns_policy_name, resources=resources
        )

    yield application


@pytest_asyncio.fixture(scope="module", name="postgresql")
async def postgresql_fixture(
    ops_test: OpsTest,
    model: Model,
):
    """Deploy the postgresql charm."""
    postgres_app = await model.deploy(
        "postgresql",
        channel="14/stable",
        config={"profile": "testing"},
    )
    async with ops_test.fast_forward():
        await model.wait_for_idle(apps=[postgres_app.name], status="active")

    yield postgres_app


@pytest_asyncio.fixture(scope="module", name="bind")
async def bind_fixture(
    ops_test: OpsTest,
    bind_name: str,
    pytestconfig: Config,
    model: Model,
):
    """Build the charm and deploys it."""
    use_existing = pytestconfig.getoption("--use-existing", default=False)
    if use_existing:
        yield model.applications[bind_name]
        return

    resources: dict = {}

    if charm := pytestconfig.getoption("--bind-charm-file"):
        application = await model.deploy(
            f"../bind-operator/{charm}", application_name=bind_name, resources=resources
        )
    else:
        charm = await ops_test.build_charm("../bind-operator/")
        application = await model.deploy(charm, application_name=bind_name, resources=resources)

    await model.wait_for_idle(apps=[application.name], status="active")

    yield application


@pytest_asyncio.fixture(scope="module", name="full_deployment")
async def full_deployment_fixture(
    model: Model,
    bind,
    dns_policy,
    postgresql,
):
    """Add necessary integration for the deployed charms."""
    await asyncio.gather(
        model.add_relation(dns_policy.name, postgresql.name),
        model.add_relation(dns_policy.name, bind.name),
    )

    await model.wait_for_idle(apps=[dns_policy.name], status="active")

    yield {
        bind.name: bind,
        dns_policy.name: dns_policy,
        postgresql.name: postgresql,
    }
