"""
referrals/models.py
Referal tizimi: havola kuzatish, bonus hisoblash
"""

import uuid
from django.db import models
from django.contrib.auth import get_user_model

User = get_user_model()


class ReferralLink(models.Model):
    """Agent yoki foydalanuvchining referal havolasi"""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    owner = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name="referral_links"
    )
    # kafil.uz/osago?ref=ABC123DE
    code = models.CharField("Referal kod", max_length=20, unique=True)
    name = models.CharField("Nom (ixtiyoriy)", max_length=100, blank=True)
    is_active = models.BooleanField("Faol", default=True)

    # Statistika
    click_count = models.PositiveIntegerField("Bosishlar soni", default=0)
    conversion_count = models.PositiveIntegerField("Sotuvlar soni", default=0)
    total_bonus_earned = models.DecimalField(
        "Jami ishlangan bonus", max_digits=12, decimal_places=2, default=0
    )

    # Bonus foizi (masalan: 5.0 = 5%)
    bonus_percent = models.DecimalField(
        "Bonus foizi", max_digits=5, decimal_places=2, default=5.00
    )

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "referral_links"
        verbose_name = "Referal havola"
        verbose_name_plural = "Referal havolalar"

    def __str__(self):
        return f"{self.owner.phone} → {self.code}"


class ReferralBonus(models.Model):
    """Referal bonuslari tarixi"""

    class Status(models.TextChoices):
        PENDING = "PENDING", "Kutilmoqda"
        PAID = "PAID", "To'langan"
        CANCELLED = "CANCELLED", "Bekor qilingan"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    referral = models.ForeignKey(
        ReferralLink, on_delete=models.PROTECT, related_name="bonuses"
    )
    policy_application = models.ForeignKey(
        "policies.PolicyApplication", on_delete=models.PROTECT
    )
    amount = models.DecimalField("Bonus miqdori", max_digits=10, decimal_places=2)
    status = models.CharField(max_length=15, choices=Status.choices, default=Status.PENDING)
    created_at = models.DateTimeField(auto_now_add=True)
    paid_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "referral_bonuses"
        verbose_name = "Referal bonus"
        unique_together = [("referral", "policy_application")]  # Bir polisga bir bonus
