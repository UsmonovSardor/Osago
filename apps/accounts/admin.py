"""accounts/admin.py"""
from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from .models import User, OTPCode

@admin.register(User)
class UserAdmin(BaseUserAdmin):
    list_display = ["phone", "get_full_name", "is_verified", "bonus_balance", "date_joined"]
    list_filter = ["is_verified", "is_active", "is_staff"]
    search_fields = ["phone", "first_name", "last_name"]
    ordering = ["-date_joined"]
    readonly_fields = ["referral_code", "date_joined", "last_login"]
    fieldsets = (
        ("Asosiy", {"fields": ("phone", "password")}),
        ("Shaxsiy", {"fields": ("first_name", "last_name", "email")}),
        ("Holat", {"fields": ("is_active", "is_staff", "is_superuser", "is_verified")}),
        ("Referal", {"fields": ("referral_code", "referred_by", "bonus_balance")}),
        ("Vaqt", {"fields": ("date_joined", "last_login")}),
    )
    add_fieldsets = (
        (None, {"classes": ("wide",), "fields": ("phone", "password1", "password2")}),
    )

@admin.register(OTPCode)
class OTPCodeAdmin(admin.ModelAdmin):
    list_display = ["phone", "code", "is_used", "attempts", "created_at", "expires_at"]
    list_filter = ["is_used"]
    search_fields = ["phone"]
