import hashlib
import importlib.util
import json
from pathlib import Path
import re
import tempfile
import unittest

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location("mixed_renderer", HERE / "render-line-mixed-media-bursts.py")
renderer = importlib.util.module_from_spec(spec)
spec.loader.exec_module(renderer)
PUBLIC = HERE.parent / "public/line-v3"


def measured():
    """Synthetic measured shape, as the benchmark's summary command writes it."""
    case = {"id": "M1", "name": "Screenshot <then> text", "kind": "direct_image_then_text",
            "conversation_scope": "direct", "review_goal": "One answer about 這家",
            "events": [{"offset_s": 0, "kind": "image", "fixture": "hotpot_a"},
                       {"offset_s": 2, "kind": "text", "text": "晚上吃這家 6:15pm"}],
            "expect": {"fixtures_named": ["hotpot_a"], "time": True, "single_answer": True}}
    row = lambda arm, answers, passed: {"arm": arm, "status": "ok", "errors": [],
        "metrics": {"answer_batches": len(answers), "model_calls": len(answers), "first_answer_ms": 7000,
                    "last_answer_ms": 7000 + 4000 * (len(answers) - 1), "last_input_to_last_answer_ms": 9000},
        "model_calls": [{"message_type": "text", "current_text": "晚上吃這家 6:15pm", "image_attached": arm == "mixed",
                         "recent_image_observations": 0, "recent_group_image_observations": 0,
                         "fixture_tokens_in_context": ["湯老大"] if arm == "mixed" else [],
                         "started_ms": 2500, "finished_ms": 6500}],
        "reader_calls": [], "messages": [{"channel": "reply", "elapsed_ms": 7000 + 4000 * index, "texts": [text]}
                                         for index, text in enumerate(answers)],
        "score": {"checks": {"fixtures_named": passed, "time_kept": passed, "single_answer": len(answers) == 1},
                  "passed": passed and len(answers) == 1}}
    case["results"] = [row("baseline", ["這是火鍋店截圖！", "這家是哪一家？<b>"], False),
                       row("mixed", ["好！6:15 湯老大見～"], True)]
    return {"schema_version": 1, "placeholder": False,
            "plan": {"revision": "synthetic-test", "arms": ["baseline", "mixed"], "source_ref": "a" * 40,
                     "baseline_mode": "separate_ref_with_identical_harness"},
            "fixtures": {"hotpot_a": {"token": "湯老大", "name": "湯老大麻辣鴛鴦鍋", "branch": "信義店",
                                      "distance": "距離你 1.2 公里", "sha256": "0" * 64,
                                      "file": "fixtures/mixed_burst_hotpot_a.jpg"}},
            "group_members": [],
            "aggregate": {"baseline": {"episodes": 1, "errors": 0, "cases_passed": 0, "cases_scored": 1,
                                       "checks": {"fixtures_named": {"passed": 0, "evaluated": 1}},
                                       "answer_batches": 2, "median_last_input_to_last_answer_ms": 9000},
                          "mixed": {"episodes": 1, "errors": 0, "cases_passed": 1, "cases_scored": 1,
                                    "checks": {"fixtures_named": {"passed": 1, "evaluated": 1}},
                                    "answer_batches": 1, "median_last_input_to_last_answer_ms": 9000}},
            "cases": [case]}


class MixedMediaReportTests(unittest.TestCase):
    def test_published_page_reproduces_from_retained_results(self):
        path = PUBLIC / renderer.RESULTS
        if not path.exists():
            self.skipTest("results not installed yet")
        data = json.loads(path.read_text())
        self.assertEqual(renderer.render(data), (PUBLIC / renderer.PAGE).read_text())
        for key, fixture in data["fixtures"].items():
            image = PUBLIC / "fixtures" / Path(fixture["file"]).name
            self.assertEqual(hashlib.sha256(image.read_bytes()).hexdigest(), fixture["sha256"], key)

    def test_measured_results_show_answers_probes_evidence_and_escape_input(self):
        page = renderer.render(measured())
        for value in ("好！6:15 湯老大見～", "這是火鍋店截圖！", "✓ 回答指出截圖中的店", "✗ 只回答一次",
                      "模型實際看得到什麼", "0/1", "1/1", 'class="timeline"', "9.00 s"):
            self.assertIn(value, page)
        self.assertIn("這家是哪一家？&lt;b&gt;", page)
        self.assertIn("Screenshot &lt;then&gt; text", page)
        self.assertNotIn("預留資料", page)
        self.assertIn('href="mixed-media-bursts.html" aria-current="page">Mixed-media bursts', page)

    def test_placeholder_is_marked_and_holds_no_measurement(self):
        data = measured()
        data.update(placeholder=True, aggregate={})
        for case in data["cases"]:
            case["results"] = [{"arm": "baseline", "status": "pending"}, {"arm": "mixed", "status": "pending"}]
        page = renderer.render(data)
        self.assertIn("預留資料", page)
        self.assertNotIn('class="timeline"', page)
        self.assertEqual(page.count("尚未量測"), 4)

    def test_unknown_schema_or_arm_fails(self):
        data = measured()
        data["plan"]["arms"] = ["baseline", "composite"]
        with self.assertRaises(ValueError):
            renderer.render(data)
        data = measured()
        data["schema_version"] = 2
        with self.assertRaises(ValueError):
            renderer.render(data)

    def test_tab_order_matches_the_build_navigation(self):
        script = (HERE / "normalize-line-navigation.mjs").read_text()
        built = re.findall(r"\['([a-z0-9-]+\.html)', '([^']+)'\]", script)
        self.assertEqual(built, [(name, title) for name, title in renderer.TABS])

    def test_install_refuses_a_fixture_that_does_not_match_its_digest(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "fixtures").mkdir()
            (root / "fixtures/mixed_burst_hotpot_a.jpg").write_bytes(b"not the frozen fixture")
            results = root / "results.json"
            results.write_text(json.dumps(measured(), ensure_ascii=False))
            with self.assertRaises(ValueError):
                renderer.install(results, root / "public", root / "fixtures")


if __name__ == "__main__":
    unittest.main()
