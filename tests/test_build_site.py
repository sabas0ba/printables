"""Unit tests for scripts/build_site.py and scripts/vendor_three.py."""

from pathlib import Path
import sys
import tempfile
import textwrap
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import build_site  # noqa: E402
import vendor_three  # noqa: E402

DESIGN_TOML = """\
title = "Example"
summary = "Example design."
prototype = true
added = 2026-01-02
lang = "ja"
source = "CadQuery"
cover = "preview.png"
pages = ["docs/notes.md"]

[[parts]]
file = "part.stl"
quantity = 2
description = "Part"

[[parts]]
file = "reference.stl"
quantity = 0
description = "Reference only"
"""


class FixtureRepository(unittest.TestCase):
    """A temporary repository with one design, kept under the ignored .work/ directory."""

    def setUp(self) -> None:
        (ROOT / ".work").mkdir(exist_ok=True)
        self.tmp = tempfile.TemporaryDirectory(dir=ROOT / ".work")
        self.root = Path(self.tmp.name)
        design = self.root / "example"
        (design / "docs").mkdir(parents=True)
        (self.root / "README.md").write_text("# root\n", encoding="utf-8")
        (self.root / "LICENSE.md").write_text("license\n", encoding="utf-8")
        (design / "design.toml").write_text(DESIGN_TOML, encoding="utf-8")
        (design / "README.md").write_text("# Example\n", encoding="utf-8")
        (design / "docs/notes.md").write_text("# Notes\n", encoding="utf-8")
        (design / "generate.py").write_text("", encoding="utf-8")
        for name in ("preview.png", "part.stl", "reference.stl"):
            (design / name).write_bytes(b"x")

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def context(self, doc: str = "README.md") -> build_site.LinkContext:
        return build_site.LinkContext(self.root, "example", doc,
                                      frozenset({"docs/notes.md"}), set())


class LinkContextTest(FixtureRepository):
    def test_published_file_keeps_relative_path(self) -> None:
        context = self.context()
        self.assertEqual(context.rewrite("preview.png"), "preview.png")
        self.assertIn("preview.png", context.published)

    def test_rendered_page_links_to_html(self) -> None:
        self.assertEqual(self.context().rewrite("docs/notes.md#a"), "docs/notes.html#a")
        self.assertEqual(self.context("docs/notes.md").rewrite("../README.md"), "../index.html")

    def test_repository_readme_links_to_site_index(self) -> None:
        self.assertEqual(self.context().rewrite("../README.md"), "../index.html")
        self.assertEqual(self.context("docs/notes.md").rewrite("../../README.md"),
                         "../../index.html")

    def test_other_files_link_to_github(self) -> None:
        base = build_site.REPOSITORY_URL
        self.assertEqual(self.context().rewrite("generate.py"),
                         f"{base}/blob/main/example/generate.py")
        self.assertEqual(self.context().rewrite("docs/"), f"{base}/tree/main/example/docs")
        self.assertEqual(self.context().rewrite("../LICENSE.md"), f"{base}/blob/main/LICENSE.md")

    def test_absolute_and_fragment_urls_are_unchanged(self) -> None:
        for url in ("https://example.com/a.md", "#section", "/root", "mailto:a@example.com"):
            self.assertEqual(self.context().rewrite(url), url)

    def test_broken_link_is_an_error(self) -> None:
        with self.assertRaises(build_site.SiteError):
            self.context().rewrite("missing.png")

    def test_link_outside_repository_is_an_error(self) -> None:
        with self.assertRaises(build_site.SiteError):
            self.context().rewrite("../../outside.md")


class RenderTest(FixtureRepository):
    def test_readme_title_is_dropped_and_links_rewritten(self) -> None:
        text = "# Title\n\n![preview](preview.png)\n\n[source](generate.py)\n"
        html = build_site.render_markdown(text, self.context(), drop_title=True)
        self.assertNotIn("<h1>", html)
        self.assertIn('src="preview.png"', html)
        self.assertIn('loading="lazy"', html)
        self.assertIn(f'href="{build_site.REPOSITORY_URL}/blob/main/example/generate.py"', html)

    def test_cjk_line_breaks_are_joined(self) -> None:
        text = textwrap.dedent("""\
            印刷した抜け止めピンで組み立て
            る。English line
            continues.
            """)
        html = build_site.render_markdown(text, self.context(), drop_title=False)
        self.assertIn("組み立てる。", html)
        self.assertIn("English line\ncontinues.", html)

    def test_code_blocks_keep_line_breaks(self) -> None:
        text = "```sh\n日本\n語\n```\n"
        html = build_site.render_markdown(text, self.context(), drop_title=False)
        self.assertIn("日本\n語", html)


class DesignTest(FixtureRepository):
    def test_load_design(self) -> None:
        design = build_site.load_design(self.root / "example")
        self.assertEqual(design.slug, "example")
        self.assertEqual(design.printed_parts, 2)
        self.assertEqual(design.printed_files, 1)
        self.assertEqual(design.optional_files, 1)
        self.assertEqual(build_site.parts_summary(design),
                         "2 printed parts from 1 STL file, 1 optional or reference")

    def test_missing_part_file_is_an_error(self) -> None:
        (self.root / "example/part.stl").unlink()
        with self.assertRaises(build_site.SiteError):
            build_site.load_design(self.root / "example")

    def test_readme_table(self) -> None:
        design = build_site.load_design(self.root / "example")
        table = build_site.readme_table([design])
        self.assertIn("| [Example](example/README.md) | 1 STL (2 prints) + 1 optional or reference, CadQuery source "
                      "| Example design; prototype |", table)
        readme = f"before\n{build_site.README_START}\nold\n{build_site.README_END}\nafter\n"
        self.assertEqual(build_site.replace_readme_table(readme, table),
                         f"before\n{table}\nafter\n")

    def test_readme_without_markers_is_an_error(self) -> None:
        with self.assertRaises(build_site.SiteError):
            build_site.replace_readme_table("no markers", "table")

    def test_plural(self) -> None:
        self.assertEqual(build_site.plural(1, "print"), "1 print")
        self.assertEqual(build_site.plural(2, "print"), "2 prints")


class VendorCheckTest(FixtureRepository):
    def test_check_reports_mismatch_missing_and_extra_files(self) -> None:
        vendor_dir = self.root / "vendor"
        vendor_dir.mkdir()
        (vendor_dir / "a.js").write_bytes(b"a")
        (vendor_dir / "extra.js").write_bytes(b"x")
        manifest = vendor_three.Manifest("repo", "tag", "commit", "MIT", (
            vendor_three.VendoredFile("a.js", "a.js", vendor_three.sha256(b"b")),
            vendor_three.VendoredFile("b.js", "b.js", vendor_three.sha256(b"b"))))
        problems = vendor_three.check(manifest, vendor_dir, self.root)
        self.assertEqual(problems, ["hash mismatch: vendor/a.js", "missing: vendor/b.js",
                                    "not in manifest: vendor/extra.js"])

    def test_committed_vendor_files_match_manifest(self) -> None:
        self.assertEqual(vendor_three.check(vendor_three.load_manifest()), [])


if __name__ == "__main__":
    unittest.main()
