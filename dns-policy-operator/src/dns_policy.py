# Copyright 2025 Canonical Ltd.
# See LICENSE file for licensing details.

"""App charm business logic."""

import json
import logging
import pathlib
import subprocess  # nosec

import ops
import pydantic
import requests
from charms.bind.v0.dns_record import RequirerEntry
from charms.operator_libs_linux.v2 import snap

import constants
import models

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


class RootTokenError(DnsPolicyCharmError):
    """Exception raised when unable to get a valid root token."""


class GetApprovedRecordRequestsError(DnsPolicyCharmError):
    """Exception raised when unable to get approved record requests."""


class DnsPolicyService:
    """DnsPolicy service class."""

    def reload(self, force_start: bool) -> None:
        """Reload the dns-policy service.

        Args:
            force_start: start the service even if it was inactive

        Raises:
            ReloadError: when encountering a SnapError
        """
        logger.debug("Reloading workload")
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
        # The location of the snap is hardcoded for now.
        # This will be soon replaced by retrieving the published snap from the snap store.
        self._install_snap_package_from_file(
            (
                f"/var/lib/juju/agents/unit-{unit_name.replace('/','-')}/charm/"
                "dns-policy-app_0.1_amd64.snap"
            )
        )

    def collect_status(
        self,
        event: ops.CollectStatusEvent,
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
            error_msg = (
                f"An exception occurred when installing {snap_path}. "
                f"Reason: {e}. Output: {e.output}"
            )
            logger.exception(error_msg)
            raise InstallError(error_msg) from e

    def get_config(self) -> dict:
        """Get the configuration of the dns-policy service.

        Returns:
            dict of configuration values

        Raises:
            ConfigureError: when encountering a SnapError
        """
        try:
            cache = snap.SnapCache()
            charmed_bind = cache[constants.DNS_SNAP_NAME]
            return charmed_bind.get(None, typed=True)
        except snap.SnapError as e:
            error_msg = (
                f"An exception occurred when configuring {constants.DNS_SNAP_NAME}. Reason: {e}"
            )
            logger.error(error_msg)
            raise ConfigureError(error_msg) from e

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

    def command(self, cmd: str) -> str:
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
            ).decode(  # nosec
                "utf-8"
            )
        except subprocess.SubprocessError as e:
            return f"Error: {e}"

    def get_api_root_token(self) -> str:
        """Get API root token."""
        try:
            res = self.command("get_root_token")
            tokens = json.loads(res)
        except json.decoder.JSONDecodeError as e:
            raise RootTokenError(str(e)) from e
        if not isinstance(tokens, dict) or "access" not in tokens or tokens["access"] == "":
            raise RootTokenError("Invalid root token!")
        return tokens["access"]

    def send_requests(self, token: str, record_requests: list[RequirerEntry]) -> bool:
        """Send record requests."""
        req = requests.post(
            "http://localhost:8080/api/requests/",
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {token}",
            },
            timeout=10,
            data=json.dumps([x.model_dump() for x in record_requests]),
        )
        return req.status_code == 200

    def create_record_request(self, token: str, record_request: models.DnsEntry) -> bool:
        """Create record request."""
        req = requests.post(
            "http://localhost:8080/api/requests/create",
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {token}",
            },
            timeout=10,
            data=record_request.json(),
        )
        return req.status_code == 201

    def get_approved_requests(self, token: str) -> list[RequirerEntry]:
        """Get approved record requests."""
        req = requests.get(
            "http://localhost:8080/api/requests/approved/",
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {token}",
            },
            timeout=10,
        )

        try:
            entries = []
            data = req.json()

            if "code" in data and data["code"] == "token_not_valid":
                raise GetApprovedRecordRequestsError(str(data))

            for rr in data:
                # The record_class is always "IN"
                rr["record_class"] = "IN"
                entry = RequirerEntry.model_validate(rr)
                entries.append(entry)
        except pydantic.ValidationError as e:
            raise GetApprovedRecordRequestsError(str(e)) from e
        return entries
