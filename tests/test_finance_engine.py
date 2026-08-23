import unittest
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))
from finance_engine import analyze_financials, audit_expenses, forecast_cost


class FinanceEngineTests(unittest.TestCase):
    def test_audit_detects_duplicate(self):
        invoices = [
            {"invoice_no": "INV-001", "invoice_date": "2026-08-10", "amount": 1200, "tax_amount": 156, "tax_rate": 0.13, "supplier": "A", "description": "差旅"},
            {"invoice_no": "INV-001", "invoice_date": "2026-08-10", "amount": 1200, "tax_amount": 156, "tax_rate": 0.13, "supplier": "A", "description": "差旅"},
        ]
        result = audit_expenses(invoices)
        self.assertEqual(result["summary"]["total"], 2)
        self.assertEqual(result["summary"]["rejected"], 2)
        self.assertIn("重复", result["items"][0]["checks"][-1]["message"])

    def test_audit_flags_cost_and_amount_rules(self):
        invoices = [
            {"invoice_no": "", "invoice_date": "2026-08-10", "amount": 20000, "tax_amount": 0, "tax_rate": 0.13, "supplier": "B", "description": "办公电脑", "tax_payer_number": "123"},
        ]
        result = audit_expenses(invoices)
        item = result["items"][0]
        self.assertEqual(item["status"], "驳回")
        self.assertTrue(item["checks"])

    def test_analyze_financials_computes_ratios(self):
        records = [
            {"month": "2026-06", "revenue": 1200, "cost": 720, "operating_expense": 180, "current_assets": 600, "current_liabilities": 300, "total_assets": 1000, "total_liabilities": 400},
            {"month": "2026-07", "revenue": 1320, "cost": 770, "operating_expense": 190, "current_assets": 660, "current_liabilities": 310, "total_assets": 1050, "total_liabilities": 410},
        ]
        result = analyze_financials(records)
        self.assertEqual(result["summary"]["latest_month"], "2026-07")
        self.assertAlmostEqual(result["summary"]["gross_margin"], 41.7, places=1)
        self.assertEqual(result["summary"]["current_ratio"], 2.13)
        self.assertEqual(result["periods"][1]["revenue_growth"], 10.0)

    def test_forecast_cost_reflects_price_change(self):
        parameters = {
            "product": "压铸件", "current_unit_cost": 12.5, "volume": 12000,
            "labor_share": 0.15, "overhead_share": 0.15,
            "materials": [{"name": "铝合金", "share": 0.6, "price_change_pct": 0.1}],
        }
        result = forecast_cost(parameters)
        self.assertIn("new_unit_cost", result)
        self.assertGreater(result["new_unit_cost"], result["old_unit_cost"])
        self.assertEqual(len(result["materials"]), 1)


if __name__ == "__main__":
    unittest.main()
