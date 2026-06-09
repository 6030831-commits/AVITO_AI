# -*- coding: utf-8 -*-
"""
Пишет план генерации инфографики (plan.json) через OpenAI API — вместо
агента Claude Code image-prompt-writer этот шаг выполняет модель OpenAI:
читает текст и макет карточки (## ОПИСАНИЕ, ## МАКЕТ), разбивает кадры
карусели на generate/owner и пишет промпты + текст наложения тем же
форматом, что ожидают tools/generate-carousel.py и tools/overlay-text.py.

Использование:
    py -3 tools/write-image-prompts.py 01
    py -3 tools/write-image-prompts.py 01 --model gpt-4o
"""

import argparse
import json
import re
from pathlib import Path

from dotenv import load_dotenv
from openai import OpenAI

PROJECT_ROOT = Path(__file__).parent.parent
LISTINGS_DIR = PROJECT_ROOT / "prompts" / "listings"

load_dotenv(PROJECT_ROOT / ".env")

SYSTEM_PROMPT = """\
Ты готовишь техническое задание для автоматической генерации инфографики
карусели карточки услуг ИИ-автоматизации на Авито. На входе — текст
объявления и макет карточки (разделы ## ОПИСАНИЕ и ## МАКЕТ). На выходе —
план в JSON, по которому скрипты сгенерируют фоновые картинки (OpenAI
Images API) и наложат русский текст (Pillow).

РАЗДЕЛИ КАДРЫ МАКЕТА НА ДВА ТИПА
В разделе «Кадры на обложке и в галерее» макета — 4-5 кадров. Каждый
относится к одному из типов:

- "generate" — обложка с текстом-наложением, обзорные схемы
  процесса/пайплайна, инфографика с цифрами и иконками. Честная
  иллюстрация сути услуги, не выдаётся за реальный кейс — можно
  генерировать нейросетью.
- "owner" — всё, что описано как подлинный кейс: лицо автора, скрины
  ботов/диалогов/панелей, расчётные таблицы, фото производства. Нужен
  настоящий материал владельца — генерировать НЕЛЬЗЯ (правило: кадры
  должны быть проверяемыми и реальными, никаких сгенерированных имитаций
  кейсов). При сомнении — относи кадр к "owner".

ЧТО ПИСАТЬ ДЛЯ КАДРОВ ТИПА "generate"
1. "prompt" — английский промпт для генерации ФОНА БЕЗ ТЕКСТА (нейросети
   ненадёжно рисуют русские буквы): объекты/композиция/стиль/палитра,
   обязательно заканчивай фразой "no text, no letters, no words, no
   typography", квадрат или 4:3. Единая палитра и стиль на все кадры
   одной карточки (тёмно-синий + бирюзовый акцент, минималистичная
   плоская корпоративная техноиллюстрация — vector illustration style),
   но не повторяй композицию/иконки других карточек — у каждой своя
   визуальная подпись под свою услугу.
2. "overlay_text" — русский текст для наложения (бери из описания кадра
   в ## МАКЕТ): "title" (главная фраза), необязательный "subtitle",
   "position" (одно из: top, top-left, top-right, bottom, bottom-left,
   bottom-right, center).

ФОРМАТ ОТВЕТА — строго JSON, без пояснений, по схеме:
{
  "frames": [
    {
      "name": "kebab-имя-кадра-латиницей",
      "source": "generate",
      "prompt": "...",
      "overlay_text": {"title": "...", "subtitle": "...", "position": "top-left"}
    },
    {
      "name": "kebab-имя-кадра-латиницей",
      "source": "owner",
      "note": "что именно нужно от владельца — копия сути из ## МАКЕТ"
    }
  ]
}
Имена кадров — латиницей, kebab-case, без пробелов (станут именами
файлов). Порядок frames — порядок показа в галерее, как в ## МАКЕТ.
Для "generate"-кадров с числовыми данными (например, «было/стало»),
у которых в макете нет конкретных цифр (это «обобщённый кейс» без
привязки к реальному показателю), ставь в subtitle понятную заглушку
вида «ЗАМЕНИТЬ на реальные цифры конкретного кейса перед наложением» —
не выдумывай цифры сам.
"""


def find_listing_dir(number: str) -> Path:
    matches = list(LISTINGS_DIR.glob(f"{number}-*.md"))
    if not matches:
        raise SystemExit(f"Не найдено объявление №{number} в {LISTINGS_DIR}")
    return matches[0]


def extract_relevant_text(full_text: str) -> str:
    """Берём только заголовок + ## ОПИСАНИЕ + ## МАКЕТ — это всё, что нужно модели."""
    parts = []
    for heading in ("## ОПИСАНИЕ", "## МАКЕТ"):
        match = re.search(rf"{re.escape(heading)}\n(.*?)(?=\n## |\Z)", full_text, re.DOTALL)
        if match:
            parts.append(f"{heading}\n{match.group(1).strip()}")
    title_match = re.match(r"(# .+)", full_text)
    title = title_match.group(1) if title_match else ""
    return "\n\n".join([title] + parts)


def main():
    parser = argparse.ArgumentParser(description="Пишет plan.json через OpenAI API")
    parser.add_argument("number", help="номер карточки, напр. 01")
    parser.add_argument("--model", default="gpt-4o", help="модель OpenAI для написания промптов (по умолчанию gpt-4o)")
    args = parser.parse_args()

    listing_file = find_listing_dir(args.number)
    full_text = listing_file.read_text(encoding="utf-8")
    relevant_text = extract_relevant_text(full_text)

    client = OpenAI()
    response = client.chat.completions.create(
        model=args.model,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": f"Текст карточки:\n\n{relevant_text}"},
        ],
        response_format={"type": "json_object"},
    )

    raw = response.choices[0].message.content
    parsed = json.loads(raw)
    plan = {"listing": listing_file.stem, "frames": parsed["frames"]}

    out_dir = LISTINGS_DIR / "images" / listing_file.stem
    out_dir.mkdir(parents=True, exist_ok=True)
    plan_path = out_dir / "plan.json"
    plan_path.write_text(json.dumps(plan, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"Сохранено: {plan_path.relative_to(PROJECT_ROOT)}")
    print(f"Кадров в плане: {len(plan['frames'])}")
    for frame in plan["frames"]:
        print(f"  - {frame['name']} ({frame['source']})")


if __name__ == "__main__":
    main()
