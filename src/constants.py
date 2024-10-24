# Copyright 2024 Canonical Ltd.
# See LICENSE file for licensing details.

"""File containing constants to be used in the charm."""

DNS_SNAP_NAME = "charmed-bind"
DNS_SNAP_SERVICE = "named"
SNAP_PACKAGES = {
    DNS_SNAP_NAME: {"channel": "edge"},
}
DNS_CONFIG_DIR = f"/var/snap/{DNS_SNAP_NAME}/common/bind"

ZONE_SERVICE_NAME = "service.test"

ZONE_SERVICE = f"""$ORIGIN {ZONE_SERVICE_NAME}.
$TTL 600
@ IN SOA {ZONE_SERVICE_NAME}. mail.{ZONE_SERVICE_NAME}. ( {{serial}} 1d 1h 1h 10m )
@ IN NS localhost.
status IN TXT "ok"
"""

ZONE_HEADER_TEMPLATE = """$ORIGIN {zone}.
$TTL 600
@ IN SOA {zone}. mail.{zone}. ( {serial} 1d 1h 1h 10m )
@ IN NS localhost.
"""

ZONE_RECORD_TEMPLATE = "{host_label} {record_class} {record_type} {record_data}\n"

NAMED_CONF_PRIMARY_ZONE_DEF_TEMPLATE = (
    'zone "{name}" IN {{ '
    'type primary; file "{absolute_path}"; allow-update {{ none; }}; '
    "also-notify {{ {zone_transfer_ips} }}; "
    "allow-transfer {{ {zone_transfer_ips} }}; }};\n"
)

NAMED_CONF_SECONDARY_ZONE_DEF_TEMPLATE = (
    'zone "{name}" IN {{ '
    'type secondary; file "{absolute_path}"; '
    "masterfile-format text; "
    "masterfile-style full; "
    "primaries {{ {primary_ip} }}; }};\n"
)

SYSTEMD_SERVICES_PATH = "/etc/systemd/system/"

DISPATCH_EVENT_SERVICE = """[Unit]
Description=Dispatch the {event} event on {unit}

[Service]
Type=oneshot
ExecStart=/usr/bin/timeout {timeout} /usr/bin/bash -c '/usr/bin/juju-exec "{unit}" "JUJU_DISPATCH_PATH={event} ./dispatch"'

[Install]
WantedBy=multi-user.target
"""

SYSTEMD_SERVICE_TIMER = """[Unit]
Description=Run {service} weekly
Requires={service}.service

[Timer]
Unit={service}.service
OnCalendar=*-*-* *:0/{interval}
Persistent=true

[Install]
WantedBy=timers.target
"""

PEER = "bind-peers"
