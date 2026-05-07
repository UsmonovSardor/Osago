"""policies/views.py"""

import logging
from datetime import date
from dateutil.relativedelta import relativedelta
from django.db import transaction
from django.http import FileResponse
from rest_framework import generics, status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated, IsAdminUser
from rest_framework.response import Response
from drf_spectacular.utils import extend_schema

from .models import PolicyApplication
from .serializers import (
    PremiumCalculateSerializer, PolicyApplicationCreateSerializer,
    PolicyApplicationSerializer, AdminPolicySerializer,
)
from .services import OsagoAPIService, OsagoAPIError

logger = logging.getLogger(__name__)


@extend_schema(tags=["Policies"])
@api_view(["POST"])
@permission_classes([IsAuthenticated])
def calculate_premium(request):
    """
    Avtomobil raqami va tex-pasport orqali sug'urta mukofotini hisoblash.
    Natija 10 daqiqaga keshlanadi.
    """
    serializer = PremiumCalculateSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    data = serializer.validated_data

    service = OsagoAPIService()
    try:
        # Avval avtomobil ma'lumotlarini olish
        vehicle_info = service.get_vehicle_info(
            data["plate_number"], data["tech_passport"]
        )
        # Narx hisoblash
        premium_data = service.calculate_premium(
            data["plate_number"], data["tech_passport"], data["period_months"]
        )
        return Response({
            "vehicle": vehicle_info,
            "premium": premium_data,
            "period_months": data["period_months"],
        })
    except OsagoAPIError as e:
        return Response({"detail": str(e)}, status=status.HTTP_502_BAD_GATEWAY)


class PolicyApplicationCreateView(generics.CreateAPIView):
    """Yangi OSAGO arizasi yaratish (To'lov kutish holatida qoladi)"""
    permission_classes = [IsAuthenticated]
    serializer_class = PolicyApplicationCreateSerializer

    @extend_schema(tags=["Policies"])
    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        service = OsagoAPIService()
        try:
            vehicle_info = service.get_vehicle_info(
                data["plate_number"], data["tech_passport"]
            )
            premium_data = service.calculate_premium(
                data["plate_number"], data["tech_passport"],
                data.get("coverage_period_months", 12)
            )
        except OsagoAPIError as e:
            return Response({"detail": str(e)}, status=status.HTTP_502_BAD_GATEWAY)

        # Referal linkni aniqlash (cookie yoki URL param)
        from apps.referrals.utils import get_referral_from_request
        referral = get_referral_from_request(request)

        # Sana hisoblash
        start = data.get("coverage_start") or date.today()
        months = data.get("coverage_period_months", 12)
        end = start + relativedelta(months=months)

        with transaction.atomic():
            application = PolicyApplication.objects.create(
                user=request.user,
                plate_number=data["plate_number"],
                tech_passport=data["tech_passport"],
                owner_full_name=data["owner_full_name"],
                owner_passport=data["owner_passport"],
                owner_pinfl=data.get("owner_pinfl", ""),
                owner_address=data.get("owner_address", ""),
                coverage_start=start,
                coverage_end=end,
                coverage_period_months=months,
                premium_amount=premium_data.get("amount"),
                vehicle_brand=vehicle_info.get("brand", ""),
                vehicle_model=vehicle_info.get("model", ""),
                vehicle_year=vehicle_info.get("year"),
                engine_power=vehicle_info.get("engine_power"),
                status=PolicyApplication.Status.PENDING_PAYMENT,
                referral=referral,
            )

        return Response(
            PolicyApplicationSerializer(application).data,
            status=status.HTTP_201_CREATED,
        )


class PolicyListView(generics.ListAPIView):
    """Foydalanuvchining barcha arizalari"""
    permission_classes = [IsAuthenticated]
    serializer_class = PolicyApplicationSerializer
    filterset_fields = ["status"]

    @extend_schema(tags=["Policies"])
    def get_queryset(self):
        return PolicyApplication.objects.filter(user=self.request.user)


class PolicyDetailView(generics.RetrieveAPIView):
    """Ariza tafsilotlari"""
    permission_classes = [IsAuthenticated]
    serializer_class = PolicyApplicationSerializer

    @extend_schema(tags=["Policies"])
    def get_queryset(self):
        return PolicyApplication.objects.filter(user=self.request.user)


@extend_schema(tags=["Policies"])
@api_view(["GET"])
@permission_classes([IsAuthenticated])
def download_policy_pdf(request, pk):
    """Foydalanuvchining PDF polisini yuklab olish."""
    try:
        application = PolicyApplication.objects.get(pk=pk, user=request.user)
    except PolicyApplication.DoesNotExist:
        return Response({"detail": "Polis topilmadi."}, status=404)

    if not application.policy_pdf:
        return Response({"detail": "PDF hali yaratilmagan."}, status=404)

    return FileResponse(
        application.policy_pdf.open("rb"),
        as_attachment=True,
        filename=f"osago_policy_{application.id}.pdf",
    )


# ── Admin views ───────────────────────────────────────────────────────────────

class AdminPolicyListView(generics.ListAPIView):
    """Admin: barcha arizalar"""
    permission_classes = [IsAdminUser]
    serializer_class = AdminPolicySerializer
    queryset = PolicyApplication.objects.select_related("user").all()
    search_fields = ["plate_number", "owner_full_name", "user__phone"]
    filterset_fields = ["status"]
    ordering_fields = ["created_at", "premium_amount"]

    @extend_schema(tags=["Admin"])
    def get(self, *args, **kwargs):
        return super().get(*args, **kwargs)


@extend_schema(tags=["Admin"])
@api_view(["GET"])
@permission_classes([IsAdminUser])
def admin_stats(request):
    """Admin: statistika"""
    from django.db.models import Sum, Count
    from django.contrib.auth import get_user_model
    User = get_user_model()

    policies_qs = PolicyApplication.objects.all()
    return Response({
        "total_users": User.objects.count(),
        "total_applications": policies_qs.count(),
        "active_policies": policies_qs.filter(status=PolicyApplication.Status.ACTIVE).count(),
        "total_revenue": policies_qs.filter(
            status__in=[PolicyApplication.Status.ACTIVE, PolicyApplication.Status.PAID]
        ).aggregate(total=Sum("premium_amount"))["total"] or 0,
        "by_status": dict(
            policies_qs.values_list("status").annotate(c=Count("id")).values_list("status", "c")
        ),
    })
