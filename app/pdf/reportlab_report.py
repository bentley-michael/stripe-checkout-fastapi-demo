
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
        return f"{float(v)*100:.2f}%"
    except Exception:
        return str(v)

def generate_tariff_pdf_reportlab(payload: dict) -> bytes:
    buf = BytesIO()
    doc = SimpleDocTemplate(
        buf, pagesize=letter, rightMargin=36, leftMargin=36, topMargin=40, bottomMargin=36
    )
    styles = getSampleStyleSheet()
    h1 = ParagraphStyle("h1", parent=styles["Heading1"], spaceAfter=6)
    h2 = ParagraphStyle("h2", parent=styles["Heading2"], spaceBefore=6, spaceAfter=4)
    body = ParagraphStyle("body", parent=styles["BodyText"], leading=14)

    story = []

    story.append(Paragraph("Tariff & Landed Cost Report", h1))
    meta = payload or {}
    story.append(Paragraph(f"Generated: {meta.get('generated_at','')}", body))
    story.append(Spacer(1, 10))

    # Shipment summary
    story.append(Paragraph("Shipment Summary", h2))
    summary_rows = [
        ["HS Code", meta.get("hs_code","")],
        ["Country of Origin", meta.get("country_of_origin","")],
        ["Destination", meta.get("destination","")],
        ["Incoterm", meta.get("incoterm","")],
        ["Base HTS Rate", _pct(meta.get("base_rate",0))],
        ["Additional Tariff", _pct(meta.get("tariff_rate",0))],
    ]
    t = Table(summary_rows, colWidths=[2.2*inch, 4.8*inch])
    t.setStyle(TableStyle([
        ("BOX",(0,0),(-1,-1),0.5,colors.grey),
        ("INNERGRID",(0,0),(-1,-1),0.25,colors.lightgrey),
        ("BACKGROUND",(0,0),(0,-1),colors.whitesmoke),
        ("VALIGN",(0,0),(-1,-1),"MIDDLE"),
        ("LEFTPADDING",(0,0),(-1,-1),6),
        ("RIGHTPADDING",(0,0),(-1,-1),6),
    ]))
    story.append(t)
    story.append(Spacer(1, 10))

    # Line items
    items = meta.get("line_items", []) or []
    if items:
        story.append(Paragraph("Line Items", h2))
        rows = [["SKU", "Description", "Qty", "Unit Value", "Unit Wt (kg)"]]
        for li in items:
            rows.append([
                str(li.get("sku","")),
                str(li.get("description","")),
                f"{li.get('qty',0):,.2f}",
                _money(li.get("unit_value",0)),
                f"{li.get('unit_wt',0):,.3f}",
            ])
        it = Table(rows, colWidths=[1.0*inch, 2.8*inch, 0.9*inch, 1.2*inch, 1.1*inch])
        it.setStyle(TableStyle([
            ("BACKGROUND",(0,0),(-1,0),colors.lightgrey),
            ("TEXTCOLOR",(0,0),(-1,0),colors.black),
            ("GRID",(0,0),(-1,-1),0.25,colors.grey),
            ("VALIGN",(0,0),(-1,-1),"TOP"),
        ]))
        story.append(it)
        story.append(Spacer(1, 10))

    # Totals
    totals = (meta.get("totals") or {})
    story.append(Paragraph("Totals", h2))
    total_rows = [
        ["Merchandise Value", _money(totals.get("merch_value",0))],
        ["Freight", _money(totals.get("freight",0))],
        ["Insurance", _money(totals.get("insurance",0))],
        ["Duty (HTS + Tariff)", _money(totals.get("duty",0))],
        ["Brokerage", _money(totals.get("brokerage",0))],
        ["Other Fees", _money(totals.get("other_fees",0))],
        ["Total Landed Cost", _money(totals.get("total_landed",0))],
    ]
    tt = Table(total_rows, colWidths=[2.6*inch, 4.4*inch])
    tt.setStyle(TableStyle([
        ("GRID",(0,0),(-1,-1),0.25,colors.grey),
        ("BACKGROUND",(0,-1),(-1,-1),colors.HexColor("#f3f8ff")),
        ("TEXTCOLOR",(0,-1),(-1,-1),colors.black),
    ]))
    story.append(tt)
    story.append(Spacer(1, 10))

    # Per-cup helper
    pc = meta.get("per_cup") or {}
    if pc:
        story.append(Paragraph("Price per Cup Helper", h2))
        pc_rows = [
            ["Brew grams/cup", f"{pc.get('brew_grams_per_cup',0):.2f} g"],
            ["Waste %", f"{pc.get('waste_percent',0):.2f}%"],
            ["Target Margin %", f"{pc.get('target_margin_percent',0):.2f}%"],
            ["Total Weight (kg)", f"{pc.get('total_weight_kg',0):.3f} kg"],
            ["Estimated Cost per Cup", _money(pc.get("per_cup_cost",0))],
            ["Suggested Price", _money(pc.get("suggested_price",0))],
        ]
        pct = Table(pc_rows, colWidths=[2.6*inch, 4.4*inch])
        pct.setStyle(TableStyle([
            ("GRID",(0,0),(-1,-1),0.25,colors.grey),
            ("BACKGROUND",(0,0),(-1,0),colors.whitesmoke),
        ]))
        story.append(pct)
        story.append(Spacer(1, 10))

    # Scenarios
    scenarios = meta.get("scenarios") or []
    if scenarios:
        story.append(Paragraph("Scenarios", h2))
        s_rows = [["Scenario", "Origin", "Tariff", "Duty", "Total Landed"]]
        for s in scenarios:
            name = s.get("name","")
            coo = s.get("country_of_origin","")
            tr = s.get("tariff_rate",0)
            subt = s.get("totals") or {}
            s_rows.append([name, coo, _pct(tr), _money(subt.get("duty",0)), _money(subt.get("total_landed",0))])
        st = Table(s_rows, colWidths=[2.4*inch, 1.2*inch, 1.0*inch, 1.4*inch, 1.6*inch])
        st.setStyle(TableStyle([
            ("BACKGROUND",(0,0),(-1,0),colors.lightgrey),
            ("GRID",(0,0),(-1,-1),0.25,colors.grey),
        ]))
        story.append(st)

    doc.build(story)
    return buf.getvalue()
