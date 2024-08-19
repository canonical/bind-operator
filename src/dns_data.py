# Copyright 2024 Canonical Ltd.
# See LICENSE file for licensing details.

"""DNS data logic."""

import logging
import typing

from charms.bind.v0.dns_record import (
    DNSProviderData,
    DNSRecordProviderData,
    DNSRecordRequirerData,
    RequirerEntry,
    Status,
)

import models

logger = logging.getLogger(__name__)


def create_dns_record_provider_data(
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
    zones = dns_record_relations_data_to_zones(relation_data)
    nonconflicting, conflicting = get_conflicts(zones)
    statuses = []
    for record_requirer_data, _ in relation_data:
        for requirer_entry in record_requirer_data.dns_entries:
            dns_entry = models.create_dns_entry_from_requirer_entry(requirer_entry)
            if dns_entry in nonconflicting:
                statuses.append(DNSProviderData(uuid=requirer_entry.uuid, status=Status.APPROVED))
                continue
            if dns_entry in conflicting:
                statuses.append(DNSProviderData(uuid=requirer_entry.uuid, status=Status.CONFLICT))
                continue
            statuses.append(DNSProviderData(uuid=requirer_entry.uuid, status=Status.UNKNOWN))
    return DNSRecordProviderData(dns_entries=statuses)


def has_changed(
    relation_data: list[tuple[DNSRecordRequirerData, DNSRecordProviderData]],
    topology: models.Topology | None,
    last_valid_state: dict[str, typing.Any],
) -> bool:
    """Check if the dns data has changed.

    This could be a change in a zone, or a removal/addition of a zone,
    or a change in the topology.
    We use the state.json file to compare the state when
    the last configuration was minted to the current one.

    Args:
        relation_data: input relation data
        topology: Topology of the current deployment
        last_valid_state: The last valid state, deserialized from a state.json file

    Returns:
        True if a zone has changed, False otherwise.
    """
    zones = dns_record_relations_data_to_zones(relation_data)

    if "zones" not in last_valid_state or {models.Zone(**z) for z in last_valid_state["zones"]} != set(zones):
        return True

    if (
        topology is not None
        and "topology" in last_valid_state
        and hash(topology) != hash(last_valid_state["topology"])
    ):
        return True

    return False


def record_requirer_data_to_zones(
    record_requirer_data: DNSRecordRequirerData,
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
        zone = models.Zone(domain=domain, entries=set())
        for entry in entries:
            zone.entries.add(models.create_dns_entry_from_requirer_entry(entry))
        zones.append(zone)
    return zones


def get_conflicts(zones: list[models.Zone]) -> tuple[set[models.DnsEntry], set[models.DnsEntry]]:
    """Return conflicting and non-conflicting entries.

    Args:
        zones: list of the zones to check

    Returns:
        A tuple containing the non-conflicting and conflicting entries
    """
    entries: set[models.DnsEntry] = {e for z in zones for e in z.entries}
    conflicting_entries: set[models.DnsEntry] = set()
    for entry in entries:
        for e in entries:
            if entry.conflicts(e) and entry != e:
                conflicting_entries.add(entry)

    return (entries - conflicting_entries, conflicting_entries)


def dns_record_relations_data_to_zones(
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
        for new_zone in record_requirer_data_to_zones(record_requirer_data):
            if new_zone.domain in zones:
                zones[new_zone.domain].entries.update(new_zone.entries)
            else:
                zones[new_zone.domain] = new_zone
    return list(zones.values())
