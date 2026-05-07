"""accounts/urls.py"""

from django.urls import path
from rest_framework_simplejwt.views import TokenRefreshView
from . import views

urlpatterns = [
    # 2FA
    path("otp/send/",   views.send_otp,    name="otp-send"),
    path("otp/verify/", views.verify_otp,  name="otp-verify"),
    path("logout/",     views.logout,      name="logout"),

    # JWT refresh
    path("token/refresh/", TokenRefreshView.as_view(), name="token-refresh"),

    # Profil
    path("profile/", views.ProfileView.as_view(), name="profile"),

    # Admin
    path("admin/users/", views.AdminUserListView.as_view(), name="admin-users"),
]
