# Copyright 2024 Canonical Ltd.
# See LICENSE file for licensing details.

"""Define views."""

from django.contrib.admin.views.decorators import staff_member_required
from django.shortcuts import redirect, render

from .models import RecordRequest


@staff_member_required
def list_pending_with_action(request):
    """Define list requests view."""
    record_requests = RecordRequest.objects.filter(status='pending')
    return render(request, 'list_pending_with_action.html', {'record_requests': record_requests})


@staff_member_required
def list_approved(request):
    """Define list approved requests view."""
    record_requests = RecordRequest.objects.filter(status='approved')
    return render(request, 'list_record_requests.html', {'record_requests': record_requests})


@staff_member_required
def list_denied(request):
    """Define list denied requests view."""
    record_requests = RecordRequest.objects.filter(status='denied')
    return render(request, 'list_record_requests.html', {'record_requests': record_requests})


@staff_member_required
def list_all(request):
    """Define list all requests view."""
    record_requests = RecordRequest.objects.filter()
    return render(request, 'list_record_requests.html', {'record_requests': record_requests})


@staff_member_required
def approve_request(request, pk):
    """Define approve requests view."""
    record_request = RecordRequest.objects.get(pk=pk)
    record_request.status = 'approved'
    record_request.approver = request.user
    record_request.save()
    return redirect('list_pending_with_action')


@staff_member_required
def deny_request(request, pk):
    """Define deny requests view."""
    record_request = RecordRequest.objects.get(pk=pk)
    record_request.status = 'denied'
    record_request.save()
    return redirect('list_pending_with_action')
