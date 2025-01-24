# Copyright 2025 Canonical Ltd.
# See LICENSE file for licensing details.

"""Test api views."""

from uuid import UUID

from django.contrib.auth.models import Group, User
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from policy.models import RecordRequest


class TestListAllRequestsView(APITestCase):
    """Test list all requests view."""

    def setUp(self):
        """Set up."""
        self.approver_group = Group.objects.create(name='Approver')
        self.user = User.objects.create_user('testuser', 'testuser@example.com', 'password')
        self.user.groups.add(self.approver_group)
        self.record_request = RecordRequest.objects.create(status='pending')

    def test_get_all_requests(self):
        """Test get all requests."""
        self.client.login(username='testuser', password='password')
        url = reverse('api_list_all')
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.json()), 1)

    def test_unauthenticated_access(self):
        """Test unauthenticated access."""
        self.client.logout()
        url = reverse('api_list_all')
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)


class TestListPendingRequestsView(APITestCase):
    """Test list pending requests view."""

    def setUp(self):
        """Set up."""
        self.approver_group = Group.objects.create(name='Approver')
        self.user = User.objects.create_user('testuser', 'testuser@example.com', 'password')
        self.user.groups.add(self.approver_group)
        self.pending_request = RecordRequest.objects.create(status='pending')
        self.approved_request = RecordRequest.objects.create(status='approved')

    def test_get_pending_requests(self):
        """Test get pending requests."""
        self.client.login(username='testuser', password='password')
        url = reverse('api_list_pending')
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.json()), 1)

    def test_unauthenticated_access(self):
        """Test unauthenticated access."""
        self.client.logout()
        url = reverse('api_list_pending')
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)


class TestListApprovedRequestsView(APITestCase):
    """Test list approved request view."""

    def setUp(self):
        """Set up."""
        self.approver_group = Group.objects.create(name='Approver')
        self.user = User.objects.create_user('testuser', 'testuser@example.com', 'password')
        self.user.groups.add(self.approver_group)
        self.approved_request = RecordRequest.objects.create(status='approved')
        self.pending_request = RecordRequest.objects.create(status='pending')

    def test_get_approved_requests(self):
        """Test get approved requests."""
        self.client.login(username='testuser', password='password')
        url = reverse('api_list_approved')
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.json()), 1)

    def test_unauthenticated_access(self):
        """Test unauthenticated access."""
        self.client.logout()
        url = reverse('api_list_approved')
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)


class TestListDeniedRequestsView(APITestCase):
    """Test list denied request view."""

    def setUp(self):
        """Set up."""
        self.approver_group = Group.objects.create(name='Approver')
        self.user = User.objects.create_user('testuser', 'testuser@example.com', 'password')
        self.user.groups.add(self.approver_group)
        self.denied_request = RecordRequest.objects.create(status='denied')
        self.approved_request = RecordRequest.objects.create(status='approved')

    def test_get_denied_requests(self):
        """Test get denied requests."""
        self.client.login(username='testuser', password='password')
        url = reverse('api_list_denied')
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.json()), 1)

    def test_unauthenticated_access(self):
        """Test unauthenticated access."""
        self.client.logout()
        url = reverse('api_list_denied')
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

class TestApproveRequestView(APITestCase):
    """Test Approve request view."""

    def setUp(self):
        """Set up."""
        self.approver_group = Group.objects.create(name='Approver')
        self.user = User.objects.create_user('testuser', 'testuser@example.com', 'password')
        self.user.groups.add(self.approver_group)
        self.request = RecordRequest.objects.create(status='pending')
        self.some_uuid = UUID('497dcba3-ecbf-4587-a2dd-5eb0665e6880')

    def test_approve_request(self):
        """Test approve request."""
        self.client.login(username='testuser', password='password')
        url = reverse('api_request_approve', args=[self.request.pk])
        response = self.client.patch(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(RecordRequest.objects.get(pk=self.request.pk).status, 'approved')

    def test_unauthenticated_access(self):
        """Test unauthenticated access."""
        self.client.logout()
        url = reverse('api_request_approve', args=[self.request.pk])
        response = self.client.patch(url)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_unexistent_request_id(self):
        """Test unexistent request id."""
        self.client.login(username='testuser', password='password')
        url = reverse('api_request_approve', args=[self.some_uuid])
        response = self.client.patch(url)
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)


class TestDenyRequestView(APITestCase):
    """Test deny request view."""

    def setUp(self):
        """Set up."""
        self.approver_group = Group.objects.create(name='Approver')
        self.user = User.objects.create_user('testuser', 'testuser@example.com', 'password')
        self.user.groups.add(self.approver_group)
        self.request = RecordRequest.objects.create(status='pending')
        self.some_uuid = UUID('497dcba3-ecbf-4587-a2dd-5eb0665e6880')

    def test_deny_request(self):
        """Test deny request."""
        self.client.login(username='testuser', password='password')
        url = reverse('api_request_deny', args=[self.request.pk])
        response = self.client.patch(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(RecordRequest.objects.get(pk=self.request.pk).status, 'denied')

    def test_unauthenticated_access(self):
        """Test unauthenticated access."""
        self.client.logout()
        url = reverse('api_request_deny', args=[self.request.pk])
        response = self.client.patch(url)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_unexistent_request_id(self):
        """Test unexistent request id."""
        self.client.login(username='testuser', password='password')
        url = reverse('api_request_deny', args=[self.some_uuid])
        response = self.client.patch(url)
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
