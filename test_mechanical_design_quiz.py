import random
import tempfile
import tkinter as tk
import unittest
from datetime import datetime
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from mechanical_design_quiz import (
    QuizApp,
    build_summary_markdown,
    create_default_progress,
    next_question_index,
    record_check_result,
    toggle_manual_mark,
    write_summary_file,
)
from questions_data import questions


class QuestionDataAnswerTests(unittest.TestCase):
    def assert_question_answer(self, snippet, expected_answer):
        matches = [item for item in questions if snippet in item["question"]]
        self.assertEqual(len(matches), 1, snippet)
        self.assertEqual(matches[0]["answer"], expected_answer)

    def assert_question_explanation_contains(self, snippet, expected_text):
        matches = [item for item in questions if snippet in item["question"]]
        self.assertEqual(len(matches), 1, snippet)
        self.assertIn(expected_text, matches[0]["explanation"])

    def test_reviewed_book_answer_corrections_are_applied(self):
        expected_answers = {
            "对于一般单向转动的转轴，其扭切应力": "B",
            "当轴系不受轴向力作用": "C",
            "增大相对间隙，则其最小": "B",
            "若发现最小油膜厚度hmin": "B",
            "滑动螺旋传动的主要失效形式": "B",
            "棘轮机构将连续回转运动": "B",
            "单销槽轮机构运动系数≤0.5": "A",
            "液体动压向心滑动轴承所受载荷越小": "A",
            "液体动压向心滑动轴承间隙越大": "B",
            "液体动压润滑向心滑动轴承的轴颈": "B",
            "深沟球轴承极限转速很高": "A",
            "滚动轴承所受轴向载荷应为": "B",
        }
        for snippet, expected_answer in expected_answers.items():
            with self.subTest(snippet=snippet):
                self.assert_question_answer(snippet, expected_answer)

    def test_rolling_bearing_speed_life_explanation_keeps_life_unit_distinction(self):
        self.assert_question_explanation_contains(
            "转速减小到原来的1/2",
            "若按总转数L10计则不随转速改变",
        )

