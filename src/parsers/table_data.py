"""Extract tables from PDF pages into structured JSON.

Tables are located by their captions ("Table N. ...") and the ruling
lines pdfminer exposes as LTLine/LTRect. Each caption's table is bounded
below by the next caption on the same page (or the page bottom), which
keeps neighbouring tables that share the same rule x-span from bleeding
into each other.

Two table styles are supported:

- "ruled" (booktabs-style): a top rule, a header-separator rule, and a
  bottom rule, with no vertical lines. Columns are inferred from the x0
  positions of the header text.
- "grid": vertical rule lines split the table into columns (e.g. a
  bordered directory-tree table). Rows are inferred by treating each
  line of text in the leftmost column as the start of a new row, and
  merging subsequent lines into that row until the next leftmost-column
  line appears.
"""

import argparse
import json
import re
from pathlib import Path

from pdfminer.high_level import extract_pages
from pdfminer.layout import LTCurve, LTLine, LTRect, LTTextLine

CAPTION_RE = re.compile(r"^Table\s+(\d+)\.\s*(.+?)\s*$")
MIN_RULE_LENGTH = 15.0
RULE_THICKNESS_TOL = 0.5
CLUSTER_TOL = 3.0


def _iter_text_lines(item):
    if isinstance(item, LTTextLine):
        yield item
    elif hasattr(item, "__iter__"):
        for child in item:
            yield from _iter_text_lines(child)


def _iter_shapes(item):
    if isinstance(item, (LTLine, LTRect, LTCurve)):
        yield item
    elif hasattr(item, "__iter__"):
        for child in item:
            yield from _iter_shapes(child)


def _classify_rules(shapes):
    hlines, vlines = [], []
    for shape in shapes:
        x0, y0, x1, y1 = shape.bbox
        if abs(y1 - y0) < RULE_THICKNESS_TOL and (x1 - x0) > MIN_RULE_LENGTH:
            hlines.append((round((y0 + y1) / 2, 2), round(x0, 2), round(x1, 2)))
        elif abs(x1 - x0) < RULE_THICKNESS_TOL and (y1 - y0) > MIN_RULE_LENGTH:
            vlines.append((round((x0 + x1) / 2, 2), round(y0, 2), round(y1, 2)))
    return hlines, vlines


def _cluster(values, tol=CLUSTER_TOL):
    clusters = []
    for value in sorted(values):
        if clusters and value - clusters[-1][-1] <= tol:
            clusters[-1].append(value)
        else:
            clusters.append([value])
    return [sum(c) / len(c) for c in clusters]


def _band_lines(sorted_lines, tol=CLUSTER_TOL):
    band, band_y = [], None
    for line in sorted_lines:
        if band_y is None or abs(line.y0 - band_y) <= tol:
            band.append(line)
            band_y = line.y0 if band_y is None else band_y
        else:
            yield band_y, band
            band, band_y = [line], line.y0
    if band:
        yield band_y, band


def _find_captions(lines):
    captions = []
    for line in lines:
        match = CAPTION_RE.match(line.get_text().strip())
        if match:
            captions.append((line.y0, int(match.group(1)), match.group(2)))
    return sorted(captions, key=lambda c: -c[0])


def _window_for(captions, index):
    upper_bound = captions[index][0]
    lower_bound = captions[index + 1][0] if index + 1 < len(captions) else float("-inf")
    return lower_bound, upper_bound


def _column_index(x, col_starts, tol=CLUSTER_TOL):
    index = 0
    for i, start in enumerate(col_starts):
        if x + tol >= start:
            index = i
    return index


