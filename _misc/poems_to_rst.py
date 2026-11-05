#!/usr/bin/env python3
"""
Join poems into one reStructuredText document, for building with ``rst_to_sphinx.py``.

Each poem is a directory holding the original and its literal translation, which are
placed side by side in two columns. A single poem is titled after both of its own
titles (e.g. "Moja mama / My Mother").

Above the columns, the poem is headed by both titles, its author and date
(e.g. "Moja mama / My Mother – by Enes Kišević, 1980"), the author and date taken from the
``:Written by:`` and ``:Date:`` fields of the poem's ``readme.rst``.

A book of poems is described by its own RST file, listing the poems in order under
category headings::

    ######################################################
    Hrvatske pjesme za djecu / Croatian Poems for Children
    ######################################################

    Mama / Mother
    =============

    - moja_mama
    - mama

The book opens with its title, split at " / " into a line each
(the original then the translation), then its contents: the categories and poems
with their pages. Each category is given a heading, and poems share a page where
they fit.

``--check-book`` validates the book's list against the poem directories beside it,
so a poem is never left out (or listed twice) by mistake.
"""

__all__ = ("main",)

import argparse
import re
import sys

from pathlib import Path

# The two halves of a poem, left to right.
ORIGINAL_FILENAME = "original_hr.rst"
TRANSLATION_FILENAME = "translated_en_gb_literal.rst"
# The poem's notes, holding its author and date as RST fields.
README_FILENAME = "readme.rst"
_README_FIELD_AUTHOR = "Written by"
_README_FIELD_DATE = "Date"
# The files every poem directory holds.
_POEM_FILENAMES = (ORIGINAL_FILENAME, TRANSLATION_FILENAME, README_FILENAME)

# An RST field on a line of its own, e.g. ":Written by: Enes Kišević".
_RST_FIELD = re.compile(r"^:([^:\n]+):[ \t]+(.+)$", re.MULTILINE)

# The body font, a fontconfig family name, passed to `rst_to_sphinx.py` as its
# `my-pdf:font` setting (which implies the xelatex engine).
#
# NOTE(@ideasman42): Gentium Plus is used as it draws the Croatian diacritics well,
# the caron on c/s/z stays distinct from the acute on c at small sizes and the bar on
# d is clear, which matters for children still learning to read them.
# The TeX Gyre fonts bundled with TeX would avoid a system font, however fontconfig
# doesn't see them so they can't be selected by name, so use a system font.
FONT = "Gentium Plus"

# The body font size in points, passed to `rst_to_sphinx.py` as its `my-pdf:font-size`
# setting. Headings are sized relative to it, so this scales all text.
FONT_SIZE = 10.0

# Adornment characters a title over-line/under-line may be drawn with.
_TITLE_ADORNMENT = frozenset("=-`:'\"~^_*+#<>.")

# NOTE: the columns are raw LaTeX `minipage` boxes wrapped around each file.
# An RST `list-table` could do the same, however it would mean stripping each file's
# title and indenting its lines into a table cell. Lines only stay level while none
# wrap within its column and a `minipage` can't break across pages, neither is a
# problem for short poems. If longer poems are added the `paracol` package handles
# both, however it's an extra dependency, so leave as-is for now.
#
# Center each line: a line block sets `\raggedright`, which is swapped for
# `\centering` within the column only (the `minipage` keeps the change local).
_COLUMN_STYLE = r"\let\raggedright\centering"
_COLUMN_BEGIN = r"\noindent\begin{minipage}[t]{0.48\linewidth}" + _COLUMN_STYLE
_COLUMN_NEXT = r"\end{minipage}\hfill\begin{minipage}[t]{0.48\linewidth}" + _COLUMN_STYLE
_COLUMN_END = r"\end{minipage}"

# Between poems: `\filbreak` keeps a poem on one page when it fits, letting several
# short poems share a page, and starts a fresh page when the poem would otherwise span
# the page break. This matches the `\filbreak` `rst_to_sphinx.py` puts before each
# section, which doesn't apply here as the poem's headings are within its columns.
_POEM_SEPARATOR = r"\filbreak\bigskip"

