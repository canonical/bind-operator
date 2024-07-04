# Copyright 2024 Canonical Ltd.
# See LICENSE file for licensing details.

"""Exceptions used by the bind charm."""


class SnapError(Exception):
    """Exception raised when an action on the snap fails.

    Attrs:
        msg (str): Explanation of the error.
    """

    def __init__(self, msg: str):
        """Initialize a new instance of the SnapError exception.

        Args:
            msg (str): Explanation of the error.
        """
        self.msg = msg


class InvalidZoneFileMetadataError(Exception):
    """Exception raised when a zonefile has invalid metadata.

    Attrs:
        msg (str): Explanation of the error.
    """

    def __init__(self, msg: str):
        """Initialize a new instance of the InvalidZoneFileMetadataError exception.

        Args:
            msg (str): Explanation of the error.
        """
        self.msg = msg


class EmptyZoneFileMetadataError(Exception):
    """Exception raised when a zonefile has no metadata.

    Attrs:
        msg (str): Explanation of the error.
    """

    def __init__(self, msg: str):
        """Initialize a new instance of the EmptyZoneFileMetadataError exception.

        Args:
            msg (str): Explanation of the error.
        """
        self.msg = msg
