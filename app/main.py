# app/main.py
import os
import logging
from datetime import datetime
from typing import Dict, Any, Optional, List

import stripe
import uvicorn
from fastapi import FastAPI, Response, Form, Request, HTTPException, Query
from fastapi.responses import HTMLResponse, JSONResponse, FileResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles

# --- ReportLab primitives (installed via: pip install reportlab)
from reportlab.pdfgen import canvas as _rl_canvas
from reportlab.lib.pagesizes import letter as _letter
from reportlab.lib.units import inch as _inch
import io as _io

from dotenv import load_dotenv, find_dotenv
load_dotenv(find_dotenv(usecwd=True), override=False)

# ---------- Helpers ----------
def env_bool(name: str, default: bool = False) -> bool:
    v = os.getenv(name)
    if v is None:
        return default
    return str(v).strip().lower() in ("1", "true", "t", "yes", "y", "on")

LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()
logging.basicConfig(level=getattr(logging, LOG_LEVEL, logging.INFO))
logging.getLogger("fontTools").setLevel(logging.WARNING)
logging.getLogger("weasyprint").setLevel(logging.INFO)

APP_URL = os.getenv("APP_URL") or "http://127.0.0.1:8000"
SUCCESS_URL = os.getenv("SUCCESS_URL") or f"{APP_URL.rstrip('/')}/success"
CANCEL_URL = os.getenv("CANCEL_URL") or f"{APP_URL.rstrip('/')}/cancel"
ENABLE_PAYWALL = env_bool("ENABLE_PAYWALL", default=False)
PAYWALL_ENABLED = env_bool("PAYWALL_ENABLED", default=False)  # alt flag
ENABLE_WEASY = env_bool("ENABLE_WEASY", default=False)  # off on Windows
PREFER_REPORTLAB = env_bool("PREFER_REPORTLAB", default=True)

# Stripe
stripe.api_key = os.getenv("STRIPE_SECRET_KEY")
if os.getenv("STRIPE_API_VERSION"):
    stripe.api_version = os.getenv("STRIPE_API_VERSION")
try:
    stripe.set_app_info("ClearTariff", version="1.4")
except Exception:
    pass

# ---------- App ----------
app = FastAPI(title="ClearTariff — Phase 1")
templates = Jinja2Templates(directory="app/templates")

logging.info(
    "ENV LOADED: APP_URL=%s SUCCESS_URL=%s CANCEL_URL=%s ENABLE_PAYWALL=%s STRIPE_KEY_SET=%s",
    APP_URL, SUCCESS_URL, CANCEL_URL, (ENABLE_PAYWALL or PAYWALL_ENABLED), bool(stripe.api_key),
)

# ---------- Optional providers (don't crash if missing) ----------
try:
    from app.data.providers import us_hts_rate, uk_tariff_rate, ecb_rate  # optional
except Exception as e:
    us_hts_rate = uk_tariff_rate = ecb_rate = None  # type: ignore
    logging.info("Rate providers unavailable: %s", e)

# ---------- CORS ----------
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---------- Static + sample ----------
app.mount("/static", StaticFiles(directory="app/static"), name="static")


@app.get("/sample", response_class=FileResponse)
def sample_pdf():
    path = "app/static/sample_report.pdf"
    if not os.path.exists(path):
        raise HTTPException(status_code=404, detail="Sample PDF not found")
    return FileResponse(path, media_type="application/pdf", filename="TariffTool_Sample.pdf")


# ---------- Presets ----------
@app.get("/presets/{name}")
def get_preset(name: str):
    import json
    base_dir = os.path.dirname(__file__)
    p = os.path.join(base_dir, "presets", f"{name}.json")
    if not os.path.exists(p):
        raise HTTPException(status_code=404, detail="Preset not found")
    with open(p, "r", encoding="utf-8") as f:
        return json.load(f)


