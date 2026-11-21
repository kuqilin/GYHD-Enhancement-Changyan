# -*- coding: utf-8 -*-
"""学段与考试倒计时。

高中三个学段数到各自的高考年份（6 月 7 日），初中三个学段数到各自的中考年份
（6 月 30 日）：高三/初三考最近一次，高二/初二再加一年，高一/初一再加两年。
考试当天为 0 天。
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from .constants import (
    DEFAULT_STAGE,
    HIGH_SCHOOL_STAGES,
    MIDDLE_SCHOOL_STAGES,
    STAGES,
)

_STAGE_OFFSET = {
    "高一": 2,
    "高二": 1,
    "高三": 0,
    "初一": 2,
    "初二": 1,
    "初三": 0,
}


@dataclass(frozen=True)
class ExamInfo:
    stage: str
    exam: str
    target: date
    days: int


def normalize_stage(stage: str) -> str:
    return stage if stage in STAGES else DEFAULT_STAGE


def exam_info(stage: str, today: date | None = None) -> ExamInfo:
    today = today or date.today()
    stage = normalize_stage(stage)

    if stage in HIGH_SCHOOL_STAGES:
        exam, month, day = "高考", 6, 7
    elif stage in MIDDLE_SCHOOL_STAGES:
        exam, month, day = "中考", 6, 30
    else:  # pragma: no cover - normalize_stage 已兜底
        exam, month, day = "高考", 6, 7
        stage = DEFAULT_STAGE

    target = date(today.year, month, day)
    if today > target:
        target = date(today.year + 1, month, day)
    target = date(target.year + _STAGE_OFFSET[stage], month, day)
    return ExamInfo(
        stage=stage,
        exam=exam,
        target=target,
        days=(target - today).days,
    )
