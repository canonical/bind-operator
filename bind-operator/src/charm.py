#!/usr/bin/env python3
# Copyright 2025 Canonical Ltd.
# See LICENSE file for licensing details.

"""Charm for bind."""

import logging
import pathlib
import subprocess  # nosec
import time
import typing

import ops
from charms.bind.v0 import dns_record

import constants
import dns_data
import events
import exceptions
import models
from bind import BindService

logger = logging.getLogger(__name__)


class PeerRelationUnavailableError(exceptions.BindCharmError):
    """Exception raised when the peer relation is unavailable."""


class PeerRelationNetworkUnavailableError(exceptions.BindCharmError):
    """Exception raised when the peer relation network is unavailable."""


class BindCharm(ops.CharmBase):
    """Charm the service."""

    def __init__(self, *args: typing.Any):
        """Construct.

        Args:
            args: Arguments passed to the CharmBase parent constructor.
        """
        super().__init__(*args)
        self.bind = BindService()
        self.dns_record = dns_record.DNSRecordProvides(self)

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
        self.framework.observe(self.on.leader_elected, self._on_leader_elected)
        self.framework.observe(
            self.on[constants.PEER].relation_departed, self._on_peer_relation_departed
        )
        self.framework.observe(
            self.on[constants.PEER].relation_joined, self._on_peer_relation_joined
        )
        self.unit.open_port("tcp", 53)  # Bind DNS
        self.unit.open_port("udp", 53)  # Bind DNS

    def _on_reload_bind(self, _: events.ReloadBindEvent) -> None:
        """Handle periodic reload bind event.

        Reloading is used to take new configuration into account.

        """
        relation_data = self._get_remote_relation_data()
        if relation_data is None:
            return
        topology = self._topology()

        # Load the last valid state
        try:
            last_valid_state = dns_data.load_state(
                pathlib.Path(constants.DNS_CONFIG_DIR, "state.json").read_text(encoding="utf-8")
            )
        except FileNotFoundError:
            # If we can't load the previous state,
            # we assume that we need to regenerate the configuration
            return
        if dns_data.has_changed(relation_data, topology, last_valid_state):
            self.bind.update_zonefiles_and_reload(relation_data, topology)

    def _on_peer_relation_joined(self, _: ops.RelationJoinedEvent) -> None:
        """Handle peer relation joined event."""
        try:
            topology = self._topology()
        except (PeerRelationUnavailableError, PeerRelationNetworkUnavailableError) as err:
            logger.info("Could not retrieve network topology: %s", err)
            return
        # If we are not the active unit, there's nothing to do
        if not topology.is_current_unit_active:
            return
        relation_data = self._get_remote_relation_data()
        if relation_data is None:
            return
        self.bind.update_zonefiles_and_reload(relation_data, topology)

    def _on_dns_record_relation_changed(self, event: ops.RelationChangedEvent) -> None:
        """Handle dns_record relation changed.

        Args:
            event: Event triggering the relation changed handler.

        """
        relation_data = self._get_remote_relation_data()
        if relation_data is None:
            return
        self.unit.status = ops.MaintenanceStatus("Handling new relation requests")
        dns_record_provider_data = dns_data.create_dns_record_provider_data(relation_data)
        relation = self.model.get_relation(self.dns_record.relation_name, event.relation.id)
        if self.unit.is_leader():
            self.dns_record.update_relation_data(relation, dns_record_provider_data)

    def _on_collect_status(self, event: ops.CollectStatusEvent) -> None:
        """Handle collect status event.

        Args:
            event: Event triggering the collect-status hook
        """
        try:
            topology = self._topology()
            if topology.is_current_unit_active:
                event.add_status(ops.ActiveStatus("active"))
            else:
                event.add_status(ops.ActiveStatus())
        except PeerRelationUnavailableError:
            event.add_status(ops.WaitingStatus("Peer relation is not available"))
        relation_data = self._get_remote_relation_data()
        if relation_data is None:
            event.add_status(ops.BlockedStatus("Non valid DNS requests"))
            return
        self.bind.collect_status(event, relation_data)

    def _on_config_changed(self, _: ops.ConfigChangedEvent) -> None:
        """Handle changed configuration event."""

    def _on_install(self, _: ops.InstallEvent) -> None:
        """Handle install."""
        self.unit.status = ops.MaintenanceStatus("Preparing bind")
        self.bind.setup(self.unit.name)

    def _on_start(self, _: ops.StartEvent) -> None:
        """Handle start."""
        self.bind.start()

    def _on_stop(self, _: ops.StopEvent) -> None:
        """Handle stop."""
        self.bind.stop()

    def _on_upgrade_charm(self, _: ops.UpgradeCharmEvent) -> None:
        """Handle upgrade-charm."""
        self.unit.status = ops.MaintenanceStatus("Upgrading dependencies")
        self.bind.setup(self.unit.name)

    def _on_leader_elected(self, _: ops.LeaderElectedEvent) -> None:
        """Handle leader-elected event."""
        # We check that we are still the leader when starting to process this event
        topology = self._topology()
        if self.unit.is_leader() and not topology.is_current_unit_active:
            self._check_and_may_become_active(topology)

    def _on_peer_relation_departed(self, event: ops.RelationDepartedEvent) -> None:
        """Handle the peer relation departed event.

        Args:
            event: Event triggering the relation-departed hook
        """
        # If we are a departing unit, we don't want to interfere with electing a new active one
        if event.departing_unit == self.model.unit:
            return

        try:
            topology = self._topology()
        except (PeerRelationUnavailableError, PeerRelationNetworkUnavailableError) as err:
            logger.info("Could not retrieve network topology: %s", err)
            return

        # We check that we are still the leader when starting to process this event
        if not topology.is_current_unit_active:
            if self.unit.is_leader():
                self._check_and_may_become_active(topology)
        else:
            try:
                relation_data = self.dns_record.get_remote_relation_data()
            except ValueError as err:
                logger.info("Validation error of the relation data: %s", err)
                return
            self.bind.update_zonefiles_and_reload(relation_data, topology)

    def _check_and_may_become_active(self, topology: models.Topology) -> bool:
        """Check the active unit status and may become active if need be.

        Args:
            topology: Topology of the current deployment

        Returns:
            True if the charm is effectively the new active unit.
        """
        relation = self.model.get_relation(constants.PEER)
        assert relation is not None  # nosec
        if not topology.active_unit_ip:
            relation.data[self.app].update({"active-unit": str(topology.current_unit_ip)})
            return True

        status = self._dig_query(
            f"@{topology.active_unit_ip} service.{constants.ZONE_SERVICE_NAME} TXT +short",
            retry=True,
            wait=1,
        )
        if status != "ok":
            relation.data[self.app].update({"active-unit": str(topology.current_unit_ip)})
            return True
        return False

    def _dig_query(self, cmd: str, retry: bool = False, wait: int = 5) -> str:
        """Query a DnsEntry with dig.

        This function was created for simplicity's sake. If we need to make more DNS requests
        in the future, we should revisit it by employing a python library.

        Args:
            cmd: The dig command to perform
            retry: If the dig request should be retried
            wait: duration in seconds to wait between retries

        Returns: the result of the DNS query
        """
        result: str = ""
        retry = False
        for _ in range(5):
            try:
                result = str(
                    subprocess.run(
                        ["dig"] + cmd.split(" "),  # nosec
                        capture_output=True,
                        text=True,
                        check=True,
                    )
                ).strip()
            except subprocess.CalledProcessError as exc:
                logger.warning("%s", exc)
                result = ""
            if result != "" or not retry:
                break
            time.sleep(wait)

        return result

    def _topology(self) -> models.Topology:
        """Create a network topology of the current deployment.

        Returns:
            A topology of the current deployment

        Raises:
            PeerRelationUnavailableError: when the peer relation does not exist
            PeerRelationNetworkUnavailableError: when the network property does not exist
        """
        start_time = time.time_ns()
        relation = self.model.get_relation(constants.PEER)
        binding = self.model.get_binding(constants.PEER)
        if not relation or not binding:
            raise PeerRelationUnavailableError(
                "Peer relation not available when trying to get topology."
            )
        try:
            if binding.network is None:
                raise PeerRelationNetworkUnavailableError(
                    "Peer relation network not available when trying to get unit IP."
                )
        except ops.model.ModelError as e:
            raise PeerRelationNetworkUnavailableError(str(e)) from e

        units_ip: list[str] = [
            unit_data.get("private-address", "")
            for _, unit_data in relation.data.items()
            if unit_data.get("private-address", "") != ""
        ]

        current_unit_ip = str(binding.network.bind_address)
        active_unit_ip = relation.data[self.app].get("active-unit")

        logger.debug("active_unit_ip: %s", active_unit_ip)
        logger.debug("current_unit_ip: %s", current_unit_ip)
        logger.debug("units_ip: %s", units_ip)
        logger.debug("topology retrieval duration (ms): %s", (time.time_ns() - start_time) / 1e6)

        return models.Topology(
            active_unit_ip=active_unit_ip,
            units_ip=units_ip,
            standby_units_ip=[ip for ip in units_ip if ip != active_unit_ip],
            current_unit_ip=current_unit_ip,
        )

    def _get_remote_relation_data(self) -> dns_record.DNSRecordProviderData | None:
        """Get the dns_record remote relation data.

        This function is used to get performance statistics on the remote relation data retrieval.

        Returns:
            the dns_record remote relation data
        """
        start_time = time.time_ns()
        relation_data = self.dns_record.get_remote_relation_data()
        logger.debug(
            "Relation data retrieval duration (ms): %s", (time.time_ns() - start_time) / 1e6
        )
        return relation_data


if __name__ == "__main__":  # pragma: nocover
    ops.main(BindCharm)