# ---------- API: quick rate lookup ----------
@app.get("/api/rates")
def api_rates(hs_code: str, market: str = "US"):
    if us_hts_rate is None and uk_tariff_rate is None:
        return JSONResponse({"ok": False, "message": "Rate providers not installed"}, status_code=501)

    data = None
    if market.upper() == "US" and us_hts_rate:
        data = us_hts_rate(hs_code)
    elif market.upper() == "UK" and uk_tariff_rate:
        data = uk_tariff_rate(hs_code)

    if not data:
        return JSONResponse({"ok": False, "message": "No rate found"}, status_code=404)
    return {"ok": True, "data": data}


# ---------- PDF engines ----------
PDF_ENGINE_LAST = "unset"


def _ct_draw_header(c, title="ClearTariff — Landed Cost & Duty Report"):
    """Simple shared header used by minimal/inline generators."""
    try:
        w, h = _letter
        c.setFont("Helvetica-Bold", 12)
        c.drawString(40, h - 40, title)
        c.setFont("Helvetica", 9)
        c.drawString(40, h - 54, "Amazon Sellers: Landed Cost & Duty Calculator")
        c.line(40, h - 58, w - 40, h - 58)
    except Exception:
        pass


def _ct_draw_footer(c):
    """Simple shared footer used by minimal/inline generators."""
    try:
        w, _ = _letter
        c.setFont("Helvetica", 8)
        c.drawString(40, 30, f"© {datetime.utcnow().year} ClearTariff — cleartariff.com")
        c.drawRightString(w - 40, 30, "Generated by ClearTariff")
    except Exception:
        pass


def _minimal_pdf_fallback(note: str = "Fallback PDF", details: Optional[dict] = None) -> bytes:
    """Tiny, bulletproof one-page PDF."""
    global PDF_ENGINE_LAST
    PDF_ENGINE_LAST = "fallback-minimal"
    buf = _io.BytesIO()
    c = _rl_canvas.Canvas(buf, pagesize=_letter)
    w, h = _letter

    _ct_draw_header(c)
    c.setFont("Helvetica-Bold", 16)
    c.drawString(72, h - 90, "ClearTariff Report")
    c.setFont("Helvetica", 10)
    c.drawString(72, h - 108, note)

    if details:
        y = h - 132
        c.setFont("Helvetica", 9)
        for k, v in list(details.items())[:20]:
            c.drawString(72, y, f"{k}: {v}")
            y -= 14
            if y < 72:
                _ct_draw_footer(c)
                c.showPage()
                _ct_draw_header(c)
                y = h - 72

    _ct_draw_footer(c)
    c.showPage()
    c.save()
    buf.seek(0)
    return buf.getvalue()


