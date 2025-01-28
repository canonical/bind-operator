# Copyright 2025 Canonical Ltd.
# See LICENSE file for licensing details.

"""Test gui views."""

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

from policy.models import RecordRequest


class TestGUIViews(TestCase):
    """Test gui views."""

    def setUp(self):
        """Set up."""
        self.user = User.objects.create_superuser('testuser', 'testuser@example.com', 'password')
        self.client.force_login(self.user)
        self.record_request = RecordRequest.objects.create(
            host_label='test',
            domain='example.com',
            ttl=3600,
            record_type='A',
            record_data='192.0.2.1',
            status='pending'
        )

    def test_list_pending_with_action(self):
        """Test list_pending_with_action view."""
        url = reverse('list_pending_with_action')
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'list_pending_with_action.html')

    def test_list_all(self):
        "Test list_all view."""
        url = reverse('list_all')
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'list_record_requests.html')

    def test_list_approved(self):
        """Test list_approved view."""
        url = reverse('list_approved')
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'list_record_requests.html')

    def test_list_denied(self):
        """Test list_denied view."""
        url = reverse('list_denied')
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'list_record_requests.html')

    def test_approve_request(self):
        """Test approve_request view."""
        url = reverse('approve_request', args=[self.record_request.pk])
        response = self.client.get(url)
        self.assertEqual(response.status_code, 302)
        self.record_request.refresh_from_db()
        self.assertEqual(self.record_request.status, 'approved')

    def test_deny_request(self):
        """Test deny request."""
        url = reverse('deny_request', args=[self.record_request.pk])
        response = self.client.get(url)
        self.assertEqual(response.status_code, 302)
        self.record_request.refresh_from_db()
        self.assertEqual(self.record_request.status, 'denied')

    def test_unauthenticated_access(self):
        """Test unauthenticated access."""
        self.client.logout()
        url = reverse('list_pending_with_action')
        response = self.client.get(url)
        self.assertEqual(response.status_code, 302)
