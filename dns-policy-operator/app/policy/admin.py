# Copyright 2025 Canonical Ltd.
# See LICENSE file for licensing details.

"""Admin module registration."""

from django.contrib import admin
from django.urls import reverse
from django.contrib.auth.models import User

from .models import RecordRequest


@admin.action(description="Approve")
def approve(modeladmin, request, queryset):
    """Approve record request."""
    queryset.update(status="approved", reviewer=request.user)


@admin.action(description="Deny")
def deny(modeladmin, request, queryset):
    """Deny record request."""
    queryset.update(status="denied", reviewer=request.user)


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

    def has_change_permission(self, request, obj=None):
        """Change permission."""
        if obj is None:
            return request.user.is_superuser or request.user.groups.filter(name='Approvers').exists()
        else:
            return request.user.is_superuser

    def has_delete_permission(self, request, obj=None):
        """Delete permission."""
        return request.user.is_superuser

    actions = [approve, deny]
    list_per_page = 20
    list_max_show_all = 200
    search_fields = ['host_label', 'domain', 'record_type', 'record_data', 'status']
    search_help_text = 'Search by status, host label, domain, record type, or record data'


admin.site.register(RecordRequest, RecordRequestAdmin)
