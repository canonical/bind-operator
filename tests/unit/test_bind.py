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
    "integration_datasets, nonconflicting, conflicting",
    (
        (
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
            {0},
            set(),
        ),
        (
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
            {0, 1, 2},
            set(),
        ),
        (
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
            set(),
            {0, 1},
        ),
    ),
    ids=(
        "Duplicate entry",
        "No conflicts",
        "Basic conflict",
    ),
)
def test_get_conflicts(integration_datasets, nonconflicting, conflicting):
    """
    arrange: prepare some integration dataset
    act: generate conflicting sets of DnsEntries
    assert: that the generate set is what we expected
    """
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
        for e in integration_datasets
    ]
    record_requirer_data = dns_record.DNSRecordRequirerData(
        dns_entries=requirer_entries,
        service_account="fakeserviceaccount",
    )

    bind_service = bind.BindService()

    zones = bind_service._record_requirer_data_to_zones(  # pylint: disable=protected-access
        record_requirer_data
    )
    output = bind_service._get_conflicts(zones)  # pylint: disable=protected-access

    nonconflicting = {e for i, e in enumerate(integration_datasets) if i in nonconflicting}
    conflicting = {e for i, e in enumerate(integration_datasets) if i in conflicting}

    assert nonconflicting == output[0]
    assert conflicting == output[1]


@pytest.mark.parametrize(
    "zonefile_content, metadata, error",
    (
        ("", {}, exceptions.EmptyZoneFileMetadataError),
        ("sometext; someothertext", {}, exceptions.EmptyZoneFileMetadataError),
        ("$ORIGIN test.dns.test.; HASH:1234", {"HASH": "1234"}, None),
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
