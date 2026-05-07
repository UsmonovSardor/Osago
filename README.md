# KAFIL-SUG'URTA — OSAGO Backend API

Django + PostgreSQL + Redis + Celery asosida qurilgan to'liq backend tizim.

---

## 📁 Loyiha Tuzilmasi

```
kafil_osago/
├── config/
│   ├── settings.py        # Barcha sozlamalar
│   ├── urls.py            # Asosiy URL yo'naltirgich
│   └── celery.py          # Celery konfiguratsiya
├── apps/
│   ├── accounts/          # Foydalanuvchilar, 2FA (OTP)
│   ├── policies/          # OSAGO arizalari, tashqi API
│   ├── payments/          # Click, Payme, Uzum Pay
│   ├── referrals/         # Referal tizimi, bonus
│   └── notifications/     # SMS (Eskiz.uz)
├── requirements.txt
├── docker-compose.yml
└── Dockerfile
```

---

## 🚀 Ishga Tushirish

### 1. Environment sozlash
```bash
cp .env.example .env
# .env faylini o'z ma'lumotlaringiz bilan to'ldiring
```

### 2. Docker orqali (tavsiya)
```bash
docker-compose up -d
docker-compose exec api python manage.py migrate
docker-compose exec api python manage.py createsuperuser
```

### 3. Mahalliy ishlab chiqish
```bash
pip install -r requirements.txt
python manage.py migrate
python manage.py createsuperuser
python manage.py runserver

# Alohida terminallarda:
celery -A config worker --loglevel=info
celery -A config beat --loglevel=info
```

---

## 🔗 API Endpointlar

| Yo'l | Metod | Tavsif |
|------|-------|--------|
| `/api/v1/auth/otp/send/` | POST | SMS-kod yuborish |
| `/api/v1/auth/otp/verify/` | POST | Kodni tasdiqlash + JWT olish |
| `/api/v1/auth/token/refresh/` | POST | Access token yangilash |
| `/api/v1/auth/logout/` | POST | Chiqish |
| `/api/v1/auth/profile/` | GET/PUT | Profil |
| `/api/v1/policies/calculate/` | POST | Sug'urta narxini hisoblash |
| `/api/v1/policies/apply/` | POST | Yangi ariza yaratish |
| `/api/v1/policies/` | GET | Mening arizalarim |
| `/api/v1/policies/<id>/` | GET | Ariza tafsiloti |
| `/api/v1/payments/invoice/` | POST | To'lov linki yaratish |
| `/api/v1/payments/callback/click/` | POST | Click callback |
| `/api/v1/payments/callback/payme/` | POST | Payme JSON-RPC |
| `/api/v1/referrals/my/links/` | GET/POST | Referal havolalar |
| `/api/v1/referrals/my/bonuses/` | GET | Bonus tarixi |
| `/api/v1/referrals/my/stats/` | GET | Statistika |
| `/api/docs/` | GET | Swagger UI |

---

## 🔒 Xavfsizlik

### 2FA jarayoni
```
1. POST /auth/otp/send/  { "phone": "+998901234567" }
   → SMS yuboriladi (5 daqiqa amal qiladi)

2. POST /auth/otp/verify/ { "phone": "...", "code": "123456" }
   → { "access": "...", "refresh": "...", "user": {...} }

3. Keyingi so'rovlar: Header: Authorization: Bearer <access_token>
```

### Spam himoya
- SMS: 1 daqiqada 1 ta so'rov (IP throttle + kod bekor qilish)
- OTP: 3 ta noto'g'ri urinishdan keyin kod bekor qilinadi
- API: anon=20/min, user=100/min

---

## 💳 To'lov Jarayoni

```
1. Ariza yaratish (PENDING_PAYMENT holati)
2. Invoice olish: POST /payments/invoice/ { provider: "CLICK"|"PAYME" }
3. Foydalanuvchi to'lov sahifasiga yo'naltiriladi
4. To'lov tizimi callback yuboradi → _activate_policy_atomically()
   ├── Tranzaksiya SUCCESS → (idempotency bilan)
   ├── Tashqi API'da polis rasmiylashtiriladi
   ├── PDF yaratiladi
   ├── Referal bonus yoziladi
   └── SMS yuboriladi
```

### Atomicity & Idempotency
- `select_for_update()` orqali race condition oldini olish
- `idempotency_key` bilan bir tranzaksiya ikki marta qayta ishlanmaydi
- Tashqi API xato bersa → Celery retry (5 marta, 1/2/4/8/16 daqiqa)

---

## 🔗 Referal Tizimi

```
1. Agent/foydalanuvchi havola oladi: kafil.uz/osago?ref=ABC12345
2. Yangi foydalanuvchi shu havola orqali kiradi → Cookie/URL param saqlanadi
3. Polis sotib olinsa → bonus_percent % bonus referal egasiga yoziladi
4. Admin panel → ReferralBonus.PAID → pul o'tkaziladi
```

---

## 📊 Admin Panel

Django Admin: `/admin/`
- Foydalanuvchilar boshqaruvi
- Polis arizalari ko'rish va eksport
- Tranzaksiyalar tarixi
- Referal statistikasi

API Admin endpointlar (IsAdminUser):
- `GET /api/v1/policies/admin/stats/` — Umumiy statistika
- `GET /api/v1/policies/admin/list/` — Barcha arizalar
- `GET /api/v1/payments/admin/transactions/` — Tranzaksiyalar
- `GET /api/v1/referrals/admin/links/` — Referal havolalar

---

## 🛠 Celery Vazifalar

| Vazifa | Ishga tushirish | Tavsif |
|--------|-----------------|--------|
| `retry_policy_registration` | Avtomatik (xato bo'lsa) | API xato → qayta urinish |
| `send_expiry_reminders` | Har kuni | 30 kundan muddati o'tadiganlar |

---

## 🌐 Tashqi Integratsiyalar

| Tizim | Tavsif |
|-------|--------|
| Eskiz.uz | SMS yuborish (token auto-refresh) |
| Click | To'lov tizimi (imzo tekshirish) |
| Payme | To'lov tizimi (JSON-RPC, Basic Auth) |
| OSAGO API | Avtomobil ma'lumotlari + polis rasmiylashtirish |
| Redis | Kesh (API natijalar, Eskiz token) |


## Ishga tushirish

```bash
cp .env.example .env
docker compose up --build
```

Swagger: http://localhost:8000/api/docs/

Demo rejimda `OSAGO_DEMO_MODE=True` bo'lsa tashqi OSAGO API credential talab qilinmaydi. SMS credential bo'lmasa, SMS service dev rejimda xatolik bermaydi.
