# Copyright 2025 Canonical Ltd.
# See LICENSE file for licensing details.

"""Admin module registration."""

from django.contrib import admin
from django.contrib.auth.models import User
from django.db.models.query import QuerySet
from django.http import HttpRequest
from django.urls import reverse

from .models import RecordRequest


@admin.action(description="Approve")
def approve(modeladmin: admin.options.ModelAdmin, request: HttpRequest, queryset: QuerySet) -> None:
    """Approve record request."""
    queryset.update(status=RecordRequest.Status.APPROVED, reviewer=request.user)


@admin.action(description="Deny")
def deny(modeladmin: admin.options.ModelAdmin, request: HttpRequest, queryset: QuerySet) -> None:
    """Deny record request."""
    queryset.update(status=RecordRequest.Status.DENIED, reviewer=request.user)


class RecordRequestAdmin(admin.ModelAdmin):
    """Define RecordRequest configuration in admin website."""

    def get_app_list(self, request: HttpRequest):
        """Get app list."""
        app_list = super().get_app_list(request)
        app_list.append({
            'name': 'Reviewer Interface',
            'url': reverse('approver_interface'),
        })
        return app_list

    def has_change_permission(self, request: HttpRequest, obj=None):
        """Change permission."""
        if obj is None:
            return request.user.is_superuser or request.user.groups.filter(name='Reviewers').exists()
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
    list_display_links = ['uuid']
    list_display = [
        'host_label',
        'domain',
        'ttl',
        'record_type',
        'record_data',
        'active',
        'status',
        'status_reason',
        'reviewer',
        'created_at',
        'last_modified_at',
        'uuid',
    ]
    list_filter = [
        'domain',
        'record_type',
        'active',
        'status',
        'reviewer',
    ]


admin.site.register(RecordRequest, RecordRequestAdmin)


class ReadOnlyUserAdmin(admin.ModelAdmin):
    """ReadOnly User for the admin site."""
    list_display = ['username', 'email', 'first_name', 'last_name', 'is_staff', 'is_active']
    list_display_links = []
    list_editable = []
    search_fields = ['username', 'email', 'first_name', 'last_name']

    def has_add_permission(self, request: HttpRequest) -> bool:
        """Check add permission."""
        return False

    def has_change_permission(self, request: HttpRequest, obj=None) -> bool:
        """Check change permission."""
        if request.user.is_superuser:
            return True
        return False

    def has_delete_permission(self, request: HttpRequest, obj=None) -> bool:
        """Check delete permission."""
        return False


admin.site.unregister(User)
admin.site.register(User, ReadOnlyUserAdmin)
