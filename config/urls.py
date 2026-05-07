"""KAFIL-SUG'URTA OSAGO — URL Configuration"""

from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView

urlpatterns = [
    path("admin/", admin.site.urls),

    # API v1
    path("api/v1/auth/",        include("apps.accounts.urls")),
    path("api/v1/policies/",    include("apps.policies.urls")),
    path("api/v1/payments/",    include("apps.payments.urls")),
    path("api/v1/referrals/",   include("apps.referrals.urls")),
    path("api/v1/notifications/", include("apps.notifications.urls")),

    # Swagger / OpenAPI
    path("api/schema/",         SpectacularAPIView.as_view(), name="schema"),
    path("api/docs/",           SpectacularSwaggerView.as_view(url_name="schema"), name="swagger-ui"),
] + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
