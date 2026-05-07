"""
accounts/views.py
2FA: SMS → OTP tasdiqlash → JWT token
"""

from datetime import timedelta
from django.utils import timezone
from django.conf import settings
from django.contrib.auth import get_user_model
from rest_framework import status, generics
from rest_framework.decorators import api_view, permission_classes, throttle_classes
from rest_framework.permissions import AllowAny, IsAuthenticated, IsAdminUser
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework_simplejwt.tokens import RefreshToken
from drf_spectacular.utils import extend_schema

from .models import OTPCode
from .serializers import (
    SendOTPSerializer, VerifyOTPSerializer,
    UserProfileSerializer, UserProfileUpdateSerializer, AdminUserSerializer,
)
from apps.notifications.services import SMSService

User = get_user_model()


class SMSThrottle(ScopedRateThrottle):
    scope = "sms"


@extend_schema(tags=["Auth"])
@api_view(["POST"])
@permission_classes([AllowAny])
@throttle_classes([SMSThrottle])
def send_otp(request):
    """
    Telefon raqamga SMS-kod yuborish.
    Har bir raqamga 5 daqiqada max 3 ta so'rov.
    """
    serializer = SendOTPSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    phone = serializer.validated_data["phone"]

    # Oxirgi 1 daqiqada yuborilgan OTP bormi? (spam himoya)
    recent = OTPCode.objects.filter(
        phone=phone,
        created_at__gte=timezone.now() - timedelta(minutes=1),
        is_used=False,
    ).exists()
    if recent:
        return Response(
            {"detail": "Iltimos, 1 daqiqa kuting."},
            status=status.HTTP_429_TOO_MANY_REQUESTS,
        )

    # Oldingi aktiv kodlarni bekor qilish
    OTPCode.objects.filter(phone=phone, is_used=False).update(is_used=True)

    # Yangi OTP yaratish
    import random
    code = str(random.randint(100000, 999999))
    OTPCode.objects.create(
        phone=phone,
        code=code,
        expires_at=timezone.now() + timedelta(minutes=settings.SMS_OTP_EXPIRE_MINUTES),
    )

    # SMS yuborish
    sms = SMSService()
    message = f"KAFIL-SUG'URTA: Tasdiqlash kodingiz: {code}. Kod {settings.SMS_OTP_EXPIRE_MINUTES} daqiqa amal qiladi."
    success = sms.send(phone, message)

    if not success:
        return Response(
            {"detail": "SMS yuborishda xatolik. Iltimos qayta urinib ko'ring."},
            status=status.HTTP_503_SERVICE_UNAVAILABLE,
        )

    return Response(
        {"detail": f"SMS-kod {phone} raqamiga yuborildi.", "expires_in": settings.SMS_OTP_EXPIRE_MINUTES * 60},
        status=status.HTTP_200_OK,
    )


@extend_schema(tags=["Auth"])
@api_view(["POST"])
@permission_classes([AllowAny])
def verify_otp(request):
    """
    OTP kodni tasdiqlash va JWT token qaytarish.
    Yangi foydalanuvchi bo'lsa avtomatik ro'yxatdan o'tkaziladi.
    """
    serializer = VerifyOTPSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)

    phone = serializer.validated_data["phone"]
    code = serializer.validated_data["code"]

    # So'nggi aktiv OTP ni topish
    try:
        otp = OTPCode.objects.filter(
            phone=phone, is_used=False
        ).latest("created_at")
    except OTPCode.DoesNotExist:
        return Response(
            {"detail": "Kod topilmadi. Iltimos qayta SMS so'rang."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    # Urinishlar soni oshirish
    otp.attempts += 1
    otp.save(update_fields=["attempts"])

    if otp.is_expired:
        return Response(
            {"detail": "Kodning amal qilish muddati o'tgan. Qayta so'rang."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    if otp.attempts > settings.SMS_OTP_MAX_ATTEMPTS:
        return Response(
            {"detail": "Urinishlar soni oshib ketdi. Qayta SMS so'rang."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    if otp.code != code:
        remaining = settings.SMS_OTP_MAX_ATTEMPTS - otp.attempts
        return Response(
            {"detail": f"Noto'g'ri kod. Qolgan urinish: {remaining}"},
            status=status.HTTP_400_BAD_REQUEST,
        )

    # OTP tasdiqlandi
    otp.is_used = True
    otp.save(update_fields=["is_used"])

    # Referal kod tekshirish (query param orqali)
    ref_code = request.data.get("ref_code", "").strip()
    referred_by = None
    if ref_code:
        try:
            referred_by = User.objects.get(referral_code=ref_code)
        except User.DoesNotExist:
            pass

    # Foydalanuvchi olish yoki yaratish
    user, created = User.objects.get_or_create(phone=phone)
    if created and referred_by and referred_by.pk != user.pk:
        user.referred_by = referred_by
    user.is_verified = True
    user.save(update_fields=["is_verified", "referred_by"])

    # JWT token yaratish
    refresh = RefreshToken.for_user(user)

    return Response(
        {
            "access": str(refresh.access_token),
            "refresh": str(refresh),
            "is_new_user": created,
            "user": UserProfileSerializer(user).data,
        },
        status=status.HTTP_200_OK,
    )


@extend_schema(tags=["Auth"])
@api_view(["POST"])
@permission_classes([IsAuthenticated])
def logout(request):
    """Refresh token'ni blacklist ga qo'shish"""
    try:
        token = RefreshToken(request.data["refresh"])
        token.blacklist()
        return Response({"detail": "Muvaffaqiyatli chiqish."})
    except Exception:
        return Response({"detail": "Noto'g'ri token."}, status=400)


class ProfileView(generics.RetrieveUpdateAPIView):
    """Foydalanuvchi profilini ko'rish va yangilash"""
    permission_classes = [IsAuthenticated]

    @extend_schema(tags=["Profile"])
    def get(self, request, *args, **kwargs):
        return Response(UserProfileSerializer(request.user).data)

    @extend_schema(tags=["Profile"])
    def put(self, request, *args, **kwargs):
        serializer = UserProfileUpdateSerializer(
            request.user, data=request.data, partial=True,
            context={"request": request}
        )
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(UserProfileSerializer(request.user).data)

    patch = put


# ── Admin views ───────────────────────────────────────────────────────────────

class AdminUserListView(generics.ListAPIView):
    """Admin: barcha foydalanuvchilar ro'yxati"""
    permission_classes = [IsAdminUser]
    serializer_class = AdminUserSerializer
    queryset = User.objects.all().order_by("-date_joined")
    search_fields = ["phone", "first_name", "last_name", "email"]
    filterset_fields = ["is_verified", "is_active"]
