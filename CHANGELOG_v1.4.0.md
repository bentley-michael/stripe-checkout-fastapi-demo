# ClearTariff v1.4.0 — Launch-Ready Changes

## New
- Amazon-seller presets added (Electronics & Accessories, Home & Kitchen, Health & Beauty, Clothing & Apparel, Toys & Games, Sports & Outdoors). Selecting a category auto-fills a starting HS code + duty % (editable).
- Trust header and value proposition added above form to improve conversions.
- Pricing clarity note added near the form (First report FREE · $9/report suggested).
- Success/Cancel templates included for a clean checkout flow.
- PDF branding helpers injected: header/footer stubs for ReportLab-based generator paths.

## Updated
- Form UI: subtle visual polish (spacing, rounded fields, helpful copy).
- Index/form templates now include preset selector and a tip explaining override ability.

## Notes
- HS codes and duty % in presets are examples to reduce friction; users can and should adjust for their exact product.
- Stripe keys and `.env` values are unchanged; confirm test/live mode in deployment.
- If you have custom PDF logic, our helpers are additive and won't remove your existing content.