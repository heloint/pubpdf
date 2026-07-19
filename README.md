pubpdf
======

**MIT-licensed Python library for extracting structured data from scientific and academic PDFs. No AGPL, no commercial license, no gotchas.**

[![PyPI version](https://img.shields.io/pypi/v/pubpdf.svg)](https://pypi.org/project/pubpdf/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python versions](https://img.shields.io/pypi/pyversions/pubpdf.svg)](https://pypi.org/project/pubpdf/)

> **Status:** early development. APIs may change. Follow along or contribute — see [Roadmap](#roadmap) below.

---

## Why pubpdf?

Most high-quality PDF parsers today are either:

- **AGPL-licensed** (e.g. PyMuPDF/fitz) — great performance, but AGPL means if you distribute or run it as a service, you may be required to open-source your entire application unless you buy a commercial license.
- **Generic-purpose** (e.g. pdfplumber, pdfminer.six) — permissively licensed, but not tuned for the specific mess that scientific papers throw at you: multi-column layouts, dense data tables, sequence blocks, citation-heavy text, and figures with captions that need to stay attached to the right context.

**pubpdf** is built specifically for scientific and academic PDFs. bioRxiv/PubMed/arXiv-style layouts, biomedical and data-heavy tables, and reference-dense text, and ships under a fully permissive **MIT license**. Use it in commercial products, SaaS platforms, or research pipelines with zero copyleft obligations.

## Features

- **Layout-aware text extraction**: Correctly reconstructs reading order across multi-column academic layouts.
- **Structured table extraction**: Tuned for dense, irregular scientific tables (not just bordered grids).
- **Domain-aware parsing**: Handles biomedical nomenclature, gene/sequence blocks, and numerical data without mangling them.
- **Citation & reference handling**: Keeps in-text citations and reference lists structured, not flattened into noise.
- **RAG/LLM-ready output**: Clean structured JSON or Markdown, ready to feed into embeddings or downstream pipelines.
- **100% MIT licensed**: No AGPL, no "contact sales," no surprises.

## Installation

```bash
pip install pubpdf
```

> Requires Python 3.9+.

## Quickstart

```python
from pubpdf import parse

result = parse("paper.pdf")

print(result.text)        # clean, reading-order-correct text
print(result.tables)       # structured tables as list of dicts / dataframes
print(result.references)   # parsed reference list
print(result.to_markdown())  # RAG/LLM-ready markdown output
```

## Example: extracting a table

```python
from pubpdf import parse

doc = parse("study.pdf")

for i, table in enumerate(doc.tables):
    print(f"Table {i + 1}:")
    print(table.to_dataframe())  # pandas DataFrame, if pandas is installed
```

## Use cases

- Feeding scientific literature into RAG pipelines and LLM-based research assistants
- Bulk-extracting tables/data from supplementary materials at scale
- Building literature-review or systematic-review tooling
- Any commercial or SaaS product that can't use AGPL-licensed dependencies

## Roadmap

- [ ] Core layout-aware text extraction (pdfminer.six-based)
- [ ] Multi-column reading-order reconstruction
- [ ] Scientific table detection & structuring
- [ ] Reference/citation parsing
- [ ] Markdown/JSON export for RAG pipelines
- [ ] Benchmark suite against pdfplumber, PyMuPDF, Docling on a scientific-PDF test corpus
- [ ] OCR fallback for scanned papers
- [ ] CLI tool

See [open issues](https://github.com/heloint/pubpdf/issues) for details and progress.

## Contributing

Contributions are welcome! Whether it's a bug report, a failing test PDF, a feature idea, or a pull request — please open an issue first for anything non-trivial so we can discuss the approach.

```bash
git clone https://github.com/heloint/pubpdf.git
cd pubpdf
pip install -e ".[dev]"
pytest
```

