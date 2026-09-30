import importlib.util
from copy import deepcopy
import json
from pathlib import Path
import tempfile
import unittest

spec = importlib.util.spec_from_file_location("burst_renderer", Path(__file__).with_name("render-line-burst-turns.py"))
renderer = importlib.util.module_from_spec(spec)
spec.loader.exec_module(renderer)


def results():
    return {"schema_version": 1, "plan": {"policies": ["baseline"], "revision": "synthetic-test",
        "source_ref": "0" * 40}, "cases": [{"id": "B001", "name": "Test <script>",
        "kind": "singleton", "events": [{"offset_s": 0, "text": "<unsafe>&"}],
        "review_goal": "Inspect all output", "results": [{"policy": "baseline", "status": "ok",
            "metrics": {"model_calls": 1, "text_bubbles": 2, "transport_batches": 1,
                "first_foreground_start_ms": 5, "first_model_start_ms": 10,
                "first_send_ms": 1200, "last_send_ms": 1200, "last_input_to_last_send_ms": 1200},
            "model_calls": [{"started_ms": 5, "finished_ms": 1100, "action": "direct"}],
            "messages": [{"elapsed_ms": 1200, "channel": "reply", "texts": ["主回答", "接話"]}]}]}]}


class BurstReportTests(unittest.TestCase):
    def test_published_page_reproduces_from_retained_results(self):
        public = Path(__file__).resolve().parents[1] / "public/line-v3"
        path = public / "burst-turns-results.public.json"
        if not path.exists():
            self.skipTest("measured artifacts not installed yet")
        data = json.loads(path.read_text())
        self.assertEqual(renderer.render(data), (public / "burst-turns.html").read_text())
        for case in data["cases"]:
            policies = [row["policy"] for row in case["results"]]
            self.assertEqual(policies, data["plan"]["policies"])
            self.assertEqual(len(policies), len(set(policies)))

    def test_complete_output_timing_and_escaped_synthetic_input(self):
        page = renderer.render(results())
        for value in ("主回答", "接話", "0.010 s", "1.200 s", "Runtime ok", "沒有自動品質評審或品質分數"):
            self.assertIn(value, page)
        self.assertIn("&lt;unsafe&gt;&amp;", page)
        self.assertNotIn("Test <script>", page)
        self.assertIn('aria-current="page">Burst turns', page)

    def test_host_failures_and_partial_final_latency_are_explicit(self):
        data = results()
        row = data["cases"][0]["results"][0]
        row.update(status="degraded", observations_complete=False,
                   host_deliveries=[{"failure_code": "conversation_unavailable"}])
        page = renderer.render(data)
        self.assertIn("conversation_unavailable", page)
        self.assertEqual(renderer.stats([row], "last_input_to_last_send_ms"), "— · n=0")
        self.assertIn("n=1", renderer.stats([row], "first_model_start_ms"))

    def test_install_changes_only_navigation_on_existing_active_pages(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            public = root / "public"
            public.mkdir()
            prior = '<html><nav class="tabs"><a href="index.html">Interaction tasks</a></nav><main>frozen report bytes</main></html>'
            for name, _ in renderer.TABS[:-1]:
                (public / name).write_text(prior)
            archive = public / "archived.html"
            archive.write_text(prior)
            source = root / "results.json"
            source.write_text(json.dumps(results(), ensure_ascii=False))
            renderer.install(source, public)
            for name, _ in renderer.TABS[:-1]:
                page = (public / name).read_text()
                self.assertEqual(page.replace('<a href="burst-turns.html">Burst turns</a>', ''), prior)
            self.assertEqual(archive.read_text(), prior)
            before = (public / "index.html").read_bytes()
            renderer.install(source, public)
            self.assertEqual((public / "index.html").read_bytes(), before)
            self.assertEqual((public / "burst-turns-results.public.json").read_bytes(), source.read_bytes())

    def test_missing_latency_is_not_zero_and_failures_keep_denominator(self):
        data = results()
        row = data["cases"][0]["results"][0]
        row.update(status="error", errors=["Timeout"], metrics={}, messages=[], model_calls=[])
        page = renderer.render(data)
        self.assertIn("0/1", page)
        self.assertIn("— · n=0", page)
        self.assertIn("Timeout", page)
        self.assertNotIn("0.000 s", page)
        self.assertIn("<td>未知 · 1 題</td><td>未知 · 1 題</td>", page)
        self.assertIn("未知 次前景 · 未知 批 / 未知 文字泡泡", page)
        self.assertIn("未保留完整的文字傳送紀錄", page)

    def test_missing_counts_preserve_known_subtotals_and_unknown_episode_counts(self):
        data = results()
        missing = deepcopy(data["cases"][0])
        missing["id"] = "B002"
        missing["results"][0].update(status="missing_receipt", metrics={}, messages=[], model_calls=[])
        data["cases"].append(missing)
        page = renderer.render(data)
        self.assertIn("<td>1/2</td>", page)
        self.assertIn("<td>≥ 1 · 未知 1 題</td><td>≥ 2 · 未知 1 題</td>", page)
        self.assertIn("不能當作零次呼叫或零個泡泡", page)

    def test_partial_receipt_counts_are_lower_bounds_in_overview_and_episode(self):
        data = results()
        partial = deepcopy(data["cases"][0])
        partial["id"] = "B002"
        partial["results"][0].update(status="error", observations_complete=False)
        partial["results"][0]["metrics"].update(model_calls=3, text_bubbles=0, transport_batches=0)
        data["cases"].append(partial)
        page = renderer.render(data)
        self.assertIn("<td>≥ 4 · 未知 1 題</td><td>≥ 2 · 未知 1 題</td>", page)
        self.assertIn("≥ 3 次前景 · ≥ 0 批 / ≥ 0 文字泡泡", page)
        self.assertIn("紀錄不完整；次數為已觀測下限，未觀測部分未知", page)

    def test_complete_zero_counts_remain_known(self):
        data = results()
        row = data["cases"][0]["results"][0]
        row.update(status="error", observations_complete=True, messages=[], model_calls=[])
        row["metrics"].update(model_calls=0, text_bubbles=0, transport_batches=0)
        page = renderer.render(data)
        self.assertIn("<td>0</td><td>0</td></tr>", page)
        self.assertIn("0 次前景 · 0 批 / 0 文字泡泡", page)
        self.assertNotIn("<td>≥ 0", page)


if __name__ == "__main__":
    unittest.main()
