#!/usr/bin/env python3

# Copyright 2025 Canonical Ltd.
# See LICENSE file for licensing details.

"""DNS policy charm."""

import json
import logging
import typing

import ops
from charms.bind.v0 import dns_record
from charms.data_platform_libs.v0.data_interfaces import (
    DatabaseCreatedEvent,
    DatabaseEndpointsChangedEvent,
)

import constants
import database
import dns_policy
import models
import timer

# Log messages can be retrieved using juju debug-log
logger = logging.getLogger(__name__)


class ReconcileEvent(ops.charm.EventBase):
    """Event representing a periodic reload of the charmed-bind service."""


class DnsPolicyCharm(ops.CharmBase):
    """Charm the service."""

    def __init__(self, *args: typing.Any):
        """Construct.

        Args:
            args: Arguments passed to the CharmBase parent constructor.
        """
        super().__init__(*args)

        self.on.define_event("reconcile", ReconcileEvent)
        self.dns_policy = dns_policy.DnsPolicyService()
        self._timer = timer.TimerService()
        self._database = database.DatabaseHandler(self, constants.DATABASE_RELATION_NAME)
        self.dns_record_provider = dns_record.DNSRecordProvides(self, "dns-record-provider")
        self.dns_record_requirer = dns_record.DNSRecordRequires(self, "dns-record-requirer")
        self.framework.observe(self.on.config_changed, self._on_config_changed)
        self.framework.observe(self.on.start, self._on_start)
        self.framework.observe(self.on.install, self._on_install)
        self.framework.observe(self.on.collect_unit_status, self._on_collect_status)
        self.framework.observe(
            self._database.database.on.database_created, self._on_database_created
        )
        self.framework.observe(
            self._database.database.on.endpoints_changed, self._on_database_endpoints_changed
        )
        self.framework.observe(self.on.create_reviewer_action, self._on_create_reviewer_action)
        self.framework.observe(self.on.reconcile, self._on_reconcile)
        self.unit.open_port("tcp", 8080)  # dns-policy-app

    def _on_collect_status(self, _: ops.CollectStatusEvent) -> None:
        """Handle collect status event."""
        if not self.dns_policy.status():
            self.unit.status = ops.MaintenanceStatus("Workload not yet ready.")
            return

        if not self._database.is_relation_ready():
            self.unit.status = ops.WaitingStatus("Waiting for a database integration.")
            return

        self.unit.status = ops.ActiveStatus()

    def _on_reconcile(self, _: ReconcileEvent) -> None:
        if not self.model.unit.is_leader():
            return
        relation_data = self.dns_record_provider.get_remote_relation_data()
        if relation_data is None:
            logger.debug("Reconciliation: no provider relation data found")
            return
        entries: list[models.DnsEntry] = []
        for record_requirer_data, _ in relation_data:
            for entry in record_requirer_data.dns_entries:
                entries.append(entry)
        if not entries:
            logger.debug("Reconciliation: no entry found in provider data")
            return

        token = self.dns_policy.get_api_root_token()
        self.dns_policy.send_requests(token, entries)

        approved_requests = self.dns_policy.get_approved_requests(token)
        dns_record_requirer_data = dns_record.DNSRecordRequirerData(dns_entries=approved_requests)
        for relation in self.model.relations[self.dns_record_requirer.relation_name]:
            self.dns_record_requirer.update_relation_data(relation, dns_record_requirer_data)

    def dns_record_relations_data_to_entries(
        self,
        relation_data: list[
            tuple[dns_record.DNSRecordRequirerData, dns_record.DNSRecordProviderData]
        ],
    ) -> list[models.DnsEntry]:
        """Convert DNSRecordRequirerData to a list of DnsEntry.

        Args:
            relation_data: input relation data
        Returns:
            A list of DnsEntry
        """
        entries: list[models.DnsEntry] = []
        for record_requirer_data, _ in relation_data:
            for entry in record_requirer_data.dns_entries:
                entries.append(models.create_dns_entry_from_requirer_entry(entry))
        return entries

    def _on_config_changed(self, _: ops.ConfigChangedEvent) -> None:
        """Handle changed configuration."""
        self.unit.status = ops.MaintenanceStatus("Configuring workload")
        self.dns_policy.configure(
            {
                "debug": "true" if self.config["debug"] else "false",
                "allowed-hosts": json.dumps(
                    [e.strip() for e in str(self.config["allowed-hosts"]).split(",")]
                ),
            }
        )

    def _on_start(self, _: ops.StartEvent) -> None:
        """Handle start event."""

    def _on_install(self, _: ops.InstallEvent) -> None:
        """Handle install event."""
        self.unit.status = ops.MaintenanceStatus("Preparing dns-policy-app")
        self.dns_policy.setup(self.unit.name)
        self._timer.start(self.unit.name, "reconcile", "30s", "1m")

    def _on_database_created(self, _: DatabaseCreatedEvent) -> None:
        """Handle database created.

        Args:
            event: Event triggering the database created handler.
        """
        database_relation_data = self._database.get_relation_data()
        self.unit.status = ops.MaintenanceStatus("Preparing database")
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
        self.dns_policy.command("migrate")

    def _on_database_endpoints_changed(self, _: DatabaseEndpointsChangedEvent) -> None:
        """Handle endpoints change.

        Args:
            event: Event triggering the endpoints changed handler.
        """
        database_relation_data = self._database.get_relation_data()
        self.unit.status = ops.MaintenanceStatus("Preparing database")
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
        self.dns_policy.command("migrate")

    def _on_create_reviewer_action(self, event: ops.charm.ActionEvent) -> None:
        """Handle the create reviewer ActionEvent.

        Args:
            event: Event triggering this action handler.
        """
        try:
            event.set_results(
                {
                    "result": self.dns_policy.command(
                        (
                            f"create_reviewer {event.params['username']} "
                            f"{event.params['email']} --generate_password"
                        ),
                    )
                }
            )
        except dns_policy.CommandError as e:
            logger.error(f"Create reviewer failed: {e}")
            event.fail(f"Create reviewer failed: {e}")


if __name__ == "__main__":  # pragma: nocover
    ops.main(DnsPolicyCharm)
