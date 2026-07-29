#!/usr/bin/env python3
"""Export Markdown sections in docs/ to a single mobile-friendly HTML file."""

from __future__ import annotations

import argparse
import html
import re
from pathlib import Path

HEADING_RE = re.compile(r"^(#{1,6})\s+(.+?)\s*$")
ORDERED_LIST_RE = re.compile(r"^\s*\d+\.\s+(.+?)\s*$")
UNORDERED_LIST_RE = re.compile(r"^\s*[-*]\s+(.+?)\s*$")
TABLE_SEPARATOR_RE = re.compile(r"^\|\s*:?-{3,}:?\s*(\|\s*:?-{3,}:?\s*)+\|?$")
BLOCKQUOTE_RE = re.compile(r"^\s*>\s?(.*)\s*$")
LINK_RE = re.compile(r"\[([^\]]+)\]\(([^)]+)\)")
CODE_RE = re.compile(r"`([^`]+)`")
STRONG_RE = re.compile(r"\*\*(.+?)\*\*")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Export a mobile-friendly HTML document from the Markdown files in docs/."
    )
    parser.add_argument("input_dir", type=Path, help="Input directory containing Markdown files")
    parser.add_argument("output_file", type=Path, help="Output HTML file path")
    parser.add_argument(
        "--title",
        default="调脂活脉颗粒治疗高脂血症的中药新药研发与临床转化",
        help="HTML page title",
    )
    return parser.parse_args()


def slugify(text: str) -> str:
    slug = re.sub(r"[^\w\u4e00-\u9fff-]+", "-", text, flags=re.UNICODE)
    slug = re.sub(r"-{2,}", "-", slug).strip("-").lower()
    return slug or "section"


def render_inline(text: str) -> str:
    code_spans: list[str] = []

    def stash_code(match: re.Match[str]) -> str:
        code_spans.append(match.group(1))
        return f"__CODE_SPAN_{len(code_spans) - 1}__"

    escaped = html.escape(CODE_RE.sub(stash_code, text))
    for index, code in enumerate(code_spans):
        placeholder = f"__CODE_SPAN_{index}__"
        escaped = escaped.replace(placeholder, f"<code>{html.escape(code)}</code>")
    escaped = STRONG_RE.sub(r"<strong>\1</strong>", escaped)
    escaped = LINK_RE.sub(
        lambda m: f'<a href="{html.escape(m.group(2), quote=True)}">{m.group(1)}</a>',
        escaped,
    )
    return escaped


def parse_table_row(line: str) -> list[str]:
    content = line.strip().strip("|")
    return [cell.strip() for cell in content.split("|")]


def render_table(lines: list[str]) -> str:
    headers = parse_table_row(lines[0])
    body_rows = [parse_table_row(line) for line in lines[2:]]
    head_html = "".join(f"<th>{render_inline(cell)}</th>" for cell in headers)
    body_html = []
    for row in body_rows:
        cells = "".join(f"<td>{render_inline(cell)}</td>" for cell in row)
        body_html.append(f"<tr>{cells}</tr>")
    return (
        '<div class="table-wrap"><table>'
        f"<thead><tr>{head_html}</tr></thead>"
        f"<tbody>{''.join(body_html)}</tbody>"
        "</table></div>"
    )


