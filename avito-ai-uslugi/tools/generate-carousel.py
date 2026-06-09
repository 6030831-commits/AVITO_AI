# -*- coding: utf-8 -*-
"""
Пакетная генерация фоновых картинок карусели по плану (plan.json).

План для каждой карточки готовит агент image-prompt-writer и кладёт в
prompts/listings/images/NN-.../plan.json (формат — см. описание агента
~/.claude/agents/image-prompt-writer.md). Этот скрипт читает план и для
каждого кадра с "source": "generate" вызывает OpenAI Images API —
по тем же параметрам, что в tools/generate-images.py (модель, размер,
качество), без ручного ввода промпта.

Кадры с "source": "owner" пропускаются — для них нужен подлинный
материал владельца (см. поле "note" в плане).

Идемпотентно: уже сгенерированный файл «<имя>.png» не перегенерирует
заново (бережём бюджет на вызовы API) — для пересоздания используйте --force.

Использование:
    py -3 tools/generate-carousel.py 01
    py -3 tools/generate-carousel.py 01 --force
    py -3 tools/generate-carousel.py 01 --quality medium
"""

import argparse
import base64
import json
from pathlib import Path

from dotenv import load_dotenv
from openai import OpenAI

PROJECT_ROOT = Path(__file__).parent.parent
LISTINGS_DIR = PROJECT_ROOT / "prompts" / "listings"

load_dotenv(PROJECT_ROOT / ".env")


def find_listing_dir(number: str) -> Path:
    matches = list(LISTINGS_DIR.glob(f"{number}-*.md"))
    if not matches:
        raise SystemExit(f"Не найдено объявление №{number} в {LISTINGS_DIR}")
    return matches[0]


def main():
    parser = argparse.ArgumentParser(description="Пакетная генерация фонов карусели по plan.json")
    parser.add_argument("number", help="номер карточки, напр. 01")
    parser.add_argument("--force", action="store_true", help="перегенерировать даже уже существующие файлы")
    parser.add_argument("--quality", default="low", choices=["low", "medium", "high"], help="качество генерации (по умолчанию low)")
    args = parser.parse_args()

    listing_file = find_listing_dir(args.number)
    plan_path = LISTINGS_DIR / "images" / listing_file.stem / "plan.json"
    if not plan_path.exists():
        raise SystemExit(
            f"Не найден план {plan_path.relative_to(PROJECT_ROOT)} — "
            "сначала подготовьте его (агент image-prompt-writer)."
        )

    plan = json.loads(plan_path.read_text(encoding="utf-8"))
    out_dir = plan_path.parent
    client = OpenAI()

    for frame in plan["frames"]:
        name = frame["name"]
        out_path = out_dir / f"{name}.png"

        if frame["source"] != "generate":
            print(f"  [пропуск] {name} — owner-кадр, нужен материал владельца ({frame.get('note', '')})")
            continue

        if out_path.exists() and not args.force:
            print(f"  [есть] {name}.png — пропускаю (--force для перегенерации)")
            continue

        print(f"  [генерирую] {name} ...")
        result = client.images.generate(
            model="gpt-image-2",
            prompt=frame["prompt"],
            size="1024x1024",
            quality=args.quality,
        )
        image_bytes = base64.b64decode(result.data[0].b64_json)
        out_path.write_bytes(image_bytes)
        print(f"  [готово] {out_path.relative_to(PROJECT_ROOT)}")

    print(f"\nГотово. Папка: {out_dir.relative_to(PROJECT_ROOT)}")


if __name__ == "__main__":
    main()
