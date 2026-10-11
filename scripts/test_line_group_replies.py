import importlib.util
from copy import deepcopy
import json
from pathlib import Path
import tempfile
import unittest

spec = importlib.util.spec_from_file_location("group_reply_renderer",
                                              Path(__file__).with_name("render-line-group-replies.py"))
renderer = importlib.util.module_from_spec(spec)
spec.loader.exec_module(renderer)


def row(answered, correct, runs=3, **extra):
    return {"runs": runs, "answered": answered, "correct": correct, "consistent": True,
            "sealed_policy": [2 if not answered else 4], "quoted_context": extra.pop("quoted", []),
            "extras": extra, "ingest_ms": [10.0] * runs}


def arm(per_case, *, returncodes=(0, 0, 0)):
    def rate(category, field, cases):
        rows = [per_case[case["id"]] for case in cases if case["category"] == category]
        return {"cases": len(rows), "runs": sum(r["runs"] for r in rows), "hits": sum(r[field] for r in rows)}
    return lambda cases: {
        "per_case": per_case,
        "answered": {c: rate(c, "answered", cases) for c in ("addressed", "reply", "quiet")},
        "correct": {c: rate(c, "correct", cases) for c in ("addressed", "reply", "quiet")},
        "correct_total": {"runs": sum(r["runs"] for r in per_case.values()),
                          "hits": sum(r["correct"] for r in per_case.values())},
        "ingest_ms": {"n": 9, "median": 10.1, "p90": 30.2, "max": 58.0},
        "pytest_returncodes": list(returncodes)}


def results():
    cases = [
        {"id": "A1", "category": "addressed", "expected": "answer", "title": "@麻吉 tag", "note": ""},
        {"id": "R1", "category": "reply", "expected": "answer", "title": "Reply <script>", "note": "x & y"},
        {"id": "Q1", "category": "quiet", "expected": "quiet", "title": "Untagged chatter", "note": ""},
    ]
    baseline = arm({"A1": row(3, 3), "R1": row(0, 0), "Q1": row(0, 3)})(cases)
    candidate = arm({"A1": row(3, 3), "R1": row(3, 3, quoted=[True, True, True], timezone_recorded=[True] * 3),
                     "Q1": row(0, 3)})(cases)
    return {"schema": "line-v3.group-replies.v1", "generated_at": "2026-10-11T00:00:00+00:00", "samples": 3,
            "arms_refs": {"baseline": {"ref": "main", "commit": "a" * 40, "subject": "base"},
                          "candidate": {"ref": "pr", "commit": "b" * 40, "subject": "fix"}},
            "harness_sha256": "c" * 64, "environment": {"python": "3.11.15", "load_average_at_end": [1.5]},
            "method": "Hermetic.", "cases": cases, "arms": {"baseline": baseline, "candidate": candidate}}


class GroupReplyReportTests(unittest.TestCase):
    def test_published_page_reproduces_from_retained_results(self):
        public = Path(__file__).resolve().parents[1] / "public/line-v3"
        path = public / renderer.RESULTS
        if not path.exists():
            self.skipTest("measured artifacts not installed yet")
        self.assertEqual(renderer.render(json.loads(path.read_text())), (public / renderer.PAGE).read_text())

    def test_headline_rates_and_escaped_synthetic_text(self):
        page = renderer.render(results())
        for value in ("100.0%", "0.0%", "+100.0 個百分點", "3/3 次回應", "0/3 次回應", "3/3 次安靜",
                      "模型收到被回覆的麻吉原句", "已記下時區", "PR #571", "aaaaaaaa", "bbbbbbbb",
                      "回覆麻吉的回答", "入站分類：回覆麻吉", "入站分類：背景"):
            self.assertIn(value, page)
        # Unknown cases keep their recorded (escaped) harness wording.
        data = results()
        data["cases"][1]["id"] = "R99"
        for name in ("baseline", "candidate"):
            data["arms"][name]["per_case"]["R99"] = data["arms"][name]["per_case"].pop("R1")
        page = renderer.render(data)
        self.assertIn("Reply &lt;script&gt;", page)
        self.assertNotIn("Reply <script>", page)
        self.assertIn("x &amp; y", page)

    def test_page_uses_the_shared_layout_contract(self):
        page = renderer.render(results())
        # One top-level tab bar for normalize-line-navigation.mjs to replace,
        # header and main as direct body children, and the shared 1500px width.
        self.assertEqual(page.count('<nav class="tabs"'), 1)
        self.assertIn("</div>\n<header>", page)
        self.assertIn('<main id="main">', page)
        self.assertIn("max-width:1500px", page)
        self.assertNotIn("max-width:1450px", page)

    def test_refuses_incomplete_or_errored_results(self):
        data = results()
        del data["arms"]["candidate"]["per_case"]["R1"]
        with self.assertRaisesRegex(ValueError, "missing_group_reply_case:R1"):
            renderer.render(data)
        data = results()
        data["arms"]["baseline"]["pytest_returncodes"] = [0, 1, 0]
        with self.assertRaisesRegex(ValueError, "harness_errors_in_results"):
            renderer.render(data)
        data = results()
        data["schema"] = "other"
        with self.assertRaisesRegex(ValueError, "unsupported_group_reply_results"):
            renderer.render(data)

    def test_install_writes_page_and_unchanged_results(self):
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / "results.json"
            raw = json.dumps(results(), ensure_ascii=False).encode()
            source.write_bytes(raw)
            public = Path(tmp) / "public"
            renderer.install(source, public)
            self.assertEqual((public / renderer.RESULTS).read_bytes(), raw)
            self.assertIn("<h1>Group replies</h1>", (public / renderer.PAGE).read_text())

    def test_misses_are_marked_and_false_replies_are_counted(self):
        data = deepcopy(results())
        data["arms"]["candidate"]["per_case"]["Q1"] = row(1, 2)
        page = renderer.render(data)
        self.assertIn("1/3 次誤回", page)
        self.assertIn('class="verdict bad"', page)


if __name__ == "__main__":
    unittest.main()
