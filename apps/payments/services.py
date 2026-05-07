"""
payments/services.py
Click, Payme, Uzum Pay integratsiya servislari
Atomicity va Idempotency ta'minlangan
"""

import hashlib
import logging
import requests
from django.conf import settings
from django.utils import timezone
from django.db import transaction as db_transaction

from .models import Transaction
from apps.policies.models import PolicyApplication
from apps.policies.services import OsagoAPIService, OsagoAPIError
from apps.notifications.services import SMSService
from apps.referrals.services import ReferralService
from .pdf_generator import generate_policy_pdf

logger = logging.getLogger(__name__)


class PaymentError(Exception):
    pass


class BasePaymentService:
    """Asosiy to'lov interfeysi"""

    PROVIDER = None

    def create_invoice(self, application: PolicyApplication) -> dict:
        raise NotImplementedError

    def _get_or_create_transaction(self, application: PolicyApplication) -> Transaction:
        """
        Idempotency: bir ariza uchun bir xil provider'dan faqat bitta aktiv tranzaksiya.
        """
        idem_key = f"{application.id}:{self.PROVIDER}"
        existing = Transaction.objects.filter(
            idempotency_key=idem_key,
            status__in=[Transaction.Status.PENDING, Transaction.Status.PROCESSING],
        ).first()
        if existing:
            return existing, False

        txn = Transaction.objects.create(
            application=application,
            provider=self.PROVIDER,
            amount=application.premium_amount * 100,  # tiyin
            idempotency_key=idem_key,
        )
        return txn, True


class ClickPaymentService(BasePaymentService):
    """Click to'lov tizimi"""

    PROVIDER = Transaction.Provider.CLICK

    def create_invoice(self, application: PolicyApplication) -> dict:
        txn, _ = self._get_or_create_transaction(application)

        # Click invoice URL shakllantirish
        params = {
            "service_id": settings.CLICK_SERVICE_ID,
            "merchant_id": settings.CLICK_MERCHANT_ID,
            "amount": int(application.premium_amount),
            "transaction_param": str(txn.id),
            "return_url": f"{settings.FRONTEND_URL}/payment/success",
        }
        invoice_url = (
            f"https://my.click.uz/services/pay?"
            f"service_id={params['service_id']}"
            f"&merchant_id={params['merchant_id']}"
            f"&amount={params['amount']}"
            f"&transaction_param={params['transaction_param']}"
        )

        # Status yangilash
        application.status = PolicyApplication.Status.PENDING_PAYMENT
        application.save(update_fields=["status"])

        return {"payment_url": invoice_url, "transaction_id": str(txn.id)}

    def handle_callback(self, data: dict) -> dict:
        """Click tomonidan kelgan callback"""
        # Click imzo tekshirish
        sign_string = (
            f"{data.get('click_trans_id')}"
            f"{settings.CLICK_SERVICE_ID}"
            f"{settings.CLICK_SECRET_KEY}"
            f"{data.get('merchant_trans_id')}"
            f"{data.get('amount')}"
            f"{data.get('action')}"
            f"{data.get('sign_time')}"
        )
        expected_sign = hashlib.md5(sign_string.encode()).hexdigest()

        if expected_sign != data.get("sign_string"):
            return {"error": -1, "error_note": "SIGN CHECK FAILED"}

        txn_id = data.get("merchant_trans_id")
        action = int(data.get("action", 0))

        try:
            txn = Transaction.objects.select_related("application").get(id=txn_id)
        except Transaction.DoesNotExist:
            return {"error": -5, "error_note": "Transaction not found"}

        if action == 1:  # To'lov tasdiqlash
            _activate_policy_atomically(txn, data.get("click_trans_id"))

        return {
            "click_trans_id": data.get("click_trans_id"),
            "merchant_trans_id": txn_id,
            "merchant_prepare_id": str(txn.id),
            "error": 0,
            "error_note": "Success",
        }


