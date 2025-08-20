
# ClearTariff — Merged (Weasy + Stripe + Email)

This build includes:
- WeasyPrint PDF generator (premium layout)
- Paywall + form at `/form` using Stripe Checkout
- `/generate` returns the PDF **and** emails a copy (SendGrid)
- Dockerfile with WeasyPrint system deps

## Local run
```bash
python -m venv .venv
source .venv/bin/activate  # Windows: .\.venv\Scripts\Activate.ps1
pip install --upgrade pip
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8001
# Open http://127.0.0.1:8001/form
```

## Environment variables
- `APP_URL` — e.g. `https://<your>.up.railway.app`
- `STRIPE_SECRET_KEY` — your Stripe secret
- `STRIPE_PRICE_ID` — a one-time $9 price
- `SENDGRID_API_KEY` — your SendGrid API key
- `EMAIL_SENDER` — e.g. `contact@content365.xyz`
- `EMAIL_SENDER_NAME` — e.g. `Nathan Bentley`

Create `.env` or set in Railway.

## Deploy (Railway)
Push this folder to GitHub → New Project → Deploy from Repo. Railway will detect the Dockerfile.
Add the environment variables above.
Open `/form` and run a test purchase.

## Notes
- If WeasyPrint system libs are missing locally, use the Dockerfile for a consistent environment.
- The `/pdf/weasy-test` endpoint lets you post raw JSON payloads and download a PDF for debugging.


## Presets (Coffee & Tea)
This build includes optional presets you can load from the form:
- Coffee Importer (0901 HS codes)
- Tea Importer (0902 HS codes)

Click **Load Preset** after selecting a Mode. You can customize values before generating the PDF.


## CSV Import
From the form, click **Import CSV** and choose a file with columns:
`sku,description,qty,unit_value,unit_wt[,hs_code,country_of_origin]`.
Rows will populate the Line Items table. If `hs_code` and `country_of_origin` are present in the first row, they fill the top fields.


## Micro UX
- Clearer labels for Base duty (HTS) and Additional tariff (301)
- HS Code tooltip with coffee/tea examples
- Import CSV now has a Sample CSV download
- Inline validation ensures HS code and at least one valid line item


## Pricing
- Recommended: **$9 per report** via Stripe Checkout (set `STRIPE_PRICE_ID`).
- Optional: monthly plan later (e.g., $29/mo for power users).


## Amazon Sellers Edition (v1.0)
- New **Amazon-focused form** with ASIN/SKU, units, unit value, and cost fields
- **Landed Cost per Unit** in the PDF summary
- Optional email delivery (writes to `/outbox` in dev)
- Keep HS code for advanced users; duty % can be adjusted for scenarios

- New /pricing page with $9 per report and $29/mo unlimited plan.
