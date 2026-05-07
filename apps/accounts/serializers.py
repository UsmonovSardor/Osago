"""accounts/serializers.py"""

from rest_framework import serializers
from django.contrib.auth import get_user_model

User = get_user_model()


class SendOTPSerializer(serializers.Serializer):
    """SMS-kod yuborish uchun"""
    phone = serializers.CharField(max_length=20)

    def validate_phone(self, value):
        # +998XXXXXXXXX formatiga keltirish
        phone = value.strip().replace(" ", "").replace("-", "")
        if not phone.startswith("+998") or len(phone) != 13:
            raise serializers.ValidationError(
                "Telefon raqam +998XXXXXXXXX formatida bo'lishi kerak"
            )
        return phone


class VerifyOTPSerializer(serializers.Serializer):
    """OTP kodni tasdiqlash va JWT token olish"""
    phone = serializers.CharField(max_length=20)
    code = serializers.CharField(max_length=6, min_length=6)


class UserProfileSerializer(serializers.ModelSerializer):
    """Foydalanuvchi profili"""

    class Meta:
        model = User
        fields = [
            "id", "phone", "first_name", "last_name", "email",
            "referral_code", "bonus_balance", "is_verified", "date_joined",
        ]
        read_only_fields = ["id", "phone", "referral_code", "bonus_balance", "is_verified", "date_joined"]


class UserProfileUpdateSerializer(serializers.ModelSerializer):
    """Profil yangilash"""

    class Meta:
        model = User
        fields = ["first_name", "last_name", "email"]

    def validate_email(self, value):
        user = self.context["request"].user
        if User.objects.exclude(pk=user.pk).filter(email=value).exists():
            raise serializers.ValidationError("Bu email allaqachon ro'yxatdan o'tgan")
        return value


class AdminUserSerializer(serializers.ModelSerializer):
    """Admin panel uchun kengaytirilgan foydalanuvchi ma'lumotlari"""
    full_name = serializers.SerializerMethodField()
    policies_count = serializers.SerializerMethodField()
    referrals_count = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = [
            "id", "phone", "full_name", "email", "is_verified",
            "bonus_balance", "referral_code", "policies_count",
            "referrals_count", "date_joined", "last_login",
        ]

    def get_full_name(self, obj):
        return obj.get_full_name()

    def get_policies_count(self, obj):
        return obj.policy_applications.count()

    def get_referrals_count(self, obj):
        return obj.referrals.count()