# A poem's heading, its titles in bold then its author and date.
# `\nopagebreak` keeps it on the same page as the poem.
_POEM_HEADING_BEGIN = r"{\centering\textbf{"
_POEM_HEADING_BYLINE = "} – by "
_POEM_HEADING_END = r"\par}\nopagebreak\smallskip"

# A category heading, larger than the poem titles. Its `\filbreak` lets it share a page
# like a poem, and `\nopagebreak` keeps it on the same page as its first poem.
# NOTE: this is raw LaTeX rather than an RST section, as a section would place the
# poem titles a level down, changing how they look.
_CATEGORY_SEPARATOR = r"\filbreak\bigskip"
_CATEGORY_BEGIN = r"{\centering\large\bfseries "
_CATEGORY_END = r"\par}\nopagebreak\medskip"

# The book's title, at the top of the first page with the contents below it.
# The running head would repeat the title, so the page uses the `plain` style
# (page number only).
_BOOK_TITLE_BEGIN = r"\thispagestyle{plain}{\centering"
_BOOK_TITLE_LINE_BEGIN = r"{\LARGE\bfseries "
_BOOK_TITLE_LINE_END = r"\par}"
_BOOK_TITLE_SEPARATOR = r"\medskip"
_BOOK_TITLE_END = r"\par}\bigskip"

# The book's contents, below its title: each category with its poems and their pages.
# LaTeX writes the entries (`_CONTENTS_ENTRY`) and their pages on one run and lists
# them on the next. The poems then start on a fresh page.
#
# NOTE: `rst_to_sphinx.py` puts a `\filbreak` before each `\section`, which includes the
# contents heading. As the contents don't fit on what's left of the title's page, this
# moves them all to the next page, leaving the title alone on the first. So disable it
# here, letting the contents break across pages as any list would.
# The space above each category is halved, which keeps the contents to two pages.
# The entries link to their pages, in black rather than Sphinx's blue, as for print.
_CONTENTS = (
    r"{\let\filbreak\relax\colorlet{InnerLinkColor}{black}"
    r"\makeatletter\patchcmd{\l@section}{1.0em}{0.5em}{}{}\makeatother"
    r"\renewcommand{\contentsname}{Sadržaj / Contents}\setcounter{tocdepth}{2}"
    r"\tableofcontents}\clearpage"
)
# A contents entry, its level ("section" for a category, "subsection" for a poem)
# then its text. Each is placed just before its heading and after the `\filbreak`,
# so it's on the heading's page; `\nopagebreak` keeps the two together.
# `\phantomsection` gives the entry's link a target.
_CONTENTS_ENTRY = r"\phantomsection\addcontentsline{{toc}}{{{:s}}}{{{:s}}}\nopagebreak"

# A book's list item naming a poem directory.
_BOOK_ITEM_PREFIX = "- "

# Characters with a special meaning in LaTeX, and how to write them literally.
_LATEX_ESCAPE = {
    "\\": r"\textbackslash{}",
    "&": r"\&",
    "%": r"\%",
    "$": r"\$",
    "#": r"\#",
    "_": r"\_",
    "{": r"\{",
    "}": r"\}",
    "~": r"\textasciitilde{}",
    "^": r"\textasciicircum{}",
}


def _is_title_adornment(line: str) -> bool:
    """True if ``line`` is a title over-/under-line: a run of one adornment char."""
    line = line.rstrip()
    return len(line) >= 3 and len(set(line)) == 1 and set(line) <= _TITLE_ADORNMENT


def _document_title(rst_text: str) -> str:
    """Return the first line which isn't blank or a title over-/under-line."""
    for line in rst_text.splitlines():
        line = line.strip()
        if line and not _is_title_adornment(line):
            return line
    return ""


def _latex_escape(text: str) -> str:
    """Return ``text`` with LaTeX's special characters written literally."""
    return "".join(_LATEX_ESCAPE.get(c, c) for c in text)


def _raw_latex(latex: str) -> str:
    """Return ``latex`` as an RST raw block, padded by blank lines."""
    return "\n.. raw:: latex\n\n   {:s}\n\n".format(latex)


