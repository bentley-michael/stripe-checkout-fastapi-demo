
from weasyprint import HTML
from markupsafe import escape

def fmt_money(v):
    try:
        return f"${float(v):,.2f}"
    except Exception:
        return str(v)

def fmt_pct(v):
    try:
        return f"{float(v)*100:.2f}%"
    except Exception:
        return str(v)

def generate_tariff_pdf_weasy(payload: dict) -> bytes:
    p = payload or {}
    totals = p.get("totals") or {}
    per_cup = p.get("per_cup") or {}
    scenarios = p.get("scenarios") or []

    # Single source of truth: use API-calculated totals
    merch_value = float(totals.get("merch_value", 0))
    freight = float(totals.get("freight", 0))
    insurance = float(totals.get("insurance", 0))
    brokerage = float(totals.get("brokerage", 0))
    other_fees = float(totals.get("other_fees", 0))
    duty = float(totals.get("duty", 0))
    total_landed = float(totals.get("total_landed", merch_value + freight + insurance + brokerage + other_fees + duty))

    # Build very simple HTML (no external assets) so it works everywhere
    html = f"""
    <html>
    <head>
      <meta charset="utf-8">
      <style>
        body {{ font-family: Arial, sans-serif; font-size: 12px; }}
        h1 {{ font-size: 18px; margin-bottom: 6px; }}
        h2 {{ font-size: 14px; margin-top: 14px; margin-bottom: 6px; }}
        table {{ width: 100%; border-collapse: collapse; }}
        th, td {{ border: 1px solid #ddd; padding: 6px; text-align: left; }}
        th {{ background: #f7f7f7; }}
        .grid2 {{ display: grid; grid-template-columns: 200px 1fr; gap: 6px; }}
        .muted {{ color: #555; }}
      </style>
    </head>
    <body>
      <h1>Tariff & Landed Cost Report</h1>
      <div class="muted">Generated: {escape(p.get('generated_at', ''))}</div>

      <h2>Assumptions & Rates</h2>
      <div class="grid2">
        <div>Country of Origin</div><div>{escape(p.get('country_of_origin',''))}</div>
        <div>Destination</div><div>{escape(p.get('destination',''))}</div>
        <div>HS Code</div><div>{escape(p.get('hs_code',''))}</div>
        <div>Declared Incoterm</div><div>{escape(p.get('incoterm',''))}</div>
        <div>Base Rate</div><div>{fmt_pct(p.get('base_rate',0))}</div>
        <div>Tariff Rate</div><div>{fmt_pct(p.get('tariff_rate',0))}</div>
      </div>

      <h2>Line Items</h2>
      <table>
        <thead><tr><th>SKU</th><th>Description</th><th>Qty</th><th>Unit Value</th><th>Unit Wt (kg)</th></tr></thead>
        <tbody>
          {''.join(f"<tr><td>{escape(str(li.get('sku','')))}</td><td>{escape(str(li.get('description','')))}</td><td>{li.get('qty',0)}</td><td>{fmt_money(li.get('unit_value',0))}</td><td>{li.get('unit_wt',0)}</td></tr>" for li in (p.get('line_items') or []))}
        </tbody>
      </table>

      <h2>Cost Summary</h2>
      <table>
        <tbody>
          <tr><td>Merchandise Value</td><td>{fmt_money(merch_value)}</td></tr>
          <tr><td>Freight</td><td>{fmt_money(freight)}</td></tr>
          <tr><td>Insurance</td><td>{fmt_money(insurance)}</td></tr>
          <tr><td>Duty</td><td>{fmt_money(duty)}</td></tr>
          <tr><td>Brokerage</td><td>{fmt_money(brokerage)}</td></tr>
          <tr><td>Other Fees</td><td>{fmt_money(other_fees)}</td></tr>
          <tr><th>Total Landed Cost</th><th>{fmt_money(total_landed)}</th></tr>
        </tbody>
      </table>

      {f"""
      <h2>Price per Cup Helper</h2>
      <div class="grid2">
        <div>Brew grams/cup</div><div>{per_cup.get('brew_grams_per_cup',0)}</div>
        <div>Waste %</div><div>{per_cup.get('waste_percent',0):.2f}%</div>
        <div>Target Margin %</div><div>{per_cup.get('target_margin_percent',0):.2f}%</div>
        <div>Total Weight (kg)</div><div>{per_cup.get('total_weight_kg',0):.3f}</div>
        <div>Estimated Cost per Cup</div><div>{fmt_money(per_cup.get('per_cup_cost',0))}</div>
        <div>Suggested Price</div><div>{fmt_money(per_cup.get('suggested_price',0))}</div>
      </div>
      """ if per_cup else ""}

      {f"""
      <h2>Scenarios</h2>
      <table>
        <thead><tr><th>Scenario</th><th>Origin</th><th>Tariff</th><th>Duty</th><th>Total Landed</th></tr></thead>
        <tbody>
          {''.join(f"<tr><td>{escape(s.get('name',''))}</td><td>{escape(s.get('country_of_origin',''))}</td><td>{fmt_pct(s.get('tariff_rate',0))}</td><td>{fmt_money((s.get('totals') or {}).get('duty',0))}</td><td>{fmt_money((s.get('totals') or {}).get('total_landed',0))}</td></tr>" for s in scenarios)}
        </tbody>
      </table>
      """ if scenarios else ""}

      <div class="muted" style="margin-top:12px;">© 2025 ClearTariff — auto-generated report</div>
    <p style="font-size:10px;color:#666;margin-top:12px;">Disclaimer: Rates are estimates and subject to official customs confirmation.</p></body>
    </html>
    """
    return HTML(string=html).write_pdf()
