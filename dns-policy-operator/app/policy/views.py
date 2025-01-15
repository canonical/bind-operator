from django.shortcuts import render, redirect
from django.contrib.admin.views.decorators import staff_member_required
from .models import RecordRequest

@staff_member_required
def list_pending_with_action(request):
    record_requests = RecordRequest.objects.filter(status='pending')
    return render(request, 'list_pending_with_action.html', {'record_requests': record_requests})

@staff_member_required
def list_approved(request):
    record_requests = RecordRequest.objects.filter(status='approved')
    return render(request, 'list_record_requests.html', {'record_requests': record_requests})

@staff_member_required
def list_denied(request):
    record_requests = RecordRequest.objects.filter(status='denied')
    return render(request, 'list_record_requests.html', {'record_requests': record_requests})

@staff_member_required
def list_all(request):
    record_requests = RecordRequest.objects.filter()
    return render(request, 'list_record_requests.html', {'record_requests': record_requests})

@staff_member_required
def approve_request(request, pk):
    record_request = RecordRequest.objects.get(pk=pk)
    record_request.status = 'approved'
    record_request.approver = request.user
    record_request.save()
    return redirect('approver_interface')

@staff_member_required
def deny_request(request, pk):
    record_request = RecordRequest.objects.get(pk=pk)
    record_request.status = 'denied'
    record_request.save()
    return redirect('approver_interface')
