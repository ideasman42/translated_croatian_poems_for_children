#########################
Translated Croatian Poems
#########################

This repository contains literal English translations of Croatian children's poems.

Each poem is printed on a single A4 page, the Croatian and English side by side,
so the two can be read against each other line by line.


Building
========

The RST files may be compiled into PDF files.

Requirements
------------

- Sphinx
- LaTeX

Run::

  make

PDF files will be generated in the ``build/`` directory:
one for each poem, and ``hrvatske_pjesme.pdf`` with every poem.
Short poems share a page; a poem is never split across pages.

The book's poems, their categories and their order are listed in ``book.rst``.
