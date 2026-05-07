"""notifications/views.py & urls.py placeholder"""

from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAdminUser
from rest_framework.response import Response
from drf_spectacular.utils import extend_schema


@extend_schema(tags=["Notifications"])
@api_view(["POST"])
@permission_classes([IsAdminUser])
def send_bulk_sms(request):
    """Admin: ommaviy SMS yuborish (masalan: eslatmalar)"""
    from apps.payments.tasks import send_expiry_reminders
    send_expiry_reminders.delay()
    return Response({"detail": "Vazifa navbatga qo'shildi."})