def _inline_rl_basic(payload: Dict[str, Any]) -> bytes:
    """Built-in clean ReportLab generator (no external imports)."""
    global PDF_ENGINE_LAST
    PDF_ENGINE_LAST = "inline-reportlab"
    buf = _io.BytesIO()
    c = _rl_canvas.Canvas(buf, pagesize=_letter)
    w, h = _letter

    # Header bar
    c.setFillGray(0.95)
    c.rect(0, h - 1.0 * _inch, w, 1.0 * _inch, stroke=0, fill=1)
    c.setFillGray(0)
    c.setFont("Helvetica-Bold", 18)
    c.drawString(0.75 * _inch, h - 0.6 * _inch, "Tariff & Landed Cost Report")
    c.setFont("Helvetica", 9)
    c.drawRightString(
        w - 0.75 * _inch,
        h - 0.35 * _inch,
        datetime.utcnow().strftime("Generated: %Y-%m-%d %H:%M UTC"),
    )

    # Basics
    y = h - 1.35 * _inch
    c.setFont("Helvetica-Bold", 12)
    c.drawString(0.75 * _inch, y, "Shipment Details")
    y -= 0.25 * _inch
    c.setFont("Helvetica", 10)
    kv = [
        ("HS Code", str(payload.get("hs_code", ""))),
        ("Origin", str(payload.get("country_of_origin", ""))),
        ("Destination", str(payload.get("destination", ""))),
        ("Incoterm", str(payload.get("incoterm", ""))),
    ]
    for k, v in kv:
        c.drawString(0.75 * _inch, y, f"{k}: {v}")
        y -= 0.18 * _inch

    # Rates
    y -= 0.08 * _inch
    c.setFont("Helvetica-Bold", 12)
    c.drawString(0.75 * _inch, y, "Rates")
    y -= 0.22 * _inch
    c.setFont("Helvetica", 10)
    base = float(payload.get("base_rate", 0.0)) * 100.0
    addl = float(payload.get("tariff_rate", 0.0)) * 100.0
    c.drawString(0.75 * _inch, y, f"Base Rate (HTS/TARIC): {base:.2f}%")
    y -= 0.18 * _inch
    c.drawString(0.75 * _inch, y, f"Additional Tariff: {addl:.2f}%")
    y -= 0.22 * _inch

    # Totals
    c.setFont("Helvetica-Bold", 12)
    c.drawString(0.75 * _inch, y, "Landed Cost Summary (USD)")
    y -= 0.22 * _inch
    c.setFont("Helvetica", 10)
    T = payload.get("totals", {}) or {}
    for k, key in [
        ("Merchandise Value", "merch_value"),
        ("Freight", "freight"),
        ("Insurance", "insurance"),
        ("Duty", "duty"),
        ("Brokerage", "brokerage"),
        ("Other Fees", "other_fees"),
        ("Total Landed", "total_landed"),
    ]:
        val = float(T.get(key, 0.0))
        c.drawString(0.75 * _inch, y, f"{k}: ${val:,.2f}")
        y -= 0.18 * _inch

    # Scenarios (if any)
    S = payload.get("scenarios", []) or []
    if S:
        y -= 0.08 * _inch
        c.setFont("Helvetica-Bold", 12)
        c.drawString(0.75 * _inch, y, "Scenarios")
        y -= 0.18 * _inch
        c.setFont("Helvetica", 10)
        for s in S:
            duty = float((s.get("totals") or {}).get("duty", 0.0))
            tot = float((s.get("totals") or {}).get("total_landed", 0.0))
            c.drawString(
                0.75 * _inch,
                y,
                f"• {s.get('name', 'Scenario')}: Duty ${duty:,.2f}, Total ${tot:,.2f}",
            )
            y -= 0.16 * _inch
            if y < 1.0 * _inch:
                c.showPage()
                w, h = _letter
                y = h - 1.0 * _inch

    # Footer
    brand = payload.get("brand", {}) or {}
    if bool(brand.get("show_footer", True)):
        text = f"© {datetime.utcnow().year} {brand.get('name', 'ClearTariff')}"
        if brand.get("website"):
            text += f" • {brand['website']}"
        text += " • For guidance only (Phase 1)."
        c.setFont("Helvetica-Oblique", 9)
        c.drawCentredString(w / 2, 0.5 * _inch, text)

    c.showPage()
    c.save()
    buf.seek(0)
    return buf.getvalue()


# Weasy (optional)
generate_tariff_pdf_weasy = None
try:
    from app.pdf.weasy_report import generate_tariff_pdf_weasy  # optional
except Exception as e:
    logging.warning("WeasyPrint unavailable: %s", e)

# External ReportLab generator (optional)
_ext_rl = None
try:
    from app.pdf.reportlab_report import generate_tariff_pdf_reportlab as _ext_rl
except Exception as e:
    logging.warning("External ReportLab generator not loaded: %s", e)


def _render_pdf(payload: Dict[str, Any]) -> bytes:
    """Try external Weasy → external RL → inline RL → minimal fallback."""
    global PDF_ENGINE_LAST
    if ENABLE_WEASY and not PREFER_REPORTLAB and generate_tariff_pdf_weasy is not None:
        try:
            PDF_ENGINE_LAST = "weasy"
            return generate_tariff_pdf_weasy(payload)
        except Exception:
            logging.exception("Weasy PDF failed; trying external ReportLab.")
    if _ext_rl is not None:
        try:
            PDF_ENGINE_LAST = "external-reportlab"
            return _ext_rl(payload)
        except Exception:
            logging.exception("External ReportLab PDF failed; using inline.")
    try:
        return _inline_rl_basic(payload)
    except Exception as e:
        logging.exception("Inline ReportLab failed; using minimal fallback.")
        return _minimal_pdf_fallback("All generators failed — minimal fallback", {"error": str(e)})


