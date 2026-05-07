"""
payments/models.py
To'lov tranzaksiyalari: Click, Payme, Uzum Pay
"""

import uuid
from django.db import models
from apps.policies.models import PolicyApplication


class Transaction(models.Model):
    """To'lov tranzaksiyasi"""

    class Provider(models.TextChoices):
        CLICK = "CLICK", "Click"
        PAYME = "PAYME", "Payme"
        UZUM = "UZUM", "Uzum Pay"

    class Status(models.TextChoices):
        PENDING = "PENDING", "Kutilmoqda"
        PROCESSING = "PROCESSING", "Jarayonda"
        SUCCESS = "SUCCESS", "Muvaffaqiyatli"
        FAILED = "FAILED", "Muvaffaqiyatsiz"
        CANCELLED = "CANCELLED", "Bekor qilingan"
        REFUNDED = "REFUNDED", "Qaytarilgan"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    application = models.ForeignKey(
        PolicyApplication, on_delete=models.PROTECT,
        related_name="transactions"
    )
    provider = models.CharField("To'lov tizimi", max_length=10, choices=Provider.choices)
    status = models.CharField("Status", max_length=15, choices=Status.choices, default=Status.PENDING)

    amount = models.DecimalField("Summa (tiyin)", max_digits=14, decimal_places=2)

    # To'lov tizimining o'z ID'si
    provider_transaction_id = models.CharField("Provider tranzaksiya ID", max_length=200, blank=True)
    provider_invoice_id = models.CharField("Provider invoice ID", max_length=200, blank=True)

    # To'liq javob (log uchun)
    provider_response = models.JSONField("Provider javobi", default=dict, blank=True)

    # Idempotency: foydalanuvchi tugmani ikki marta bosmasin
    idempotency_key = models.CharField(max_length=100, unique=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "payment_transactions"
        verbose_name = "Tranzaksiya"
        verbose_name_plural = "Tranzaksiyalar"
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["application", "status"]),
            models.Index(fields=["provider_transaction_id"]),
        ]

    def __str__(self):
        return f"{self.provider} | {self.amount} | {self.status}"

    def save(self, *args, **kwargs):
        if not self.idempotency_key:
            # Ariza ID + provider = har doim unikal
            self.idempotency_key = f"{self.application_id}:{self.provider}"
        super().save(*args, **kwargs)
