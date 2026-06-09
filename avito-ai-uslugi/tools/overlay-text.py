# -*- coding: utf-8 -*-
"""
Наложение русского текста на сгенерированные фоны карусели по плану (plan.json).

Нейросети ненадёжно рисуют русские буквы, поэтому tools/generate-carousel.py
генерирует фоны БЕЗ текста, а этот скрипт дорисовывает поверх title/subtitle
из "overlay_text" — обычным шрифтом (Pillow), с поддержкой кириллицы.

Источник фона — «<имя>.png» (сгенерированный generate-carousel.py),
результат с текстом сохраняется рядом как «<имя>-final.png» — оригинальный
фон не перезаписывается, можно перенакладывать текст заново при правках.

Кадры без "overlay_text" (включая owner-кадры) пропускаются.

Использование:
    py -3 tools/overlay-text.py 01
    py -3 tools/overlay-text.py 01 --force
"""

import argparse
import json
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

PROJECT_ROOT = Path(__file__).parent.parent
LISTINGS_DIR = PROJECT_ROOT / "prompts" / "listings"

FONT_DIR = Path(r"C:\Windows\Fonts")
FONT_TITLE = FONT_DIR / "segoeuib.ttf"     # полужирный — заголовок
FONT_SUBTITLE = FONT_DIR / "segoeui.ttf"   # обычный — подзаголовок

TITLE_SIZE = 64
SUBTITLE_SIZE = 34
MARGIN = 64
LINE_GAP = 16
TEXT_COLOR = (255, 255, 255, 255)
SHADOW_COLOR = (0, 20, 40, 160)
SHADOW_OFFSET = (2, 3)

# (горизонталь, вертикаль) для каждого "position" из плана
POSITIONS = {
    "top": ("center", "top"),
    "top-left": ("left", "top"),
    "top-right": ("right", "top"),
    "bottom": ("center", "bottom"),
    "bottom-left": ("left", "bottom"),
    "bottom-right": ("right", "bottom"),
    "center": ("center", "middle"),
}


def find_listing_dir(number: str) -> Path:
    matches = list(LISTINGS_DIR.glob(f"{number}-*.md"))
    if not matches:
        raise SystemExit(f"Не найдено объявление №{number} в {LISTINGS_DIR}")
    return matches[0]


def wrap_text(draw: ImageDraw.ImageDraw, text: str, font: ImageFont.FreeTypeFont, max_width: int) -> list[str]:
    words = text.split()
    lines, current = [], ""
    for word in words:
        candidate = f"{current} {word}".strip()
        if draw.textlength(candidate, font=font) <= max_width:
            current = candidate
        else:
            if current:
                lines.append(current)
            current = word
    if current:
        lines.append(current)
    return lines


def draw_block(draw, lines, font, x_anchor, y, max_width, color, shadow):
    line_height = font.size + LINE_GAP
    for i, line in enumerate(lines):
        w = draw.textlength(line, font=font)
        if x_anchor == "left":
            x = MARGIN
        elif x_anchor == "right":
            x = max_width - w - MARGIN
        else:
            x = (max_width - w) / 2
        ly = y + i * line_height
        draw.text((x + SHADOW_OFFSET[0], ly + SHADOW_OFFSET[1]), line, font=font, fill=shadow)
        draw.text((x, ly), line, font=font, fill=color)
    return len(lines) * line_height


def overlay_frame(bg_path: Path, out_path: Path, overlay_text: dict):
    img = Image.open(bg_path).convert("RGBA")
    draw = ImageDraw.Draw(img)
    width, height = img.size
    max_text_width = width - 2 * MARGIN

    h_anchor, v_anchor = POSITIONS.get(overlay_text.get("position", "top"), ("left", "top"))

    title_font = ImageFont.truetype(str(FONT_TITLE), TITLE_SIZE)
    subtitle_font = ImageFont.truetype(str(FONT_SUBTITLE), SUBTITLE_SIZE)

    title_lines = wrap_text(draw, overlay_text["title"], title_font, max_text_width)
    subtitle_lines = wrap_text(draw, overlay_text["subtitle"], subtitle_font, max_text_width) if overlay_text.get("subtitle") else []

    title_h = len(title_lines) * (title_font.size + LINE_GAP)
    subtitle_h = len(subtitle_lines) * (subtitle_font.size + LINE_GAP)
    block_h = title_h + (subtitle_h + LINE_GAP if subtitle_lines else 0)

    if v_anchor == "top":
        y = MARGIN
    elif v_anchor == "bottom":
        y = height - MARGIN - block_h
    else:
        y = (height - block_h) / 2

    y += draw_block(draw, title_lines, title_font, h_anchor, y, width, TEXT_COLOR, SHADOW_COLOR)
    if subtitle_lines:
        y += LINE_GAP
        draw_block(draw, subtitle_lines, subtitle_font, h_anchor, y, width, TEXT_COLOR, SHADOW_COLOR)

    img.convert("RGB").save(out_path, "PNG")


def main():
    parser = argparse.ArgumentParser(description="Наложение текста на фоны карусели по plan.json")
    parser.add_argument("number", help="номер карточки, напр. 01")
    parser.add_argument("--force", action="store_true", help="перезаписать уже готовые -final.png")
    args = parser.parse_args()

    listing_file = find_listing_dir(args.number)
    images_dir = LISTINGS_DIR / "images" / listing_file.stem
    plan_path = images_dir / "plan.json"
    if not plan_path.exists():
        raise SystemExit(f"Не найден план {plan_path.relative_to(PROJECT_ROOT)}")

    plan = json.loads(plan_path.read_text(encoding="utf-8"))

    for frame in plan["frames"]:
        name = frame["name"]
        overlay_text = frame.get("overlay_text")
        if not overlay_text:
            print(f"  [пропуск] {name} — нет overlay_text (owner-кадр или фон без надписи)")
            continue

        bg_path = images_dir / f"{name}.png"
        out_path = images_dir / f"{name}-final.png"
        if not bg_path.exists():
            print(f"  [нет фона] {name}.png — сначала запустите generate-carousel.py")
            continue
        if out_path.exists() and not args.force:
            print(f"  [есть] {out_path.name} — пропускаю (--force для перезаписи)")
            continue

        overlay_frame(bg_path, out_path, overlay_text)
        print(f"  [готово] {out_path.relative_to(PROJECT_ROOT)}")

    print(f"\nГотово. Папка: {images_dir.relative_to(PROJECT_ROOT)}")


if __name__ == "__main__":
    main()
