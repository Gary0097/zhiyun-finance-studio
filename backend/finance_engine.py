# -*- coding: utf-8 -*-
"""Expense/invoice audit, financial dashboard ratios and cost sensitivity forecasting."""

from __future__ import annotations

from collections import defaultdict
from datetime import date, datetime, timedelta
from typing import Any


def _numeric(value: Any, default: float = 0.0) -> float:
    try:
        if value is None:
            return default
        return float(value)
    except (TypeError, ValueError):
        return default


def _parse_date(value: Any) -> date | None:
    if not value:
        return None
    text = str(value).strip()
    for fmt in ("%Y-%m-%d", "%Y/%m/%d", "%Y-%m-%d %H:%M:%S", "%d/%m/%Y", "%Y%m%d"):
        try:
            return datetime.strptime(text[:19], fmt).date()
        except (ValueError, TypeError):
            continue
    return None


EXPENSE_TYPES: list[tuple[str, list[str]]] = [
    ("差旅", ["差旅", "机票", "高铁", "住宿", "酒店", "打车", "出租车"]),
    ("业务招待", ["招待", "餐饮", "餐费", "礼品", "宴请"]),
    ("办公", ["办公", "文具", "耗材", "打印", "电脑", "软件"]),
    ("采购", ["采购", "原材料", "物料", "设备", "供应商"]),
    ("其他", []),
]


def _classify_expense(text: str) -> str:
    for label, keywords in EXPENSE_TYPES:
        if any(keyword in text for keyword in keywords):
            return label
    return "其他"


def audit_invoice(invoice: dict[str, Any]) -> dict[str, Any]:
    """Run a single invoice through field extraction and compliance checks."""
    invoice_no = str(invoice.get("invoice_no") or invoice.get("invoice_number") or "").strip()
    supplier = str(invoice.get("supplier") or invoice.get("vendor") or "未知供应商")
    amount = _numeric(invoice.get("amount"), -1.0)
    tax_amount = _numeric(invoice.get("tax_amount"), 0.0)
    tax_rate = _numeric(invoice.get("tax_rate"), 0.13)
    invoice_date = _parse_date(invoice.get("invoice_date") or invoice.get("date"))
    desc = str(invoice.get("description") or invoice.get("expense") or "")
    expense_type = str(invoice.get("expense_type") or _classify_expense(desc))
    tax_payer = str(invoice.get("tax_payer_number") or invoice.get("buyer_tax_no") or "")

    checks: list[dict[str, Any]] = []
    if not invoice_no:
        checks.append({"rule": "发票号码", "level": "error", "message": "缺少发票号码，无法校验唯一性。"})
    if invoice_date is None:
        checks.append({"rule": "开票日期", "level": "error", "message": "缺少或无法解析开票日期。"})
    else:
        today = date.today()
        if invoice_date > today + timedelta(days=1):
            checks.append({"rule": "开票日期", "level": "error", "message": "开票日期晚于当前日期。"})
        elif invoice_date < today - timedelta(days=90):
            checks.append({"rule": "开票日期", "level": "warning", "message": "开票日期距今超过90天，请确认是否超期报销。"})
    if amount <= 0:
        checks.append({"rule": "金额", "level": "error", "message": "金额必须大于0。"})
    if amount >= 10000:
        checks.append({"rule": "金额上限", "level": "warning", "message": "金额超过10000元，需更高层级审批。"})
    expected_tax = round(amount * tax_rate, 2)
    if tax_amount > 0 and abs(tax_amount - expected_tax) > 0.05:
        checks.append({"rule": "税额校验", "level": "warning", "message": f"税额与税率不一致：应约{expected_tax}，实际{tax_amount}。"})
    if tax_payer and len(tax_payer) < 8:
        checks.append({"rule": "税号", "level": "error", "message": "购买方税号位数不足，可能为无效发票。"})

    status = "通过"
    if any(check["level"] == "error" for check in checks):
        status = "驳回"
    elif checks:
        status = "退回补正"

    return {
        **invoice,
        "invoice_no": invoice_no,
        "supplier": supplier,
        "amount": round(amount, 2),
        "tax_amount": round(tax_amount, 2),
        "tax_rate": tax_rate,
        "invoice_date": invoice_date.isoformat() if invoice_date else "",
        "expense_type": expense_type,
        "checks": checks,
        "status": status,
        "method": "expense-audit-v1",
    }


def audit_expenses(invoices: list[dict[str, Any]]) -> dict[str, Any]:
    """Audit a batch of invoices and detect duplicates."""
    if len(invoices) > 20000:
        raise ValueError("单次最多审核20000张发票")
    if not invoices:
        return {"items": [], "count": 0, "summary": {}, "method": "expense-audit-v1"}
    audited = [audit_invoice(invoice) for invoice in invoices]
    seen: dict[str, list[int]] = defaultdict(list)
    for index, item in enumerate(audited):
        if item["invoice_no"]:
            seen[item["invoice_no"]].append(index)
    for invoice_no, indices in seen.items():
        if len(indices) > 1:
            for index in indices:
                audited[index]["checks"].append({
                    "rule": "发票重复", "level": "error",
                    "message": f"发票号码 {invoice_no} 出现 {len(indices)} 次，疑似重复报销。",
                })
                audited[index]["status"] = "驳回"
    summary = {
        "total": len(audited),
        "passed": sum(1 for item in audited if item["status"] == "通过"),
        "returned": sum(1 for item in audited if item["status"] == "退回补正"),
        "rejected": sum(1 for item in audited if item["status"] == "驳回"),
        "total_amount": round(sum(item["amount"] for item in audited), 2),
    }
    return {"items": audited, "count": len(audited), "summary": summary, "method": "expense-audit-v1"}


