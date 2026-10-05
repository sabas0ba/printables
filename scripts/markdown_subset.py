"""Render the Markdown subset used by the design notes to HTML.

Supported blocks: ATX headings, paragraphs, unordered (`- `) and ordered (`1. `)
lists without nesting, pipe tables with alignment, and fenced code blocks.
Supported inline syntax: code spans, `**strong**`, links, images and
`<https://...>` autolinks. Other block syntax raises MarkdownError, so that
an unsupported construct fails the build instead of rendering incorrectly.
"""

from collections.abc import Callable
from html import escape
import re


class MarkdownError(Exception):
    pass


Rewrite = Callable[[str], str]

# A source line break between two CJK characters is not a word boundary;
# browsers would otherwise render it as a space inside Japanese text.
CJK = "\u3000-\u30ff\u3400-\u4dbf\u4e00-\u9fff\uf900-\ufaff\uff00-\uffef"
CJK_LINE_BREAK = re.compile(f"(?<=[{CJK}])\n(?=[{CJK}])")

HEADING = re.compile(r"^(#{1,6})\s+(.*?)\s*#*\s*$")
FENCE = re.compile(r"^```\s*([\w+-]*)\s*$")
BULLET = re.compile(r"^- (.*)$")
ORDERED = re.compile(r"^(\d+)\. (.*)$")
CONTINUATION = re.compile(r"^ {2,}\S")
TABLE_ROW = re.compile(r"^\|.*\|\s*$")
TABLE_DELIMITER = re.compile(r"^\|(\s*:?-+:?\s*\|)+\s*$")
UNSUPPORTED = [
    (re.compile(r"^ {0,3}>"), "block quote"),
    (re.compile(r"^ {0,3}[*+] "), "list marker other than '-'"),
    (re.compile(r"^ {4,}"), "indented code block or nested content"),
    (re.compile(r"^ {0,3}(?:-{3,}|\*{3,}|_{3,})\s*$"), "thematic break"),
    (re.compile(r"^ {0,3}(?:=+|-+)\s*$"), "setext heading"),
    (re.compile(r"^ {0,3}<(?!https?://)"), "raw HTML block"),
    (re.compile(r"^ {1,3}\S"), "unexpected indentation"),
]

INLINE = re.compile(
    r"(?P<code>`(?P<code_text>[^`]+)`)"
    r"|(?P<image>!\[(?P<alt>[^\]]*)\]\((?P<src>[^)\s]+)\))"
    r"|(?P<link>\[(?P<label>(?:[^\]`]|`[^`]*`)+)\]\((?P<href>[^)\s]+)\))"
    r"|(?P<autolink><(?P<url>https?://[^>\s]+)>)"
    r"|(?P<strong>\*\*(?P<strong_text>.+?)\*\*)",
    re.DOTALL,
)


def join_lines(lines: list[str]) -> str:
    return CJK_LINE_BREAK.sub("", "\n".join(line.strip() for line in lines))


def render_inline(text: str, rewrite: Rewrite) -> str:
    out, position = [], 0
    for match in INLINE.finditer(text):
        out.append(escape(text[position:match.start()], quote=False))
        position = match.end()
        if match["code"]:
            out.append(f"<code>{escape(match['code_text'], quote=False)}</code>")
        elif match["image"]:
            out.append(f'<img alt="{escape(match["alt"])}" src="{escape(rewrite(match["src"]))}" '
                       'loading="lazy">')
        elif match["link"]:
            label = render_inline(match["label"], rewrite)
            out.append(f'<a href="{escape(rewrite(match["href"]))}">{label}</a>')
        elif match["autolink"]:
            url = match["url"]
            out.append(f'<a href="{escape(url)}">{escape(url, quote=False)}</a>')
        else:
            out.append(f"<strong>{render_inline(match['strong_text'], rewrite)}</strong>")
    out.append(escape(text[position:], quote=False))
    return "".join(out)


def split_row(line: str) -> list[str]:
    return [cell.strip() for cell in line.strip()[1:-1].split("|")]


