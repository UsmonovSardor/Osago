"""referrals/views.py"""

from rest_framework import generics, status, serializers
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated, IsAdminUser
from rest_framework.response import Response
from drf_spectacular.utils import extend_schema

from .models import ReferralLink, ReferralBonus
from .services import ReferralService


class ReferralLinkSerializer(serializers.ModelSerializer):
    referral_url = serializers.SerializerMethodField()

    class Meta:
        model = ReferralLink
        fields = [
            "id", "code", "name", "referral_url", "is_active",
            "click_count", "conversion_count", "total_bonus_earned",
            "bonus_percent", "created_at",
        ]
        read_only_fields = ["id", "code", "click_count", "conversion_count", "total_bonus_earned", "created_at"]

    def get_referral_url(self, obj):
        from django.conf import settings
        return f"{settings.FRONTEND_URL}/osago?ref={obj.code}"


class ReferralBonusSerializer(serializers.ModelSerializer):
    class Meta:
        model = ReferralBonus
        fields = ["id", "amount", "status", "created_at", "paid_at"]


class MyReferralLinksView(generics.ListCreateAPIView):
    """Foydalanuvchining referal havolalari"""
    permission_classes = [IsAuthenticated]
    serializer_class = ReferralLinkSerializer

    @extend_schema(tags=["Referrals"])
    def get_queryset(self):
        return ReferralLink.objects.filter(owner=self.request.user)

    def perform_create(self, serializer):
        import random, string
        code = "".join(random.choices(string.ascii_uppercase + string.digits, k=8))
        while ReferralLink.objects.filter(code=code).exists():
            code = "".join(random.choices(string.ascii_uppercase + string.digits, k=8))
        serializer.save(owner=self.request.user, code=code)


class MyBonusHistoryView(generics.ListAPIView):
    """Foydalanuvchining bonus tarixi"""
    permission_classes = [IsAuthenticated]
    serializer_class = ReferralBonusSerializer

    @extend_schema(tags=["Referrals"])
    def get_queryset(self):
        return ReferralBonus.objects.filter(referral__owner=self.request.user).order_by("-created_at")


@extend_schema(tags=["Referrals"])
@api_view(["GET"])
@permission_classes([IsAuthenticated])
def my_stats(request):
    """Foydalanuvchining referal statistikasi"""
    from django.db.models import Sum
    user = request.user
    links = ReferralLink.objects.filter(owner=user)
    bonuses = ReferralBonus.objects.filter(referral__owner=user)

    return Response({
        "total_clicks": links.aggregate(total=Sum("click_count"))["total"] or 0,
        "total_conversions": links.aggregate(total=Sum("conversion_count"))["total"] or 0,
        "total_bonus_earned": links.aggregate(total=Sum("total_bonus_earned"))["total"] or 0,
        "bonus_balance": user.bonus_balance,
        "pending_bonus": bonuses.filter(status=ReferralBonus.Status.PENDING).aggregate(
            total=Sum("amount"))["total"] or 0,
    })


# ── Admin ─────────────────────────────────────────────────────────────────────

class AdminReferralListView(generics.ListAPIView):
    """Admin: barcha referal havolalar"""
    permission_classes = [IsAdminUser]
    serializer_class = ReferralLinkSerializer
    queryset = ReferralLink.objects.select_related("owner").all()
    search_fields = ["code", "owner__phone"]
    filterset_fields = ["is_active"]