# ---------- Basic routes ----------
@app.get("/", response_class=HTMLResponse)
def marketing_home(request: Request):
    # Serve marketing landing page as the homepage
    return templates.TemplateResponse("index.html", {"request": request})


@app.get("/__health")
def healthcheck():
    return {"ok": True, "status": "healthy"}


@app.get("/_envcheck")
def envcheck():
    return {
        "APP_URL": os.getenv("APP_URL"),
        "SUCCESS_URL": os.getenv("SUCCESS_URL"),
        "CANCEL_URL": os.getenv("CANCEL_URL"),
        "ENABLE_PAYWALL": os.getenv("ENABLE_PAYWALL"),
        "PAYWALL_ENABLED": os.getenv("PAYWALL_ENABLED"),
        "ENABLE_WEASY": os.getenv("ENABLE_WEASY"),
        "PREFER_REPORTLAB": os.getenv("PREFER_REPORTLAB"),
        "STRIPE_KEY_SET": bool(os.getenv("STRIPE_SECRET_KEY")),
    }


# ---------- Generate report (legacy, multi-line-items) ----------
@app.post("/generate_legacy")
def generate_legacy(
    request: Request,
    country_of_origin: str = Form("CN"),
    destination: str = Form("US"),
    hs_code: str = Form("9403.60.8081"),
    incoterm: str = Form("FOB"),
    base_rate: float = Form(0.03),
    tariff_rate: float = Form(0.25),
    merch_value: float = Form(0.0),
    freight: float = Form(0.0),
    insurance: float = Form(0.0),
    brokerage: float = Form(0.0),
    other_fees: float = Form(0.0),
    email: Optional[str] = Form(None),
    session_id: Optional[str] = Query(None),
    sku: List[str] = Form([]),
    description: List[str] = Form([]),
    qty: List[float] = Form([]),
    unit_value: List[float] = Form([]),
    unit_wt: List[float] = Form([]),
    brew_grams_per_cup: float = Form(18.0),
    waste_percent: float = Form(10.0),
    target_margin_percent: float = Form(60.0),
    include_scenarios: Optional[str] = Form(None),
    scenario_tariff_increase: float = Form(0.10),
    scenario_alt_origin: Optional[str] = Form(None),
    scenario_alt_tariff_rate: Optional[float] = Form(None),
    notes: Optional[str] = Form(None),
) -> Response:
    # Build line items
    line_items: List[Dict[str, Any]] = []
    n = min(len(sku), len(description), len(qty), len(unit_value), len(unit_wt))
    for i in range(n):
        try:
            line_items.append(
                {
                    "sku": sku[i],
                    "description": description[i],
                    "qty": float(qty[i] or 0),
                    "unit_value": float(unit_value[i] or 0),
                    "unit_wt": float(unit_wt[i] or 0),
                }
            )
        except Exception:
            pass

    # Auto-sum merchandise value if blank
    if not merch_value and line_items:
        merch_value = sum((li.get("qty", 0) or 0) * (li.get("unit_value", 0) or 0) for li in line_items)

    # Total shipment weight (kg)
    try:
        total_weight_kg = sum((li.get("qty", 0) or 0) * (li.get("unit_wt", 0) or 0) for li in line_items) or 0.0
    except Exception:
        total_weight_kg = 0.0

    # Optional: server-side rate fetch (if providers present)
    rate_data = None
    try:
        if (destination or "").upper() == "US" and us_hts_rate:
            rate_data = us_hts_rate(hs_code)
            if rate_data and (not base_rate or float(base_rate) == 0.0):
                base_rate = float(rate_data.get("base_rate") or 0.0)
        elif (destination or "").upper() == "UK" and uk_tariff_rate:
            rate_data = uk_tariff_rate(hs_code)
            if rate_data and (not base_rate or float(base_rate) == 0.0):
                base_rate = float(rate_data.get("base_rate") or 0.0)
    except Exception as e:
        logging.warning("Rate lookup failed: %s", e)
        rate_data = None

    # Price-per-cup helper inputs → decimals
    try:
        grams = float(brew_grams_per_cup or 0.0)
        waste_frac = float(waste_percent or 0.0) / 100.0
        margin_frac = float(target_margin_percent or 0.0) / 100.0
    except Exception:
        grams, waste_frac, margin_frac = 0.0, 0.0, 0.0
    effective_grams = grams * (1.0 + waste_frac)

    # Duty (base HTS + additional tariff)
    duty = float(merch_value) * (float(base_rate or 0.0) + float(tariff_rate or 0.0))

    total_landed = (
        float(merch_value)
        + float(freight)
        + float(insurance)
        + duty
        + float(brokerage)
        + float(other_fees)
    )

    payload: Dict[str, Any] = {
        "country_of_origin": country_of_origin,
        "destination": destination,
        "hs_code": hs_code,
        "incoterm": incoterm,
        "notes": notes or "",
        "base_rate": base_rate,
        "tariff_rate": tariff_rate,
        "line_items": line_items,
        "totals": {
            "merch_value": merch_value,
            "freight": freight,
            "insurance": insurance,
            "duty": duty,
            "brokerage": brokerage,
            "other_fees": other_fees,
            "total_landed": total_landed,
        },
        "generated_at": datetime.utcnow().isoformat() + "Z",
        "brand": {
            "name": os.getenv("BRAND_NAME") or os.getenv("EMAIL_SENDER_NAME") or "ClearTariff",
            "email": os.getenv("EMAIL_SENDER") or "",
            "website": os.getenv("BRAND_URL") or "",
            "show_footer": str(os.getenv("SHOW_BRAND_FOOTER", "true")).strip().lower() in ("1", "true", "yes", "on"),
        },
        "sources": {
            "tariff_market": (destination or "US").upper(),
            "base_rate_source": (rate_data or {}).get("source"),
            "base_rate_source_url": (rate_data or {}).get("source_url"),
            "fx_source": None,
        },
    }

    # Per-cup helper (kept as-is for coffee/tea users)
    per_cup_cost = suggested_price = 0.0
    if total_weight_kg and effective_grams > 0:
        cost_per_gram = float(total_landed) / (total_weight_kg * 1000.0)
        per_cup_cost = cost_per_gram * effective_grams
        if margin_frac < 0.99:
            suggested_price = per_cup_cost / max(1.0 - margin_frac, 0.01)
    payload["per_cup"] = {
        "brew_grams_per_cup": grams,
        "waste_percent": waste_frac * 100.0,
        "target_margin_percent": margin_frac * 100.0,
        "per_cup_cost": per_cup_cost,
        "suggested_price": suggested_price,
        "total_weight_kg": total_weight_kg,
    }

    # Scenarios
    payload["scenarios"] = []
    include = (include_scenarios or "").strip().lower() in ("1", "true", "on", "yes")
    if include:
        inc = float(scenario_tariff_increase or 0.0)
        t_rate_A = float(tariff_rate or 0.0) + inc
        duty_A = float(merch_value) * (float(base_rate or 0.0) + t_rate_A)
        total_A = float(merch_value) + float(freight) + float(insurance) + float(brokerage) + float(other_fees) + duty_A
        payload["scenarios"].append(
            {
                "name": f"Tariff +{int(inc * 100)}%",
                "country_of_origin": country_of_origin,
                "tariff_rate": t_rate_A,
                "totals": {"total_landed": total_A, "duty": duty_A},
            }
        )
        if scenario_alt_origin:
            try:
                alt_rate = (
                    float(scenario_alt_tariff_rate)
                    if scenario_alt_tariff_rate is not None
                    else float(tariff_rate or 0.0)
                )
            except Exception:
                alt_rate = float(tariff_rate or 0.0)
            duty_B = float(merch_value) * (float(base_rate or 0.0) + alt_rate)
            total_B = float(merch_value) + float(freight) + float(insurance) + float(brokerage) + float(other_fees) + duty_B
            payload["scenarios"].append(
                {
                    "name": f"Alt Origin: {scenario_alt_origin}",
                    "country_of_origin": scenario_alt_origin,
                    "tariff_rate": alt_rate,
                    "totals": {"total_landed": total_B, "duty": duty_B},
                }
            )

    # Render (guaranteed to return bytes)
    pdf_bytes = _render_pdf(payload)

    # Optional email (best-effort)
    try:
        from app.utils.send_email import send_pdf_email  # noqa: F401
    except Exception:
        send_pdf_email = None  # type: ignore
    if email and send_pdf_email is not None:
        filename = f"TariffReport_{hs_code}_{datetime.now().strftime('%Y%m%d')}.pdf"
        subject = "Your Tariff & Landed Cost Report"
        text = "Attached is your generated Tariff & Landed Cost Report. Thanks for using ClearTariff!"
        try:
            _status = send_pdf_email(email, subject, text, pdf_bytes, filename)  # type: ignore[misc]
            logging.info("Email send status: %s", _status)
        except Exception as e:
            logging.warning("Email send failed: %s", e)

    headers = {
        "Content-Disposition": f"attachment; filename=TariffReport_{hs_code}.pdf",
        "X-PDF-Engine": PDF_ENGINE_LAST,
    }
    return Response(content=pdf_bytes, media_type="application/pdf", headers=headers)


