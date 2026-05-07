"""
referrals/services.py & utils.py
Referal kuzatish va bonus hisoblash
"""

import logging
from django.db import transaction
from django.utils import timezone

logger = logging.getLogger(__name__)


# ── Utils ─────────────────────────────────────────────────────────────────────

def get_referral_from_request(request):
    """
    So'rovdan referal havolani aniqlash.
    Ustuvorlik: 1) URL param, 2) Cookie
    """
    from .models import ReferralLink

    ref_code = (
        request.query_params.get("ref")
        or request.data.get("ref_code")
        or request.COOKIES.get("ref_code")
    )
    if not ref_code:
        return None

    try:
        return ReferralLink.objects.get(code=ref_code, is_active=True)
    except ReferralLink.DoesNotExist:
        return None


# ── Service ───────────────────────────────────────────────────────────────────

class ReferralService:

    @staticmethod
    def apply_bonus(application):
        """
        Polis rasmiylashtirilgandan keyin referal bonusini hisoblash va yozish.
        Atomik operatsiya — xatolikda rollback qilinadi.
        """
        from .models import ReferralBonus

        if not application.referral:
            return

        ref = application.referral
        bonus_amount = application.premium_amount * (ref.bonus_percent / 100)

        with transaction.atomic():
            # Bonus yozish (takrorlanmaslik uchun get_or_create)
            bonus, created = ReferralBonus.objects.get_or_create(
                referral=ref,
                policy_application=application,
                defaults={"amount": bonus_amount, "status": ReferralBonus.Status.PENDING},
            )
            if not created:
                logger.warning(f"[Referral] Bonus already exists for app {application.id}")
                return

            # Referal statistikasini yangilash
            from django.db.models import F
            ref.__class__.objects.filter(pk=ref.pk).update(
                conversion_count=F("conversion_count") + 1,
                total_bonus_earned=F("total_bonus_earned") + bonus_amount,
            )

            # Egasining bonus balansini yangilash
            owner = ref.owner
            owner.__class__.objects.filter(pk=owner.pk).update(
                bonus_balance=F("bonus_balance") + bonus_amount,
            )

        logger.info(
            f"[Referral] Bonus {bonus_amount} so'm yozildi: "
            f"ref={ref.code}, app={application.id}"
        )

    @staticmethod
    def record_click(referral_link):
        """Havola bosilganini hisobga olish"""
        from django.db.models import F
        referral_link.__class__.objects.filter(pk=referral_link.pk).update(
            click_count=F("click_count") + 1
        )
