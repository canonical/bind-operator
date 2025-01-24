# Copyright 2025 Canonical Ltd.
# See LICENSE file for licensing details.

"""Admin module registration."""

from django.contrib import admin
from django.urls import reverse

from .models import RecordRequest

admin.site.register(RecordRequest)


class RecordRequestAdmin(admin.ModelAdmin):
    """Define RecordRequest configuration in admin website."""

    def get_app_list(self, request):
        """Get app list."""
        app_list = super().get_app_list(request)
        app_list.append({
            'name': 'Approver Interface',
            'url': reverse('approver_interface'),
        })
        return app_list
