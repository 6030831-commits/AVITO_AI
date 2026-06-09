# -*- coding: utf-8 -*-
"""
Генерация кадров карусели для карточек Авито через OpenAI Images API.

Адаптировано из generate_image.py (рабочий скрипт владельца) — логика вызова
API и сохранения файла сохранены без изменений, добавлено только: чтение
ключа из .env проекта и сохранение результата в папку рядом с текстом нужной
карточки (prompts/listings/images/NN-.../), а не в корень проекта.

Использование:
    py -3 tools/generate-images.py 01 oblozhka

Спросит промпт и качество в терминале (как раньше), сохранит файл
prompts/listings/images/01-.../oblozhka.png
"""

import base64
import sys
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
    if len(sys.argv) < 3:
        raise SystemExit(
            "Использование: py -3 tools/generate-images.py <номер, напр. 01> <имя кадра, напр. oblozhka>"
        )
    number, frame_name = sys.argv[1], sys.argv[2]
    listing_file = find_listing_dir(number)
    out_dir = LISTINGS_DIR / "images" / listing_file.stem
    out_dir.mkdir(parents=True, exist_ok=True)

    prompt = input("Опишите картинку: ")
    quality = input("Качество (low / medium / high) [Enter = low]: ")
    if quality == "":
        quality = "low"

    client = OpenAI()
    result = client.images.generate(
        model="gpt-image-2",
        prompt=prompt,
        size="1024x1024",
        quality=quality,
    )

    image_bytes = base64.b64decode(result.data[0].b64_json)
    out_path = out_dir / f"{frame_name}.png"
    out_path.write_bytes(image_bytes)

    print(f"Готово, сохранил в {out_path.relative_to(PROJECT_ROOT)}")


if __name__ == "__main__":
    main()
