#!/usr/bin/env python3
"""
Produce the public CV from the private résumé by removing the phone number.

This is a real redaction, not a white box over the text: apply_redactions()
rewrites the content stream, so the digits are gone from the text layer and
cannot be recovered by copy-paste or `pdftotext`.

Removing the phone leaves a hole in the middle of the contact line, so the line
is rebuilt: the surviving items are re-laid-out with the original spacing, in
the document's own embedded Helvetica Neue, and their hyperlinks re-attached.

    python3 scripts/build-cv.py <source.pdf> [public/data/cv.pdf]
"""
import os
import re
import shutil
import subprocess
import sys

# --------------------------------------------------------------------------
# Find an interpreter that can actually run this.
#
# `python3` is frequently an old conda base env. PyMuPDF dropped 3.7, so pip
# resolves to a 1.x sdist and tries to build it, which needs swig, whose
# pyproject.toml then chokes conda's ancient vendored TOML parser. Chasing that
# is a waste of time when a working interpreter is usually already installed —
# so look for one and re-exec into it rather than lecturing the user.
# --------------------------------------------------------------------------

_PROBE = "import fitz; fitz.Rect"  # the unrelated PyPI "fitz" imports but has no API
_REEXEC_FLAG = "_BUILD_CV_REEXEC"


def _usable(exe):
    try:
        return subprocess.run(
            [exe, "-c", _PROBE], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=30
        ).returncode == 0
    except Exception:
        return False


def _candidates():
    names = ["python3.13", "python3.12", "python3.11", "python3.10", "python3.9", "python3"]
    dirs = ["/opt/homebrew/bin", "/usr/local/bin", "/usr/bin", os.path.expanduser("~/.local/bin")]
    out, seen = [], {os.path.realpath(sys.executable)}
    for name in names:
        found = [os.path.join(d, name) for d in dirs]
        which = shutil.which(name)
        if which:
            found.append(which)
        for path in found:
            if not os.path.exists(path):
                continue
            real = os.path.realpath(path)
            if real in seen:
                continue
            seen.add(real)
            out.append(path)
    return out


try:
    import fitz  # PyMuPDF

    fitz.Rect
except (ImportError, AttributeError):
    if os.environ.get(_REEXEC_FLAG):  # already retried once; don't loop
        sys.exit("ERROR: re-exec did not yield a working PyMuPDF. Install it and retry.")

    env = {**os.environ, _REEXEC_FLAG: "1"}
    args = sys.argv[1:]

    for exe in _candidates():
        if _usable(exe):
            print(f"[build-cv] {sys.executable} has no usable PyMuPDF; using {exe}", file=sys.stderr)
            os.execve(exe, [exe, os.path.abspath(__file__), *args], env)

    # Nothing installed has it — uv can conjure an ephemeral env without
    # touching any of the interpreters already on this machine.
    if shutil.which("uv"):
        print("[build-cv] no interpreter has PyMuPDF; running via `uv run --with pymupdf`", file=sys.stderr)
        os.execvpe(
            "uv",
            ["uv", "run", "--with", "pymupdf", "python", os.path.abspath(__file__), *args],
            env,
        )

    sys.exit(
        "This script needs PyMuPDF and no interpreter on this machine has a usable copy.\n"
        f"  tried: {sys.executable} (Python {sys.version.split()[0]}) and "
        f"{len(_candidates())} other interpreter(s)\n\n"
        "Easiest fix, no environment to manage:\n"
        "    uv run --with pymupdf python scripts/build-cv.py <src.pdf> [out.pdf]\n\n"
        "Or install into a Python >= 3.9 (PyMuPDF does not support 3.7/3.8):\n"
        "    python3.11 -m pip install pymupdf\n\n"
        "If the import fails with \"No module named 'frontend'\", the unrelated PyPI\n"
        "package named 'fitz' is shadowing PyMuPDF:\n"
        "    python3 -m pip uninstall -y fitz && python3 -m pip install pymupdf"
    )

PHONE = re.compile(r"(\+?\d{1,2}[\s.-]*)?\(?\d{3}\)?[\s.-]*\d{3}[\s.-]*\d{4}")
GAP = 13.51  # separator width used between contact items in the source


