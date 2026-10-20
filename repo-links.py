"""Point "Edit this page" and "Report an issue" at the repository that owns
each page.

Quarto builds both links from website.repo-url, so every page links into
wxylib/docs, including pages that live elsewhere: design/ is a checkout of
wxylib/design, and reference/cli.qmd is generated from wxylib/core. Quarto
runs this after every render (post-render in _quarto.yml) and rewrites the
two links on those pages. Pages in this repository are left alone.

Run it by hand with `python3 repo-links.py` after `quarto render`.
"""

import pathlib

SITE = pathlib.Path(__file__).parent / "_site"
DOCS = "https://github.com/wxylib/docs"


def rewrite(page, edit_from, edit_to, repo):
    text = page.read_text(encoding="utf-8")
    new = text.replace(f"{DOCS}/edit/main/{edit_from}", edit_to)
    new = new.replace(f"{DOCS}/issues/new", f"{repo}/issues/new")
    if new != text:
        page.write_text(new, encoding="utf-8")
        return 1
    return 0


def main():
    design = "https://github.com/wxylib/design"
    n = 0
    # design/<path>.html came from <path>.md in wxylib/design.
    for page in (SITE / "design").rglob("*.html"):
        n += rewrite(page, "design/", f"{design}/edit/main/", design)
    # The command reference is generated from the CLI's doc comments.
    core = "https://github.com/wxylib/core"
    cli = SITE / "reference" / "cli.html"
    if cli.exists():
        n += rewrite(cli, "reference/cli.qmd",
                     f"{core}/edit/main/crates/wxy-cli/src/main.rs", core)
    print(f"repo-links: {n} page(s) now link to their own repository")


if __name__ == "__main__":
    main()
