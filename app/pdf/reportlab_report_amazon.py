
from io import BytesIO
from reportlab.lib.pagesizes import letter
from reportlab.lib import colors
from reportlab.lib.units import inch
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle

def _money(v):
    try:
        return f"${float(v):,.2f}"
    except Exception:
        return str(v)

def _pct(v):
    try:
        return f"{float(v):.2f}%"
    except Exception:
        return str(v)

def build_pdf(payload: dict) -> bytes:
    meta = payload.get("meta", {})
    numbers = payload.get("numbers", {})

    units = float(numbers.get("units") or 0)
    unit_value = float(numbers.get("unit_value_usd") or 0.0)
    declared = units * unit_value

    duty_rate = float(numbers.get("duty_rate_pct") or 0.0) / 100.0
    duty_due = declared * duty_rate

    freight = float(numbers.get("freight_usd") or 0.0)
    insurance = float(numbers.get("insurance_usd") or 0.0)
    other = float(numbers.get("other_costs_usd") or 0.0)

    landed_total = declared + duty_due + freight + insurance + other
    per_unit = (landed_total / units) if units > 0 else 0.0

    buff = BytesIO()
    doc = SimpleDocTemplate(buff, pagesize=letter, leftMargin=36, rightMargin=36, topMargin=40, bottomMargin=36)
    styles = getSampleStyleSheet()
    h1 = ParagraphStyle("h1", parent=styles["Heading1"], fontSize=16, spaceAfter=8)
    h2 = ParagraphStyle("h2", parent=styles["Heading2"], fontSize=12, spaceAfter=6)
    body = styles["BodyText"]

    story = []
    story.append(Paragraph("ClearTariff — Amazon Sellers Duty & Landed Cost Report", h1))
    story.append(Paragraph(meta.get("date_str",""), body))
    story.append(Spacer(1, 8))

    # Meta table
    meta_rows = [
        ["ASIN/Link", meta.get("asin") or ""],
        ["SKU", meta.get("sku") or ""],
        ["Product", meta.get("product_name") or ""],
        ["HS Code", meta.get("hs_code") or ""],
        ["Market", meta.get("market","")],
        ["Origin", meta.get("country_of_origin","")],
        ["Email", meta.get("email","")],
    ]
    mt = Table(meta_rows, colWidths=[1.6*inch, 4.8*inch])
    mt.setStyle(TableStyle([("GRID",(0,0),(-1,-1),0.25,colors.lightgrey)]))
    story.append(mt)
    story.append(Spacer(1, 10))

    # Summary
    story.append(Paragraph("Summary", h2))
    sum_rows = [
        ["Units", f"{int(units):,}"],
        ["Unit Value (USD)", _money(unit_value)],
        ["Declared Value", _money(declared)],
        ["Duty Rate", _pct(duty_rate*100)],
        ["Duty Due", _money(duty_due)],
        ["Freight", _money(freight)],
        ["Insurance", _money(insurance)],
        ["Other Costs", _money(other)],
        ["Landed Cost (Total)", _money(landed_total)],
        ["Landed Cost per Unit", _money(per_unit)],
    ]
    st = Table(sum_rows, colWidths=[2.6*inch, 3.8*inch])
    st.setStyle(TableStyle([
        ("GRID",(0,0),(-1,-1),0.25,colors.grey),
        ("BACKGROUND", (0,-1), (-1,-1), colors.HexColor("#f3f8ff")),
    ]))
    story.append(st)
    story.append(Spacer(1, 10))
    # Per-Unit Highlight
    story.append(Paragraph(f"<b>Per-Unit Landed Cost: {_money(per_unit)}</b>", ParagraphStyle("highlight", parent=body, fontSize=14, textColor=colors.HexColor("#0d9488"))))
    story.append(Spacer(1, 14))

    note = meta.get("usd_fx_note")
    if note:
        story.append(Paragraph(f"FX Note: {note}", body))

    story.append(Spacer(1, 16))
    story.append(Paragraph("This report is for estimation only. Verify HS codes and duty rates with your customs broker.", ParagraphStyle("legal", parent=body, fontSize=9, textColor=colors.grey)))
    doc.build(story)
    return buff.getvalue()
