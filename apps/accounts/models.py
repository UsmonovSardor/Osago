"""
accounts/models.py
Foydalanuvchi modeli: telefon raqam asosida autentifikatsiya
"""

import uuid
from django.contrib.auth.models import AbstractBaseUser, PermissionsMixin, BaseUserManager
from django.db import models
from django.utils import timezone


class UserManager(BaseUserManager):
    """Telefon raqam orqali foydalanuvchi yaratish"""

    def create_user(self, phone, password=None, **extra_fields):
        if not phone:
            raise ValueError("Telefon raqam majburiy")
        user = self.model(phone=phone, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, phone, password=None, **extra_fields):
        extra_fields.setdefault("is_staff", True)
        extra_fields.setdefault("is_superuser", True)
        extra_fields.setdefault("is_verified", True)
        return self.create_user(phone, password, **extra_fields)


class User(AbstractBaseUser, PermissionsMixin):
    """Asosiy foydalanuvchi modeli"""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    phone = models.CharField("Telefon raqam", max_length=20, unique=True)
    first_name = models.CharField("Ism", max_length=100, blank=True)
    last_name = models.CharField("Familiya", max_length=100, blank=True)
    email = models.EmailField("Email", blank=True)

    is_active = models.BooleanField(default=True)
    is_staff = models.BooleanField(default=False)
    is_verified = models.BooleanField("Telefon tasdiqlangan", default=False)

    # Referal egasi
    referral_code = models.CharField(max_length=20, unique=True, blank=True)
    referred_by = models.ForeignKey(
        "self", on_delete=models.SET_NULL, null=True, blank=True,
        related_name="referrals"
    )

    # Bonus balans (so'mda)
    bonus_balance = models.DecimalField(
        "Bonus balans", max_digits=12, decimal_places=2, default=0
    )

    date_joined = models.DateTimeField("Ro'yxatdan o'tish", default=timezone.now)
    last_login = models.DateTimeField("Oxirgi kirish", null=True, blank=True)

    USERNAME_FIELD = "phone"
    REQUIRED_FIELDS = []

    objects = UserManager()

    class Meta:
        verbose_name = "Foydalanuvchi"
        verbose_name_plural = "Foydalanuvchilar"
        db_table = "accounts_user"

    def __str__(self):
        return f"{self.phone} ({self.get_full_name() or 'Nomsiz'})"

    def get_full_name(self):
        return f"{self.first_name} {self.last_name}".strip()

    def save(self, *args, **kwargs):
        if not self.referral_code:
            self.referral_code = self._generate_referral_code()
        super().save(*args, **kwargs)

    def _generate_referral_code(self):
        import random, string
        chars = string.ascii_uppercase + string.digits
        while True:
            code = "".join(random.choices(chars, k=8))
            if not User.objects.filter(referral_code=code).exists():
                return code


class OTPCode(models.Model):
    """SMS orqali yuborilgan bir martalik kod"""

    phone = models.CharField("Telefon", max_length=20)
    code = models.CharField("Kod", max_length=6)
    is_used = models.BooleanField("Ishlatilgan", default=False)
    attempts = models.PositiveSmallIntegerField("Urinishlar soni", default=0)
    created_at = models.DateTimeField("Yaratilgan vaqt", auto_now_add=True)
    expires_at = models.DateTimeField("Amal qilish muddati")

    class Meta:
        verbose_name = "OTP Kod"
        verbose_name_plural = "OTP Kodlar"
        db_table = "accounts_otp"
        indexes = [models.Index(fields=["phone", "is_used"])]

    def __str__(self):
        return f"{self.phone} → {self.code}"

    @property
    def is_expired(self):
        return timezone.now() > self.expires_at

    @property
    def is_valid(self):
        return not self.is_used and not self.is_expired and self.attempts < 3
