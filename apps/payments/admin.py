"""payments/admin.py"""
from django.contrib import admin
from .models import Transaction

@admin.register(Transaction)
class TransactionAdmin(admin.ModelAdmin):
    list_display = ["id", "provider", "amount", "status", "created_at"]
    list_filter = ["provider", "status"]
    search_fields = ["provider_transaction_id", "application__plate_number"]
    readonly_fields = ["id", "created_at", "updated_at", "completed_at", "provider_response"]