class QuizProgressTests(unittest.TestCase):
    def make_root(self):
        try:
            root = tk.Tk()
        except tk.TclError as exc:
            self.skipTest(f"Tk is not available: {exc}")
        root.withdraw()
        return root

    def test_default_progress_has_one_status_per_question_and_saved_random_order(self):
        progress = create_default_progress(4, rng=random.Random(7))

        self.assertEqual(progress["current_index"], 0)
        self.assertEqual(progress["mode"], "sequential")
        self.assertTrue(progress["auto_save"])
        self.assertCountEqual(progress["random_order"], [0, 1, 2, 3])
        self.assertEqual(len(progress["question_status"]), 4)
        self.assertEqual(
            progress["question_status"][0],
            {
                "selected": None,
                "checked": False,
                "is_correct": None,
                "auto_wrong": False,
                "manual_marked": False,
            },
        )

    def test_next_question_uses_sequential_or_saved_random_order(self):
        progress = create_default_progress(5, rng=random.Random(1))

        self.assertEqual(next_question_index(progress, 5), 1)

        progress["mode"] = "random"
        progress["random_order"] = [3, 1, 4, 0, 2]
        progress["current_index"] = 1

        self.assertEqual(next_question_index(progress, 5), 4)

    def test_all_review_scope_keeps_sequential_navigation_unchanged(self):
        progress = create_default_progress(5, rng=random.Random(1))
        progress["current_index"] = 2
        progress["question_status"][1]["auto_wrong"] = True
        progress["question_status"][4]["manual_marked"] = True

        self.assertEqual(next_question_index(progress, 5), 3)
        self.assertEqual(next_question_index(progress, 5, direction=-1), 1)

    def test_all_review_scope_keeps_random_navigation_unchanged(self):
        progress = create_default_progress(5, rng=random.Random(1))
        progress["mode"] = "random"
        progress["random_order"] = [4, 1, 3, 0, 2]
        progress["current_index"] = 1
        progress["question_status"][0]["auto_wrong"] = True
        progress["question_status"][4]["manual_marked"] = True

        self.assertEqual(next_question_index(progress, 5), 3)
        self.assertEqual(next_question_index(progress, 5, direction=-1), 4)

    def test_wrong_marked_scope_navigates_only_live_wrong_or_marked_questions(self):
        progress = create_default_progress(5, rng=random.Random(1))
        progress["review_scope"] = "wrong_marked"
        progress["current_index"] = 1
        progress["question_status"][1]["auto_wrong"] = True
        progress["question_status"][3]["manual_marked"] = True

        self.assertEqual(next_question_index(progress, 5), 3)
        progress["current_index"] = 3
        self.assertEqual(next_question_index(progress, 5, direction=-1), 1)

    def test_wrong_marked_scope_random_navigation_uses_filtered_saved_order(self):
        progress = create_default_progress(5, rng=random.Random(1))
        progress["mode"] = "random"
        progress["review_scope"] = "wrong_marked"
        progress["random_order"] = [2, 4, 0, 3, 1]
        progress["current_index"] = 4
        progress["question_status"][1]["auto_wrong"] = True
        progress["question_status"][4]["manual_marked"] = True

        self.assertEqual(next_question_index(progress, 5), 1)
        progress["current_index"] = 1
        self.assertEqual(next_question_index(progress, 5, direction=-1), 4)

    def test_last_wrong_marked_scope_navigates_saved_previous_round_indices(self):
        progress = create_default_progress(5, rng=random.Random(1))
        progress["review_scope"] = "last_wrong_marked"
        progress["last_wrong_marked_indices"] = [1, 4]
        progress["current_index"] = 1

        self.assertEqual(next_question_index(progress, 5), 4)
        progress["current_index"] = 4
        self.assertEqual(next_question_index(progress, 5, direction=-1), 1)

    def test_random_next_question_follows_saved_order_even_when_checked(self):
        progress = create_default_progress(5, rng=random.Random(1))
        progress["mode"] = "random"
        progress["random_order"] = [0, 2, 4, 1, 3]
        progress["current_index"] = 0
        progress["question_status"][2]["checked"] = True
        progress["question_status"][4]["checked"] = True

        self.assertEqual(next_question_index(progress, 5), 2)

    def test_random_previous_question_follows_saved_order_even_when_checked(self):
        progress = create_default_progress(5, rng=random.Random(1))
        progress["mode"] = "random"
        progress["random_order"] = [0, 2, 4, 1, 3]
        progress["current_index"] = 3
        progress["question_status"][1]["checked"] = True
        progress["question_status"][4]["checked"] = True

        self.assertEqual(next_question_index(progress, 5, direction=-1), 1)

    def test_random_navigation_allows_checked_question_when_no_unchecked_remains(self):
        progress = create_default_progress(3, rng=random.Random(1))
        progress["mode"] = "random"
        progress["random_order"] = [0, 1, 2]
        progress["current_index"] = 0
        for status in progress["question_status"]:
            status["checked"] = True

        self.assertEqual(next_question_index(progress, 3), 1)

    def test_random_next_stops_at_saved_order_end(self):
        progress = create_default_progress(4, rng=random.Random(1))
        progress["mode"] = "random"
        progress["random_order"] = [0, 1, 2, 3]
        progress["current_index"] = 3
        progress["question_status"][0]["checked"] = True
        progress["question_status"][1]["checked"] = False
        progress["question_status"][2]["checked"] = True

        self.assertEqual(next_question_index(progress, 4), 3)

    def test_wrong_answer_sets_auto_wrong_without_requiring_manual_mark(self):
        progress = create_default_progress(2, rng=random.Random(2))

        record_check_result(progress, 0, "A", "B")

        self.assertEqual(progress["question_status"][0]["selected"], "A")
        self.assertTrue(progress["question_status"][0]["checked"])
        self.assertFalse(progress["question_status"][0]["is_correct"])
        self.assertTrue(progress["question_status"][0]["auto_wrong"])
        self.assertFalse(progress["question_status"][0]["manual_marked"])

    def test_manual_mark_toggle_does_not_clear_auto_wrong(self):
        progress = create_default_progress(1, rng=random.Random(3))
        record_check_result(progress, 0, "A", "B")

        toggle_manual_mark(progress, 0)
        toggle_manual_mark(progress, 0)

        self.assertTrue(progress["question_status"][0]["auto_wrong"])
        self.assertFalse(progress["question_status"][0]["manual_marked"])

    def test_tk_app_can_initialize_with_minimal_question_bank(self):
        root = self.make_root()
        try:
            with tempfile.TemporaryDirectory() as temp_dir:
                progress_path = Path(temp_dir) / "quiz_progress.json"
                QuizApp(
                    root,
                    question_bank=[
                        {
                            "question": "Question",
                            "options": ["A. one", "B. two"],
                            "answer": "A",
                        }
                    ],
                    progress_path=progress_path,
                )
                root.update_idletasks()
                self.assertTrue(progress_path.exists())
        finally:
            root.destroy()

    def test_keyboard_selection_check_and_arrow_navigation(self):
        root = self.make_root()
        try:
            with tempfile.TemporaryDirectory() as temp_dir:
                app = QuizApp(
                    root,
                    question_bank=[
                        {"question": "Q1", "options": ["A. one", "B. two"], "answer": "B"},
                        {"question": "Q2", "options": ["A. one", "B. two"], "answer": "A"},
                    ],
                    progress_path=Path(temp_dir) / "quiz_progress.json",
                )

                app.handle_key_press(SimpleNamespace(keysym="a", char="a"))

                status = app.progress["question_status"][0]
                self.assertEqual(status["selected"], "A")
                self.assertFalse(status["checked"])

                app.handle_key_press(SimpleNamespace(keysym="Return", char=""))

                self.assertTrue(status["checked"])
                self.assertTrue(status["auto_wrong"])

                app.handle_key_press(SimpleNamespace(keysym="Return", char=""))
                self.assertEqual(app.progress["current_index"], 1)

                app.handle_key_press(SimpleNamespace(keysym="Left", char=""))
                self.assertEqual(app.progress["current_index"], 0)

                app.handle_key_press(SimpleNamespace(keysym="Right", char=""))
                self.assertEqual(app.progress["current_index"], 1)
        finally:
            root.destroy()

    def test_unchecked_selection_does_not_reveal_correct_answer_color(self):
        root = self.make_root()
        try:
            with tempfile.TemporaryDirectory() as temp_dir:
                app = QuizApp(
                    root,
                    question_bank=[
                        {"question": "Q1", "options": ["A. one", "B. two"], "answer": "B"}
                    ],
                    progress_path=Path(temp_dir) / "quiz_progress.json",
                )

                app.select_answer("A")

                self.assertEqual(app.option_buttons[0].cget("bg"), "#dbeafe")
                self.assertEqual(app.option_buttons[0].cget("selectcolor"), "#dbeafe")
                self.assertEqual(app.option_buttons[1].cget("bg"), "#ffffff")
                self.assertEqual(app.option_buttons[1].cget("selectcolor"), "#ffffff")
        finally:
            root.destroy()

    def test_wrong_answer_marks_selected_option_red_and_correct_option_green(self):
        root = self.make_root()
        try:
            with tempfile.TemporaryDirectory() as temp_dir:
                app = QuizApp(
                    root,
                    question_bank=[
                        {"question": "Q1", "options": ["A. one", "B. two"], "answer": "B"}
                    ],
                    progress_path=Path(temp_dir) / "quiz_progress.json",
                )

                app.select_answer("A")
                app.check_answer()

                self.assertEqual(app.option_buttons[0].cget("bg"), "#fee2e2")
                self.assertEqual(app.option_buttons[0].cget("selectcolor"), "#fee2e2")
                self.assertEqual(app.option_buttons[1].cget("bg"), "#dcfce7")
                self.assertEqual(app.option_buttons[1].cget("selectcolor"), "#dcfce7")
        finally:
            root.destroy()

    def test_correct_answer_marks_only_selected_correct_option_green(self):
        root = self.make_root()
        try:
            with tempfile.TemporaryDirectory() as temp_dir:
                app = QuizApp(
                    root,
                    question_bank=[
                        {"question": "Q1", "options": ["A. one", "B. two"], "answer": "B"}
                    ],
                    progress_path=Path(temp_dir) / "quiz_progress.json",
                )

                app.select_answer("B")
                app.check_answer()

                self.assertEqual(app.option_buttons[0].cget("bg"), "#ffffff")
                self.assertEqual(app.option_buttons[0].cget("selectcolor"), "#ffffff")
                self.assertEqual(app.option_buttons[1].cget("bg"), "#dcfce7")
                self.assertEqual(app.option_buttons[1].cget("selectcolor"), "#dcfce7")
        finally:
            root.destroy()

    def test_random_mode_next_uses_queue_but_jump_uses_original_index(self):
        root = self.make_root()
        try:
            with tempfile.TemporaryDirectory() as temp_dir:
                app = QuizApp(
                    root,
                    question_bank=[
                        {"question": "Q1", "options": ["A. one"], "answer": "A"},
                        {"question": "Q2", "options": ["A. one"], "answer": "A"},
                        {"question": "Q3", "options": ["A. one"], "answer": "A"},
                    ],
                    progress_path=Path(temp_dir) / "quiz_progress.json",
                )
                app.progress["mode"] = "random"
                app.progress["random_order"] = [2, 0, 1]
                app.progress["current_index"] = 0

                app.next_question()
                self.assertEqual(app.progress["current_index"], 1)

                app.go_to_question(2)
                self.assertEqual(app.progress["current_index"], 2)
        finally:
            root.destroy()

    def test_random_left_arrow_returns_to_previous_checked_question_in_order(self):
        root = self.make_root()
        try:
            with tempfile.TemporaryDirectory() as temp_dir:
                app = QuizApp(
                    root,
                    question_bank=[
                        {"question": "Q1", "options": ["A. one"], "answer": "A"},
                        {"question": "Q2", "options": ["A. one"], "answer": "A"},
                        {"question": "Q3", "options": ["A. one"], "answer": "A"},
                        {"question": "Q4", "options": ["A. one"], "answer": "A"},
                        {"question": "Q5", "options": ["A. one"], "answer": "A"},
                    ],
                    progress_path=Path(temp_dir) / "quiz_progress.json",
                )
                app.progress["mode"] = "random"
                app.progress["random_order"] = [0, 3, 4, 1, 2]
                app.progress["current_index"] = 3
                app.progress["question_status"][0]["checked"] = True

                app.handle_key_press(SimpleNamespace(keysym="Left", char=""))

                self.assertEqual(app.progress["current_index"], 0)
        finally:
            root.destroy()

    def test_switching_to_random_from_checked_question_moves_to_first_unchecked_question(self):
        root = self.make_root()
        try:
            with tempfile.TemporaryDirectory() as temp_dir:
                app = QuizApp(
                    root,
                    question_bank=[
                        {"question": "Q1", "options": ["A. one"], "answer": "A"},
                        {"question": "Q2", "options": ["A. one"], "answer": "A"},
                        {"question": "Q3", "options": ["A. one"], "answer": "A"},
                        {"question": "Q4", "options": ["A. one"], "answer": "A"},
                    ],
                    progress_path=Path(temp_dir) / "quiz_progress.json",
                )
                app.progress["current_index"] = 0
                app.progress["random_order"] = [3, 1, 0, 2]
                app.progress["question_status"][0]["checked"] = True
                app.progress["question_status"][1]["checked"] = True
                app.mode_var.set("random")

                with patch("mechanical_design_quiz.random.shuffle", side_effect=lambda values: values.reverse()):
                    app.change_mode()

                self.assertEqual(app.progress["random_order"], [0, 1, 3, 2])
                self.assertEqual(app.progress["current_index"], 3)
        finally:
            root.destroy()

    def test_switching_to_random_keeps_unchecked_current_question_at_unchecked_front(self):
        root = self.make_root()
        try:
            with tempfile.TemporaryDirectory() as temp_dir:
                app = QuizApp(
                    root,
                    question_bank=[
                        {"question": "Q1", "options": ["A. one"], "answer": "A"},
                        {"question": "Q2", "options": ["A. one"], "answer": "A"},
                        {"question": "Q3", "options": ["A. one"], "answer": "A"},
                        {"question": "Q4", "options": ["A. one"], "answer": "A"},
                        {"question": "Q5", "options": ["A. one"], "answer": "A"},
                    ],
                    progress_path=Path(temp_dir) / "quiz_progress.json",
                )
                app.progress["current_index"] = 2
                app.progress["random_order"] = [4, 3, 2, 1, 0]
                app.progress["question_status"][0]["checked"] = True
                app.progress["question_status"][1]["checked"] = True
                app.mode_var.set("random")

                with patch("mechanical_design_quiz.random.shuffle", side_effect=lambda values: values.reverse()):
                    app.change_mode()

                self.assertEqual(app.progress["random_order"], [0, 1, 2, 4, 3])
                self.assertEqual(app.progress["current_index"], 2)
        finally:
            root.destroy()

    def test_empty_wrong_marked_scope_is_rejected(self):
        root = self.make_root()
        try:
            with tempfile.TemporaryDirectory() as temp_dir:
                app = QuizApp(
                    root,
                    question_bank=[
                        {"question": "Q1", "options": ["A. one"], "answer": "A"},
                        {"question": "Q2", "options": ["A. one"], "answer": "A"},
                    ],
                    progress_path=Path(temp_dir) / "quiz_progress.json",
                )

                app.review_scope_var.set("wrong_marked")
                app.change_review_scope()

                self.assertEqual(app.progress["review_scope"], "all")
                self.assertEqual(app.review_scope_var.get(), "all")
                self.assertIn("暂无错题或标记题", app.feedback_var.get())
        finally:
            root.destroy()

    def test_filtered_review_scope_meta_shows_original_question_position_and_scoped_checked_count(self):
        root = self.make_root()
        try:
            with tempfile.TemporaryDirectory() as temp_dir:
                app = QuizApp(
                    root,
                    question_bank=[
                        {"question": "Q1", "options": ["A. one"], "answer": "A"},
                        {"question": "Q2", "options": ["A. one"], "answer": "A"},
                        {"question": "Q3", "options": ["A. one"], "answer": "A"},
                        {"question": "Q4", "options": ["A. one"], "answer": "A"},
                        {"question": "Q5", "options": ["A. one"], "answer": "A"},
                    ],
                    progress_path=Path(temp_dir) / "quiz_progress.json",
                )
                app.progress["review_scope"] = "last_wrong_marked"
                app.progress["last_wrong_marked_indices"] = [1, 3]
                app.progress["current_index"] = 3
                app.progress["question_status"][0]["checked"] = True
                app.progress["question_status"][1]["checked"] = True

                app.show_question()

                self.assertIn("上一轮错题/标记 | 第 4/5 题", app.meta_var.get())
                self.assertIn("已检查 1/2", app.meta_var.get())
        finally:
            root.destroy()

    def test_reset_keeps_previous_round_wrong_marked_indices_for_review(self):
        root = self.make_root()
        try:
            with tempfile.TemporaryDirectory() as temp_dir:
                app = QuizApp(
                    root,
                    question_bank=[
                        {"question": "Q1", "options": ["A. one", "B. two"], "answer": "B"},
                        {"question": "Q2", "options": ["A. one"], "answer": "A"},
                        {"question": "Q3", "options": ["A. one"], "answer": "A"},
                    ],
                    progress_path=Path(temp_dir) / "quiz_progress.json",
                    summary_dir=Path(temp_dir) / "summary",
                )
                record_check_result(app.progress, 0, "A", "B")
                app.progress["question_status"][2]["manual_marked"] = True

                with patch("mechanical_design_quiz.messagebox.askyesno", return_value=True), patch(
                    "mechanical_design_quiz.messagebox.showinfo"
                ):
                    app.reset_progress()

                self.assertEqual(app.progress["last_wrong_marked_indices"], [0, 2])
                self.assertFalse(app.progress["question_status"][0]["auto_wrong"])
                self.assertFalse(app.progress["question_status"][2]["manual_marked"])
        finally:
            root.destroy()

    def test_summary_includes_auto_wrong_and_manual_marked_questions_once(self):
        question_bank = [
            {
                "question": "Q1 text",
                "options": ["A. one", "B. two"],
                "answer": "B",
                "explanation": "Q1 explanation",
            },
            {"question": "Q2 text", "options": ["A. yes"], "answer": "A"},
            {"question": "Q3 text", "options": ["A. yes", "B. no"], "answer": "A"},
        ]
        progress = create_default_progress(3, rng=random.Random(4))
        record_check_result(progress, 0, "A", "B")
        progress["question_status"][1]["manual_marked"] = True
        record_check_result(progress, 2, "B", "A")
        progress["question_status"][2]["manual_marked"] = True

        markdown = build_summary_markdown(
            question_bank,
            progress,
            generated_at=datetime(2026, 5, 27, 17, 30, 5),
        )

        self.assertIn("# 错题 Summary", markdown)
        self.assertIn("生成时间：2026-05-27 17:30:05", markdown)
        self.assertIn("总题数：3", markdown)
        self.assertIn("已检查题数：2", markdown)
        self.assertIn("导出题数：3", markdown)
        self.assertIn("## 1. 第 1 题", markdown)
        self.assertIn("来源：自动错题", markdown)
        self.assertIn("用户选择：A", markdown)
        self.assertIn("正确答案：B", markdown)
        self.assertIn("最近结果：错误", markdown)
        self.assertIn("解析：Q1 explanation", markdown)
        self.assertIn("## 2. 第 2 题", markdown)
        self.assertIn("来源：手动标记", markdown)
        self.assertIn("最近结果：未检查", markdown)
        self.assertIn("## 3. 第 3 题", markdown)
        self.assertIn("来源：自动错题、手动标记", markdown)
        self.assertEqual(markdown.count("Q3 text"), 1)

    def test_summary_records_empty_state_before_reset(self):
        progress = create_default_progress(1, rng=random.Random(5))

        markdown = build_summary_markdown(
            [{"question": "Q1", "options": ["A. one"], "answer": "A"}],
            progress,
            generated_at=datetime(2026, 5, 27, 17, 31),
        )

        self.assertIn("导出题数：0", markdown)
        self.assertIn("本次重置前没有错题或标记题。", markdown)

    def test_write_summary_file_creates_summary_directory_and_timestamped_file(self):
        progress = create_default_progress(1, rng=random.Random(6))
        progress["question_status"][0]["manual_marked"] = True

        with tempfile.TemporaryDirectory() as temp_dir:
            path = write_summary_file(
                Path(temp_dir) / "summary",
                [{"question": "Q1", "options": ["A. one"], "answer": "A"}],
                progress,
                generated_at=datetime(2026, 5, 27, 17, 32, 9),
            )

            self.assertEqual(path.name, "summary-20260527-173209.md")
            self.assertTrue(path.exists())
            self.assertIn("Q1", path.read_text(encoding="utf-8"))

    def test_reset_writes_summary_before_clearing_progress(self):
        root = self.make_root()
        try:
            with tempfile.TemporaryDirectory() as temp_dir:
                app = QuizApp(
                    root,
                    question_bank=[
                        {"question": "Q1", "options": ["A. one", "B. two"], "answer": "B"}
                    ],
                    progress_path=Path(temp_dir) / "quiz_progress.json",
                    summary_dir=Path(temp_dir) / "summary",
                )
                record_check_result(app.progress, 0, "A", "B")

                with patch("mechanical_design_quiz.messagebox.askyesno", return_value=True), patch(
                    "mechanical_design_quiz.messagebox.showinfo"
                ):
                    app.reset_progress()

                summary_files = list((Path(temp_dir) / "summary").glob("summary-*.md"))
                self.assertEqual(len(summary_files), 1)
                self.assertIn("Q1", summary_files[0].read_text(encoding="utf-8"))
                self.assertFalse(app.progress["question_status"][0]["checked"])
                self.assertFalse(app.progress["question_status"][0]["auto_wrong"])
        finally:
            root.destroy()

    def test_reset_does_not_clear_progress_when_summary_write_fails(self):
        root = self.make_root()
        try:
            with tempfile.TemporaryDirectory() as temp_dir:
                app = QuizApp(
                    root,
                    question_bank=[
                        {"question": "Q1", "options": ["A. one", "B. two"], "answer": "B"}
                    ],
                    progress_path=Path(temp_dir) / "quiz_progress.json",
                    summary_dir=Path(temp_dir) / "summary",
                )
                record_check_result(app.progress, 0, "A", "B")

                with patch("mechanical_design_quiz.messagebox.askyesno", return_value=True), patch(
                    "mechanical_design_quiz.write_summary_file",
                    side_effect=OSError("disk full"),
                ), patch("mechanical_design_quiz.messagebox.showerror") as showerror:
                    app.reset_progress()

                self.assertTrue(app.progress["question_status"][0]["checked"])
                self.assertTrue(app.progress["question_status"][0]["auto_wrong"])
                showerror.assert_called_once()
        finally:
            root.destroy()


if __name__ == "__main__":
    unittest.main()
