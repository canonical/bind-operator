# Copyright 2024 Canonical Ltd.
# See LICENSE file for licensing details.

"""Bind charm business logic."""

import logging
import os
import pathlib
import re
import shutil
import tempfile
import time

import ops
import pydantic
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
import models

logger = logging.getLogger(__name__)


class SnapError(exceptions.BindCharmError):
    """Exception raised when an action on the snap fails."""


class InvalidZoneFileMetadataError(exceptions.BindCharmError):
    """Exception raised when a zonefile has invalid metadata."""


class EmptyZoneFileMetadataError(exceptions.BindCharmError):
    """Exception raised when a zonefile has no metadata."""


class DuplicateMetadataEntryError(exceptions.BindCharmError):
    """Exception raised when a zonefile has metadata with duplicate entries."""


class ReloadError(SnapError):
    """Exception raised when unable to reload the service."""


class StartError(SnapError):
    """Exception raised when unable to start the service."""


class StopError(SnapError):
    """Exception raised when unable to stop the service."""


class InstallError(SnapError):
    """Exception raised when unable to install dependencies for the service."""


class BindService:
    """Bind service class."""

    def reload(self, force_start: bool) -> None:
        """Reload the charmed-bind service.

        Args:
            force_start: start the service even if it was inactive

        Raises:
            ReloadError: when encountering a SnapError
        """
        logger.debug("Reloading charmed bind")
        try:
            cache = snap.SnapCache()
            charmed_bind = cache[constants.DNS_SNAP_NAME]
            charmed_bind_service = charmed_bind.services[constants.DNS_SNAP_SERVICE]
            if charmed_bind_service["active"] or force_start:
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

    def setup(self, unit_name: str) -> None:
        """Prepare the machine.

        Args:
            unit_name: The name of the current unit
        """
        self._install_snap_package(
            snap_name=constants.DNS_SNAP_NAME,
            snap_channel=constants.SNAP_PACKAGES[constants.DNS_SNAP_NAME]["channel"],
        )
        self._install_bind_reload_service(unit_name)
        # We need to put the service zone in place so we call
        # the following with an empty relation and topology.
        self.update_zonefiles_and_reload([], None)

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
            ),
            encoding="utf-8",
        )
        (pathlib.Path(constants.SYSTEMD_SERVICES_PATH) / "dispatch-reload-bind.timer").write_text(
            constants.SYSTEMD_SERVICE_TIMER.format(interval="1", service="dispatch-reload-bind"),
            encoding="utf-8",
        )
        systemd.service_enable("dispatch-reload-bind.timer")
        systemd.service_start("dispatch-reload-bind.timer")

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
        zones: list[models.Zone] = []
        for record_requirer_data, _ in relation_data:
            zones.extend(self._record_requirer_data_to_zones(record_requirer_data))
        _, conflicting = self._get_conflicts(zones)
        if len(conflicting) > 0:
            event.add_status(ops.BlockedStatus("Conflicting requests"))
        event.add_status(ops.ActiveStatus())

    def update_zonefiles_and_reload(
        self,
        relation_data: list[tuple[DNSRecordRequirerData, DNSRecordProviderData]],
        topology: models.Topology | None,
    ) -> None:
        """Update the zonefiles from bind's config and reload bind.

        Args:
            relation_data: input relation data
            topology: Topology of the current deployment
        """
        logger.debug("Starting update of zonefiles")
        zones = self._dns_record_relations_data_to_zones(relation_data)
        logger.debug("Zones: %s", [z.domain for z in zones])

        # Check for conflicts
        _, conflicting = self._get_conflicts(zones)
        if len(conflicting) > 0:
            return

        # Create staging area
        # This is done to avoid having a partial configuration remaining if something goes wrong.
        with tempfile.TemporaryDirectory() as tempdir:

            # Write the service.test file
            pathlib.Path(constants.DNS_CONFIG_DIR, f"db.{constants.ZONE_SERVICE_NAME}").write_text(
                constants.ZONE_SERVICE.format(
                    serial=int(time.time() / 60),
                ),
                encoding="utf-8",
            )

            if topology is not None and topology.is_current_unit_active:
                # Write zone files
                zone_files: dict[str, str] = self._zones_to_files_content(zones)
                for domain, content in zone_files.items():
                    pathlib.Path(tempdir, f"db.{domain}").write_text(content, encoding="utf-8")

            # Write the named.conf file
            pathlib.Path(tempdir, "named.conf.local").write_text(
                self._generate_named_conf_local([z.domain for z in zones], topology),
                encoding="utf-8",
            )

            # Move the staging area files to the config dir
            for file_name in os.listdir(tempdir):
                shutil.move(
                    pathlib.Path(tempdir, file_name),
                    pathlib.Path(constants.DNS_CONFIG_DIR, file_name),
                )

        # Reload charmed-bind config (only if already started).
        # When stopped, we assume this was on purpose.
        # We can be here following a regular reload-bind event
        # and we don't want to interfere with another operation.
        self.reload(force_start=False)

    def create_dns_record_provider_data(
        self,
        relation_data: list[tuple[DNSRecordRequirerData, DNSRecordProviderData]],
    ) -> DNSRecordProviderData:
        """Create dns record provider data from relation data.

        The result of this function should be used to update the relation.
        It contains statuses for each DNS record request.

        Args:
            relation_data: input relation data

        Returns:
            A DNSRecordProviderData object with requests' status
        """
        zones = self._dns_record_relations_data_to_zones(relation_data)
        nonconflicting, conflicting = self._get_conflicts(zones)
        statuses = []
        for record_requirer_data, _ in relation_data:
            for requirer_entry in record_requirer_data.dns_entries:
                dns_entry = models.create_dns_entry_from_requirer_entry(requirer_entry)
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

    def has_a_zone_changed(
        self,
        relation_data: list[tuple[DNSRecordRequirerData, DNSRecordProviderData]],
        topology: models.Topology | None,
    ) -> bool:
        """Check if a zone definition has changed.

        The zone definition is checked from a custom hash constructed from its DNS records.

        Args:
            relation_data: input relation data
            topology: Topology of the current deployment

        Returns:
            True if a zone has changed, False otherwise.
        """
        zones = self._dns_record_relations_data_to_zones(relation_data)
        logger.debug("Zones: %s", [z.domain for z in zones])
        for zone in zones:
            try:
                zonefile_content = pathlib.Path(
                    constants.DNS_CONFIG_DIR, f"db.{zone.domain}"
                ).read_text(encoding="utf-8")
                metadata = self._get_zonefile_metadata(zonefile_content)
            except (
                InvalidZoneFileMetadataError,
                EmptyZoneFileMetadataError,
                FileNotFoundError,
            ):
                return True
            if "HASH" in metadata and hash(zone) != int(metadata["HASH"]):
                logger.debug("Config hash has changed !")
                return True

        if topology is not None and topology.is_current_unit_active:
            try:
                named_conf_content = pathlib.Path(
                    constants.DNS_CONFIG_DIR, "named.conf.local"
                ).read_text(encoding="utf-8")
            except FileNotFoundError:
                return True
            return (
                self._get_secondaries_ip_from_conf(named_conf_content).sort()
                != [str(ip) for ip in topology.standby_units_ip].sort()
            )

        return False

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
    ) -> list[models.Zone]:
        """Convert DNSRecordRequirerData to zone files.

        Args:
            record_requirer_data: The input DNSRecordRequirerData

        Returns:
            A list of zones
        """
        zones_entries: dict[str, list[RequirerEntry]] = {}
        for entry in record_requirer_data.dns_entries:
            if entry.domain not in zones_entries:
                zones_entries[entry.domain] = []
            zones_entries[entry.domain].append(entry)

        zones: list[models.Zone] = []
        for domain, entries in zones_entries.items():
            zone = models.Zone(domain=domain, entries=[])
            for entry in entries:
                zone.entries.add(models.create_dns_entry_from_requirer_entry(entry))
            zones.append(zone)
        return zones

    def _get_conflicts(
        self, zones: list[models.Zone]
    ) -> tuple[set[models.DnsEntry], set[models.DnsEntry]]:
        """Return conflicting and non-conflicting entries.

        Args:
            zones: list of the zones to check

        Returns:
            A tuple containing the non-conflicting and conflicting entries
        """
        entries = [e for z in zones for e in z.entries]
        nonconflicting_entries: set[models.DnsEntry] = set()
        conflicting_entries: set[models.DnsEntry] = set()
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

    def _zones_to_files_content(self, zones: list[models.Zone]) -> dict[str, str]:
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
                zone=zone.domain,
                # The serial is the timestamp divided by 60.
                # We only need precision to the minute and want to avoid overflows
                serial=int(time.time() / 60),
                hash=hash(zone),
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

    def _generate_named_conf_local(
        self, zones: list[str], topology: models.Topology | None
    ) -> str:
        """Generate the content of `named.conf.local`.

        Args:
            zones: A list of all the zones names
            topology: Topology of the current deployment

        Returns:
            The content of `named.conf.local`
        """
        # It's good practice to include rfc1918
        content: str = f'include "{constants.DNS_CONFIG_DIR}/zones.rfc1918";\n'
        # Include a zone specifically used for some services tests
        content += constants.NAMED_CONF_PRIMARY_ZONE_DEF_TEMPLATE.format(
            name=f"{constants.ZONE_SERVICE_NAME}",
            absolute_path=f"{constants.DNS_CONFIG_DIR}/db.{constants.ZONE_SERVICE_NAME}",
            zone_transfer_ips="",
        )
        for name in zones:
            if topology is None:
                pass
            elif topology.is_current_unit_active:
                content += constants.NAMED_CONF_PRIMARY_ZONE_DEF_TEMPLATE.format(
                    name=name,
                    absolute_path=f"{constants.DNS_CONFIG_DIR}/db.{name}",
                    zone_transfer_ips=self._bind_config_ip_list(topology.standby_units_ip),
                )
            else:
                content += constants.NAMED_CONF_SECONDARY_ZONE_DEF_TEMPLATE.format(
                    name=name,
                    absolute_path=f"{constants.DNS_CONFIG_DIR}/db.{name}",
                    primary_ip=self._bind_config_ip_list([topology.active_unit_ip]),
                )
        return content

    def _dns_record_relations_data_to_zones(
        self,
        relation_data: list[tuple[DNSRecordRequirerData, DNSRecordProviderData]],
    ) -> list[models.Zone]:
        """Return zones from all the dns_record relations data.

        Args:
            relation_data: input relation data

        Returns:
            The zones from the record_requirer_data
        """
        zones: dict[str, models.Zone] = {}
        for record_requirer_data, _ in relation_data:
            for new_zone in self._record_requirer_data_to_zones(record_requirer_data):
                if new_zone.domain in zones:
                    zones[new_zone.domain].entries.update(new_zone.entries)
                else:
                    zones[new_zone.domain] = new_zone
        return list(zones.values())

    def _get_zonefile_metadata(self, zonefile_content: str) -> dict[str, str]:
        """Get the metadata of a zonefile.

        Args:
            zonefile_content: The content of the zonefile.

        Returns:
            The hash of the corresponding zonefile.

        Raises:
            InvalidZoneFileMetadataError: when the metadata of the zonefile could not be parsed.
            EmptyZoneFileMetadataError: when the metadata of the zonefile is empty.
            DuplicateMetadataEntryError: when the metadata of the zonefile has duplicate entries.
        """
        # This assumes that the file was generated with the constants.ZONE_HEADER_TEMPLATE template
        metadata = {}
        try:
            lines = zonefile_content.split("\n")
            for line in lines:
                # We only take the $ORIGIN line into account
                if not line.startswith("$ORIGIN"):
                    continue
                for token in line.split(";")[1].split():
                    k, v = token.split(":")
                    if k in metadata:
                        raise DuplicateMetadataEntryError(f"Duplicate metadata entry '{k}'")
                    metadata[k] = v
        except (IndexError, ValueError) as err:
            raise InvalidZoneFileMetadataError(err) from err

        if metadata:
            return metadata
        raise EmptyZoneFileMetadataError("No metadata found !")

    def _get_secondaries_ip_from_conf(self, named_conf_content: str) -> list[str]:
        """Get the secondaries IP addresses from the named.conf.local file.

        This is useful to check if we need to regenerate
        the file after a change in the network topology.

        This function is only taking the first line of named.conf.local with a zone-transfer
        into account. It works when the charm is writing the config files but is a bit
        brittle if those are modified by a human.
        TODO: This should be reworked (along with the metadata system) in something more durable
        like an external json file to store that information.

        Args:
            named_conf_content: content of the named.conf.local file

        Returns:
            A list of IPs as strings
        """
        for line in named_conf_content.splitlines():
            if "allow-transfer" in line:
                if match := re.search(r"allow-transfer\s*\{([^}]+)\}", line):
                    return [ip.strip() for ip in match.group(1).split(";") if ip.strip() != ""]
        return []

    def _bind_config_ip_list(self, ips: list[pydantic.IPvAnyAddress]) -> str:
        """Generate a string with a list of IPs that can be used in bind's config.

        This is just a helper function to keep things clean in `_generate_named_conf_local`.

        Args:
            ips: A list of IPs

        Returns:
            A ";" separated list of ips
        """
        if not ips:
            return ""
        return f"{';'.join([str(ip) for ip in ips])};"
