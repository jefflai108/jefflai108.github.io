import importlib.util
from copy import deepcopy
import json
from pathlib import Path
import unittest

spec = importlib.util.spec_from_file_location("sticker_renderer", Path(__file__).with_name("render-line-stickers.py"))
renderer = importlib.util.module_from_spec(spec)
spec.loader.exec_module(renderer)


def verdict(sent, fit, score=None, reason="理由 <b>"):
    return {"sticker_sent": sent, "sticker_fit": fit, "fit_reason": reason, "appropriateness": score,
            "issues": ["none"] if sent else [], "appropriateness_reason": reason if sent else ""}


def rate(stickers, turns):
    return {"turns": turns, "sticker_turns": stickers, "rate": stickers / turns if turns else None}


def arm_summary(stickers):
    by = {label: rate(stickers if label == "welcome" else 0, 1) for label in ("welcome", "neutral", "avoid")}
    appropriateness = {"judged_stickers": stickers, "mean": 5.0 if stickers else None,
                       "distribution": {"1": 0, "2": 0, "3": 0, "4": 0, "5": stickers},
                       "appropriate": stickers, "appropriate_rate": 1.0 if stickers else None,
                       "inappropriate": 0, "issues": {}}
    consistency = {"turns_judged_twice": 1, "sticker_sent": 1.0, "fit": 1.0, "scored_twice": stickers,
                   "score_exact": 1.0, "score_within_one": 1.0}
    return {"response": {**rate(stickers, 1), "direct": rate(stickers, 1), "by_expectation": by,
                         "by_category": {"social": rate(stickers, 1)}},
            "funnel": {"turns": 1, "eligible": 1, "model_selected": 1, "model_selected_on_rest": 1,
                       "parsed_kept": stickers, "host_reserved": stickers, "delivered": stickers,
                       "dropped_at_parse": 1 - stickers, "dropped_at_host": 0, "trailing_delivered": stickers},
            "appropriateness": appropriateness, "appropriateness_pass2": appropriateness,
            "judge": {"judged_turns": 1, "judge_sticker_rate": stickers, "wire_agreement": 1.0,
                      "fit_labels": {"welcome": 1, "neutral": 0, "avoid": 0},
                      "rate_by_judge_fit": by, "consistency": consistency},
            "distinct_stickers": stickers, "top_stickers": [["s337", 1]] if stickers else [],
            "actions": {"direct": 1}, "interaction_errors": 0,
            "foreground_elapsed_ms": {"n": 1, "p50": 3000.0, "p90": 3000.0}}


def results():
    turn_input = {"type": "text", "text": "考過了 <script>alert(1)</script>"}
    sticker = {"type": "sticker", "package_id": "11537", "sticker_id": "52002734", "catalog_key": "s337",
               "catalog_valid": True, "description": "Brown firing party popper; celebration", "channel": "reply"}

    def turn(arm, sent):
        return {"slot": f"ST01.{arm}.r1", "arm": arm, "episode_id": "ST01", "repeat": 1, "account": "primary",
                "category": "social", "title": "錄取 & 慶祝", "turn_index": 0, "expectation": "welcome",
                "input": turn_input, "action": "direct", "interaction_status": "ok", "error_code": None,
                "delivered": [{"type": "text", "text": "恭喜！<b>", "channel": "reply"}] + ([sticker] if sent else []),
                "sticker_delivered": sent,
                "funnel": {"eligible": True, "model_selected": "s337", "model_follow_up_kind": "rest",
                           "parsed_selected": "s337" if sent else None, "host_reserved": "s337" if sent else None,
                           "host_trailing": sent, "delivered": ["s337"] if sent else []},
                "reply": "恭喜！", "follow_up": "", "initiative_kind": "rest", "foreground_elapsed_ms": 3000.0,
                "turn_elapsed_ms": 3200.0,
                "judge": {"1": verdict(sent, "welcome", 5 if sent else None),
                          "2": verdict(sent, "welcome", 4 if sent else None)}}
    judge = {"model": "gpt-6-sol", "reasoning": "medium", "passes": 2, "rubric_sha256": "a" * 64,
             "judge_sha256": "b" * 64, "packets_sha256": "c" * 64, "attempts": {"total": 4, "ok": 4, "errors": 0},
             "usage": {}}
    return {"metadata": {"cohort": "test", "refs": {"existing": "1" * 40, "proactive": "2" * 40},
                         "repeats": 1, "episode_count": 1, "turn_count": 1, "slot_count": 2,
                         "models": {"foreground": "gemini-3.8-flash", "foreground_thinking": "native low",
                                    "foreground_timeout_s": 80}, "judge": judge},
            "slot_status": {"existing:measured": 1, "proactive:measured": 1},
            "summary": {"existing": arm_summary(0), "proactive": arm_summary(1)},
            "comparison": {"paired_clusters": 1, "rate_difference": 1.0, "rate_ratio": None, "relative_change": None,
                           "appropriateness_difference": None, "draws": 10000, "seed": 1,
                           "rate_difference_ci95": [1.0, 1.0], "rate_ratio_ci95": None,
                           "appropriateness_difference_ci95": None},
            "judge_controls": {"judgments": 1, "as_expected": 1, "items": [{"packet_id": "C01",
                "expect": {"fit": "welcome", "min": 4},
                "judged": [{"pass": 1, "as_expected": True, "verdict": verdict(True, "welcome", 5)}]}]},
            "turns": [turn("existing", False), turn("proactive", True)]}


