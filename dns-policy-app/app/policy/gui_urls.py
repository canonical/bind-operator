# Copyright 2025 Canonical Ltd.
# See LICENSE file for licensing details.

"""Define urls."""

from django.urls import path
from django.views.generic import RedirectView

from . import gui_views

urlpatterns = [
    path('', RedirectView.as_view(url='pending/')),
    path('pending/', gui_views.list_pending_with_actions, name='list_pending_with_actions'),
    path('all/', gui_views.list_all, name='list_all'),
    path('approved/', gui_views.list_approved, name='list_approved'),
    path('denied/', gui_views.list_denied, name='list_denied'),
    path('approver/approve/<uuid:pk>/', gui_views.approve_request, name='approve_request'),
    path('approver/deny/<uuid:pk>/', gui_views.deny_request, name='deny_request'),
]
