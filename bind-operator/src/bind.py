# Copyright 2025 Canonical Ltd.
# See LICENSE file for licensing details.

"""Bind charm business logic."""

import logging
import os
import pathlib
import shutil
import subprocess  # nosec
import tempfile
import time

import ops
import pydantic
from charms.bind.v0.dns_record import DNSRecordProviderData, DNSRecordRequirerData
from charms.operator_libs_linux.v1 import systemd
from charms.operator_libs_linux.v2 import snap

import constants
import dns_data
import exceptions
import models
import templates

logger = logging.getLogger(__name__)


class SnapError(exceptions.BindCharmError):
    """Exception raised when an action on the snap fails."""


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
        self._install_snap_package_from_file(
            f"/var/lib/juju/agents/unit-{unit_name.replace('/','-')}/charm/charmed-bind_jammy_amd64.snap"
        )
        self._install_bind_reload_service(unit_name)
        # We need to put the service zone in place so we call
        # the following with an empty relation and topology.
        self.update_zonefiles_and_reload([], None)

    def _install_snap_package_from_file(self, snap_path: str) -> None:
        """Installs snap package.

        Args:
            snap_path: The path to the snap to install, can be blank.

        Raises:
            InstallError: when encountering a SnapError or a SnapNotFoundError
        """
        try:
            # Installing the charm via subprocess.
            # Calling subprocess here is not a security issue.
            logger.info(
                "Installing from custom dns-policy snap located: %s",
                snap_path,
            )
            subprocess.check_output(["sudo", "snap", "install", snap_path, "--dangerous"])  # nosec
        except (snap.SnapError, snap.SnapNotFoundError) as e:
            error_msg = f"An exception occurred when installing {snap_path}. Reason: {e}"
            logger.exception(error_msg)
            raise InstallError(error_msg) from e
        except subprocess.CalledProcessError as e:
            error_msg = f"An exception occurred when installing {snap_path}. Reason: {e}. Output: {e.output}"
            logger.exception(error_msg)
            raise InstallError(error_msg) from e

    def _install_bind_reload_service(self, unit_name: str) -> None:
        """Install the bind reload service.

        Args:
            unit_name: The name of the current unit
        """
        (
            pathlib.Path(constants.SYSTEMD_SERVICES_PATH) / "dispatch-reload-bind.service"
        ).write_text(
            templates.DISPATCH_EVENT_SERVICE.format(
                event="reload-bind",
                timeout="10s",
                unit=unit_name,
            ),
            encoding="utf-8",
        )
        (pathlib.Path(constants.SYSTEMD_SERVICES_PATH) / "dispatch-reload-bind.timer").write_text(
            templates.SYSTEMD_SERVICE_TIMER.format(interval="1", service="dispatch-reload-bind"),
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
            zones.extend(dns_data.record_requirer_data_to_zones(record_requirer_data))
        _, conflicting = dns_data.get_conflicts(zones)
        if len(conflicting) > 0:
            event.add_status(ops.BlockedStatus("Conflicting requests"))
        event.add_status(ops.ActiveStatus())

    def _write_file(self, path: pathlib.Path, content: str) -> None:
        """Write a file to the filesystem.

        This function exists to be easily mocked during unit tests.

        Args:
            path: path to the file
            content: content of the file
        """
        pathlib.Path(path).write_text(
            content,
            encoding="utf-8",
        )

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
        start_time = time.time_ns()
        logger.debug("Starting update of zonefiles")
        zones = dns_data.dns_record_relations_data_to_zones(relation_data)
        logger.debug("Zones: %s", [z.domain for z in zones])

        # Check for conflicts
        _, conflicting = dns_data.get_conflicts(zones)
        if len(conflicting) > 0:
            return

        # Create staging area
        # This is done to avoid having a partial configuration remaining if something goes wrong.
        with tempfile.TemporaryDirectory() as tempdir:

            # Write the serialized state to a json file for future comparison
            self._write_file(
                pathlib.Path(constants.DNS_CONFIG_DIR) / "state.json",
                dns_data.dump_state(zones, topology),
            )

            # Write the service.test file
            self._write_file(
                pathlib.Path(constants.DNS_CONFIG_DIR) / f"db.{constants.ZONE_SERVICE_NAME}",
                templates.ZONE_SERVICE.format(
                    serial=int(time.time() / 60),
                ),
            )

            if topology is not None and topology.is_current_unit_active:
                # Write zone files
                zone_files: dict[str, str] = self._zones_to_files_content(zones, topology)
                for domain, content in zone_files.items():
                    self._write_file(pathlib.Path(tempdir) / f"db.{domain}", content)

            # Write the named.conf file
            self._write_file(
                pathlib.Path(tempdir) / "named.conf.local",
                self._generate_named_conf_local([z.domain for z in zones], topology),
            )

            # Move the staging area files to the config dir
            for file_name in os.listdir(tempdir):
                shutil.move(
                    pathlib.Path(tempdir) / file_name,
                    pathlib.Path(constants.DNS_CONFIG_DIR, file_name),
                )

        # Reload charmed-bind config (only if already started).
        # When stopped, we assume this was on purpose.
        # We can be here following a regular reload-bind event
        # and we don't want to interfere with another operation.
        self.reload(force_start=False)
        logger.debug("Update and reload duration (ms): %s", (time.time_ns() - start_time) / 1e6)

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
        except (snap.SnapError, snap.SnapNotFoundError, subprocess.CalledProcessError) as e:
            error_msg = f"An exception occurred when installing {snap_name}. Reason: {e}"
            logger.exception(error_msg)
            raise InstallError(error_msg) from e

    def _zones_to_files_content(
        self, zones: list[models.Zone], topology: models.Topology
    ) -> dict[str, str]:
        """Return zone files and their content.

        Args:
            zones: list of the zones to transform to text
            topology: Topology of the current deployment

        Returns:
            A dict whose keys are the domain of each zone
            and the values the content of the zone file
        """
        zone_files: dict[str, str] = {}
        for zone in zones:
            content = templates.ZONE_APEX_TEMPLATE.format(
                zone=zone.domain,
                # The serial is the timestamp divided by 60.
                # We only need precision to the minute and want to avoid overflows
                serial=int(time.time() / 60),
            )

            # By default, we hide the active unit.
            # So only the standbies are used to respond to queries and receive NOTIFY events
            # If we have no standby unit (a single unit deployment)
            # then use current unit IP instead
            ip_list: list[pydantic.IPvAnyAddress] = topology.standby_units_ip or [
                topology.current_unit_ip
            ]
            # We sort the list to hopefully present the NS in a stable order in the file
            for ip in sorted(ip_list):
                content += templates.ZONE_APEX_NS_TEMPLATE.format(
                    # We convert the IP to an int and use that as the NS record number
                    # This way, we generate a somewhat stable list of NS records
                    number=int(ip),
                    ip=ip,
                )

            for entry in zone.entries:
                content += templates.ZONE_RECORD_TEMPLATE.format(
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
        content += templates.NAMED_CONF_PRIMARY_ZONE_DEF_TEMPLATE.format(
            name=f"{constants.ZONE_SERVICE_NAME}",
            absolute_path=f"{constants.DNS_CONFIG_DIR}/db.{constants.ZONE_SERVICE_NAME}",
            zone_transfer_ips="",
        )
        if topology is not None:
            for name in zones:
                if topology.is_current_unit_active:
                    content += templates.NAMED_CONF_PRIMARY_ZONE_DEF_TEMPLATE.format(
                        name=name,
                        absolute_path=f"{constants.DNS_CONFIG_DIR}/db.{name}",
                        zone_transfer_ips=self._bind_config_ip_list(topology.standby_units_ip),
                    )
                else:
                    content += templates.NAMED_CONF_SECONDARY_ZONE_DEF_TEMPLATE.format(
                        name=name,
                        absolute_path=f"{constants.DNS_CONFIG_DIR}/db.{name}",
                        primary_ip=self._bind_config_ip_list([topology.active_unit_ip]),
                    )
        return content

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