def analyze_financials(records: list[dict[str, Any]]) -> dict[str, Any]:
    """Compute key financial ratios and month-over-month trends."""
    if len(records) > 100000:
        raise ValueError("单次最多分析100000条财务记录")
    if not records:
        return {"periods": [], "summary": {}, "method": "finance-ratio-v1"}

    periods: list[dict[str, Any]] = []
    for record in records:
        revenue = _numeric(record.get("revenue"), 0.0)
        cost = _numeric(record.get("cost"), 0.0)
        operating_expense = _numeric(record.get("operating_expense"), 0.0)
        net_profit = _numeric(record.get("net_profit"), revenue - cost - operating_expense)
        current_assets = _numeric(record.get("current_assets"), 0.0)
        current_liabilities = _numeric(record.get("current_liabilities"), 0.0)
        total_assets = _numeric(record.get("total_assets"), 0.0)
        total_liabilities = _numeric(record.get("total_liabilities"), 0.0)
        gross_margin = (revenue - cost) / revenue * 100.0 if revenue else 0.0
        net_margin = net_profit / revenue * 100.0 if revenue else 0.0
        operating_margin = (revenue - cost - operating_expense) / revenue * 100.0 if revenue else 0.0
        current_ratio = current_assets / current_liabilities if current_liabilities else None
        debt_ratio = total_liabilities / total_assets * 100.0 if total_assets else 0.0
        periods.append({
            **record,
            "month": str(record.get("month") or record.get("period") or ""),
            "revenue": round(revenue, 2), "cost": round(cost, 2),
            "operating_expense": round(operating_expense, 2), "net_profit": round(net_profit, 2),
            "gross_margin": round(gross_margin, 1), "operating_margin": round(operating_margin, 1),
            "net_margin": round(net_margin, 1),
            "current_ratio": round(current_ratio, 2) if current_ratio is not None else None,
            "debt_ratio": round(debt_ratio, 1),
        })
    periods.sort(key=lambda row: row["month"])
    for index in range(1, len(periods)):
        prev_revenue = periods[index - 1]["revenue"]
        if prev_revenue:
            periods[index]["revenue_growth"] = round((periods[index]["revenue"] - prev_revenue) / prev_revenue * 100.0, 1)
    latest = periods[-1]
    summary = {"latest_month": latest["month"], **latest}
    return {"periods": periods, "summary": summary, "method": "finance-ratio-v1"}


def forecast_cost(parameters: dict[str, Any]) -> dict[str, Any]:
    """Forecast unit cost under raw-materials/BOM price changes and volume shifts."""
    current_unit_cost = _numeric(parameters.get("current_unit_cost"), 0.0)
    materials = parameters.get("materials") or []
    volume = max(1.0, _numeric(parameters.get("volume"), 1.0))
    overhead_share = _numeric(parameters.get("overhead_share"), 0.15)
    labor_share = _numeric(parameters.get("labor_share"), 0.15)
    if not materials:
        materials = [{"name": "主料", "share": max(0.0, 1.0 - overhead_share - labor_share), "price_change_pct": 0.0}]

    labor_base = current_unit_cost * labor_share
    overhead_base = current_unit_cost * overhead_share
    material_share_total = sum(_numeric(material.get("share"), 0.0) for material in materials)
    # Any share not captured by materials/labor/overhead is treated as unchanged "other" cost.
    other_base = current_unit_cost * max(0.0, 1.0 - material_share_total - labor_share - overhead_share)
    material_breakdown: list[dict[str, Any]] = []
    new_material_cost = 0.0
    for material in materials:
        name = str(material.get("name") or "物料")
        share = _numeric(material.get("share"), 0.0)
        price_change = _numeric(material.get("price_change_pct"), 0.0)
        base_cost = current_unit_cost * share
        new_cost = base_cost * (1.0 + price_change)
        new_material_cost += new_cost
        material_breakdown.append({
            "name": name, "share": round(share, 3), "price_change_pct": round(price_change * 100.0, 1),
            "base_cost": round(base_cost, 3), "new_cost": round(new_cost, 3),
            "impact_pct": round((new_cost - base_cost) / current_unit_cost * 100.0, 2) if current_unit_cost else 0.0,
        })

    labor_change = _numeric(parameters.get("labor_change_pct"), 0.0)
    labor_new = labor_base * (1.0 + labor_change)
    old_unit = current_unit_cost
    new_unit = new_material_cost + labor_new + overhead_base + other_base
    total_delta = new_unit - old_unit
    return {
        "product": str(parameters.get("product") or "未命名产品"),
        "volume": volume,
        "old_unit_cost": round(old_unit, 3),
        "new_unit_cost": round(new_unit, 3),
        "unit_cost_change": round(total_delta, 3),
        "unit_cost_change_pct": round(total_delta / old_unit * 100.0, 2) if old_unit else 0.0,
        "materials": material_breakdown,
        "annual_saving": round(total_delta * volume, 2),
        "method": "cost-sensitivity-v1",
    }
