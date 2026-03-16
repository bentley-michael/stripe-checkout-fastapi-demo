# Upgrade Guide (v1.4.0)

## 1) Environment
Ensure your `.env` has (examples):
```
APP_URL=http://127.0.0.1:8000
SUCCESS_URL=http://127.0.0.1:8000/success
CANCEL_URL=http://127.0.0.1:8000/cancel
ENABLE_PAYWALL=false   # set true when ready to charge
STRIPE_PUBLIC_KEY=pk_test_xxx
STRIPE_SECRET_KEY=sk_test_xxx
```
(Use your live keys and set `ENABLE_PAYWALL=true` when launching.)

## 2) Deploy
- `pip install -r requirements.txt`
- `uvicorn app.main:app --reload` (local)
- Deploy to Railway; add the same env vars there.

## 3) Using Presets
- Choose a category from the new dropdown to auto-fill HS code + duty %.
- You can override HS code and duty % anytime.

## 4) PDF
- We added lightweight header/footer helpers for ReportLab paths to brand the PDF.
- If you use WeasyPrint, your current templates should remain untouched.

## 5) Pricing
- The page shows a price note. You can tune copy or logic in templates.
- Suggested: First report FREE; then $9/report to start.