# -*- coding: utf-8 -*-
"""
Проверка попарной уникальности текстов объявлений Авито.

Метрика: score = 0.35 * Jaccard(words) + 0.65 * Jaccard(bigrams)
Порог риска дубля: 40% (настраивается ниже).

Использование:
    py -3 05-similarity-checker.py

Перед запуском поменяйте только блок "НАСТРОЙКИ" под свой проект:
- LISTINGS_DIR — папка с готовыми объявлениями (.md)
- THRESHOLD    — порог в долях (0.40 = 40%)
- TEXT_START_MARKER — если в файле есть служебные блоки (категория/цена/характеристики),
                      укажите маркер, с которого начинается текст ОПИСАНИЯ для сравнения.
                      Если файл — это просто текст объявления целиком, оставьте None.

Зависимости: только стандартная библиотека (re, pathlib, itertools).
"""

import re
import sys
from pathlib import Path
from itertools import combinations

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

# ───────────────────────── НАСТРОЙКИ ─────────────────────────
LISTINGS_DIR = Path(__file__).parent.parent / "avito-listings"
THRESHOLD = 0.40
TEXT_START_MARKER = "## ОПИСАНИЕ"   # None — если сравнивать весь файл целиком
TEXT_END_MARKER = "## ХАРАКТЕРИСТИКИ"
# ──────────────────────────────────────────────────────────────


def extract_text(raw: str) -> str:
    """Вырезает блок описания между маркерами (если заданы), иначе — весь текст."""
    text = raw
    if TEXT_START_MARKER:
        idx = text.find(TEXT_START_MARKER)
        if idx != -1:
            text = text[idx + len(TEXT_START_MARKER):]
    if TEXT_END_MARKER:
        idx = text.find(TEXT_END_MARKER)
        if idx != -1:
            text = text[:idx]
    return text


def tokenize(text: str) -> list[str]:
    text = text.lower()
    text = re.sub(r"[^a-zа-яё0-9\s]", " ", text)
    return [w for w in text.split() if len(w) > 2]


def bigrams(words: list[str]) -> set[tuple[str, str]]:
    return set(zip(words, words[1:]))


def jaccard(a: set, b: set) -> float:
    if not a and not b:
        return 0.0
    return len(a & b) / len(a | b)


def similarity(text_a: str, text_b: str) -> float:
    words_a, words_b = tokenize(text_a), tokenize(text_b)
    score_words = jaccard(set(words_a), set(words_b))
    score_bigrams = jaccard(bigrams(words_a), bigrams(words_b))
    return 0.35 * score_words + 0.65 * score_bigrams


def main():
    files = sorted(LISTINGS_DIR.glob("*.md"))
    if len(files) < 2:
        print(f"Найдено {len(files)} файлов в {LISTINGS_DIR} — нечего сравнивать.")
        return

    texts = {f.name: extract_text(f.read_text(encoding="utf-8")) for f in files}
    names = list(texts.keys())

    results = []
    for name_a, name_b in combinations(names, 2):
        score = similarity(texts[name_a], texts[name_b])
        results.append((score, name_a, name_b))

    results.sort(reverse=True)

    print(f"Сравнено файлов: {len(names)}  |  пар: {len(results)}  |  порог риска: {THRESHOLD:.0%}\n")

    risky = [r for r in results if r[0] >= THRESHOLD]
    if risky:
        print(f"⚠ Пары выше порога ({len(risky)}):")
        for score, a, b in risky:
            print(f"  {score:.1%}   {a}  ×  {b}")
    else:
        print("✓ Пар выше порога не найдено — почти-дублей нет.")

    print("\nТоп-10 ближайших пар (для контроля):")
    for score, a, b in results[:10]:
        print(f"  {score:.1%}   {a}  ×  {b}")

    print(f"\nМаксимальное пересечение: {results[0][0]:.1%} ({results[0][1]} × {results[0][2]})")


if __name__ == "__main__":
    main()
