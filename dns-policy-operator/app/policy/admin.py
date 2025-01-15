from django.contrib import admin
from .models import RecordRequest
from django.urls import reverse

admin.site.register(RecordRequest)


class RecordRequestAdmin(admin.ModelAdmin):
    def get_app_list(self, request):
        app_list = super().get_app_list(request)
        app_list.append({
            'name': 'Approver Interface',
            'url': reverse('approver_interface'),
        })
        return app_list
