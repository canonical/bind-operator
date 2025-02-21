# Copyright 2025 Canonical Ltd.
# See LICENSE file for licensing details.

"""Define serializers."""

from rest_framework import serializers

from .models import RecordRequest


class RecordRequestSerializer(serializers.ModelSerializer):
    """Define record request serializer."""
    uuid = serializers.UUIDField(required=True)

    class Meta:
        """Define meta of the serializer."""
        model = RecordRequest
        fields = '__all__'
