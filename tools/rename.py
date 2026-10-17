"""Replace a name throughout the site: text files, worksheet PDFs and their preview pictures.

Usage: python3 tools/rename.py <folder> <OldName> <NewName> [--text-only]

The real name is passed in on the command line and is never written into the repo.
--text-only leaves PDFs and their previews alone (the site keeps the real name on the printed
worksheets only; everything else uses NewName).
- Text files (.html .js .json .md .txt .css): OldName/oldname/OLDNAME -> NewName in the same case.
- PDFs: each occurrence is removed and NewName is written in its place, same size, colour and
  baseline, in Patrick Hand (the worksheets' handwriting font).
- X.png next to a changed X.pdf: only the changed spots are re-drawn from the new PDF, so the
  rest of the preview stays pixel-identical.
Exits non-zero if OldName can still be found afterwards.
"""
import io
import pathlib
import re
import sys

import pymupdf
from PIL import Image

FONT = pathlib.Path(__file__).resolve().parent / "PatrickHand-Regular.ttf"
TEXT_EXT = {".html", ".js", ".json", ".md", ".txt", ".css", ".webmanifest"}
PREVIEW_DPI = 110  # ws/*.png are 935x1210 renders of 612x792pt pages


def case_map(old, new):
    return [(old, new), (old.lower(), new.lower()), (old.upper(), new.upper())]


def fix_text(path, old, new):
    t = path.read_text(encoding="utf-8")
    n = t
    for a, b in case_map(old, new):
        n = n.replace(a, b)
    if n != t:
        path.write_text(n, encoding="utf-8")
        return True
    return False


def name_hits(page, old):
    """(rect, origin, size, rgb, fontname) for each occurrence, from character positions."""
    hits = []
    for b in page.get_text("rawdict")["blocks"]:
        for l in b.get("lines", []):
            for s in l["spans"]:
                chars = s["chars"]
                text = "".join(c["c"] for c in chars)
                for m in re.finditer(re.escape(old), text, re.I):
                    cs = chars[m.start():m.end()]
                    r = pymupdf.Rect(cs[0]["bbox"])
                    for c in cs[1:]:
                        r |= pymupdf.Rect(c["bbox"])
                    col = s["color"]
                    rgb = ((col >> 16 & 255) / 255, (col >> 8 & 255) / 255, (col & 255) / 255)
                    # Type3 fonts here are the bold question headings.
                    bold = s["font"].startswith("Type3")
                    hits.append((r, pymupdf.Point(cs[0]["origin"]), s["size"], rgb, m.group(0), bold))
    return hits


def fix_pdf(path, old, new):
    doc = pymupdf.open(path)
    changed = {}
    for pno, page in enumerate(doc):
        hits = name_hits(page, old)
        if not hits:
            continue
        for r, *_ in hits:
            # Inset so neighbouring letters that touch the box aren't removed too.
            page.add_redact_annot(pymupdf.Rect(r.x0 + 0.3, r.y0 + 0.5, r.x1 - 0.3, r.y1 - 0.5), fill=False)
        page.apply_redactions(images=pymupdf.PDF_REDACT_IMAGE_NONE,
                              graphics=pymupdf.PDF_REDACT_LINE_ART_NONE,
                              text=pymupdf.PDF_REDACT_TEXT_REMOVE)
        font = pymupdf.Font(fontfile=str(FONT))
        for r, origin, size, rgb, found, bold in hits:
            word = new.upper() if found.isupper() else new.lower() if found.islower() else new
            # Stretch or squeeze the new word to the old word's width so the line spacing is unchanged.
            sx = (r.x1 - origin.x) / max(font.text_length(word, fontsize=size), 0.1)
            sx = min(max(sx, 0.8), 1.35)
            page.insert_text(origin, word, fontsize=size, fontname="PatrickHand", fontfile=str(FONT),
                             color=rgb, morph=(origin, pymupdf.Matrix(sx, 1)),
                             render_mode=2 if bold else 0, border_width=0.035 if bold else 0.05)
        changed[pno] = [h[0] for h in hits]
    if changed:
        data = doc.tobytes(garbage=3, deflate=True)
        doc.close()
        path.write_bytes(data)
    return changed


def fix_preview(png, pdf, rects):
    if not png.exists():
        return
    doc = pymupdf.open(pdf)
    pix = doc[0].get_pixmap(dpi=PREVIEW_DPI)
    fresh = Image.open(io.BytesIO(pix.tobytes("png"))).convert("RGB")
    im = Image.open(png)
    mode = im.mode
    im = im.convert("RGB")
    if fresh.size != im.size:
        # Not the size we expect; replace the whole preview rather than guess an alignment.
        fresh.save(png)
        return
    k = PREVIEW_DPI / 72
    for r in rects:
        box = (max(0, int((r.x0 - 4) * k)), max(0, int((r.y0 - 3) * k)),
               min(im.width, int((r.x1 + 14) * k) + 1), min(im.height, int((r.y1 + 3) * k) + 1))
        im.paste(fresh.crop(box), box[:2])
    im.convert(mode).save(png, optimize=True)


def main(folder, old, new, pdfs=True):
    root = pathlib.Path(folder)
    n_text = n_pdf = 0
    for p in sorted(root.rglob("*")):
        if ".git" in p.parts or not p.is_file():
            continue
        if p.suffix in TEXT_EXT:
            n_text += fix_text(p, old, new)
        elif p.suffix == ".pdf" and pdfs:
            changed = fix_pdf(p, old, new)
            if changed:
                n_pdf += 1
                fix_preview(p.with_suffix(".png"), p, changed.get(0, []))
    left = []
    for p in sorted(root.rglob("*")):
        if ".git" in p.parts or not p.is_file():
            continue
        if p.suffix in TEXT_EXT and old.lower() in p.read_text(encoding="utf-8", errors="ignore").lower():
            left.append(str(p))
        elif p.suffix == ".pdf" and pdfs and any(old.lower() in pg.get_text().lower() for pg in pymupdf.open(p)):
            left.append(str(p))
    print(f"renamed in {n_text} text files and {n_pdf} PDFs")
    if left:
        sys.exit("Name still found in: " + ", ".join(left))


if __name__ == "__main__":
    args = [a for a in sys.argv[1:] if a != "--text-only"]
    if len(args) != 3:
        sys.exit(__doc__)
    main(*args, pdfs="--text-only" not in sys.argv)