# ---------- Simple pages (success/cancel) ----------
try:
    from app.routes.routes_pages import router as pages_router
    app.include_router(pages_router)
except Exception as e:
    logging.warning("Pages router not loaded: %s", e)

try:
    from app.routes.routes_success import router as success_router
    app.include_router(success_router)
except Exception as e:
    logging.warning("Success router not loaded: %s", e)

try:
    from app.routes.routes_checkout import router as checkout_router
    app.include_router(checkout_router)
except Exception as e:
    logging.warning("Checkout router not loaded: %s", e)

try:
    from app.routes.routes_webhook import router as webhook_router
    app.include_router(webhook_router)
except Exception as e:
    logging.warning("Webhook router not loaded: %s", e)


def _route_exists(path: str, methods: Optional[set[str]] = None) -> bool:
    for route in app.routes:
        if getattr(route, "path", None) != path:
            continue
        route_methods = set(getattr(route, "methods", set()) or set())
        if methods is None or methods.issubset(route_methods):
            return True
    return False


if not _route_exists("/success", {"GET"}):
    @app.get("/success", response_class=HTMLResponse)
    async def success_fallback():
        return HTMLResponse(
            """
            <html>
                <head><title>Checkout Complete</title></head>
                <body>
                    <h1>Checkout complete</h1>
                    <p>Your checkout has been completed successfully.</p>
                </body>
            </html>
            """
        )


