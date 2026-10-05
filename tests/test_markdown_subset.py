"""Unit tests for scripts/markdown_subset.py."""

from pathlib import Path
import sys
import textwrap
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from markdown_subset import MarkdownError, render, render_inline  # noqa: E402


def identity(url: str) -> str:
    return url


def md(text: str, **kwargs: bool) -> str:
    return render(textwrap.dedent(text), identity, **kwargs)


class InlineTest(unittest.TestCase):
    def test_text_is_escaped(self) -> None:
        self.assertEqual(render_inline("a < b & c", identity), "a &lt; b &amp; c")

    def test_code_span_is_literal(self) -> None:
        self.assertEqual(render_inline("`**x** <y>`", identity),
                         "<code>**x** &lt;y&gt;</code>")

    def test_strong_may_span_lines(self) -> None:
        self.assertEqual(render_inline("**50 mm\nfront**", identity),
                         "<strong>50 mm\nfront</strong>")

    def test_link_with_code_label(self) -> None:
        self.assertEqual(render_inline("[`a.stl`](a.stl)", lambda u: "x/" + u),
                         '<a href="x/a.stl"><code>a.stl</code></a>')

    def test_image(self) -> None:
        self.assertEqual(render_inline('![a "b"](p.png)', identity),
                         '<img alt="a &quot;b&quot;" src="p.png" loading="lazy">')

    def test_autolink(self) -> None:
        self.assertEqual(render_inline("<https://example.com/a>", identity),
                         '<a href="https://example.com/a">https://example.com/a</a>')


class BlockTest(unittest.TestCase):
    def test_headings_and_dropped_title(self) -> None:
        self.assertEqual(md("# T\n\n## S\n", drop_title=True), "<h2>S</h2>\n")
        self.assertEqual(md("# T\n"), "<h1>T</h1>\n")

    def test_paragraph_joins_cjk_lines(self) -> None:
        self.assertEqual(md("組み立て\nる。\nText\nmore\n"), "<p>組み立てる。\nText\nmore</p>\n")

    def test_lists_with_continuation_lines(self) -> None:
        html = md("""\
            - one
              two
            - three

            3. first
               second
            4. next
            """)
        self.assertEqual(html, "<ul>\n<li>one\ntwo</li>\n<li>three</li>\n</ul>\n"
                               '<ol start="3">\n<li>first\nsecond</li>\n<li>next</li>\n</ol>\n')

    def test_table_with_alignment(self) -> None:
        html = md("""\
            | a | b | c |
            | --- | ---: | :-: |
            | 1 | `2` | 3 |
            """)
        self.assertIn("<th>a</th>", html)
        self.assertIn('<td style="text-align: right;"><code>2</code></td>', html)
        self.assertIn('<td style="text-align: center;">3</td>', html)

    def test_fenced_code_keeps_text(self) -> None:
        self.assertEqual(md("```sh\na <b>\n日本\n語\n```\n"),
                         '<pre><code class="language-sh">a &lt;b&gt;\n日本\n語\n</code></pre>\n')

    def test_paragraph_ends_before_block(self) -> None:
        self.assertEqual(md("text\n- item\n"), "<p>text</p>\n<ul>\n<li>item</li>\n</ul>\n")


class UnsupportedTest(unittest.TestCase):
    def assert_error(self, text: str, message: str) -> None:
        with self.assertRaisesRegex(MarkdownError, message):
            render(text, identity)

    def test_block_quote(self) -> None:
        self.assert_error("> quote\n", "block quote")

    def test_other_list_markers(self) -> None:
        self.assert_error("* item\n", "list marker")

    def test_nested_list(self) -> None:
        self.assert_error("- a\n  - b\n", "nested list")

    def test_unindented_list_continuation(self) -> None:
        self.assert_error("- a\nb\n", "must be indented")

    def test_indented_code(self) -> None:
        self.assert_error("    code\n", "indented code")

    def test_raw_html(self) -> None:
        self.assert_error("<div>x</div>\n", "raw HTML")

    def test_thematic_break(self) -> None:
        self.assert_error("---\n", "thematic break")

    def test_unterminated_fence(self) -> None:
        self.assert_error("```\ncode\n", "unterminated")

    def test_table_cell_count(self) -> None:
        self.assert_error("| a | b |\n| --- | --- |\n| 1 |\n", "number of cells")

    def test_table_without_delimiter(self) -> None:
        self.assert_error("| a |\n| b |\n", "delimiter")


if __name__ == "__main__":
    unittest.main()