def render_markdown(markdown_text: str, base_level: int = 2) -> str:
    lines = markdown_text.splitlines()
    blocks: list[str] = []
    paragraph: list[str] = []
    blockquote: list[str] = []
    list_items: list[str] = []
    list_kind: str | None = None
    in_comment_block = False
    index = 0

    def flush_paragraph() -> None:
        nonlocal paragraph
        if paragraph:
            text = " ".join(part.strip() for part in paragraph if part.strip())
            if text:
                blocks.append(f"<p>{render_inline(text)}</p>")
        paragraph = []

    def flush_list() -> None:
        nonlocal list_items, list_kind
        if list_items and list_kind:
            tag = "ol" if list_kind == "ordered" else "ul"
            items = "".join(f"<li>{render_inline(item)}</li>" for item in list_items)
            blocks.append(f"<{tag}>{items}</{tag}>")
        list_items = []
        list_kind = None

    def flush_blockquote() -> None:
        nonlocal blockquote
        if blockquote:
            text = " ".join(part.strip() for part in blockquote if part.strip())
            if text:
                blocks.append(f"<blockquote><p>{render_inline(text)}</p></blockquote>")
        blockquote = []

    while index < len(lines):
        line = lines[index].rstrip()
        stripped = line.strip()

        if in_comment_block:
            if "-->" in stripped:
                in_comment_block = False
            index += 1
            continue

        if not stripped:
            flush_paragraph()
            flush_list()
            flush_blockquote()
            index += 1
            continue

        if stripped.startswith("<!--"):
            flush_paragraph()
            flush_list()
            flush_blockquote()
            if "-->" not in stripped:
                in_comment_block = True
            index += 1
            continue

        heading_match = HEADING_RE.match(stripped)
        if heading_match:
            flush_paragraph()
            flush_list()
            flush_blockquote()
            level = min(base_level + len(heading_match.group(1)) - 1, 6)
            text = heading_match.group(2).strip()
            blocks.append(f"<h{level}>{render_inline(text)}</h{level}>")
            index += 1
            continue

        if stripped.startswith("|") and index + 1 < len(lines) and TABLE_SEPARATOR_RE.match(
            lines[index + 1].strip()
        ):
            flush_paragraph()
            flush_list()
            flush_blockquote()
            table_lines = [stripped, lines[index + 1].strip()]
            index += 2
            while index < len(lines) and lines[index].strip().startswith("|"):
                table_lines.append(lines[index].strip())
                index += 1
            blocks.append(render_table(table_lines))
            continue

        blockquote_match = BLOCKQUOTE_RE.match(stripped)
        if blockquote_match:
            flush_paragraph()
            flush_list()
            blockquote.append(blockquote_match.group(1))
            index += 1
            continue

        ordered_match = ORDERED_LIST_RE.match(stripped)
        if ordered_match:
            flush_paragraph()
            flush_blockquote()
            if list_kind not in (None, "ordered"):
                flush_list()
            list_kind = "ordered"
            list_items.append(ordered_match.group(1))
            index += 1
            continue

        unordered_match = UNORDERED_LIST_RE.match(stripped)
        if unordered_match:
            flush_paragraph()
            flush_blockquote()
            if list_kind not in (None, "unordered"):
                flush_list()
            list_kind = "unordered"
            list_items.append(unordered_match.group(1))
            index += 1
            continue

        if list_kind:
            flush_list()
        if blockquote:
            flush_blockquote()
        paragraph.append(stripped)
        index += 1

    flush_paragraph()
    flush_list()
    flush_blockquote()
    return "\n".join(blocks)


def strip_leading_title(text: str, title: str) -> str:
    lines = text.splitlines()
    for index, line in enumerate(lines):
        stripped = line.strip()
        if not stripped:
            continue
        if re.sub(r"^#\s+", "", stripped).strip() == title:
            remainder = lines[index + 1 :]
            if remainder and not remainder[0].strip():
                remainder = remainder[1:]
            return "\n".join(remainder)
        break
    return text


def collect_sections(input_dir: Path) -> list[tuple[str, str, str]]:
    sections: list[tuple[str, str, str]] = []
    for path in sorted(input_dir.glob("[0-9][0-9]-*.md")):
        text = path.read_text(encoding="utf-8")
        first_line = next((line.strip() for line in text.splitlines() if line.strip()), path.stem)
        title = re.sub(r"^#\s+", "", first_line).strip()
        section_id = slugify(path.stem)
        body = render_markdown(strip_leading_title(text, title), base_level=2)
        sections.append((section_id, title, body))
    if not sections:
        raise SystemExit(
            f"No Markdown sections matching [0-9][0-9]-*.md were found under {input_dir}."
        )
    return sections


