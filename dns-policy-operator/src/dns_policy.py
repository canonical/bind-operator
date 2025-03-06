# Copyright 2025 Canonical Ltd.
# See LICENSE file for licensing details.

"""App charm business logic."""

import json
import logging
import subprocess  # nosec

import pydantic
import requests
from charms.bind.v0.dns_record import RequirerEntry
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


class ApiError(DnsPolicyCharmError):
    """Exception raised when an API request to the workload fails."""


class CommandError(DnsPolicyCharmError):
    """Exception raised when a command fails."""


class SnapError(DnsPolicyCharmError):
    """Exception raised when an action on the snap fails."""


class StatusError(SnapError):
    """Exception raised when unable to get the status the service."""


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

    def status(self) -> bool:
        """Get the status of the snap service.

        Returns:
            true if the service is active
        """
        try:
            cache = snap.SnapCache()
            dns_policy = cache[constants.DNS_SNAP_NAME]
            dns_policy_service = dns_policy.services[constants.DNS_SNAP_SERVICE]
            return dns_policy_service["active"]
        except snap.SnapError as e:
            error_msg = (
                f"An exception occurred when retrieving the status of {constants.DNS_SNAP_NAME}. "
                f"Reason: {e}"
            )
            logger.error(error_msg)
            raise StatusError(error_msg) from e

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

        Raises:
            CommandError if the command call errors

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
            raise CommandError(str(e)) from e

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

    def send_requests(self, token: str, record_requests: list[RequirerEntry]) -> None:
        """Send record requests.

        Args:
            token: root token for the API
            record_requests: list of record requests from the relations

        Returns:
            True if the request succeeded False otherwise

        Raises:
            ApiError if the request errors
        """
        try:
            req = requests.post(
                f"{constants.DNS_POLICY_ENDPOINTS_BASE}/",
                headers={
                    "Content-Type": "application/json",
                    "Authorization": f"Bearer {token}",
                },
                timeout=10,
                data=json.dumps([x.model_dump() for x in record_requests]),
            )
            req.raise_for_status()
        except requests.RequestException as e:
            raise ApiError(str(e)) from e

    def get_approved_requests(self, token: str) -> list[RequirerEntry]:
        """Get approved record requests.

        Args:
            token: root token for the API

        Returns:
            A list of RequirerEntry to update the relations

        Raises:
            ApiError if the request errors
        """
        try:
            req = requests.get(
                f"{constants.DNS_POLICY_ENDPOINTS_BASE}/approved/",
                headers={
                    "Content-Type": "application/json",
                    "Authorization": f"Bearer {token}",
                },
                timeout=10,
            )
        except requests.RequestException as e:
            raise ApiError(str(e)) from e

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
