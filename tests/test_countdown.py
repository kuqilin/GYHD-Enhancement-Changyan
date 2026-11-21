# -*- coding: utf-8 -*-

from __future__ import annotations

import unittest
from datetime import date

from gyhd.countdown import exam_info, normalize_stage


class CountdownTest(unittest.TestCase):
    def test_high_school_gaokao(self) -> None:
        info = exam_info("高三", today=date(2026, 11, 22))
        self.assertEqual(info.exam, "高考")
        self.assertEqual(info.target, date(2027, 6, 7))
        self.assertEqual(info.days, 197)

    def test_high_school_stages_have_different_years(self) -> None:
        high2 = exam_info("高二", today=date(2026, 11, 22))
        high1 = exam_info("高一", today=date(2026, 11, 22))
        self.assertEqual(high2.target, date(2028, 6, 7))
        self.assertEqual(high1.target, date(2029, 6, 7))
        self.assertGreater(high2.days, 197)
        self.assertGreater(high1.days, high2.days)

    def test_middle_school_zhongkao(self) -> None:
        info = exam_info("初三", today=date(2026, 11, 22))
        self.assertEqual(info.exam, "中考")
        self.assertEqual(info.target, date(2027, 6, 30))
        self.assertEqual(info.days, 220)

    def test_middle_school_stages_have_different_years(self) -> None:
        middle2 = exam_info("初二", today=date(2026, 11, 22))
        middle1 = exam_info("初一", today=date(2026, 11, 22))
        self.assertEqual(middle2.target, date(2028, 6, 30))
        self.assertEqual(middle1.target, date(2029, 6, 30))
        self.assertGreater(middle2.days, 220)
        self.assertGreater(middle1.days, middle2.days)

    def test_all_high_school_stages_use_gaokao(self) -> None:
        for stage in ("高一", "高二", "高三"):
            info = exam_info(stage, today=date(2026, 11, 22))
            self.assertEqual(info.exam, "高考")

    def test_all_middle_school_stages_use_zhongkao(self) -> None:
        for stage in ("初一", "初二", "初三"):
            info = exam_info(stage, today=date(2026, 11, 22))
            self.assertEqual(info.exam, "中考")

    def test_exam_day_is_zero(self) -> None:
        info = exam_info("高三", today=date(2027, 6, 7))
        self.assertEqual(info.days, 0)
        self.assertEqual(info.target, date(2027, 6, 7))

    def test_day_after_exam_rolls_to_next_year(self) -> None:
        info = exam_info("高三", today=date(2027, 6, 8))
        self.assertEqual(info.target, date(2028, 6, 7))

    def test_invalid_stage_falls_back(self) -> None:
        self.assertEqual(normalize_stage("大学"), "高三")
        info = exam_info("大学", today=date(2026, 11, 22))
        self.assertEqual(info.stage, "高三")
        self.assertEqual(info.exam, "高考")


if __name__ == "__main__":
    unittest.main()
