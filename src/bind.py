# Copyright 2024 Canonical Ltd.
# See LICENSE file for licensing details.

"""Bind charm business logic."""

import logging
import os
import pathlib
import shutil
import tempfile
import time

import ops
from charms.bind.v0.dns_record import (
    DNSProviderData,
    DNSRecordProviderData,
    DNSRecordRequirerData,
    RequirerEntry,
    Status,
)
from charms.operator_libs_linux.v1 import systemd
from charms.operator_libs_linux.v2 import snap

import constants
import exceptions
from models import DnsEntry, Zone, create_dns_entry_from_requirer_entry

logger = logging.getLogger(__name__)


class ReloadError(exceptions.SnapError):
    """Exception raised when unable to reload the service."""


class StartError(exceptions.SnapError):
    """Exception raised when unable to start the service."""


class StopError(exceptions.SnapError):
    """Exception raised when unable to stop the service."""


class InstallError(exceptions.SnapError):
    """Exception raised when unable to install dependencies for the service."""


class BindService:
    """Bind service class."""

    def reload(self) -> None:
        """Reload the charmed-bind service.

        Raises:
            ReloadError: when encountering a SnapError
        """
        try:
            cache = snap.SnapCache()
            charmed_bind = cache[constants.DNS_SNAP_NAME]
            charmed_bind.restart(reload=True)
        except snap.SnapError as e:
            error_msg = (
                f"An exception occurred when reloading {constants.DNS_SNAP_NAME}. Reason: {e}"
            )
            logger.error(error_msg)
            raise ReloadError(error_msg) from e

    def start(self) -> None:
        """Start the charmed-bind service.

        Raises:
            StartError: when encountering a SnapError
        """
        try:
            cache = snap.SnapCache()
            charmed_bind = cache[constants.DNS_SNAP_NAME]
            charmed_bind.start()
        except snap.SnapError as e:
            error_msg = (
                f"An exception occurred when stopping {constants.DNS_SNAP_NAME}. Reason: {e}"
            )
            logger.error(error_msg)
            raise StartError(error_msg) from e

    def stop(self) -> None:
        """Stop the charmed-bind service.

        Raises:
            StopError: when encountering a SnapError
        """
        try:
            cache = snap.SnapCache()
            charmed_bind = cache[constants.DNS_SNAP_NAME]
            charmed_bind.stop()
        except snap.SnapError as e:
            error_msg = (
                f"An exception occurred when stopping {constants.DNS_SNAP_NAME}. Reason: {e}"
            )
            logger.error(error_msg)
            raise StopError(error_msg) from e

    def prepare(self, unit_name: str) -> None:
        """Prepare the machine.

        Args:
            unit_name: The name of the current unit
        """
        self._install_snap_package(
            snap_name=constants.DNS_SNAP_NAME,
            snap_channel=constants.SNAP_PACKAGES[constants.DNS_SNAP_NAME]["channel"],
        )
        self._install_bind_reload_service(unit_name)

    def _install_bind_reload_service(self, unit_name: str) -> None:
        """Install the bind reload service.

        Args:
            unit_name: The name of the current unit
        """
        (
            pathlib.Path(constants.SYSTEMD_SERVICES_PATH) / "dispatch-reload-bind.service"
        ).write_text(
            constants.DISPATCH_EVENT_SERVICE.format(
                event="reload-bind",
                timeout="10s",
                unit=unit_name,
            )
        )
        (pathlib.Path(constants.SYSTEMD_SERVICES_PATH) / "dispatch-reload-bind.timer").write_text(
            constants.SYSTEMD_SERVICE_TIMER.format(interval="1", service="dispatch-reload-bind")
        )
        systemd.service_enable("dispatch-reload-bind.timer")
        systemd.service_start("dispatch-reload-bind.timer")

    def _install_snap_package(
        self, snap_name: str, snap_channel: str, refresh: bool = False
    ) -> None:
        """Installs snap package.

        Args:
            snap_name: the snap package to install
            snap_channel: the snap package channel
            refresh: whether to refresh the snap if it's already present.

        Raises:
            InstallError: when encountering a SnapError or a SnapNotFoundError
        """
        try:
            snap_cache = snap.SnapCache()
            snap_package = snap_cache[snap_name]

            if not snap_package.present or refresh:
                snap_package.ensure(snap.SnapState.Latest, channel=snap_channel)

        except (snap.SnapError, snap.SnapNotFoundError) as e:
            error_msg = f"An exception occurred when installing {snap_name}. Reason: {e}"
            logger.error(error_msg)
            raise InstallError(error_msg) from e

    def _record_requirer_data_to_zones(
        self, record_requirer_data: DNSRecordRequirerData
    ) -> list[Zone]:
        """Convert DNSRecordRequirerData to zone files.

        Args:
            record_requirer_data: The input DNSRecordRequirerData

        Returns:
            A dict of zones names as keys with the zones contents as values
        """
        zones_entries: dict[str, list[RequirerEntry]] = {}
        for entry in record_requirer_data.dns_entries:
            if entry.domain not in zones_entries:
                zones_entries[entry.domain] = []
            zones_entries[entry.domain].append(entry)

        zones: list[Zone] = []
        for domain, entries in zones_entries.items():
            zone = Zone(domain=domain, entries=[])
            for entry in entries:
                zone.entries.append(create_dns_entry_from_requirer_entry(entry))
            zones.append(zone)
        return zones

    def _get_conflicts(self, zones: list[Zone]) -> tuple[set[DnsEntry], set[DnsEntry]]:
        """Return conflicting and non-conflicting entries.

        Args:
            zones: list of the zones to check

        Returns:
            A tuple containing the non-conflicting and conflicting entries
        """
        entries = [e for z in zones for e in z.entries]
        nonconflicting_entries: set[DnsEntry] = set()
        conflicting_entries: set[DnsEntry] = set()
        while entries:
            entry = entries.pop()
            found_conflict = False
            if entry in conflicting_entries:
                continue
            for e in entries:
                if entry.conflicts(e) and entry != e:
                    found_conflict = True
                    conflicting_entries.add(entry)
                    conflicting_entries.add(e)

            if not found_conflict:
                nonconflicting_entries.add(entry)

        return (nonconflicting_entries, conflicting_entries)

    def _zones_to_files_content(self, zones: list[Zone]) -> dict[str, str]:
        """Return zone files and their content.

        Args:
            zones: list of the zones to transform to text

        Returns:
            A dict whose keys are the domain of each zone
            and the values the content of the zone file
        """
        zone_files: dict[str, str] = {}
        for zone in zones:
            content = constants.ZONE_HEADER_TEMPLATE.format(
                zone=zone.domain, serial=int(time.time())
            )
            for entry in zone.entries:
                content += constants.ZONE_RECORD_TEMPLATE.format(
                    host_label=entry.host_label,
                    record_class=entry.record_class,
                    record_type=entry.record_type,
                    record_data=entry.record_data,
                )
            zone_files[zone.domain] = content
        return zone_files

    def _generate_named_conf_local(self, zones: list[str]) -> str:
        """Generate the content of `named.conf.local`.

        Args:
            zones: A list of all the zones names

        Returns:
            The content of `named.conf.local`
        """
        # It's good practice to include rfc1918
        content: str = f'include "{constants.DNS_CONFIG_DIR}/zones.rfc1918";\n'
        for name in zones:
            content += constants.NAMED_CONF_ZONE_DEF_TEMPLATE.format(
                name=name, absolute_path=f"{constants.DNS_CONFIG_DIR}/db.{name}"
            )
        return content

    def handle_relation_data(
        self,
        relation_data: list[tuple[DNSRecordRequirerData, DNSRecordProviderData]],
    ) -> DNSRecordProviderData:
        """Handle new relation data.

        Args:
            relation_data: The list of DNSRecordRequirerData from the dns_record relations

        Returns:
            A resulting DNSRecordProviderData to put in the relation databag
        """
        # Create zones list
        zones: list[Zone] = []
        for record_requirer_data, _ in relation_data:
            zones.extend(self._record_requirer_data_to_zones(record_requirer_data))

        # Check for conflicts
        _, conflicting = self._get_conflicts(zones)
        if len(conflicting) > 0:
            return self._create_dns_record_provider_data(relation_data)

        # Create staging area
        with tempfile.TemporaryDirectory() as tempdir:
            # Write zone files
            zone_files: dict[str, str] = self._zones_to_files_content(zones)
            for name, content in zone_files.items():
                pathlib.Path(tempdir, f"db.{name}").write_text(content, encoding="utf-8")

            # Write the named.conf file
            pathlib.Path(tempdir, "named.conf.local").write_text(
                self._generate_named_conf_local([z.domain for z in zones]), encoding="utf-8"
            )

            # Move the valid staging area files to the config dir
            for file_name in os.listdir(tempdir):
                shutil.move(
                    pathlib.Path(tempdir, file_name),
                    pathlib.Path(constants.DNS_CONFIG_DIR, file_name),
                )

        # Reload charmed-bind config
        self.reload()

        # Return the provider data with the entries' status
        return self._create_dns_record_provider_data(relation_data)

    def _create_dns_record_provider_data(
        self,
        relation_data: list[tuple[DNSRecordRequirerData, DNSRecordProviderData]],
    ) -> DNSRecordProviderData:
        """Create dns record provider data from relation data.

        Args:
            relation_data: input relation data

        Returns:
            A DNSRecordProviderData object with requests' status
        """
        zones: list[Zone] = []
        for record_requirer_data, _ in relation_data:
            zones.extend(self._record_requirer_data_to_zones(record_requirer_data))
        nonconflicting, conflicting = self._get_conflicts(zones)
        statuses = []
        for record_requirer_data, _ in relation_data:
            for requirer_entry in record_requirer_data.dns_entries:
                dns_entry = create_dns_entry_from_requirer_entry(requirer_entry)
                if dns_entry in nonconflicting:
                    statuses.append(
                        DNSProviderData(uuid=requirer_entry.uuid, status=Status.APPROVED)
                    )
                    continue
                if dns_entry in conflicting:
                    statuses.append(
                        DNSProviderData(uuid=requirer_entry.uuid, status=Status.CONFLICT)
                    )
                    continue
                statuses.append(DNSProviderData(uuid=requirer_entry.uuid, status=Status.UNKNOWN))
        return DNSRecordProviderData(dns_entries=statuses)

    def collect_status(
        self,
        event: ops.CollectStatusEvent,
        relation_data: list[tuple[DNSRecordRequirerData, DNSRecordProviderData]],
    ) -> None:
        """Add status for the charm based on the status of the dns record requests.

        Args:
            event: Event triggering the collect-status hook
            relation_data: data coming from the relation databag
        """
        zones: list[Zone] = []
        for record_requirer_data, _ in relation_data:
            zones.extend(self._record_requirer_data_to_zones(record_requirer_data))
        _, conflicting = self._get_conflicts(zones)
        if len(conflicting) > 0:
            event.add_status(ops.BlockedStatus("Conflicting requests"))
        event.add_status(ops.ActiveStatus())
