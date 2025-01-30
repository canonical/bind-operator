# Copyright 2025 Canonical Ltd.
# See LICENSE file for licensing details.

"""App charm business logic."""

import logging
import pathlib
import subprocess  # nosec

import ops
from charms.bind.v0.dns_record import DNSRecordProviderData, DNSRecordRequirerData
from charms.operator_libs_linux.v1 import systemd
from charms.operator_libs_linux.v2 import snap
import constants

logger = logging.getLogger(__name__)


class DnsPolicyCharmError(Exception):
    """Base exception for the bind charm."""

    def __init__(self, msg: str):
        """Initialize a new instance of the exception.

        Args:
            msg (str): Explanation of the error.
        """
        self.msg = msg


class SnapError(DnsPolicyCharmError):
    """Exception raised when an action on the snap fails."""


class ReloadError(SnapError):
    """Exception raised when unable to reload the service."""


class StartError(SnapError):
    """Exception raised when unable to start the service."""


class StopError(SnapError):
    """Exception raised when unable to stop the service."""


class InstallError(SnapError):
    """Exception raised when unable to install dependencies for the service."""


class ConfigureError(SnapError):
    """Exception raised when unable to configure the service."""


class DnsPolicyService:
    """DnsPolicy service class."""

    def reload(self, force_start: bool) -> None:
        """Reload the dns-policy service.

        Args:
            force_start: start the service even if it was inactive

        Raises:
            ReloadError: when encountering a SnapError
        """
        logger.debug("Reloading charmed bind")
        try:
            cache = snap.SnapCache()
            dns_policy = cache[constants.DNS_SNAP_NAME]
            dns_policy_service = dns_policy.services[constants.DNS_SNAP_SERVICE]
            if dns_policy_service["active"] or force_start:
                dns_policy.restart(reload=True)
        except snap.SnapError as e:
            error_msg = (
                f"An exception occurred when reloading {constants.DNS_SNAP_NAME}. Reason: {e}"
            )
            logger.error(error_msg)
            raise ReloadError(error_msg) from e

    def start(self) -> None:
        """Start the dns-policy service.

        Raises:
            StartError: when encountering a SnapError
        """
        try:
            cache = snap.SnapCache()
            dns_policy = cache[constants.DNS_SNAP_NAME]
            dns_policy.start()
        except snap.SnapError as e:
            error_msg = (
                f"An exception occurred when stopping {constants.DNS_SNAP_NAME}. Reason: {e}"
            )
            logger.error(error_msg)
            raise StartError(error_msg) from e

    def stop(self) -> None:
        """Stop the dns-policy service.

        Raises:
            StopError: when encountering a SnapError
        """
        try:
            cache = snap.SnapCache()
            dns_policy = cache[constants.DNS_SNAP_NAME]
            dns_policy.stop()
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
            "/var/lib/juju/agents/unit-dns-policy-operator-0/charm/dns-policy-app_0.1_amd64.snap"
        )

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

    def _install_snap_package_from_snapstore(
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

    def _install_snap_package_from_file(
        self, snap_path: str | None
    ) -> None:
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
            subprocess.check_output(
                ["sudo", "snap", "install", snap_path, "--dangerous"]
            )  # nosec
        except (snap.SnapError, snap.SnapNotFoundError, subprocess.CalledProcessError) as e:
            error_msg = f"An exception occurred when installing {snap_path}. Reason: {e}"
            logger.exception(error_msg)
            raise InstallError(error_msg) from e

    def configure(self, config: dict[str, str]) -> None:
        """Configure the dns-policy service.

        Args:
            config: dict of configuration values

        Raises:
            ConfigureError: when encountering a SnapError
        """
        try:
            cache = snap.SnapCache()
            charmed_bind = cache[constants.DNS_SNAP_NAME]
            charmed_bind.set(config)
        except snap.SnapError as e:
            error_msg = (
                f"An exception occurred when configuring {constants.DNS_SNAP_NAME}. Reason: {e}"
            )
            logger.error(error_msg)
            raise ConfigureError(error_msg) from e

    def command(self, cmd: str, env: dict) -> str:
        """Run manage command of the dns-policy service.

        Args:
            cmd: command to execute by django's manage script
            env: environment

        Returns:
            The resulting output of the command's execution
        """
        try:
            # We ignore security issues with this subprocess call
            # as it can only be done from the operator of the charm
            return subprocess.check_output(
                ["sudo", "snap", "run", f"{constants.DNS_SNAP_NAME}.manage"] + cmd.split(),
                env=env,
            ).decode(  # nosec
                "utf-8"
            )
        except subprocess.SubprocessError as e:
            return f"Error: {e}"