class StickerReportTests(unittest.TestCase):
    def test_published_page_reproduces_from_public_json(self):
        public = Path(__file__).resolve().parents[1] / "public/line-v3"
        path = public / renderer.JSON_NAME
        if not path.exists():
            self.skipTest("measured artifacts not installed yet")
        data = json.loads(path.read_text(encoding="utf-8"))
        renderer.check_public(data)
        self.assertEqual(renderer.render(data), (public / renderer.PAGE_NAME).read_text(encoding="utf-8"))
        arms = {(turn["episode_id"], turn["repeat"], turn["turn_index"], turn["arm"]) for turn in data["turns"]}
        self.assertEqual(len(arms), len(data["turns"]))
        for turn in data["turns"]:
            sent = any(item["type"] == "sticker" for item in turn["delivered"])
            self.assertEqual(sent, turn["sticker_delivered"])

    def test_page_escapes_untrusted_text_and_marks_its_tab(self):
        data = renderer.project(results(), generated_at="2026-10-06")
        page = renderer.render(data)
        self.assertIn("&lt;script&gt;alert(1)&lt;/script&gt;", page)
        self.assertNotIn("<script>alert(1)", page)
        self.assertIn("恭喜！&lt;b&gt;", page)
        self.assertEqual(page.count('<nav class="tabs"'), 1)
        self.assertIn('<a href="line-stickers.html" aria-current="page">LINE Stickers</a>', page)
        self.assertIn("stickershop.line-scdn.net/stickershop/v1/sticker/52002734/android/sticker.png", page)
        for value in ("① 貼圖回應率", "② 貼圖適切度", "表格檢視", "1/1 符合預期"):
            self.assertIn(value, page)

    def test_projection_refuses_private_strings_and_partial_judging(self):
        data = results()
        data["turns"][0]["delivered"][0]["text"] = "see /Users/someone/secret"
        with self.assertRaises(ValueError):
            renderer.project(data, generated_at="2026-10-06")
        data = results()
        del data["turns"][1]["judge"]["2"]
        with self.assertRaises(ValueError):
            renderer.project(data, generated_at="2026-10-06")
        data = results()
        del data["metadata"]["judge"]
        with self.assertRaises(ValueError):
            renderer.project(data, generated_at="2026-10-06")

    def test_projection_keeps_only_public_fields(self):
        data = renderer.project(results(), generated_at="2026-10-06")
        turn = data["turns"][1]
        self.assertEqual(set(turn), {"episode_id", "arm", "repeat", "account", "turn_index", "action",
                                     "interaction_status", "sticker_delivered", "delivered", "funnel", "judge",
                                     "foreground_elapsed_ms"})
        self.assertNotIn("channel", turn["delivered"][1])
        self.assertEqual(data["episodes"][0]["turns"][0]["expectation"], "welcome")


if __name__ == "__main__":
    unittest.main()
