"""policies/serializers.py"""

from rest_framework import serializers
from .models import PolicyApplication


class PremiumCalculateSerializer(serializers.Serializer):
    """Narx hisoblash uchun kirish"""
    plate_number = serializers.CharField(max_length=20)
    tech_passport = serializers.CharField(max_length=20)
    period_months = serializers.ChoiceField(choices=[3, 6, 9, 12], default=12)


class PolicyApplicationCreateSerializer(serializers.ModelSerializer):
    """Yangi ariza yaratish"""

    class Meta:
        model = PolicyApplication
        fields = [
            "plate_number", "tech_passport",
            "owner_full_name", "owner_passport", "owner_pinfl", "owner_address",
            "coverage_start", "coverage_period_months",
        ]

    def validate_coverage_period_months(self, value):
        if value not in [3, 6, 9, 12]:
            raise serializers.ValidationError("Muddat 3, 6, 9 yoki 12 oy bo'lishi mumkin.")
        return value


class PolicyApplicationSerializer(serializers.ModelSerializer):
    """Ariza ma'lumotlari"""
    status_display = serializers.CharField(source="get_status_display", read_only=True)

    class Meta:
        model = PolicyApplication
        fields = [
            "id", "plate_number", "tech_passport",
            "vehicle_brand", "vehicle_model", "vehicle_year",
            "owner_full_name", "premium_amount",
            "coverage_start", "coverage_end", "coverage_period_months",
            "status", "status_display",
            "external_policy_id", "policy_pdf",
            "created_at", "updated_at", "activated_at",
        ]
        read_only_fields = fields


class AdminPolicySerializer(serializers.ModelSerializer):
    """Admin panel uchun kengaytirilgan ko'rinish"""
    user_phone = serializers.CharField(source="user.phone", read_only=True)
    user_name = serializers.CharField(source="user.get_full_name", read_only=True)
    status_display = serializers.CharField(source="get_status_display", read_only=True)

    class Meta:
        model = PolicyApplication
        fields = "__all__"
