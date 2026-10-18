"""Turn a download of the Coral Calendar artifact into the GitHub Pages site.

Usage: python3 tools/sync_from_artifact.py <artifact-download-dir> [Old=New] [--settings <db-export-dir>]

The download dir holds the artifact's published files (index.html, asl/, aslgif/, ws/, pdfjs/,
wsboxes.json). This copies them into the repo root and adds standalone.js, which stands in for
Claude's database so the page can save in the browser on GitHub Pages.

Old=New (optional) replaces a name in the page and data files (see tools/rename.py). The printed
worksheets (ws/*.pdf and their previews) keep the original name on purpose. Pass it on the command
line so the original name is never stored in the repo's text.

--settings (optional) writes settings-seed.js from an export of the artifact database (one JSON
file per document at <collection>/<doc id>.json). Only the lesson plans and schedule settings in
SETTINGS_DOCS are copied; her check-ins, results, logs, summaries and the consent record never are.
"""
import hashlib
import json
import pathlib
import shutil
import sys

REPO = pathlib.Path(__file__).resolve().parent.parent
FOLDERS = ["asl", "aslgif", "ws", "pdfjs"]
FILES = ["wsboxes.json"]
# The shims must run before the page's own scripts, so they go first in <head>.
SHIM_TAGS = '<script src="settings-seed.js"></script><script src="standalone.js"></script>'
SETTINGS_DOCS = ["plans/A", "plans/B", "plans/S", "config/main",
                 "schedule/daytimes", "schedule/missing", "schedule/moves", "schedule/swaps"]
CONFIG_SKIP = {"consent"}


def build_seed(dbdir):
    dbdir = pathlib.Path(dbdir)
    docs = {}
    for p in SETTINGS_DOCS:
        f = dbdir / (p + ".json")
        if f.exists():
            d = json.loads(f.read_text(encoding="utf-8"))
            if p == "config/main":
                d = {k: v for k, v in d.items() if k not in CONFIG_SKIP}
            docs[p] = d
    if "config/main" not in docs:
        sys.exit("The settings export has no config/main; refusing to write an incomplete seed.")
    # Versioned by content, so devices re-check their settings whenever anything in the seed changes.
    text = json.dumps(docs, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    version = hashlib.sha1(text.encode("utf-8")).hexdigest()[:12]
    body = json.dumps({"version": version, "docs": docs}, ensure_ascii=False, separators=(",", ":"))
    (REPO / "settings-seed.js").write_text(
        "/* Coral Calendar lesson plans and schedule settings, copied from the Claude version. */\n"
        f"window.TIDE_SEED = {body};\n", encoding="utf-8")
    return sorted(docs)


def main(src, swap=None, settings=None):
    src = pathlib.Path(src)
    html = (src / "index.html").read_text(encoding="utf-8")
    if "<head>" not in html:
        sys.exit("index.html has no <head>; can't add standalone.js")
    if SHIM_TAGS not in html:
        html = html.replace("<head>", "<head>" + SHIM_TAGS, 1)
    for name in FOLDERS + FILES:
        if not (src / name).exists():
            sys.exit(f"Missing from the download: {name}")
    for name in FOLDERS:
        shutil.rmtree(REPO / name, ignore_errors=True)
        shutil.copytree(src / name, REPO / name)
    for name in FILES:
        shutil.copy2(src / name, REPO / name)
    (REPO / "index.html").write_text(html, encoding="utf-8")
    if settings:
        print("Settings copied:", ", ".join(build_seed(settings)))
    elif not (REPO / "settings-seed.js").exists():
        (REPO / "settings-seed.js").write_text("window.TIDE_SEED = null;\n", encoding="utf-8")
    if swap:
        old, _, new = swap.partition("=")
        if not old or not new:
            sys.exit("The rename must look like Old=New")
        sys.path.insert(0, str(REPO / "tools"))
        import rename
        rename.main(REPO, old, new, pdfs=False)
    print("Synced", src, "->", REPO)


if __name__ == "__main__":
    args = sys.argv[1:]
    settings = None
    if "--settings" in args:
        i = args.index("--settings")
        if i + 1 >= len(args):
            sys.exit(__doc__)
        settings = args[i + 1]
        del args[i:i + 2]
    if len(args) not in (1, 2):
        sys.exit(__doc__)
    main(*args, settings=settings)
