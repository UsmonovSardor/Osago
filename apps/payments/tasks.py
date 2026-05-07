"""payments/tasks.py — Celery vazifalar"""

import logging
from celery import shared_task
from django.utils import timezone

logger = logging.getLogger(__name__)


@shared_task(bind=True, max_retries=5, default_retry_delay=60)
def retry_policy_registration(self, application_id: str):
    """
    To'lov muvaffaqiyatli bo'lgan, lekin tashqi API xato bergan holat uchun.
    5 marta qayta urinadi (1, 2, 4, 8, 16 daqiqa).
    """
    from apps.policies.models import PolicyApplication
    from apps.policies.services import OsagoAPIService, OsagoAPIError

    try:
        app = PolicyApplication.objects.get(id=application_id)
    except PolicyApplication.DoesNotExist:
        logger.error(f"[Retry] Application {application_id} topilmadi")
        return

    if app.status == PolicyApplication.Status.ACTIVE:
        logger.info(f"[Retry] Already active: {application_id}")
        return

    service = OsagoAPIService()
    try:
        result = service.register_policy(app)
        app.external_policy_id = result.get("policy_id", "")
        app.external_response = result
        app.status = PolicyApplication.Status.ACTIVE
        app.activated_at = timezone.now()
        app.save(update_fields=["external_policy_id", "external_response", "status", "activated_at"])
        logger.info(f"[Retry] Success: {application_id}")

        # PDF va SMS
        from apps.payments.pdf_generator import generate_policy_pdf
        generate_policy_pdf(app)

        from apps.notifications.services import SMSService
        SMSService().send(
            app.user.phone,
            f"KAFIL-SUG'URTA: OSAGO polisingiz #{app.external_policy_id} faollashtirildi."
        )
    except OsagoAPIError as exc:
        logger.warning(f"[Retry] Attempt {self.request.retries + 1} failed for {application_id}: {exc}")
        raise self.retry(exc=exc, countdown=60 * (2 ** self.request.retries))


@shared_task
def send_expiry_reminders():
    """
    Har kuni bajariladi — 30 kun ichida tugaydigan polislar egalariga SMS yuborish.
    """
    from datetime import date, timedelta
    from apps.policies.models import PolicyApplication
    from apps.notifications.services import SMSService

    expiry_date = date.today() + timedelta(days=30)
    expiring = PolicyApplication.objects.filter(
        status=PolicyApplication.Status.ACTIVE,
        coverage_end=expiry_date,
    ).select_related("user")

    sms = SMSService()
    for app in expiring:
        sms.send(
            app.user.phone,
            f"KAFIL-SUG'URTA: OSAGO polisingiz {app.coverage_end} sanada tugaydi. "
            f"Yangilash uchun kafil.uz saytiga kiring."
        )
    logger.info(f"[Expiry] {expiring.count()} ta eslatma yuborildi")
