"""Turn a download of the Coral Calendar artifact into the GitHub Pages site.

Usage: python3 tools/sync_from_artifact.py <artifact-download-dir> [Old=New]

The download dir holds the artifact's published files (index.html, asl/, aslgif/, ws/, pdfjs/,
wsboxes.json). This copies them into the repo root and adds standalone.js, which stands in for
Claude's database so the page can save in the browser on GitHub Pages.

Old=New (optional) replaces a name in the page and data files (see tools/rename.py). The printed
worksheets (ws/*.pdf and their previews) keep the original name on purpose. Pass it on the command
line so the original name is never stored in the repo's text.
"""
import pathlib
import shutil
import sys

REPO = pathlib.Path(__file__).resolve().parent.parent
FOLDERS = ["asl", "aslgif", "ws", "pdfjs"]
FILES = ["wsboxes.json"]
# The shim must run before the page's own scripts, so it goes first in <head>.
SHIM_TAG = '<script src="standalone.js"></script>'


def main(src, swap=None):
    src = pathlib.Path(src)
    html = (src / "index.html").read_text(encoding="utf-8")
    if "<head>" not in html:
        sys.exit("index.html has no <head>; can't add standalone.js")
    if SHIM_TAG not in html:
        html = html.replace("<head>", "<head>" + SHIM_TAG, 1)
    for name in FOLDERS + FILES:
        if not (src / name).exists():
            sys.exit(f"Missing from the download: {name}")
    for name in FOLDERS:
        shutil.rmtree(REPO / name, ignore_errors=True)
        shutil.copytree(src / name, REPO / name)
    for name in FILES:
        shutil.copy2(src / name, REPO / name)
    (REPO / "index.html").write_text(html, encoding="utf-8")
    if swap:
        old, _, new = swap.partition("=")
        if not old or not new:
            sys.exit("The rename must look like Old=New")
        sys.path.insert(0, str(REPO / "tools"))
        import rename
        rename.main(REPO, old, new, pdfs=False)
    print("Synced", src, "->", REPO)


if __name__ == "__main__":
    if len(sys.argv) not in (2, 3):
        sys.exit(__doc__)
    main(*sys.argv[1:])