class PaymePaymentService(BasePaymentService):
    """Payme to'lov tizimi"""

    PROVIDER = Transaction.Provider.PAYME

    def create_invoice(self, application: PolicyApplication) -> dict:
        txn, _ = self._get_or_create_transaction(application)
        amount_tiyin = int(application.premium_amount * 100)

        invoice_url = (
            f"https://checkout.paycom.uz/{settings.PAYME_MERCHANT_ID}"
            f"/{str(txn.id)}/{amount_tiyin}"
        )
        application.status = PolicyApplication.Status.PENDING_PAYMENT
        application.save(update_fields=["status"])

        return {"payment_url": invoice_url, "transaction_id": str(txn.id)}

    def handle_rpc(self, method: str, params: dict) -> dict:
        """Payme JSON-RPC metodlarini qayta ishlash"""
        handlers = {
            "CheckPerformTransaction": self._check_perform,
            "CreateTransaction": self._create_txn,
            "PerformTransaction": self._perform_txn,
            "CancelTransaction": self._cancel_txn,
        }
        handler = handlers.get(method)
        if not handler:
            return {"error": {"code": -32601, "message": "Method not found"}}
        return handler(params)

    def _check_perform(self, params):
        order_id = params.get("account", {}).get("order_id")
        try:
            app = PolicyApplication.objects.get(id=order_id)
            if app.status not in [
                PolicyApplication.Status.PENDING_PAYMENT,
                PolicyApplication.Status.DRAFT,
            ]:
                return {"error": {"code": -31008, "message": "Already paid"}}
            return {"result": {"allow": True}}
        except PolicyApplication.DoesNotExist:
            return {"error": {"code": -31050, "message": "Order not found"}}

    def _create_txn(self, params):
        order_id = params.get("account", {}).get("order_id")
        payme_id = params.get("id")
        try:
            app = PolicyApplication.objects.get(id=order_id)
            txn, _ = self._get_or_create_transaction(app)
            txn.provider_transaction_id = payme_id
            txn.status = Transaction.Status.PROCESSING
            txn.save(update_fields=["provider_transaction_id", "status"])
            app.status = PolicyApplication.Status.PAYMENT_PROCESSING
            app.save(update_fields=["status"])
            return {"result": {"create_time": int(txn.created_at.timestamp() * 1000), "transaction": str(txn.id), "state": 1}}
        except PolicyApplication.DoesNotExist:
            return {"error": {"code": -31050, "message": "Order not found"}}

    def _perform_txn(self, params):
        payme_id = params.get("id")
        try:
            txn = Transaction.objects.select_related("application").get(
                provider_transaction_id=payme_id
            )
            _activate_policy_atomically(txn, payme_id)
            return {"result": {"perform_time": int(txn.completed_at.timestamp() * 1000), "transaction": str(txn.id), "state": 2}}
        except Transaction.DoesNotExist:
            return {"error": {"code": -31003, "message": "Transaction not found"}}

    def _cancel_txn(self, params):
        payme_id = params.get("id")
        reason = params.get("reason", 0)
        try:
            txn = Transaction.objects.get(provider_transaction_id=payme_id)
            txn.status = Transaction.Status.CANCELLED
            txn.provider_response = {"cancel_reason": reason}
            txn.save()
            txn.application.status = PolicyApplication.Status.CANCELLED
            txn.application.save(update_fields=["status"])
            return {"result": {"cancel_time": int(timezone.now().timestamp() * 1000), "transaction": str(txn.id), "state": -1}}
        except Transaction.DoesNotExist:
            return {"error": {"code": -31003, "message": "Transaction not found"}}


class UzumPaymentService(BasePaymentService):
    """Uzum Pay uchun sodda invoice servisi. Real merchant credential ulanganda URL formatini provider talabiga moslang."""

    PROVIDER = Transaction.Provider.UZUM

    def create_invoice(self, application: PolicyApplication) -> dict:
        txn, _ = self._get_or_create_transaction(application)
        amount_tiyin = int(application.premium_amount * 100)
        application.status = PolicyApplication.Status.PENDING_PAYMENT
        application.save(update_fields=["status"])

        # Demo/development rejimda ham frontend oqimi ishlashi uchun test URL qaytariladi.
        invoice_url = (
            f"{settings.FRONTEND_URL}/payment/uzum"
            f"?transaction_id={txn.id}&amount={amount_tiyin}"
        )
        return {"payment_url": invoice_url, "transaction_id": str(txn.id)}


