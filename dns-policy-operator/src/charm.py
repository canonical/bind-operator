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

import json
import logging
import pathlib
import time
import typing

import ops
from charms.bind.v0 import dns_record
from charms.data_platform_libs.v0.data_interfaces import (
    DatabaseCreatedEvent,
    DatabaseEndpointsChangedEvent,
)
from charms.operator_libs_linux.v1 import systemd

import constants
import models
import templates
from database import DatabaseHandler
from dns_policy import DnsPolicyService

# Log messages can be retrieved using juju debug-log
logger = logging.getLogger(__name__)

VALID_LOG_LEVELS = ["info", "debug", "warning", "error", "critical"]


class ReconciliateEvent(ops.charm.EventBase):
    """Event representing a periodic reload of the charmed-bind service."""


class DnsPolicyOperatorCharm(ops.CharmBase):
    """Charm the service."""

    def __init__(self, *args: typing.Any):
        """Construct.

        Args:
            args: Arguments passed to the CharmBase parent constructor.
        """
        super().__init__(*args)

        self.on.define_event("reconciliate", ReconciliateEvent)
        logger.debug("unit name: %s", self.unit.name)

        self.dns_policy = DnsPolicyService()
        self._database = DatabaseHandler(self, constants.DATABASE_RELATION_NAME)
        self.dns_record_provider = dns_record.DNSRecordProvides(self, "dns-record-provider")
        self.dns_record_requirer = dns_record.DNSRecordRequires(self, "dns-record-requirer")
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
        self.framework.observe(self.on.create_reviewer_action, self._on_create_reviewer_action)
        self.framework.observe(
            self.dns_record_provider.on.dns_record_request_received,
            self._on_dns_record_request_received,
        )
        self.framework.observe(self.on.reconciliate, self._on_reconciliate)
        self.unit.open_port("tcp", 8080)  # dns-policy-app

    def _on_reconciliate(self, _: ReconciliateEvent) -> None:
        relation_data = self._get_remote_relation_data()
        if relation_data is None:
            return
        dns_policy_config = self.dns_policy.get_config()
        entries: list[models.DnsEntry] = []
        for record_requirer_data, _ in relation_data:
            for entry in record_requirer_data.dns_entries:
                entries.append(entry)
        # logger.debug("Entries: %s", entries)
        if not entries:
            return
        logger.debug("Config: %s", dns_policy_config)
        token = self.dns_policy.get_api_root_token()
        self.dns_policy.send_requests(token, entries)

        if not self.model.unit.is_leader():
            return

        approved_requests = self.dns_policy.get_approved_requests(token)
        dns_record_requirer_data = dns_record.DNSRecordRequirerData(dns_entries=approved_requests)
        for relation in self.model.relations[self.dns_record_requirer.relation_name]:
            logger.debug("dnsrecordrequirerdata: %s", dns_record_requirer_data)
            self.dns_record_requirer.update_relation_data(relation, dns_record_requirer_data)

    def _on_dns_record_request_received(self, event: dns_record.DNSRecordRequestReceived) -> None:
        """Handle dns record request received."""
        # relation_data = self._get_remote_relation_data()
        # if relation_data is None:
        #     return
        # dns_policy_config = self.dns_policy.get_config()
        # entries = self.dns_record_relations_data_to_entries(relation_data)
        # logger.debug("Entries: %s", entries)
        # if not entries:
        #     return
        # logger.debug("Config: %s", dns_policy_config)
        # token = self.dns_policy.get_api_root_token()
        # for entry in entries:
        #     self.dns_policy.create_record_request(token, entry)

    def _start_timer(self, event_name: str, timeout: str, interval: str) -> None:
        """Install a timer.

        Syntax of time spans: https://www.freedesktop.org/software/systemd/man/latest/systemd.time.html

        Args:
            event_name: The event to be fired
            timeout: timeout before killing the command
            interval: interval between each execution
        """
        # TODO: make idempotent
        (
            pathlib.Path(constants.SYSTEMD_SERVICES_PATH) / f"dispatch-{event_name}.service"
        ).write_text(
            templates.DISPATCH_EVENT_SERVICE.format(
                event=event_name,
                timeout="10s",
                unit=self.unit.name,
            ),
            encoding="utf-8",
        )
        (
            pathlib.Path(constants.SYSTEMD_SERVICES_PATH) / f"dispatch-{event_name}.timer"
        ).write_text(
            templates.SYSTEMD_SERVICE_TIMER.format(interval="1", service=f"dispatch-{event_name}"),
            encoding="utf-8",
        )
        systemd.service_enable(f"dispatch-{event_name}.timer")
        systemd.service_start(f"dispatch-{event_name}.timer")

    def _stop_timer(self, event_name: str) -> None:
        """Stop a timer.

        Args:
            event_name: The event to be fired
        """
        # TODO: make idempotent
        systemd.service_disable(f"dispatch-{event_name}.timer")
        systemd.service_stop(f"dispatch-{event_name}.timer")

    def dns_record_relations_data_to_zones(
        self,
        relation_data: list[
            tuple[dns_record.DNSRecordRequirerData, dns_record.DNSRecordProviderData]
        ],
    ) -> list[models.Zone]:
        """Return zones from all the dns_record relations data.

        Args:
            relation_data: input relation data

        Returns:
            The zones from the record_requirer_data
        """
        zones: dict[str, models.Zone] = {}
        for record_requirer_data, _ in relation_data:
            for new_zone in self.record_requirer_data_to_zones(record_requirer_data):
                if new_zone.domain in zones:
                    zones[new_zone.domain].entries.update(new_zone.entries)
                else:
                    zones[new_zone.domain] = new_zone
        return list(zones.values())

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

    def record_requirer_data_to_zones(
        self,
        record_requirer_data: dns_record.DNSRecordRequirerData,
    ) -> list[models.Zone]:
        """Convert DNSRecordRequirerData to zone files.

        Args:
            record_requirer_data: The input DNSRecordRequirerData

        Returns:
            A list of zones
        """
        zones_entries: dict[str, list[models.RequirerEntry]] = {}
        for entry in record_requirer_data.dns_entries:
            if entry.domain not in zones_entries:
                zones_entries[entry.domain] = []
            zones_entries[entry.domain].append(entry)

        zones: list[models.Zone] = []
        for domain, entries in zones_entries.items():
            zone = models.Zone(domain=domain, entries=set())
            for entry in entries:
                zone.entries.add(models.create_dns_entry_from_requirer_entry(entry))
            zones.append(zone)
        return zones

    def _get_remote_relation_data(self) -> dns_record.DNSRecordProviderData | None:
        """Get the dns_record remote relation data.

        This function is used to get performance statistics on the remote relation data retrieval.

        Returns:
            the dns_record remote relation data
        """
        start_time = time.time_ns()
        relation_data = self.dns_record_provider.get_remote_relation_data()
        logger.debug(
            "Relation data retrieval duration (ms): %s", (time.time_ns() - start_time) / 1e6
        )
        return relation_data

    def _on_config_changed(self, event: ops.ConfigChangedEvent) -> None:
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

    def _on_start(self, event: ops.StartEvent) -> None:
        """Handle start event."""
        self.unit.status = ops.ActiveStatus("")

    def _on_install(self, event: ops.InstallEvent) -> None:
        """Handle install event."""
        self.unit.status = ops.MaintenanceStatus("Preparing dns-policy-app")
        self.dns_policy.setup(self.unit.name)
        self.unit.status = ops.ActiveStatus("")
        self._start_timer("reconciliate", "60s", "1m")

    def _on_database_created(self, _: DatabaseCreatedEvent) -> None:
        """Handle database created.

        Args:
            event: Event triggering the database created handler.
        """
        database_relation_data = self._database.get_relation_data()
        logger.info(
            "%s",
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
            },
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
        self.dns_policy.command("migrate")

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
        self.dns_policy.command("migrate")

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
                )
            }
        )


if __name__ == "__main__":  # pragma: nocover
    ops.main(DnsPolicyOperatorCharm)
