# Copyright 2025 Canonical Ltd.
# See LICENSE file for licensing details.

"""File containing templates used in the charm."""

# Let's disable too long lines for templates
# pylint: disable=line-too-long

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
