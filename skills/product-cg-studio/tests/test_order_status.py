import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"


class OrderHandoff(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.queue = self.root / "orders"
        self.record = self.queue / "camera" / "delivery.json"

    def run_tool(self, script, *args, code=0):
        result = subprocess.run([sys.executable, "-B", "-X", "utf8", SCRIPTS / script, *args],
                                capture_output=True, encoding="utf-8", check=False)
        self.assertEqual(result.returncode, code, result.stdout + result.stderr)
        return result.stdout

    def prepare(self, *extra_products, code=0):
        products = [{"id": "camera", "mode": "concept", "brief": "18 mm 厚外壳，22 mm 固定模组",
                     "planning": {"decision_owner": "设计委托人", "budget": "一轮白模"}}, *extra_products]
        manifest = self.root / "manifest.json"
        manifest.write_text(json.dumps({"version": 1, "products": products}), encoding="utf-8")
        self.run_tool("prepare_queue.py", manifest, "--out", self.queue, code=code)

    def status(self, *args, code=0):
        return json.loads(self.run_tool("order_status.py", self.queue, "--json", *args, code=code))

    def write_record(self, data):
        self.record.write_text(json.dumps(data), encoding="utf-8")

    def test_only_affected_shot_reopens_and_new_version_requires_approval(self):
        self.prepare()
        order = self.record.parent
        brief = (order / "brief.md").read_text(encoding="utf-8")
        self.assertIn("设计委托人", brief)
        self.assertIn("一轮白模", brief)
        (order / "review.txt").write_text("fixture evidence", encoding="utf-8")
        data = json.loads(self.record.read_text(encoding="utf-8"))
        shots = ["hero", "fold"]
        data.update(stage="review", revisions=[{"version": "v1", "affected_shots": shots}],
                    shot_reviews={shot: {"version": "v1", "evidence": "review.txt"} for shot in shots},
                    approval={"version": "v1", "by": "test client", "evidence": "review.txt"})
        self.write_record(data)
        self.assertEqual(self.status()[0]["decision"], "已签收")
        data["revisions"].append({"version": "v2", "affected_shots": ["fold"]})
        self.write_record(data)
        row = self.status()[0]
        self.assertEqual(row["open_shots"], {"fold": "v2"})
        self.assertEqual(row["decision"], "新版待签")
        data["approval"]["version"] = "v2"
        self.write_record(data)
        self.assertEqual(self.status()[0]["decision"], "签收待复核")
        data["shot_reviews"]["fold"]["version"] = "v2"
        self.write_record(data)
        self.assertEqual(self.status()[0]["decision"], "已签收")
        data["blocker"] = "确认尺寸"
        self.write_record(data)
        self.assertEqual(self.status()[0]["decision"], "签收待复核")
        (order / "review.txt").unlink()
        self.assertEqual(self.status(code=1)[0]["stage"], "记录有误")

    def test_older_and_failed_products_remain_visible(self):
        self.prepare({"id": "cam", "mode": "concept", "brief": "sketch"},
                     {"id": "bad", "mode": "concept", "brief": "bad", "planning": {"budegt": 2}}, code=1)
        self.record.unlink()
        self.assertEqual([r["stage"] for r in self.status(code=1)], ["未登记", "intake", "工单失败"])
        before = (self.record.parent / "brief.md").read_bytes()
        self.assertEqual(len(self.status("--only", "camera", "--init-missing")), 1)
        self.assertEqual(self.status("--only", "camera")[0]["decision"], "待签收")
        self.assertEqual(before, (self.record.parent / "brief.md").read_bytes())
        self.run_tool("order_status.py", self.queue, "--only", "missing", code=2)


if __name__ == "__main__":
    unittest.main()