# The PDF's own Helvetica Neue is embedded as an Identity-H *subset* with no
# usable ToUnicode table, so text drawn with it renders correctly but extracts
# as nothing — which would silently break copy-paste and CV parsers. Prefer a
# full system copy, which round-trips properly.
SYSTEM_FONTS = [
    "/System/Library/Fonts/HelveticaNeue.ttc",
    "/System/Library/Fonts/Helvetica.ttc",
]


def find_regular_font(sample):
    """Return (fontfile_path_or_None, Font) able to render `sample`."""
    for path in SYSTEM_FONTS:
        try:
            font = fitz.Font(fontfile=path)
        except Exception:
            continue
        if all(font.has_glyph(ord(c)) for c in sample):
            return path, font
    return None, fitz.Font("helv")  # base-14; metrically close, always extracts


def main():
    src_path = sys.argv[1]
    out_path = sys.argv[2] if len(sys.argv) > 2 else "public/data/cv.pdf"

    doc = fitz.open(src_path)
    removed = 0

    for page in doc:
        spans = [
            s
            for b in page.get_text("dict")["blocks"]
            for l in b.get("lines", [])
            for s in l["spans"]
            if s["text"].strip()
        ]
        phone_spans = [s for s in spans if PHONE.fullmatch(s["text"].strip())]
        if not phone_spans:
            continue

        for phone in phone_spans:
            baseline = round(phone["origin"][1], 2)
            # Everything sharing the phone's baseline is the contact line.
            line = sorted(
                (s for s in spans if abs(s["origin"][1] - baseline) < 0.5),
                key=lambda s: s["origin"][0],
            )
            keep = [s for s in line if s is not phone]
            links = {
                round(l["from"].x0): l
                for l in page.get_links()
                if abs(l["from"].y0 - (baseline - 9.7)) < 3
            }

            sample = "".join(s["text"] for s in keep)
            fontpath, font = find_regular_font(sample)

            # Wipe the whole line, then rebuild it without the gap.
            band = fitz.Rect(line[0]["bbox"][0], baseline - 11, line[-1]["bbox"][2] + 2, baseline + 4)
            page.add_redact_annot(band)
            for l in list(links.values()):
                page.delete_link(l)
            page.apply_redactions(images=fitz.PDF_REDACT_IMAGE_NONE)
            removed += 1
            print(f"  removed {phone['text'].strip()!r} and rebuilt the contact line")

            x = line[0]["origin"][0]
            for s in keep:
                size = s["size"]
                text = s["text"]
                colour = [((s["color"] >> 16) & 255) / 255, ((s["color"] >> 8) & 255) / 255, (s["color"] & 255) / 255]
                kwargs = {"fontsize": size, "color": colour}
                if fontpath is not None:
                    kwargs.update(fontname="HNeue", fontfile=fontpath)
                else:
                    kwargs.update(fontname="helv")
                page.insert_text((x, baseline), text, **kwargs)
                width = font.text_length(text, fontsize=size)
                old = links.get(round(s["bbox"][0]))
                if old is not None:
                    page.insert_link(
                        {
                            "kind": fitz.LINK_URI,
                            "uri": old["uri"],
                            "from": fitz.Rect(x, baseline - 9.7, x + width, baseline + 3.7),
                        }
                    )
                x += width + GAP

    if removed == 0:
        sys.exit("ERROR: no phone number found — refusing to write a CV that was not checked")

    # Embedding a full system .ttc triples the file size; keep only the glyphs
    # actually used. Older PyMuPDF builds lack this, so it is best-effort.
    try:
        doc.subset_fonts()
    except AttributeError:
        pass

    doc.save(out_path, garbage=4, deflate=True, clean=True)
    doc.close()

    # Refuse to emit a file that still contains a phone-shaped string.
    check = fitz.open(out_path)
    text = "".join(p.get_text() for p in check)
    leftovers = re.findall(r"\(?\d{3}\)?[\s.-]*\d{3}[\s.-]*\d{4}", text)
    check.close()
    if leftovers:
        sys.exit(f"ERROR: phone-shaped text survived redaction: {leftovers}")

    # The rebuilt line must still be real, selectable text — a CV that renders
    # correctly but extracts as nothing is invisible to every résumé parser.
    for needle in ("Mountain View", "jefflai108@gmail.com", "Google Scholar"):
        if needle not in text:
            sys.exit(f"ERROR: {needle!r} did not survive as extractable text")

    print(f"wrote {out_path} — {removed} redaction(s); phone gone, contact line still extracts")


if __name__ == "__main__":
    main()