if not _route_exists("/cancel", {"GET"}):
    @app.get("/cancel", response_class=HTMLResponse)
    async def cancel_fallback():
        return HTMLResponse(
            """
            <html>
                <head><title>Checkout Canceled</title></head>
                <body>
                    <h1>Checkout canceled</h1>
                    <p>Your checkout was canceled and no charge was made.</p>
                </body>
            </html>
            """
        )


# ---------- Self-test (tells you which engine ran) ----------
@app.get("/_pdf_selftest")
def pdf_selftest():
    if ENABLE_PAYWALL:
        return HTMLResponse(
            '<h2>Purchase Required</h2><p>Please buy a report on <a href="/pricing">/pricing</a>.</p>',
            status_code=402,
        )

    payload = {
        "hs_code": "6403.59",
        "country_of_origin": "CN",
        "destination": "US",
        "incoterm": "FOB",
        "base_rate": 0.03,
        "tariff_rate": 0.25,
        "totals": {
            "merch_value": 5000,
            "freight": 300,
            "insurance": 25,
            "duty": 1400,
            "brokerage": 75,
            "other_fees": 50,
            "total_landed": 6850,
        },
        "brand": {"name": "ClearTariff", "website": "", "show_footer": True},
        "scenarios": [{"name": "Tariff +10%", "totals": {"duty": 1900, "total_landed": 7350}}],
        "sources": {"tariff_market": "US", "base_rate_source": "Manual/Static (Phase 1)"},
    }
    try:
        pdf_bytes = _render_pdf(payload)
        headers = {
            "Content-Disposition": "attachment; filename=TariffReport_SelfTest.pdf",
            "X-PDF-Engine": PDF_ENGINE_LAST,
        }
        return Response(content=pdf_bytes, media_type="application/pdf", headers=headers)
    except Exception as e:
        return JSONResponse({"ok": False, "error": str(e)}, status_code=500)


