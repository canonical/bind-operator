# Copyright 2025 Canonical Ltd.
# See LICENSE file for licensing details.

"""Define models."""

import uuid

from django.contrib.auth.models import User
from django.db import models
from django.utils import timezone


class RecordRequest(models.Model):
    """Record request model."""

    class Status(models.TextChoices):
        """Record request statuses."""
        PENDING = 'pending'
        APPROVED = 'approved'
        DENIED = 'denied'
        INVALID = 'invalid'
        FAILED = 'failed'
        PUBLISHED = 'published'

    uuid = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    domain = models.CharField(max_length=255)
    host_label = models.CharField(max_length=255)
    ttl = models.IntegerField(null=True)
    record_type = models.CharField(max_length=10)
    record_data = models.CharField(max_length=255)
    active = models.BooleanField(default=False)
    requirer_id = models.CharField(max_length=255, null=True)
    status = models.CharField(max_length=50, choices=Status.choices)
    status_reason = models.CharField(max_length=255, null=True)
    reviewer = models.ForeignKey(User, null=True, on_delete=models.SET_NULL)
    created_at = models.DateTimeField(default=timezone.now)
    last_modified_at = models.DateTimeField(default=timezone.now)

    def __str__(self):
        """Record request model string representation."""
        return f"[{self.status}] {self.host_label} {self.domain} {self.ttl} {self.record_type} {self.record_data}"
