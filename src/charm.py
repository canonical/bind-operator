#!/usr/bin/env python3
# Copyright 2024 Canonical Ltd.
# See LICENSE file for licensing details.

"""Charm for bind."""

import logging
import typing

import ops
from charms.bind.v0.dns_record import DNSRecordProvides

import events
from bind import BindService

logger = logging.getLogger(__name__)


class BindCharm(ops.CharmBase):
    """Charm the service."""

    def __init__(self, *args: typing.Any):
        """Construct.

        Args:
            args: Arguments passed to the CharmBase parent constructor.
        """
        super().__init__(*args)
        self.bind = BindService()
        self.dns_record = DNSRecordProvides(self)

        self.on.define_event("reload_bind", events.ReloadBindEvent)

        self.framework.observe(self.on.config_changed, self._on_config_changed)
        self.framework.observe(self.on.install, self._on_install)
        self.framework.observe(self.on.start, self._on_start)
        self.framework.observe(self.on.stop, self._on_stop)
        self.framework.observe(self.on.upgrade_charm, self._on_upgrade_charm)
        self.framework.observe(
            self.on.dns_record_relation_changed, self._on_dns_record_relation_changed
        )
        self.framework.observe(self.on.collect_unit_status, self._on_collect_status)
        self.framework.observe(self.on.reload_bind, self._on_reload_bind)

    def _on_reload_bind(self, _: events.ReloadBindEvent) -> None:
        """Handle periodic reload bind event."""
        logger.info("PERIODIC RELOAD")

    def _on_dns_record_relation_changed(self, event: ops.RelationChangedEvent) -> None:
        """Handle dns_record relation changed.

        Args:
            event: Event triggering the relation changed handler.

        """
        try:
            relation_requirer_data = self.dns_record.get_remote_relation_data()
        except ValueError as err:
            logger.info("Validation error of the relation data: %s", err)
            return
        self.unit.status = ops.MaintenanceStatus("Handling new relation requests")
        relation_provider_data = self.bind.handle_relation_data(relation_requirer_data)
        relation = self.model.get_relation(self.dns_record.relation_name, event.relation.id)
        self.dns_record.update_relation_data(relation, relation_provider_data)

    def _on_collect_status(self, event: ops.CollectStatusEvent) -> None:
        """Handle collect status event.

        Args:
            event: Event triggering the collect-status hook
        """
        try:
            relation_requirer_data = self.dns_record.get_remote_relation_data()
        except ValueError as err:
            logger.info("Validation error of the relation data: %s", err)
            event.add_status(ops.BlockedStatus(f"Validation error of the relation data: {err}"))
            return
        self.bind.collect_status(event, relation_requirer_data)

    def _on_config_changed(self, _: ops.ConfigChangedEvent) -> None:
        """Handle changed configuration event."""

    def _on_install(self, _: ops.InstallEvent) -> None:
        """Handle install."""
        self.unit.status = ops.MaintenanceStatus("Preparing bind")
        self.bind.prepare(self.unit.name)

    def _on_start(self, _: ops.StartEvent) -> None:
        """Handle start."""
        self.bind.start()

    def _on_stop(self, _: ops.StopEvent) -> None:
        """Handle stop."""
        self.bind.stop()

    def _on_upgrade_charm(self, _: ops.UpgradeCharmEvent) -> None:
        """Handle upgrade-charm."""
        self.unit.status = ops.MaintenanceStatus("Upgrading dependencies")
        self.bind.prepare(self.unit.name)


if __name__ == "__main__":  # pragma: nocover
    ops.main.main(BindCharm)
