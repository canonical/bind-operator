# Copyright 2025 Canonical Ltd.
# See LICENSE file for licensing details.

"""File containing constants to be used in the charm."""

DNS_SNAP_NAME = "dns-policy-app"
DNS_SNAP_SERVICE = "nginx"
SNAP_PACKAGES = {
    DNS_SNAP_NAME: {"channel": "edge"},
}
DNS_CONFIG_DIR = f"/var/snap/{DNS_SNAP_NAME}/common/app"

PEER = "bind-peers"
DATABASE_RELATION_NAME = "database"
DATABASE_NAME = "dnspolicy"
SYSTEMD_SERVICES_PATH = "/etc/systemd/system/"
DNS_POLICY_ENDPOINTS_BASE = "http://localhost:8080/api/requests"
