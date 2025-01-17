# Copyright 2024 Canonical Ltd.
# See LICENSE file for licensing details.

"""Define urls."""

from django.urls import path

from . import views

urlpatterns = [
    path('pending/', views.list_pending_with_action, name='list_pending_with_action'),
    path('all/', views.list_all, name='list_all'),
    path('approved/', views.list_approved, name='list_approved'),
    path('denied/', views.list_denied, name='list_denied'),
    path('approver/approve/<pk>/', views.approve_request, name='approve_request'),
    path('approver/deny/<pk>/', views.deny_request, name='deny_request'),
]
