# Copyright 2025 Canonical Ltd.
# See LICENSE file for licensing details.

"""Define urls."""

from django.urls import path

from . import api_views

urlpatterns = [
    path('requests/all/', api_views.ListAllRequestsView.as_view(), name="api_list_all"),
    path('requests/pending/', api_views.ListPendingRequestsView.as_view(), name="api_list_pending"),
    path('requests/approved/', api_views.ListApprovedRequestsView.as_view(), name="api_list_approved"),
    path('requests/denied/', api_views.ListDeniedRequestsView.as_view(), name="api_list_denied"),
    path('requests/<uuid:pk>/approve/', api_views.ApproveRequestView.as_view(), name="api_request_approve"),
    path('requests/<uuid:pk>/deny/', api_views.DenyRequestView.as_view(), name="api_request_deny"),
    path('requests/create', api_views.CreateRecordRequestView.as_view(), name='create_record_request'),
]
