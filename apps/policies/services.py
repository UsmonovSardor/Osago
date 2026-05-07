"""
policies/services.py
Tashqi OSAGO API bilan integratsiya + Redis kesh
"""

import logging
import hashlib
import requests
from decimal import Decimal
from django.conf import settings
from django.core.cache import cache

logger = logging.getLogger(__name__)


class OsagoAPIService:
    """
    Tashqi OSAGO API bilan ishlash servisi.
    Redis orqali natijalar keshlanadi (10 daqiqa).
    """

    BASE_URL = settings.OSAGO_API_BASE_URL
    API_KEY = settings.OSAGO_API_KEY
    API_SECRET = settings.OSAGO_API_SECRET
    TIMEOUT = 15  # sekund

    def _headers(self):
        return {
            "Authorization": f"Bearer {self.API_KEY}",
            "X-API-Secret": self.API_SECRET,
            "Content-Type": "application/json",
            "Accept": "application/json",
        }

    def _cache_key(self, prefix: str, *args) -> str:
        raw = "_".join(str(a) for a in args)
        h = hashlib.md5(raw.encode()).hexdigest()
        return f"osago:{prefix}:{h}"

    def _demo_vehicle_info(self, plate_number: str, tech_passport: str) -> dict:
        """Real API credential yo'q paytda loyiha to'liq test qilinishi uchun demo javob."""
        year_seed = sum(ord(ch) for ch in plate_number) % 10
        return {
            "plate_number": plate_number.upper(),
            "tech_passport": tech_passport.upper(),
            "brand": "Chevrolet",
            "model": "Cobalt",
            "year": 2014 + year_seed,
            "engine_power": 106,
            "vehicle_type": "YENGIL_AVTOMOBIL",
        }

    def _demo_premium(self, plate_number: str, tech_passport: str, period_months: int) -> dict:
        base = Decimal("168000")
        coeff = Decimal(str(period_months)) / Decimal("12")
        amount = (base * coeff).quantize(Decimal("1"))
        return {
            "amount": str(amount),
            "currency": "UZS",
            "period_months": int(period_months),
            "tariff": "DEMO_OSAGO_STANDARD",
        }

    def get_vehicle_info(self, plate_number: str, tech_passport: str) -> dict:
        """
        Avtomobil ma'lumotlarini olish.
        Natija 10 daqiqaga keshlanadi.
        """
        if settings.OSAGO_DEMO_MODE or not self.BASE_URL:
            return self._demo_vehicle_info(plate_number, tech_passport)

        cache_key = self._cache_key("vehicle", plate_number, tech_passport)
        cached = cache.get(cache_key)
        if cached:
            logger.info(f"[OSAGO] Vehicle cache hit: {plate_number}")
            return cached

        try:
            response = requests.post(
                f"{self.BASE_URL}/vehicle/info",
                json={"plate_number": plate_number, "tech_passport": tech_passport},
                headers=self._headers(),
                timeout=self.TIMEOUT,
            )
            response.raise_for_status()
            data = response.json()
            cache.set(cache_key, data, timeout=settings.OSAGO_CACHE_TIMEOUT)
            return data
        except requests.Timeout:
            logger.error(f"[OSAGO] Timeout: get_vehicle_info {plate_number}")
            raise OsagoAPIError("Tashqi API javob bermadi. Qayta urinib ko'ring.")
        except requests.HTTPError as e:
            logger.error(f"[OSAGO] HTTPError: {e.response.status_code} - {e.response.text}")
            raise OsagoAPIError(f"API xatosi: {e.response.status_code}")
        except Exception as e:
            logger.exception(f"[OSAGO] Unexpected error: {e}")
            raise OsagoAPIError("Ichki xatolik yuz berdi.")

    def calculate_premium(
        self,
        plate_number: str,
        tech_passport: str,
        period_months: int = 12,
    ) -> dict:
        """
        Sug'urta mukofotini hisoblash.
        """
        if settings.OSAGO_DEMO_MODE or not self.BASE_URL:
            return self._demo_premium(plate_number, tech_passport, period_months)

        cache_key = self._cache_key("premium", plate_number, tech_passport, period_months)
        cached = cache.get(cache_key)
        if cached:
            return cached

        try:
            response = requests.post(
                f"{self.BASE_URL}/osago/calculate",
                json={
                    "plate_number": plate_number,
                    "tech_passport": tech_passport,
                    "period_months": period_months,
                },
                headers=self._headers(),
                timeout=self.TIMEOUT,
            )
            response.raise_for_status()
            data = response.json()
            cache.set(cache_key, data, timeout=settings.OSAGO_CACHE_TIMEOUT)
            return data
        except requests.Timeout:
            raise OsagoAPIError("Narx hisoblash API'si javob bermadi.")
        except requests.HTTPError as e:
            raise OsagoAPIError(f"Narx hisoblashda xatolik: {e.response.status_code}")

    def register_policy(self, application) -> dict:
        """
        Polisni tashqi API'da rasmiylashtirish.
        Bu atomik bo'lishi kerak — to'lov muvaffaqiyatli bo'lgandan keyin chaqiriladi.
        """
        if settings.OSAGO_DEMO_MODE or not self.BASE_URL:
            return {
                "policy_id": f"KAFIL-{str(application.id)[:8].upper()}",
                "status": "ACTIVE",
                "provider": "DEMO_OSAGO",
            }

        payload = {
            "plate_number": application.plate_number,
            "tech_passport": application.tech_passport,
            "owner_full_name": application.owner_full_name,
            "owner_passport": application.owner_passport,
            "owner_pinfl": application.owner_pinfl,
            "coverage_start": str(application.coverage_start),
            "coverage_end": str(application.coverage_end),
            "period_months": application.coverage_period_months,
            "premium_amount": str(application.premium_amount),
            # Idempotency key — bir xil ariza ikki marta yuborilmasin
            "idempotency_key": str(application.id),
        }
        try:
            response = requests.post(
                f"{self.BASE_URL}/osago/register",
                json=payload,
                headers=self._headers(),
                timeout=30,
            )
            response.raise_for_status()
            return response.json()
        except requests.HTTPError as e:
            logger.error(
                f"[OSAGO] register_policy failed: app={application.id}, "
                f"status={e.response.status_code}, body={e.response.text}"
            )
            raise OsagoAPIError(f"Polisni rasmiylashtirish muvaffaqiyatsiz: {e.response.status_code}")
        except Exception as e:
            logger.exception(f"[OSAGO] register_policy exception: {e}")
            raise OsagoAPIError("Polisni rasmiylashtirish jarayonida xatolik yuz berdi.")


class OsagoAPIError(Exception):
    """Tashqi API xatoligi"""
    pass
