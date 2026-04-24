from __future__ import annotations

import argparse
import csv
import html
import re
from pathlib import Path


TERM_BLOCK_PATTERN = re.compile(
    r'<div aria-label="Term" class="SetPageTermsList-term">(.*?)(?=<div aria-label="Term" class="SetPageTermsList-term">|</section>|</body>|</html>)',
    re.S,
)
TERM_TEXT_PATTERN = re.compile(r'<span class="TermText notranslate lang-en">(.*?)</span>', re.S)
DEFAULT_INPUT_PATH = Path(__file__).with_name("quizlet_input.txt")
DEFAULT_OUTPUT_PATH = Path(__file__).with_name("output").joinpath("quizlet_scraped.csv")


def _read_input_text(source: str) -> str:
    input_path = Path(source)
    if not input_path.is_absolute():
        input_path = Path(__file__).with_name(source)

    if not input_path.exists():
        raise FileNotFoundError(f"Input file not found: {input_path}")

    input_text = input_path.read_text(encoding="utf-8", errors="replace")
    if not input_text.strip():
        raise ValueError(f"Input file is empty: {input_path}")

    return input_text


def _order_term_pair(first_text: str, second_text: str) -> tuple[str, str]:
    first_text = re.sub(r"\s+", " ", first_text).strip()
    second_text = re.sub(r"\s+", " ", second_text).strip()

    if not first_text:
        return second_text, first_text
    if not second_text:
        return first_text, second_text
    if len(second_text) < len(first_text):
        return second_text, first_text

    return first_text, second_text


def extract_quizlet_rows(html_text: str):
    rows = []
    for block in TERM_BLOCK_PATTERN.findall(html_text):
        texts = [html.unescape(match).strip() for match in TERM_TEXT_PATTERN.findall(block)]
        if len(texts) < 2:
            continue

        word, definition = _order_term_pair(texts[0], texts[1])
        if not word and not definition:
            continue

        rows.append({"Word": word, "Definition": definition})

    return rows


def write_csv(rows, output_path: str):
    output_file = Path(output_path)
    output_file.parent.mkdir(parents=True, exist_ok=True)
    with output_file.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=["Word", "Definition"])
        writer.writeheader()
        writer.writerows(rows)


def main():
    parser = argparse.ArgumentParser(description="Parse Quizlet set HTML into a Word/Definition CSV.")
    parser.add_argument("source", nargs="?", default=str(DEFAULT_INPUT_PATH), help="Quizlet HTML/TXT file path")
    parser.add_argument("-o", "--output", default=str(DEFAULT_OUTPUT_PATH), help="Output CSV path")
    args = parser.parse_args()

    html_text = _read_input_text(args.source)
    rows = extract_quizlet_rows(html_text)
    write_csv(rows, args.output)
    print(f"Wrote {len(rows)} rows to {args.output}")


if __name__ == "__main__":
    main()