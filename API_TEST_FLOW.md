# KAFIL OSAGO Backend — test oqimi

1) `.env` yarating:

```bash
cp .env.example .env
```

2) Docker orqali ishga tushiring:

```bash
docker compose up --build
```

3) Swagger:

```text
http://localhost:8000/api/docs/
```

4) Demo rejimda test qilish:

- `POST /api/v1/auth/otp/send/`
- `POST /api/v1/auth/otp/verify/`
- `POST /api/v1/policies/calculate/`
- `POST /api/v1/policies/apply/`
- `POST /api/v1/payments/invoice/`
- `POST /api/v1/payments/demo/complete/`
- `GET /api/v1/policies/{policy_id}/download/`

`OSAGO_DEMO_MODE=True` bo'lsa, real OSAGO API credential bo'lmasa ham calculation, policy activation va PDF generation ishlaydi.