def _strip_title(rst_text: str) -> str:
    """Return ``rst_text`` without its leading title (and its over-/under-lines)."""
    lines = rst_text.lstrip("\n").splitlines(keepends=True)
    while lines and (_is_title_adornment(lines[0]) or not lines[0].strip()):
        lines.pop(0)
    # The title, then its under-line.
    if len(lines) >= 2 and _is_title_adornment(lines[1]):
        del lines[:2]
    return "".join(lines)


def _readme_fields(poem_dir: Path) -> dict[str, str]:
    """Return the RST fields of the poem's readme, e.g. ``{"Written by": "..."}``."""
    text = (poem_dir / README_FILENAME).read_text(encoding="utf-8")
    return {m.group(1): m.group(2).strip() for m in _RST_FIELD.finditer(text)}


def _poem_heading(poem_dir: Path) -> str:
    """Return the poem's heading, e.g. "Moja mama / My Mother – by Enes Kišević, 1980"."""
    fields = _readme_fields(poem_dir)
    byline = fields.get(_README_FIELD_AUTHOR, "Unknown")
    if date := fields.get(_README_FIELD_DATE):
        byline += ", " + date
    return _raw_latex(
        _POEM_HEADING_BEGIN + _latex_escape(_poem_title(poem_dir))
        + _POEM_HEADING_BYLINE + _latex_escape(byline) + _POEM_HEADING_END
    )


def _poem_body(poem_dir: Path) -> str:
    """Return the poem in ``poem_dir``: its heading, then its two files side by side."""
    original = _strip_title((poem_dir / ORIGINAL_FILENAME).read_text(encoding="utf-8"))
    translation = _strip_title((poem_dir / TRANSLATION_FILENAME).read_text(encoding="utf-8"))
    return (
        _poem_heading(poem_dir)
        + _raw_latex(_COLUMN_BEGIN) + original
        + _raw_latex(_COLUMN_NEXT) + translation
        + _raw_latex(_COLUMN_END)
    )


def _poem_title(poem_dir: Path) -> str:
    """Return the poem's original and translated titles, e.g. "Moja mama / My Mother"."""
    return " / ".join(
        _document_title((poem_dir / filename).read_text(encoding="utf-8"))
        for filename in (ORIGINAL_FILENAME, TRANSLATION_FILENAME)
    )


def _document_head(title: str) -> str:
    """Return the document title, as an RST heading, and the build settings."""
    # NOTE: each poem file has its own title, these are placed under the document
    # title, so both become section headings. Without it, the first title is taken as
    # the document title, showing only in the running head, while the second is shown
    # as a heading. The document title uses an under-line only, a different adornment
    # from the files' over-/under-lines, so the files are included as-is.
    #
    # The build settings are an RST comment, so they never render.
    return "{:s}\n{:s}\n\n..\n   my-pdf:font={:s}\n   my-pdf:font-size={:g}\n\n".format(
        title, "=" * len(title), FONT, FONT_SIZE,
    )


def poem_to_rst(poem_dir: Path) -> str:
    """Return the RST document for the poem in ``poem_dir``."""
    return _document_head(_poem_title(poem_dir)) + _poem_body(poem_dir)


def read_book(book_path: Path) -> tuple[str, list[tuple[str, list[Path]]]]:
    """Return the title and the categories of the book ``book_path`` describes.

    Each category is its title and its poem directories, in order.
    Poem directories are relative to the book file.
    """
    lines = book_path.read_text(encoding="utf-8").splitlines()
    categories: list[tuple[str, list[Path]]] = []
    for i, line in enumerate(lines):
        if line.startswith(_BOOK_ITEM_PREFIX):
            if not categories:
                raise ValueError(
                    "{!s}: poem listed before any category: {!r}".format(book_path, line),
                )
            categories[-1][1].append(book_path.parent / line[len(_BOOK_ITEM_PREFIX):].strip())
        elif (
                # A category is a title under-lined (only) with "=".
                line.strip() and i + 1 < len(lines) and
                _is_title_adornment(lines[i + 1]) and lines[i + 1].startswith("=") and
                not (i and _is_title_adornment(lines[i - 1]))
        ):
            categories.append((line.strip(), []))
    return _document_title("\n".join(lines)), categories


