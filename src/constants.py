# Copyright 2024 Canonical Ltd.
# See LICENSE file for licensing details.

"""File containing constants to be used in the charm."""

DNS_SNAP_NAME = "charmed-bind"
SNAP_PACKAGES = {
    DNS_SNAP_NAME: {"channel": "edge"},
}
DNS_CONFIG_DIR = f"/var/snap/{DNS_SNAP_NAME}/current/etc/bind"

ZONE_HEADER_TEMPLATE = """$ORIGIN {zone}.
$TTL 600
@ IN SOA {zone}. mail.{zone}. ( {serial} 1d 1h 1h 10m )
@ IN NS localhost.
"""

ZONE_RECORD_TEMPLATE = "{host_label} {record_class} {record_type} {record_data}\n"

NAMED_CONF_ZONE_DEF_TEMPLATE = (
    'zone "{name}" IN {{ type primary; file "{absolute_path}"; allow-update {{ none; }}; }};\n'
)
