# Copyright 2025 Canonical Ltd.
# See LICENSE file for licensing details.

"""Define app."""

from django.apps import AppConfig


class PolicyConfig(AppConfig):
    """Define policy app configuration."""
    default_auto_field = "django.db.models.BigAutoField"
    name = "policy"