def check_book(book_path: Path) -> list[str]:
    """Return the problems with the book ``book_path`` describes, empty when there are none.

    Each listed poem must hold all its files and be listed once, each category must
    list a poem, and every poem directory beside the book must be listed.
    """
    _title, categories = read_book(book_path)
    problems = []
    listed: set[Path] = set()
    for category_title, poem_dirs in categories:
        if not poem_dirs:
            problems.append("category lists no poems: {:s}".format(category_title))
        for poem_dir in poem_dirs:
            if poem_dir in listed:
                problems.append("poem listed more than once: {:s}".format(poem_dir.name))
            listed.add(poem_dir)
            if not poem_dir.is_dir():
                problems.append("poem directory not found: {:s}".format(poem_dir.name))
                continue
            for filename in _POEM_FILENAMES:
                if not (poem_dir / filename).is_file():
                    problems.append("poem has no {:s}: {:s}".format(filename, poem_dir.name))

    # NOTE: a directory holding an original is taken to be a poem, so a new poem which
    # hasn't been added to the book is reported rather than silently left out.
    for poem_dir in sorted(path.parent for path in book_path.parent.glob("*/" + ORIGINAL_FILENAME)):
        if poem_dir not in listed:
            problems.append("poem not listed in {:s}: {:s}".format(book_path.name, poem_dir.name))
    return problems


def _book_title(title: str) -> str:
    """Return the book's title, a line for each of the title's " / " parts."""
    return _raw_latex(
        _BOOK_TITLE_BEGIN
        + _BOOK_TITLE_SEPARATOR.join(
            _BOOK_TITLE_LINE_BEGIN + _latex_escape(part.strip()) + _BOOK_TITLE_LINE_END
            for part in title.split(" / ")
        )
        + _BOOK_TITLE_END
    )


def book_to_rst(book_path: Path) -> str:
    """Return the RST document for the book ``book_path`` describes."""
    title, categories = read_book(book_path)
    parts = [_document_head(title), _book_title(title), _raw_latex(_CONTENTS)]
    for category_title, poem_dirs in categories:
        category_title = _latex_escape(category_title)
        parts.append(_raw_latex(
            _CATEGORY_SEPARATOR + _CONTENTS_ENTRY.format("section", category_title)
            + _CATEGORY_BEGIN + category_title + _CATEGORY_END
        ))
        for i, poem_dir in enumerate(poem_dirs):
            contents_entry = _CONTENTS_ENTRY.format(
                "subsection", _latex_escape(_poem_title(poem_dir)),
            )
            parts.append(_raw_latex((_POEM_SEPARATOR if i else "") + contents_entry))
            parts.append(_poem_body(poem_dir))
    return "".join(parts)


def main() -> int:
    """Parse command-line arguments and write the requested document."""
    parser = argparse.ArgumentParser(
        description="Join poems, side by side with their translations, into one RST document.",
    )
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--poem", type=Path, help="a poem directory")
    source.add_argument("--book", type=Path, help="an RST file listing a book's poems")
    source.add_argument(
        "--check-book", type=Path, metavar="BOOK",
        help="check the book's list against its poem directories, writing nothing",
    )
    parser.add_argument("-o", "--output", type=Path, help="the RST file to write")
    args = parser.parse_args()

    if args.check_book:
        try:
            problems = check_book(args.check_book)
        except (FileNotFoundError, ValueError) as ex:
            problems = [str(ex)]
        for problem in problems:
            sys.stderr.write("error: {!s}: {:s}\n".format(args.check_book, problem))
        return 1 if problems else 0

    if args.output is None:
        parser.error("--output is required with --poem or --book")

    try:
        rst_text = poem_to_rst(args.poem) if args.poem else book_to_rst(args.book)
    except (FileNotFoundError, ValueError) as ex:
        sys.stderr.write("error: {!s}\n".format(ex))
        return 1

    args.output.write_text(rst_text, encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main())
