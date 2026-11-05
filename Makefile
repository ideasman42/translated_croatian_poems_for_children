# Build poem PDFs into ./build/ via _misc/rst_to_sphinx.py.
# Each PDF shows the original and the literal translation, side by side.
# `make` builds all, `make <poem>` builds one, `make book` builds every poem
# into one PDF, `make check_book` checks the book lists every poem.

# The book lists every poem, by category, in reading order: add a poem there.
BOOK_FILE := book.rst
BOOK := hrvatske_pjesme

# Each poem's directory, from the book's list items (lines starting with "- ").
POEMS := $(shell sed -n 's/^- //p' $(BOOK_FILE))

# The check is first so a problem with the list is reported before any poem builds.
all: check_book $(POEMS) book
$(POEMS): %: build/%.pdf
book: build/$(BOOK).pdf

$(POEMS:%=build/%.pdf) build/$(BOOK).pdf: build/%.pdf: build/%.rst _misc/rst_to_sphinx.py
	python3 _misc/rst_to_sphinx.py $< --output $@

# The layout is defined in `poems_to_rst.py`, so changing it rebuilds the poems.
$(POEMS:%=build/%.rst): build/%.rst: %/original_hr.rst %/translated_en_gb_literal.rst %/readme.rst _misc/poems_to_rst.py | build
	python3 _misc/poems_to_rst.py --poem $* --output $@

# The book is checked before it's built: `check_book` is phony so it runs every time,
# as a new poem directory needs listing even when nothing listed has changed.
# Order-only, so passing the check doesn't rebuild the book. The poems' files are
# matched with `wildcard`, so a missing poem is reported by the check, not by make.
build/$(BOOK).rst: $(BOOK_FILE) $(wildcard $(foreach p,$(POEMS),$(p)/original_hr.rst $(p)/translated_en_gb_literal.rst $(p)/readme.rst)) _misc/poems_to_rst.py | build check_book
	python3 _misc/poems_to_rst.py --book $(BOOK_FILE) --output $@

.INTERMEDIATE: $(POEMS:%=build/%.rst) build/$(BOOK).rst

build:
	mkdir -p $@

check_book:
	python3 _misc/poems_to_rst.py --check-book $(BOOK_FILE)

clean:
	rm -rf build

check_all: check_mypy check_ruff check_pylint

check_mypy:
	mypy --strict _misc/rst_to_sphinx.py _misc/poems_to_rst.py

check_ruff:
	ruff check _misc/rst_to_sphinx.py _misc/poems_to_rst.py

check_pylint:
	pylint --disable=C0209,R0913,R0917 _misc/rst_to_sphinx.py _misc/poems_to_rst.py

.PHONY: all book check_book clean check_all check_mypy check_ruff check_pylint $(POEMS)
