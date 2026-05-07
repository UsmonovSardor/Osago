"""policies/urls.py"""

from django.urls import path
from . import views

urlpatterns = [
    path("calculate/",       views.calculate_premium,           name="calculate-premium"),
    path("apply/",           views.PolicyApplicationCreateView.as_view(), name="policy-create"),
    path("",                 views.PolicyListView.as_view(),     name="policy-list"),
    path("<uuid:pk>/download/", views.download_policy_pdf,        name="policy-pdf-download"),
    path("<uuid:pk>/",       views.PolicyDetailView.as_view(),   name="policy-detail"),

    # Admin
    path("admin/list/",      views.AdminPolicyListView.as_view(), name="admin-policy-list"),
    path("admin/stats/",     views.admin_stats,                  name="admin-stats"),
]
