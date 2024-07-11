# Copyright 2024 Canonical Ltd.
# See LICENSE file for licensing details.

"""Unit tests for the bind module."""

import uuid

import pytest
from charms.bind.v0 import dns_record

import bind
import exceptions
import models


@pytest.mark.parametrize(
    "integration_datasets, zones_name, nonconflicting, conflicting",
    (
        (
            [
                [
                    models.DnsEntry(
                        domain="dns.test",
                        host_label="admin",
                        ttl=600,
                        record_class="IN",
                        record_type="A",
                        record_data="42.42.42.42",
                    ),
                    models.DnsEntry(
                        domain="dns.test",
                        host_label="admin",
                        ttl=600,
                        record_class="IN",
                        record_type="A",
                        record_data="42.42.42.42",
                    ),
                ],
                [
                    models.DnsEntry(
                        domain="dns.test",
                        host_label="admin",
                        ttl=600,
                        record_class="IN",
                        record_type="A",
                        record_data="42.42.42.42",
                    ),
                    models.DnsEntry(
                        domain="dns2.test",
                        host_label="admin",
                        ttl=600,
                        record_class="IN",
                        record_type="A",
                        record_data="42.42.42.43",
                    ),
                ],
            ],
            {"dns.test", "dns2.test"},
            {"admin.dns.test", "admin.dns2.test"},
            set(),
        ),
        (
            [
                [
                    models.DnsEntry(
                        domain="dns.test",
                        host_label="admin",
                        ttl=600,
                        record_class="IN",
                        record_type="A",
                        record_data="42.42.42.42",
                    ),
                    models.DnsEntry(
                        domain="dns2.test",
                        host_label="admin",
                        ttl=600,
                        record_class="IN",
                        record_type="A",
                        record_data="41.41.41.41",
                    ),
                    models.DnsEntry(
                        domain="dns.test",
                        host_label="admin2",
                        ttl=600,
                        record_class="IN",
                        record_type="A",
                        record_data="40.40.40.40",
                    ),
                ],
            ],
            {"dns.test", "dns2.test"},
            {"admin.dns.test", "admin.dns2.test", "admin2.dns.test"},
            set(),
        ),
        (
            [
                [
                    models.DnsEntry(
                        domain="dns.test",
                        host_label="admin",
                        ttl=600,
                        record_class="IN",
                        record_type="A",
                        record_data="42.42.42.42",
                    ),
                    models.DnsEntry(
                        domain="dns.test",
                        host_label="admin",
                        ttl=600,
                        record_class="IN",
                        record_type="A",
                        record_data="41.41.41.41",
                    ),
                ],
            ],
            {"dns.test"},
            set(),
            {"admin.dns.test"},
        ),
    ),
    ids=(
        "Duplicate entry",
        "No conflicts",
        "Basic conflict",
    ),
)
def test_get_conflicts(integration_datasets, zones_name, nonconflicting, conflicting):
    """
    arrange: prepare some integration datasets
    act: generate conflicting sets of DnsEntries
    assert: that the generate set is what we expected
    """
    record_requirers_data = []
    for requirer in integration_datasets:
        requirer_entries = [
            dns_record.RequirerEntry(
                domain=e.domain,
                host_label=e.host_label,
                ttl=e.ttl,
                record_class=e.record_class,
                record_type=e.record_type,
                record_data=e.record_data,
                uuid=uuid.uuid4(),
            )
            for e in requirer
        ]
        record_requirer_data = dns_record.DNSRecordRequirerData(
            dns_entries=requirer_entries,
            service_account="fakeserviceaccount",
        )
        record_requirers_data.append(record_requirer_data)

    bind_service = bind.BindService()

    zones = bind_service._dns_record_relations_data_to_zones(  # pylint: disable=protected-access
        [(record_requirer_data, None) for record_requirer_data in record_requirers_data]
    )
    assert zones_name == {zone.domain for zone in zones}

    output = bind_service._get_conflicts(zones)  # pylint: disable=protected-access
    assert nonconflicting == {f"{e.host_label}.{e.domain}" for e in output[0]}
    assert conflicting == {f"{e.host_label}.{e.domain}" for e in output[1]}


@pytest.mark.parametrize(
    "zonefile_content, metadata, error",
    (
        ("", {}, exceptions.EmptyZoneFileMetadataError),
        ("sometext; someothertext", {}, exceptions.EmptyZoneFileMetadataError),
        ("$ORIGIN test.dns.test.; HASH:1234", {"HASH": "1234"}, None),
        (
            "$ORIGIN test.dns.test.; HASH:1234\n$ORIGIN test2.dns.test.; PLOP:plop",
            {"HASH": "1234", "PLOP": "plop"},
            None,
        ),
        (
            "$ORIGIN test.dns.test.; HASH:1234 HASH:4567",
            {},
            exceptions.DuplicateMetadataEntryError,
        ),
        (
            "$ORIGIN test.dns.test.; HASH:1234\n$ORIGIN test2.dns.test.; HASH:4567",
            {},
            exceptions.DuplicateMetadataEntryError,
        ),
        ("$ORIGIN test.dns.test.; HASH::", None, exceptions.InvalidZoneFileMetadataError),
        ("$ORIGIN test.dns.test.;    ", {"HASH": "1234"}, exceptions.EmptyZoneFileMetadataError),
        (
            "\n\nsometext\n\n$ORIGIN test.dns.test.; HASH:1234 PLOP:plop\nsomeothertext",
            {"HASH": "1234", "PLOP": "plop"},
            None,
        ),
    ),
)
def test_get_zonefile_metadata(zonefile_content: str, metadata: dict[str, str], error):
    """
    arrange: nothing
    act: get the metadata from the zonefile_content
    assert: the correct metadata should be found or the correct exception raised
    """
    bind_service = bind.BindService()
    if error is not None:
        with pytest.raises(error):
            bind_service._get_zonefile_metadata(  # pylint: disable=protected-access
                zonefile_content
            )
    else:
        assert metadata == bind_service._get_zonefile_metadata(  # pylint: disable=protected-access
            zonefile_content
        )