class Renderer:
    def __init__(self, text: str, rewrite: Rewrite, drop_title: bool, name: str):
        self.lines = text.splitlines()
        self.rewrite = rewrite
        self.drop_title = drop_title
        self.name = name
        self.index = 0
        self.out: list[str] = []

    def error(self, message: str) -> MarkdownError:
        return MarkdownError(f"{self.name}:{self.index + 1}: {message}")

    def inline(self, text: str) -> str:
        return render_inline(text, self.rewrite)

    def render(self) -> str:
        while self.index < len(self.lines):
            line = self.lines[self.index]
            if not line.strip():
                self.index += 1
            elif FENCE.match(line):
                self.fenced_code()
            elif HEADING.match(line):
                self.heading()
            elif TABLE_ROW.match(line):
                self.table()
            elif BULLET.match(line) or ORDERED.match(line):
                self.list()
            else:
                self.paragraph()
        return "\n".join(self.out) + "\n"

    def check_supported(self, line: str) -> None:
        for pattern, description in UNSUPPORTED:
            if pattern.match(line):
                raise self.error(f"unsupported Markdown: {description}")

    def starts_block(self, line: str) -> bool:
        return bool(not line.strip() or FENCE.match(line) or HEADING.match(line)
                    or TABLE_ROW.match(line) or BULLET.match(line) or ORDERED.match(line))

    def heading(self) -> None:
        match = HEADING.match(self.lines[self.index])
        assert match is not None
        level = len(match[1])
        self.index += 1
        if level == 1 and self.drop_title and not self.out:
            return
        self.out.append(f"<h{level}>{self.inline(match[2])}</h{level}>")

    def fenced_code(self) -> None:
        match = FENCE.match(self.lines[self.index])
        assert match is not None
        start = self.index
        self.index += 1
        body = []
        while self.index < len(self.lines) and self.lines[self.index].strip() != "```":
            body.append(self.lines[self.index])
            self.index += 1
        if self.index == len(self.lines):
            self.index = start
            raise self.error("unterminated code block")
        self.index += 1
        language = f' class="language-{match[1]}"' if match[1] else ""
        code = escape("\n".join(body), quote=False)
        self.out.append(f"<pre><code{language}>{code}\n</code></pre>")

    def table(self) -> None:
        header = split_row(self.lines[self.index])
        self.index += 1
        if self.index == len(self.lines) or not TABLE_DELIMITER.match(self.lines[self.index]):
            raise self.error("table header without a delimiter row")
        aligns = []
        for cell in split_row(self.lines[self.index]):
            if cell.startswith(":") and cell.endswith(":"):
                aligns.append("center")
            elif cell.endswith(":"):
                aligns.append("right")
            else:
                aligns.append("left" if cell.startswith(":") else "")
        if len(aligns) != len(header):
            raise self.error("delimiter row does not match the header")
        self.index += 1

        def row(cells: list[str], tag: str) -> str:
            items = []
            for cell, align in zip(cells, aligns):
                style = f' style="text-align: {align};"' if align else ""
                items.append(f"<{tag}{style}>{self.inline(cell)}</{tag}>")
            return "<tr>" + "".join(items) + "</tr>"

        body = []
        while self.index < len(self.lines) and TABLE_ROW.match(self.lines[self.index]):
            cells = split_row(self.lines[self.index])
            if len(cells) != len(aligns):
                raise self.error("table row has a different number of cells")
            body.append(row(cells, "td"))
            self.index += 1
        self.out.append('<table class="table">\n<thead>\n' + row(header, "th")
                        + "\n</thead>\n<tbody>\n" + "\n".join(body) + "\n</tbody>\n</table>")

    def list(self) -> None:
        ordered = bool(ORDERED.match(self.lines[self.index]))
        marker = ORDERED if ordered else BULLET
        items: list[list[str]] = []
        start = 1
        while self.index < len(self.lines):
            line = self.lines[self.index]
            match = marker.match(line)
            if match:
                if ordered and not items:
                    start = int(match[1])
                items.append([match[2] if ordered else match[1]])
            elif items and CONTINUATION.match(line):
                if BULLET.match(line.strip()) or ORDERED.match(line.strip()):
                    raise self.error("unsupported Markdown: nested list")
                items[-1].append(line)
            elif not line.strip() or self.starts_block(line):
                break
            else:
                raise self.error("list continuation lines must be indented")
            self.index += 1
        tag = "ol" if ordered else "ul"
        attributes = f' start="{start}"' if ordered and start != 1 else ""
        body = "\n".join(f"<li>{self.inline(join_lines(item))}</li>" for item in items)
        self.out.append(f"<{tag}{attributes}>\n{body}\n</{tag}>")

    def paragraph(self) -> None:
        lines = []
        while self.index < len(self.lines) and not self.starts_block(self.lines[self.index]):
            self.check_supported(self.lines[self.index])
            lines.append(self.lines[self.index])
            self.index += 1
        self.out.append(f"<p>{self.inline(join_lines(lines))}</p>")


def render(text: str, rewrite: Rewrite, drop_title: bool = False, name: str = "<markdown>") -> str:
    """Render `text`; `rewrite` maps every link and image URL to its output URL."""
    return Renderer(text, rewrite, drop_title, name).render()
