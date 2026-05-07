"""
notifications/services.py
SMS Gateway: Eskiz.uz integratsiya
Token avtomatik yangilanadi va Redis'da keshlanadi
"""

import logging
import requests
from django.conf import settings
from django.core.cache import cache

logger = logging.getLogger(__name__)

ESKIZ_TOKEN_CACHE_KEY = "eskiz:access_token"


class SMSService:
    """Eskiz.uz orqali SMS yuborish"""

    BASE_URL = settings.ESKIZ_BASE_URL
    EMAIL = settings.ESKIZ_EMAIL
    PASSWORD = settings.ESKIZ_PASSWORD

    def _get_token(self) -> str | None:
        """
        Eskiz.uz API tokenini olish.
        Token Redis'da 24 soat saqlanadi.
        """
        token = cache.get(ESKIZ_TOKEN_CACHE_KEY)
        if token:
            return token

        try:
            response = requests.post(
                f"{self.BASE_URL}/auth/login",
                data={"email": self.EMAIL, "password": self.PASSWORD},
                timeout=10,
            )
            response.raise_for_status()
            data = response.json()
            token = data.get("data", {}).get("token")
            if token:
                cache.set(ESKIZ_TOKEN_CACHE_KEY, token, timeout=86000)  # ~23.9 soat
            return token
        except Exception as e:
            logger.error(f"[SMS] Eskiz login failed: {e}")
            return None

    def _refresh_token(self):
        """Tokenni qayta olish"""
        cache.delete(ESKIZ_TOKEN_CACHE_KEY)
        return self._get_token()

    def send(self, phone: str, message: str) -> bool:
        """
        SMS yuborish.
        Agar token muddati o'tgan bo'lsa — avtomatik yangilanadi.
        """
        if not self.EMAIL or not self.PASSWORD:
            logger.warning("[SMS] Eskiz credentials sozlanmagan. SMS yuborilmadi.")
            return True  # Dev rejimida xato chiqarmasin

        token = self._get_token()
        if not token:
            logger.error(f"[SMS] Token olishda xatolik. Phone: {phone}")
            return False

        # +998 prefiksini olib tashlash
        clean_phone = phone.replace("+", "")

        for attempt in range(2):
            try:
                response = requests.post(
                    f"{self.BASE_URL}/message/sms/send",
                    headers={"Authorization": f"Bearer {token}"},
                    json={
                        "mobile_phone": clean_phone,
                        "message": message,
                        "from": "4546",
                    },
                    timeout=10,
                )

                if response.status_code == 401 and attempt == 0:
                    # Token muddati o'tgan — yangilash
                    token = self._refresh_token()
                    continue

                response.raise_for_status()
                data = response.json()

                if data.get("status") == "waiting":
                    logger.info(f"[SMS] Yuborildi: {phone}")
                    return True
                else:
                    logger.warning(f"[SMS] Kutilmagan javob: {data}")
                    return False

            except requests.RequestException as e:
                logger.error(f"[SMS] Request error (attempt {attempt+1}): {e}")
                if attempt == 1:
                    return False

        return False
