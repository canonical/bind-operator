#!/usr/bin/env python3
# Copyright 2025 Niels
# See LICENSE file for licensing details.
#
# Learn more at: https://juju.is/docs/sdk

"""Charm the service.

Refer to the following tutorial that will help you
develop a new k8s charm using the Operator Framework:

https://juju.is/docs/sdk/create-a-minimal-kubernetes-charm
"""

import logging
import json
import typing

import ops
import constants
from dns_policy import DnsPolicyService
from database import DatabaseHandler
from charms.data_platform_libs.v0.data_interfaces import (
    DatabaseCreatedEvent,
    DatabaseEndpointsChangedEvent,
)

# Log messages can be retrieved using juju debug-log
logger = logging.getLogger(__name__)

VALID_LOG_LEVELS = ["info", "debug", "warning", "error", "critical"]


class DnsPolicyOperatorCharm(ops.CharmBase):
    """Charm the service."""

    def __init__(self, *args: typing.Any):
        """Construct.

        Args:
            args: Arguments passed to the CharmBase parent constructor.
        """
        super().__init__(*args)

        self.dns_policy = DnsPolicyService()
        self._database = DatabaseHandler(self, constants.DATABASE_RELATION_NAME)
        self.framework.observe(self.on.config_changed, self._on_config_changed)
        self.framework.observe(self.on.start, self._on_start)
        self.framework.observe(self.on.install, self._on_install)
        self.framework.observe(
            self._database.database.on.database_created, self._on_database_created
        )
        self.framework.observe(
            self._database.database.on.endpoints_changed, self._on_database_endpoints_changed
        )
        self.framework.observe(
            self.on[constants.DATABASE_RELATION_NAME].relation_broken,
            self._on_database_relation_broken,
        )
        self.framework.observe(
            self.on.create_reviewer_action, self._on_create_reviewer_action
        )
        self.unit.open_port("tcp", 8080)  # dns-policy-app

    def _on_config_changed(self, event: ops.ConfigChangedEvent):
        """Handle changed configuration.

        Change this example to suit your needs. If you don't need to handle config, you can remove
        this method.

        Learn more about config at https://juju.is/docs/sdk/config
        """
        # Fetch the new config value
        log_level = typing.cast(str, self.model.config["log-level"]).lower()

        # Do some validation of the configuration option
        if log_level not in VALID_LOG_LEVELS:
            # In this case, the config option is bad, so block the charm and notify the operator.
            self.unit.status = ops.BlockedStatus(f"invalid log level: '{log_level}'")

        self.unit.status = ops.MaintenanceStatus("Configuring workload")
        self.dns_policy.configure(
            {
                "debug": "true" if self.config["debug"] else "false",
                "allowed-hosts": json.dumps(
                    [e.strip() for e in str(self.config["allowed-hosts"]).split(",")]
                ),
            }
        )
        self.unit.status = ops.ActiveStatus("")

    def _on_start(self, event: ops.StartEvent):
        """Handle start event."""
        self.unit.status = ops.ActiveStatus("")

    def _on_install(self, event: ops.InstallEvent):
        """Handle install event."""
        self.unit.status = ops.MaintenanceStatus("Preparing dns-policy-app")
        self.dns_policy.setup(self.unit.name)
        self.unit.status = ops.ActiveStatus("")

    def _on_database_created(self, _: DatabaseCreatedEvent) -> None:
        """Handle database created.

        Args:
            event: Event triggering the database created handler.
        """
        database_relation_data = self._database.get_relation_data()
        logger.info("%s", 
            {
                "debug": "true" if self.config["debug"] else "false",
                "allowed-hosts": json.dumps(
                    [e.strip() for e in str(self.config["allowed-hosts"]).split(",")]
                ),
                "database-port": database_relation_data["POSTGRES_PORT"],
                "database-host": database_relation_data["POSTGRES_HOST"],
                "database-name": database_relation_data["POSTGRES_DB"],
                "database-password": database_relation_data["POSTGRES_PASSWORD"],
                "database-user": database_relation_data["POSTGRES_USER"],
            }
        )
        self.dns_policy.configure(
            {
                "debug": "true" if self.config["debug"] else "false",
                "allowed-hosts": json.dumps(
                    [e.strip() for e in str(self.config["allowed-hosts"]).split(",")]
                ),
                "database-port": database_relation_data["POSTGRES_PORT"],
                "database-host": database_relation_data["POSTGRES_HOST"],
                "database-name": database_relation_data["POSTGRES_DB"],
                "database-password": database_relation_data["POSTGRES_PASSWORD"],
                "database-user": database_relation_data["POSTGRES_USER"],
            }
        )
        self.dns_policy.command("migrate", env=None)

    def _on_database_endpoints_changed(self, _: DatabaseEndpointsChangedEvent) -> None:
        """Handle endpoints change.

        Args:
            event: Event triggering the endpoints changed handler.
        """
        database_relation_data = self._database.get_relation_data()
        self.dns_policy.configure(
            {
                "debug": "true" if self.config["debug"] else "false",
                "allowed-hosts": json.dumps(
                    [e.strip() for e in str(self.config["allowed-hosts"]).split(",")]
                ),
                "database-port": database_relation_data["POSTGRES_PORT"],
                "database-host": database_relation_data["POSTGRES_HOST"],
                "database-name": database_relation_data["POSTGRES_DB"],
                "database-password": database_relation_data["POSTGRES_PASSWORD"],
                "database-user": database_relation_data["POSTGRES_USER"],
            }
        )
        self.dns_policy.command("migrate", env=None)

    def _on_database_relation_broken(self, _: ops.RelationBrokenEvent) -> None:
        """Handle broken relation.

        Args:
            event: Event triggering the broken relation handler.
        """
        self.unit.status = ops.WaitingStatus("Waiting for database relation")
        # self._stop_service()

    def _on_create_reviewer_action(self, event: ops.charm.ActionEvent) -> None:
        """Handle the create reviewer ActionEvent.

        Args:
            event: Event triggering this action handler.
        """
        event.set_results(
            {
                "result": self.dns_policy.command(
                    f"create_reviewer {event.params['username']} {event.params['email']} --generate_password",
                    env={},
                )
            }
        )


if __name__ == "__main__":  # pragma: nocover
    ops.main(DnsPolicyOperatorCharm)
