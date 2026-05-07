"""
policies/models.py
OSAGO polis arizalari va avtomobil ma'lumotlari
"""

import uuid
from django.db import models
from django.contrib.auth import get_user_model
from django.core.validators import MinValueValidator

User = get_user_model()


class PolicyApplication(models.Model):
    """OSAGO sug'urta polis arizasi"""

    class Status(models.TextChoices):
        DRAFT = "DRAFT", "Qoralama"
        PENDING_PAYMENT = "PENDING_PAYMENT", "To'lov kutilmoqda"
        PAYMENT_PROCESSING = "PAYMENT_PROCESSING", "To'lov jarayonida"
        PAID = "PAID", "To'langan"
        ACTIVE = "ACTIVE", "Faol (API tasdiqlagan)"
        FAILED = "FAILED", "Muvaffaqiyatsiz"
        CANCELLED = "CANCELLED", "Bekor qilingan"
        EXPIRED = "EXPIRED", "Muddati o'tgan"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        User, on_delete=models.PROTECT,
        related_name="policy_applications"
    )

    # Avtomobil ma'lumotlari
    plate_number = models.CharField("Avtomobil raqami", max_length=20)
    tech_passport = models.CharField("Tex-pasport seriyasi", max_length=20)
    vehicle_type = models.CharField("Transport turi", max_length=50, blank=True)
    vehicle_brand = models.CharField("Marka", max_length=100, blank=True)
    vehicle_model = models.CharField("Model", max_length=100, blank=True)
    vehicle_year = models.PositiveSmallIntegerField("Ishlab chiqarilgan yil", null=True, blank=True)
    engine_power = models.PositiveSmallIntegerField("Dvigatel quvvati (ot kuchi)", null=True, blank=True)

    # Egasi ma'lumotlari
    owner_full_name = models.CharField("Egasining FIO", max_length=200)
    owner_passport = models.CharField("Egasining pasport seriyasi", max_length=20)
    owner_pinfl = models.CharField("PINFL", max_length=14, blank=True)
    owner_address = models.TextField("Manzil", blank=True)

    # Narx va muddat
    premium_amount = models.DecimalField(
        "Sug'urta mukofoti (so'm)", max_digits=12, decimal_places=2,
        null=True, blank=True, validators=[MinValueValidator(0)]
    )
    coverage_start = models.DateField("Sug'urta boshlanishi", null=True, blank=True)
    coverage_end = models.DateField("Sug'urta tugashi", null=True, blank=True)
    coverage_period_months = models.PositiveSmallIntegerField(
        "Muddat (oy)", default=12
    )

    # Status
    status = models.CharField(
        max_length=30, choices=Status.choices, default=Status.DRAFT
    )

    # Tashqi API natijasi
    external_policy_id = models.CharField(
        "Tashqi API polis ID", max_length=100, blank=True
    )
    external_response = models.JSONField("API javobi", default=dict, blank=True)

    # PDF fayl
    policy_pdf = models.FileField(
        "Polis PDF", upload_to="policies/pdf/", null=True, blank=True
    )

    # Referal havola
    referral = models.ForeignKey(
        "referrals.ReferralLink", on_delete=models.SET_NULL,
        null=True, blank=True, related_name="policy_applications"
    )

    created_at = models.DateTimeField("Yaratildi", auto_now_add=True)
    updated_at = models.DateTimeField("Yangilandi", auto_now=True)
    activated_at = models.DateTimeField("Faollashtirildi", null=True, blank=True)

    class Meta:
        verbose_name = "Polis arizasi"
        verbose_name_plural = "Polis arizalari"
        db_table = "policy_applications"
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["user", "status"]),
            models.Index(fields=["plate_number"]),
            models.Index(fields=["status", "created_at"]),
        ]

    def __str__(self):
        return f"OSAGO #{self.id} | {self.plate_number} | {self.status}"


class VehicleDataCache(models.Model):
    """Avtomobil ma'lumotlari keshi (Tashqi API'dan olingan)"""

    plate_number = models.CharField("Avtomobil raqami", max_length=20, unique=True)
    tech_passport = models.CharField("Tex-pasport", max_length=20, blank=True)
    data = models.JSONField("Ma'lumotlar", default=dict)
    fetched_at = models.DateTimeField("Olingan vaqt", auto_now=True)

    class Meta:
        db_table = "vehicle_data_cache"
        verbose_name = "Avtomobil keshi"
