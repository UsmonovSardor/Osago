"""payments/urls.py"""

from django.urls import path
from . import views

urlpatterns = [
    path("invoice/",          views.create_invoice,                name="create-invoice"),
    path("demo/complete/",    views.demo_complete_payment,        name="demo-complete-payment"),

    # Callbacklar (to'lov tizimlari chaqiradi)
    path("callback/click/",   views.click_callback,                name="click-callback"),
    path("callback/payme/",   views.payme_endpoint,                name="payme-endpoint"),

    # Admin
    path("admin/transactions/", views.AdminTransactionListView.as_view(), name="admin-transactions"),
]