# ---- DEBUG: routes and quick hello.pdf ----
@app.get("/__routes")
def _list_routes():
    return [getattr(r, "path", None) for r in app.router.routes]


@app.get("/hello.pdf")
def hello_pdf():
    buf = _io.BytesIO()
    c = _rl_canvas.Canvas(buf, pagesize=_letter)
    w, h = _letter
    c.setFont("Helvetica-Bold", 18)
    c.drawString(72, h - 72, "Hello from ClearTariff")
    c.setFont("Helvetica", 11)
    c.drawString(72, h - 96, "If you see this, PDF rendering works.")
    c.showPage()
    c.save()
    buf.seek(0)
    b = buf.getvalue()
    headers = {"Content-Disposition": "attachment; filename=hello.pdf"}
    logging.info("/hello.pdf rendered %s bytes", len(b))
    return Response(content=b, media_type="application/pdf", headers=headers)


# ---- Amazon Sellers: simple generate endpoint ----
from app.pdf.reportlab_report_amazon import build_pdf as build_pdf_amazon


@app.post("/generate")
async def generate_amazon(
    request: Request,
    asin: str = Form(None),
    sku: str = Form(None),
    product_name: str = Form(""),
    hs_code: str = Form(""),
    incoterm: str = Form("FOB"),
    duty_rate_pct: float = Form(0.0),
    units: int = Form(0),
    unit_value_usd: float = Form(0.0),
    freight_usd: float = Form(0.0),
    insurance_usd: float = Form(0.0),
    other_costs_usd: float = Form(0.0),
    fba_prep_usd: float = Form(0.0),
    usd_fx_note: str = Form(""),
    notes: str = Form(""),
    buyer: str = Form(""),
    seller: str = Form(""),
    country_of_origin: str = Form(""),
    market: str = Form("US"),
    email: str = Form(""),
):
    if ENABLE_PAYWALL:
        return HTMLResponse(
            '<h2>Purchase Required</h2><p>Please buy a report on <a href="/pricing">/pricing</a>.</p>',
            status_code=402,
        )

    payload = {
        "meta": {
            "asin": asin,
            "sku": sku,
            "product_name": product_name,
            "hs_code": hs_code,
            "market": market,
            "country_of_origin": country_of_origin,
            "email": email,
            "buyer": buyer,
            "seller": seller,
            "usd_fx_note": usd_fx_note,
            "notes": notes,
            "date_str": datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC"),
        },
        "numbers": {
            "duty_rate_pct": duty_rate_pct,
            "units": units,
            "unit_value_usd": unit_value_usd,
            "freight_usd": freight_usd,
            "insurance_usd": insurance_usd,
            "other_costs_usd": other_costs_usd,
            "fba_prep_usd": fba_prep_usd,
        },
    }
    pdf_bytes = build_pdf_amazon(payload)
    fname = f"TariffReport_{(hs_code or 'NA').replace('.', '')}_{datetime.utcnow().strftime('%Y%m%d%H%M%S')}.pdf"

    if email:
        try:
            from app.utils.send_email import send_email_or_write_outbox_copy

            send_email_or_write_outbox_copy(
                email,
                "Your ClearTariff Report",
                "Attached is your duty & landed cost estimate.",
                pdf_bytes,
                fname,
            )
        except Exception as e:
            logging.exception("Email send failed: %s", e)

    headers = {"Content-Disposition": f"attachment; filename={fname}", "X-PDF-Engine": PDF_ENGINE_LAST}
    return Response(pdf_bytes, media_type="application/pdf", headers=headers)


# --- Amazon Sellers form page (override any legacy /form) ---
@app.get("/form", response_class=HTMLResponse)
def amazon_form(request: Request):
    return templates.TemplateResponse("form.html", {"request": request})


#--- Marketing landing page (alias) ---
@app.get("/marketing", response_class=HTMLResponse)
def marketing(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=int(os.environ.get("PORT", 8080)))
