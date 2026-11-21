# -*- coding: utf-8 -*-
"""在壁纸副本上印倒计时/气温，不改源图。

输出到 ``%LOCALAPPDATA%\\GYHD-Enhancement-Changyan\\wallpapers\\wallpaper-*.jpg``，
源文件只读，永远不会被覆盖。
"""

from __future__ import annotations

import logging
from datetime import datetime
from pathlib import Path

from PyQt5.QtCore import QPointF, QRectF, Qt
from PyQt5.QtGui import (
    QColor,
    QFont,
    QFontMetrics,
    QGuiApplication,
    QImage,
    QImageReader,
    QPainter,
)

from .constants import app_data_dir
from .weather import Temperature

logger = logging.getLogger(__name__)

OUTPUT_DIR = app_data_dir() / "wallpapers"


class OverlayError(RuntimeError):
    """壁纸副本生成失败。"""


def output_dir() -> Path:
    return OUTPUT_DIR


def build_text(
    stage: str,
    exam: str,
    days: int,
    temperature: Temperature | None,
) -> tuple[str, str | None]:
    if days <= 0:
        title = f"{stage} · 今天{exam}"
    else:
        title = f"{stage} · 距离{exam} {days} 天"
    return title, temperature.text if temperature is not None else None


def render_wallpaper(
    source: str | Path,
    *,
    stage: str,
    exam: str,
    days: int,
    temperature: Temperature | None = None,
    destination_dir: str | Path | None = None,
) -> Path:
    """读取源图，画上文字，保存成新的 JPG，返回新文件路径。"""
    if QGuiApplication.instance() is None:
        raise OverlayError("QGuiApplication 尚未创建，无法绘制壁纸")

    reader = QImageReader(str(source))
    reader.setAutoTransform(True)
    image = reader.read()
    if image.isNull():
        raise OverlayError(
            f"读取壁纸失败：{source}（{reader.errorString() or '未知格式'}）"
        )

    canvas = QImage(image.size(), QImage.Format_RGB32)
    canvas.fill(Qt.black)

    painter = QPainter()
    try:
        if not painter.begin(canvas):
            raise OverlayError("QPainter 初始化失败")
        painter.setRenderHint(QPainter.Antialiasing, True)
        painter.setRenderHint(QPainter.TextAntialiasing, True)
        painter.drawImage(0, 0, image)

        title, temp_text = build_text(stage, exam, days, temperature)
        margin_x = max(20, int(canvas.width() * 0.03))
        margin_y = max(18, int(canvas.height() * 0.03))
        max_box_width = max(40, canvas.width() - margin_x * 2)
        max_box_height = max(40, canvas.height() - margin_y * 2)

        base = max(18, min(64, int(canvas.width() * 0.022)))
        while True:
            title_font = QFont("Microsoft YaHei UI")
            title_font.setPixelSize(base)
            title_font.setBold(True)
            temp_font = QFont("Microsoft YaHei UI")
            temp_font.setPixelSize(max(12, int(base * 0.82)))

            title_metrics = QFontMetrics(title_font)
            temp_metrics = QFontMetrics(temp_font)
            line_gap = max(4, int(base * 0.22))
            widths = [title_metrics.horizontalAdvance(title)]
            if temp_text:
                widths.append(temp_metrics.horizontalAdvance(temp_text))

            padding_x = max(14, int(base * 0.6))
            padding_y = max(10, int(base * 0.35))
            box_width = max(widths) + padding_x * 2
            box_height = padding_y * 2 + title_metrics.height()
            if temp_text:
                box_height += line_gap + temp_metrics.height()

            if (
                box_width <= max_box_width and box_height <= max_box_height
            ) or base <= 12:
                break
            base = max(12, int(base * 0.88))

        # 顶部居中：不贴右边缘，也不会因为字太长跑出屏幕。
        x = max(0, (canvas.width() - box_width) // 2)
        y = margin_y

        painter.setPen(Qt.NoPen)
        painter.setBrush(QColor(0, 0, 0, 118))
        radius = max(8, int(base * 0.35))
        painter.drawRoundedRect(
            QRectF(x, y, box_width, box_height), radius, radius
        )

        painter.setPen(QColor(255, 255, 255, 242))
        painter.setFont(title_font)
        baseline = y + padding_y + title_metrics.ascent()
        painter.drawText(QPointF(x + padding_x, baseline), title)

        if temp_text:
            painter.setFont(temp_font)
            baseline += title_metrics.height() + line_gap
            painter.drawText(QPointF(x + padding_x, baseline), temp_text)
    finally:
        if painter.isActive():
            painter.end()

    target_dir = Path(destination_dir) if destination_dir is not None else output_dir()
    target_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S-%f")
    output = target_dir / f"wallpaper-{stamp}.jpg"
    if not canvas.save(str(output), "JPG", 92):
        raise OverlayError(f"保存壁纸副本失败：{output}")
    logger.info("已生成带文字的壁纸：%s", output)
    return output


def cleanup_generated(keep: int = 5, folder: str | Path | None = None) -> None:
    """只保留最近几张生成的副本，避免无限占空间。"""
    target_dir = Path(folder) if folder is not None else output_dir()
    try:
        files = sorted(
            (path for path in target_dir.glob("wallpaper-*.jpg") if path.is_file()),
            key=lambda path: path.stat().st_mtime,
            reverse=True,
        )
    except OSError:
        return
    for old in files[max(1, keep) :]:
        try:
            old.unlink()
        except OSError:
            logger.debug("删除旧壁纸副本失败：%s", old, exc_info=True)