def _activate_policy_atomically(txn: Transaction, provider_txn_id: str):
    """
    ATOMIK operatsiya:
    1. Tranzaksiyani SUCCESS deb belgilash
    2. Tashqi API'da polisni rasmiylashtirish
    3. PDF yaratish
    4. Referal bonus yozish
    5. SMS yuborish

    Agar API muvaffaqiyatsiz bo'lsa — hamma narsa rollback qilinadi.
    """
    with db_transaction.atomic():
        # Qayta ishlanmasin (Idempotency)
        txn_locked = Transaction.objects.select_for_update().get(pk=txn.pk)
        if txn_locked.status == Transaction.Status.SUCCESS:
            logger.warning(f"[Payment] Already processed: {txn.pk}")
            return

        txn_locked.status = Transaction.Status.SUCCESS
        txn_locked.provider_transaction_id = provider_txn_id
        txn_locked.completed_at = timezone.now()
        txn_locked.save(update_fields=["status", "provider_transaction_id", "completed_at"])

        app = txn_locked.application
        app.status = PolicyApplication.Status.PAID
        app.save(update_fields=["status"])

        # Tashqi API'da polisni rasmiylashtirish
        osago = OsagoAPIService()
        try:
            result = osago.register_policy(app)
            app.external_policy_id = result.get("policy_id", "")
            app.external_response = result
            app.status = PolicyApplication.Status.ACTIVE
            app.activated_at = timezone.now()
            app.save(update_fields=["external_policy_id", "external_response", "status", "activated_at"])
        except OsagoAPIError as e:
            logger.error(f"[Payment] API registration failed for app {app.id}: {e}")
            # To'lov muvaffaqiyatli, lekin API xato — admin ko'rishi uchun PAID holatda qoldirish
            # Celery retry vazifasi yuboriladi
            from apps.payments.tasks import retry_policy_registration
            retry_policy_registration.delay(str(app.id))
            return

    # Atomik blokdan tashqarida (rollback ta'sir qilmaydi)
    # PDF yaratish
    try:
        generate_policy_pdf(app)
    except Exception as e:
        logger.error(f"[PDF] Generation failed for app {app.id}: {e}")

    # Referal bonus
    try:
        if app.referral:
            ReferralService.apply_bonus(app)
    except Exception as e:
        logger.error(f"[Referral] Bonus failed for app {app.id}: {e}")

    # SMS yuborish
    try:
        sms = SMSService()
        sms.send(
            app.user.phone,
            f"KAFIL-SUG'URTA: OSAGO polisingiz #{app.external_policy_id} rasmiylashtirildi. "
            f"Polis PDF faylini saytdan yuklab oling."
        )
    except Exception as e:
        logger.error(f"[SMS] Failed for app {app.id}: {e}")


def complete_demo_payment(application: PolicyApplication, provider: str = Transaction.Provider.CLICK) -> Transaction:
    """
    Demo/test rejim uchun: real Click/Payme callbacksiz to'lovni muvaffaqiyatli yakunlaydi.
    Productionda OSAGO_DEMO_MODE=False bo'lsa ishlamaydi.
    """
    if not settings.OSAGO_DEMO_MODE:
        raise PaymentError("Demo payment faqat OSAGO_DEMO_MODE=True bo'lganda ishlaydi.")
    service_map = {
        Transaction.Provider.CLICK: ClickPaymentService,
        Transaction.Provider.PAYME: PaymePaymentService,
        Transaction.Provider.UZUM: UzumPaymentService,
    }
    service_cls = service_map.get(provider)
    if not service_cls:
        raise PaymentError("Noto'g'ri payment provider.")
    txn, _ = service_cls()._get_or_create_transaction(application)
    _activate_policy_atomically(txn, f"DEMO-{txn.id}")
    txn.refresh_from_db()
    return txn
