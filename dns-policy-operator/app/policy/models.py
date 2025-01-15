from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone
import uuid


class RecordRequest(models.Model):
    uuid = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    domain = models.CharField(max_length=255)
    host_label = models.CharField(max_length=255)
    ttl = models.IntegerField(null=True)
    record_type = models.CharField(max_length=10)
    record_data = models.CharField(max_length=255)
    requirer_id = models.CharField(max_length=255)
    status = models.CharField(max_length=50)
    status_reason = models.CharField(max_length=255, null=True)
    approver = models.ForeignKey(User, null=True, on_delete=models.SET_NULL)
    created_at = models.DateTimeField(default=timezone.now)
    last_modified_at = models.DateTimeField(default=timezone.now)

    def __str__(self):
        return f"{self.domain} - {self.host_label}"
