"""notifications/urls.py"""

from django.urls import path
from . import views

urlpatterns = [
    path("admin/send-bulk/", views.send_bulk_sms, name="admin-bulk-sms"),
]
