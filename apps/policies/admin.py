"""policies/admin.py"""
from django.contrib import admin
from .models import PolicyApplication

@admin.register(PolicyApplication)
class PolicyApplicationAdmin(admin.ModelAdmin):
    list_display = ["id", "plate_number", "owner_full_name", "status", "premium_amount", "created_at"]
    list_filter = ["status", "coverage_period_months"]
    search_fields = ["plate_number", "owner_full_name", "user__phone", "external_policy_id"]
    readonly_fields = ["id", "created_at", "updated_at", "activated_at", "external_response"]
    ordering = ["-created_at"]
