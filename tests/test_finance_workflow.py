import tempfile
import unittest
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))
from finance_workflow import FinanceWorkflowStore


class FinanceWorkflowTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.store = FinanceWorkflowStore(Path(self.tmp.name) / "finance.db")

    def tearDown(self):
        self.tmp.cleanup()

    def test_artifact_lifecycle(self):
        created = self.store.create_artifact("expense", "报销审核", {"summary": {}})
        self.assertEqual(created["status"], "pending_review")
        reviewed = self.store.review_artifact(created["id"], "accept", "赵经理", "核对无误")
        self.assertEqual(reviewed["status"], "accepted")
        self.assertEqual(len(reviewed["reviews"]), 1)

    def test_reviewer_required(self):
        created = self.store.create_artifact("finance", "财务看板", {"periods": []})
        with self.assertRaises(ValueError):
            self.store.review_artifact(created["id"], "accept", "")

    def test_export_only_accepted(self):
        created = self.store.create_artifact("cost", "成本预测", {})
        with self.assertRaises(ValueError):
            self.store.export_artifact(created["id"])
        self.store.review_artifact(created["id"], "accept", "赵经理")
        content, media_type = self.store.export_artifact(created["id"])
        self.assertEqual(media_type, "application/json")
        self.assertIn("cost", content)

    def test_invalid_kind(self):
        with self.assertRaises(ValueError):
            self.store.create_artifact("bogus", "标题", {})


if __name__ == "__main__":
    unittest.main()
