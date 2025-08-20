# ClearTariff — Project Charter (Amazon FBA First)

## Vision
The fastest way for Amazon sellers to calculate duties & tariffs before shipping, with clean PDF documentation for team/brokers.

## Target Users
- Primary: Amazon FBA sellers (China → US/EU importers)
- Secondary: Coffee/tea importers (case studies, presets)
- Future: Freight forwarders & customs consultants

## Core Objectives
- Instant duty/tariff calculation from HS code + shipment value
- Professional PDF report branded as ClearTariff
- Stripe pay-per-report ($9) with future subscription option
- Simple, trustworthy UX with presets & CSV import

## Scope (MVP)
- Form at `/form` with HS code, countries, value, costs
- Generate PDF via `/generate` (Weasy/ReportLab fallback)
- Paywall via Stripe Checkout, success/cancel routes
- Email delivery optional via SendGrid

## Risks & Mitigations
- Data freshness → show disclaimer; add live sources in v2
- Adoption → niche positioning (Amazon FBA) + examples
- Payment failures → Stripe sandbox test, graceful errors
- Legal/compliance → disclaimers; broker validation path

## KPIs
- Reports generated / week
- Conversion rate to paid
- Revenue (MRR/one-off)
- Time from open → PDF download

## Timeline (MVP)
- Week 1: Branding, PDF polish, paywall enforcement
- Week 2: Launch on Railway + first users
- Week 3–4: Add live data sources & testimonials