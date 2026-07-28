#!/usr/bin/env python3
"""将旧版 Word .doc 文档提取为 Markdown。"""

from __future__ import annotations

import argparse
import re
import shutil
import subprocess
from pathlib import Path

SECTION_PATTERN = re.compile(r"^第([一二三四五六七八九十]+)部分\s+(.+)$")


def extract_text(input_path: Path, extractor: str | None) -> str:
    candidates = [extractor] if extractor else ["catdoc", "antiword"]
    for name in candidates:
        if not name:
            continue
        binary = shutil.which(name)
        if not binary:
            continue
        result = subprocess.run(
            [binary, str(input_path)],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="ignore",
            check=False,
        )
        if result.returncode == 0 and result.stdout.strip():
            return result.stdout
    raise SystemExit("未找到可用提取工具，请先安装 catdoc 或 antiword。")


def normalize(text: str) -> str:
    text = text.replace("\r\n", "\n").replace("\r", "\n").replace("\f", "\n\n")
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    lines = [line.strip() for line in text.splitlines()]
    return "\n".join(lines).strip() + "\n"


def split_sections(text: str) -> list[tuple[str, str]]:
    sections: list[tuple[str, list[str]]] = []
    current_title = "前置内容"
    current_lines: list[str] = []

    for raw_line in text.splitlines():
        line = raw_line.strip()
        match = SECTION_PATTERN.match(line)
        if match:
            sections.append((current_title, current_lines))
            current_title = f"第{match.group(1)}部分 {match.group(2)}"
            current_lines = []
            continue
        current_lines.append(raw_line)

    sections.append((current_title, current_lines))
    return [
        (title, "\n".join(lines).strip() + "\n")
        for title, lines in sections
        if "\n".join(lines).strip()
    ]


def safe_name(index: int, title: str) -> str:
    title = re.sub(r"[^0-9A-Za-z\u4e00-\u9fff]+", "-", title).strip("-")
    return f"{index:02d}-{title}.md"


def write_markdown(sections: list[tuple[str, str]], output_dir: Path) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    readme_lines = ["# 提取结果", "", "以下文件由脚本自动生成，建议人工复核。", ""]

    for index, (title, content) in enumerate(sections, start=1):
        filename = safe_name(index, title)
        path = output_dir / filename
        path.write_text(f"# {title}\n\n{content}", encoding="utf-8")
        readme_lines.append(f"- [{title}]({filename})")

    (output_dir / "README.md").write_text("\n".join(readme_lines) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="提取旧版 Word .doc 文档并转为 Markdown")
    parser.add_argument("input", type=Path, help="输入 .doc 文件路径")
    parser.add_argument("output", type=Path, help="输出目录")
    parser.add_argument("--extractor", choices=["catdoc", "antiword"], help="指定提取工具")
    args = parser.parse_args()

    text = extract_text(args.input, args.extractor)
    normalized = normalize(text)
    sections = split_sections(normalized)
    write_markdown(sections, args.output)


if __name__ == "__main__":
    main()
