"""referrals/admin.py"""
from django.contrib import admin
from .models import ReferralLink, ReferralBonus

@admin.register(ReferralLink)
class ReferralLinkAdmin(admin.ModelAdmin):
    list_display = ["code", "owner", "click_count", "conversion_count", "total_bonus_earned", "is_active"]
    list_filter = ["is_active"]
    search_fields = ["code", "owner__phone"]

@admin.register(ReferralBonus)
class ReferralBonusAdmin(admin.ModelAdmin):
    list_display = ["referral", "amount", "status", "created_at"]
    list_filter = ["status"]
