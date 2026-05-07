"""payments/views.py"""

import base64
import logging
from django.conf import settings
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated, AllowAny, IsAdminUser
from rest_framework.response import Response
from rest_framework import generics, serializers
from drf_spectacular.utils import extend_schema

from apps.policies.models import PolicyApplication
from .models import Transaction
from .services import ClickPaymentService, PaymePaymentService, UzumPaymentService, complete_demo_payment

logger = logging.getLogger(__name__)


class CreateInvoiceSerializer(serializers.Serializer):
    application_id = serializers.UUIDField()
    provider = serializers.ChoiceField(choices=["CLICK", "PAYME", "UZUM"])


@extend_schema(tags=["Payments"])
@api_view(["POST"])
@permission_classes([IsAuthenticated])
def create_invoice(request):
    """To'lov uchun invoice (link) yaratish"""
    serializer = CreateInvoiceSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    data = serializer.validated_data

    try:
        application = PolicyApplication.objects.get(
            id=data["application_id"], user=request.user
        )
    except PolicyApplication.DoesNotExist:
        return Response({"detail": "Ariza topilmadi."}, status=404)

    if application.status not in [
        PolicyApplication.Status.DRAFT,
        PolicyApplication.Status.PENDING_PAYMENT,
    ]:
        return Response(
            {"detail": f"Bu ariza to'lov uchun mavjud emas. Status: {application.status}"},
            status=400,
        )

    provider = data["provider"]
    try:
        if provider == "CLICK":
            service = ClickPaymentService()
        elif provider == "PAYME":
            service = PaymePaymentService()
        elif provider == "UZUM":
            service = UzumPaymentService()
        else:
            return Response({"detail": "Noto'g'ri to'lov provayderi."}, status=400)

        result = service.create_invoice(application)
        return Response(result)
    except Exception as e:
        logger.error(f"[Invoice] Error: {e}")
        return Response({"detail": "Invoice yaratishda xatolik."}, status=500)


@extend_schema(tags=["Payments"])
@api_view(["POST"])
@permission_classes([IsAuthenticated])
def demo_complete_payment(request):
    """Demo/test rejim: real payment callbacksiz arizani to'langan qilib, polis PDF yaratadi."""
    serializer = CreateInvoiceSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    data = serializer.validated_data

    try:
        application = PolicyApplication.objects.get(
            id=data["application_id"], user=request.user
        )
    except PolicyApplication.DoesNotExist:
        return Response({"detail": "Ariza topilmadi."}, status=404)

    try:
        txn = complete_demo_payment(application, data["provider"])
        application.refresh_from_db()
        return Response({
            "detail": "Demo to'lov muvaffaqiyatli yakunlandi.",
            "transaction_id": str(txn.id),
            "policy_id": str(application.id),
            "status": application.status,
            "pdf_url": application.policy_pdf.url if application.policy_pdf else None,
        })
    except Exception as e:
        logger.error(f"[Demo payment] Error: {e}")
        return Response({"detail": str(e)}, status=400)


# ── Click Callback ─────────────────────────────────────────────────────────────

@extend_schema(tags=["Payments - Callbacks"])
@api_view(["POST"])
@permission_classes([AllowAny])
def click_callback(request):
    """Click to'lov tizimidan kelgan callback (webhook)"""
    service = ClickPaymentService()
    result = service.handle_callback(request.data)
    return Response(result)


# ── Payme JSON-RPC ─────────────────────────────────────────────────────────────

@extend_schema(tags=["Payments - Callbacks"])
@api_view(["POST"])
@permission_classes([AllowAny])
def payme_endpoint(request):
    """
    Payme JSON-RPC endpoint.
    Basic Auth tekshirish: merchant_id:key
    """
    # Basic Auth tekshirish
    auth_header = request.META.get("HTTP_AUTHORIZATION", "")
    if auth_header.startswith("Basic "):
        try:
            decoded = base64.b64decode(auth_header[6:]).decode()
            _, key = decoded.split(":", 1)
            if key != settings.PAYME_SECRET_KEY:
                return Response(
                    {"error": {"code": -32504, "message": "Insufficient privilege"}},
                    status=403,
                )
        except Exception:
            return Response({"error": {"code": -32504, "message": "Bad auth"}}, status=403)
    else:
        return Response({"error": {"code": -32504, "message": "Unauthorized"}}, status=403)

    body = request.data
    method = body.get("method")
    params = body.get("params", {})
    rpc_id = body.get("id", 1)

    service = PaymePaymentService()
    result = service.handle_rpc(method, params)
    return Response({"id": rpc_id, **result})


# ── Admin ─────────────────────────────────────────────────────────────────────

class TransactionSerializer(serializers.ModelSerializer):
    class Meta:
        model = Transaction
        fields = "__all__"


class AdminTransactionListView(generics.ListAPIView):
    """Admin: barcha tranzaksiyalar"""
    permission_classes = [IsAdminUser]
    serializer_class = TransactionSerializer
    queryset = Transaction.objects.select_related("application").all()
    filterset_fields = ["provider", "status"]
    search_fields = ["provider_transaction_id", "application__plate_number"]
    ordering_fields = ["created_at", "amount"]