def build_html(title: str, sections: list[tuple[str, str, str]]) -> str:
    toc_items = "\n".join(
        f'<li><a href="#{section_id}">{html.escape(section_title)}</a></li>'
        for section_id, section_title, _ in sections
    )
    section_html = "\n".join(
        (
            f'<section id="{section_id}" class="doc-section">'
            f"<h2>{html.escape(section_title)}</h2>"
            f"{body}"
            "</section>"
        )
        for section_id, section_title, body in sections
    )
    return f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
  <title>{html.escape(title)}</title>
  <style>
    :root {{
      color-scheme: light;
      --bg: #f7f8fa;
      --card: #ffffff;
      --text: #1f2328;
      --muted: #59636e;
      --line: #d0d7de;
      --accent: #0969da;
    }}
    * {{ box-sizing: border-box; }}
    body {{
      margin: 0;
      padding: 16px;
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", "PingFang SC",
        "Hiragino Sans GB", "Microsoft YaHei", sans-serif;
      line-height: 1.7;
      color: var(--text);
      background: var(--bg);
    }}
    main {{
      max-width: 960px;
      margin: 0 auto;
    }}
    .hero, .doc-section {{
      background: var(--card);
      border: 1px solid var(--line);
      border-radius: 14px;
      padding: 20px;
      margin-bottom: 16px;
      box-shadow: 0 1px 2px rgba(31, 35, 40, 0.04);
    }}
    h1, h2, h3, h4, h5, h6 {{
      line-height: 1.4;
      margin: 0 0 12px;
    }}
    h1 {{ font-size: 1.6rem; }}
    h2 {{ font-size: 1.3rem; padding-bottom: 8px; border-bottom: 1px solid var(--line); }}
    h3 {{ font-size: 1.15rem; margin-top: 20px; }}
    h4 {{ font-size: 1.02rem; margin-top: 16px; }}
    p, li {{ font-size: 0.98rem; }}
    .meta {{
      margin-top: 8px;
      color: var(--muted);
      font-size: 0.92rem;
    }}
    .toc {{
      padding-left: 1.2em;
      margin: 0;
    }}
    .toc li + li {{ margin-top: 6px; }}
    a {{ color: var(--accent); text-decoration: none; }}
    code {{
      padding: 0.1em 0.35em;
      border-radius: 6px;
      background: rgba(175, 184, 193, 0.2);
      font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
      font-size: 0.92em;
    }}
    ul, ol {{
      padding-left: 1.4em;
      margin: 10px 0;
    }}
    blockquote {{
      margin: 12px 0;
      padding: 0 0 0 12px;
      border-left: 4px solid var(--line);
      color: var(--muted);
    }}
    blockquote p {{ margin: 0; }}
    .table-wrap {{
      overflow-x: auto;
      margin: 12px 0;
      -webkit-overflow-scrolling: touch;
    }}
    table {{
      width: 100%;
      border-collapse: collapse;
      min-width: 640px;
      background: var(--card);
    }}
    th, td {{
      border: 1px solid var(--line);
      padding: 10px 12px;
      vertical-align: top;
      text-align: left;
      font-size: 0.94rem;
    }}
    th {{ background: #f6f8fa; }}
    @media (max-width: 640px) {{
      body {{ padding: 12px; }}
      .hero, .doc-section {{ padding: 16px; border-radius: 12px; }}
      h1 {{ font-size: 1.4rem; }}
      h2 {{ font-size: 1.18rem; }}
      table {{ min-width: 560px; }}
    }}
  </style>
</head>
<body>
  <main>
    <section class="hero">
      <h1>{html.escape(title)}</h1>
      <p>本页面由 Markdown 章节自动汇总生成，适合在手机浏览器或文件管理器中直接打开查看。</p>
      <p class="meta">目录</p>
      <ol class="toc">
        {toc_items}
      </ol>
    </section>
    {section_html}
  </main>
</body>
</html>
"""


def main() -> None:
    args = parse_args()
    sections = collect_sections(args.input_dir)
    html_text = build_html(args.title, sections)
    args.output_file.parent.mkdir(parents=True, exist_ok=True)
    args.output_file.write_text(html_text, encoding="utf-8")


if __name__ == "__main__":
    main()
