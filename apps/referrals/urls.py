"""referrals/urls.py"""

from django.urls import path
from . import views

urlpatterns = [
    path("my/links/",       views.MyReferralLinksView.as_view(), name="my-referral-links"),
    path("my/bonuses/",     views.MyBonusHistoryView.as_view(),  name="my-bonuses"),
    path("my/stats/",       views.my_stats,                      name="my-referral-stats"),
    path("admin/links/",    views.AdminReferralListView.as_view(), name="admin-referral-links"),
]