def _extract_ruled_table(lines, hlines):
    rule_ys = sorted({y for y, _, _ in hlines}, reverse=True)
    if len(rule_ys) < 2:
        return [], []
    top, bottom = rule_ys[0], rule_ys[-1]
    header_sep = rule_ys[1] if len(rule_ys) > 2 else bottom

    in_window = [l for l in lines if bottom - CLUSTER_TOL <= l.y0 <= top + CLUSTER_TOL]
    if not in_window:
        return [], []

    header_lines = sorted(
        (l for l in in_window if header_sep - CLUSTER_TOL <= l.y0), key=lambda l: l.x0
    )
    header_x0s = _cluster([l.x0 for l in header_lines])
    col_starts = sorted(header_x0s)

    headers = []
    for i, start in enumerate(col_starts):
        match = next((l for l in header_lines if abs(l.x0 - start) <= CLUSTER_TOL), None)
        headers.append(match.get_text().strip() if match else f"column_{i + 1}")

    body_lines = sorted(
        (l for l in in_window if l.y0 < header_sep - CLUSTER_TOL), key=lambda l: (-l.y0, l.x0)
    )

    rows = []
    for _, band in _band_lines(body_lines):
        filled = {}
        for line in band:
            col = _column_index(line.x0, col_starts)
            filled.setdefault(col, []).append(line.get_text().strip())

        if len(filled) >= 2 or not rows:
            row = {headers[i]: " ".join(texts) for i, texts in filled.items()}
            rows.append({h: row.get(h, "") for h in headers})
        else:
            ((col, texts),) = filled.items()
            key = headers[col]
            rows[-1][key] = f"{rows[-1][key]} {' '.join(texts)}".strip()

    return headers, rows


def _extract_grid_table(lines, vlines, lower_bound, upper_bound):
    col_centers = _cluster([v[0] for v in vlines])
    if len(col_centers) < 2:
        return [], []
    inner_bounds = col_centers[1:-1]
    num_cols = len(inner_bounds) + 1

    x_min, x_max = min(col_centers), max(col_centers)
    in_window = sorted(
        (
            l
            for l in lines
            if lower_bound < l.y0 < upper_bound and x_min - CLUSTER_TOL <= l.x0 <= x_max + CLUSTER_TOL
        ),
        key=lambda l: (-l.y0, l.x0),
    )

    headers = [f"column_{i + 1}" for i in range(num_cols)]
    rows = []
    for line in in_window:
        col = sum(1 for b in inner_bounds if line.x0 >= b - CLUSTER_TOL)
        text = line.get_text().strip()
        if not text:
            continue
        if col == 0:
            rows.append({h: "" for h in headers})
            rows[-1][headers[0]] = text
        elif rows:
            key = headers[col]
            rows[-1][key] = f"{rows[-1][key]}\n{text}".strip() if rows[-1][key] else text

    return headers, rows


def extract_tables(pdf_path):
    tables = []
    for page_index, page in enumerate(extract_pages(str(pdf_path))):
        lines = list(_iter_text_lines(page))
        shapes = list(_iter_shapes(page))
        hlines, vlines = _classify_rules(shapes)
        captions = _find_captions(lines)

        for index, (caption_y0, table_number, title) in enumerate(captions):
            lower_bound, upper_bound = _window_for(captions, index)

            window_vlines = [v for v in vlines if lower_bound < v[1] and v[2] < upper_bound]
            window_hlines = [h for h in hlines if lower_bound < h[0] < upper_bound]

            if window_vlines:
                headers, rows = _extract_grid_table(lines, window_vlines, lower_bound, upper_bound)
                style = "grid"
            elif window_hlines:
                headers, rows = _extract_ruled_table(lines, window_hlines)
                style = "ruled"
            else:
                continue

            if not rows:
                continue

            tables.append(
                {
                    "table_number": table_number,
                    "title": title,
                    "page": page_index + 1,
                    "style": style,
                    "headers": headers,
                    "rows": rows,
                }
            )
    return tables


def save_tables_as_json(pdf_path, output_dir):
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    written = []
    for table in extract_tables(pdf_path):
        out_path = output_dir / f"table_{table['table_number']}.json"
        out_path.write_text(json.dumps(table, indent=2, ensure_ascii=False))
        written.append(out_path)
    return written


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "pdf_path", nargs="?", default="tests/data/lqaf158.pdf", help="Path to the source PDF"
    )
    parser.add_argument(
        "output_dir", nargs="?", default="output/tables", help="Directory to write JSON files into"
    )
    args = parser.parse_args()

    for path in save_tables_as_json(args.pdf_path, args.output_dir):
        print(f"wrote {path}")


if __name__ == "__main__":
    main()
