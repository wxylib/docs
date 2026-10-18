"""Render the capability map from capabilities.yml.

Quarto runs this before every render (pre-render in _quarto.yml). It
writes capabilities/_generated.md, which capabilities.qmd includes. When
wxylib/core is checked out into core/ (as the publish workflow does), the
headline facts are counted from its source and the page says whether core
has moved on since the statuses were last reviewed.

Run it by hand with `python3 capabilities/build.py`; it needs PyYAML.
"""

import html
import os
import re
import string
import subprocess
import sys

import yaml

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
CORE = os.path.join(ROOT, "core")

STATUSES = {
    "built": "built and GDAL-checked",
    "partial": "built with known gaps",
    "planned": "planned in a numbered stage",
    "asp": "type slot or aspiration",
    "none": "not there yet",
}
CELL_STATUSES = set(STATUSES) | {"na"}


class DataError(Exception):
    pass


def inline(text):
    """ASCII text with `code` and [links](url) to HTML."""
    if not text.isascii():
        raise DataError("non-ASCII text: %r" % text)
    out = []
    pos = 0
    for m in re.finditer(r"`([^`]+)`|\[([^\]]+)\]\(([^)\s]+)\)|\*([^*]+)\*", text):
        out.append(html.escape(text[pos:m.start()], quote=False))
        if m.group(1) is not None:
            out.append("<code>%s</code>" % html.escape(m.group(1), quote=False))
        elif m.group(2) is not None:
            url = m.group(3)
            # Site-relative pages are rendered to .html beside this page.
            if "://" not in url:
                url = re.sub(r"\.(q?md)(#|$)", r".html\2", url)
            out.append('<a href="%s">%s</a>' % (html.escape(url), inline(m.group(2))))
        else:
            out.append("<em>%s</em>" % html.escape(m.group(4), quote=False))
        pos = m.end()
    out.append(html.escape(text[pos:], quote=False))
    return "".join(out)


def cell(value, where, colspan=None):
    if not (isinstance(value, list) and len(value) == 2):
        raise DataError("%s: a cell is [status, \"text\"], got %r" % (where, value))
    status, text = value
    if status not in CELL_STATUSES:
        raise DataError("%s: unknown status %r (one of %s)"
                        % (where, status, ", ".join(sorted(CELL_STATUSES))))
    span = ' colspan="%d"' % colspan if colspan else ""
    return '<td%s><div class="c %s"><span>%s</span></div></td>' % (
        span, status, inline(str(text)))


def table(columns, rows, head_label):
    """rows: list of (header html, dict of cells, where)."""
    keys = list(columns)
    out = ['<div class="tbox"><table>', "<thead><tr><th>%s</th>" % head_label]
    out += ["<th>%s</th>" % inline(columns[k]) for k in keys]
    out.append("</tr></thead><tbody>")
    for header, cells, where in rows:
        unknown = set(cells) - set(keys) - {"span", "name", "model"}
        if unknown:
            raise DataError("%s: unknown columns %s" % (where, sorted(unknown)))
        out.append("<tr><th>%s</th>" % header)
        rest = keys
        if "span" in cells:
            # A span covers every column after the ones the row names.
            named = [k for k in keys if k in cells]
            for k in named:
                out.append(cell(cells[k], "%s.%s" % (where, k)))
            out.append(cell(cells["span"], where + ".span", len(keys) - len(named)))
            rest = []
        for k in rest:
            out.append(cell(cells.get(k, ["none", ""]), "%s.%s" % (where, k)))
        out.append("</tr>")
    out.append("</tbody></table></div>")
    return "\n".join(out)


def core_facts():
    """Facts counted from a core checkout, or None without one."""
    if not os.path.isdir(os.path.join(CORE, "crates")):
        return None
    crates = sorted(d for d in os.listdir(os.path.join(CORE, "crates"))
                    if os.path.isfile(os.path.join(CORE, "crates", d, "Cargo.toml")))
    lines = tests = 0
    for dirpath, _, files in os.walk(os.path.join(CORE, "crates")):
        if "/target" in dirpath:
            continue
        for f in files:
            if not f.endswith(".rs"):
                continue
            with open(os.path.join(dirpath, f), encoding="utf-8") as fh:
                src = fh.read()
            tests += len(re.findall(r"#\[(?:tokio::)?test\b", src))
            if os.sep + "src" in dirpath[len(CORE):]:
                lines += src.count("\n")
    verbs = []
    main = os.path.join(CORE, "crates", "wxy-cli", "src", "main.rs")
    if os.path.isfile(main):
        with open(main, encoding="utf-8") as fh:
            m = re.search(r"enum Command \{(.*?)\n\}", fh.read(), re.S)
        if m:
            verbs = [v.lower() for v in re.findall(r"^\s{4}([A-Z]\w*)\s*[({,]", m.group(1), re.M)]
    sha = subprocess.run(["git", "-C", CORE, "rev-parse", "--short=7", "HEAD"],
                         capture_output=True, text=True).stdout.strip()
    return {"crates": len(crates), "lines": "%.1fk" % (lines / 1000.0),
            "tests": tests, "verbs": verbs, "sha": sha}


def ladder(data):
    with open(os.path.join(HERE, "ladder.svg.in"), encoding="utf-8") as fh:
        template = fh.read()
    template = re.sub(r"^<!--.*?-->\n", "", template)
    slots = {}
    centre = {}
    for i, r in enumerate(data["rungs"]):
        if r["status"] not in STATUSES:
            raise DataError("rungs.%s: unknown status %r" % (r["id"], r["status"]))
        slots[r["id"] + "_status"] = r["status"]
        slots[r["id"] + "_pill"] = html.escape(r["pill"])
        centre[r["id"]] = 60 + 120 * i
    target = centre["R1"] + 8
    arrows = ['<text x="%d" y="292" class="bt">conversions to R1 that run today</text>'
              % centre["R1"]]
    for i, c in enumerate(data["conversions"]):
        if c["status"] not in ("built", "partial"):
            raise DataError("conversions: status is built or partial, got %r" % c["status"])
        x, y = centre[c["from"]], 322 + 30 * i
        head = "ahb" if c["status"] == "built" else "ahp"
        arrows += [
            '<circle cx="%d" cy="%d" r="3" class="%s"/>' % (x, y, head),
            '<path class="arc %s" d="M%d,%d H%d" marker-end="url(#ah-%s)"/>'
            % (c["status"], x, y, target, c["status"]),
            '<text x="%d" y="%d" class="at %s" text-anchor="end">%s</text>'
            % (x - 8, y - 7, c["status"], html.escape(c["label"])),
        ]
    slots["conversions"] = "\n".join(arrows)
    slots["height"] = str(310 + 30 * len(data["conversions"]))
    return string.Template(template).substitute(slots)


def build(data):
    reviewed = data["reviewed"]
    facts = dict(data["facts"])
    counted = core_facts()
    stale = ""
    sha = reviewed["core"]
    if counted:
        facts.update({k: counted[k] for k in ("crates", "lines", "tests", "verbs")
                      if counted[k]})
        if counted["sha"] and counted["sha"] != reviewed["core"]:
            stale = (
                '<p class="stale">wxylib/core is now at <code>%s</code>; these statuses were '
                'last reviewed at <code>%s</code> (<a href="https://github.com/wxylib/core/'
                'compare/%s...%s">what changed</a>). Counts below are from <code>%s</code>.</p>'
                % (counted["sha"], sha, sha, counted["sha"], counted["sha"]))

    def sub(text):
        return string.Template(text).safe_substitute(
            {k: str(v) for k, v in reviewed.items()})

    out = []
    out.append('<p class="eyebrow">Statuses read from wxylib/core at <code>%s</code>, %s</p>'
               % (html.escape(sha), html.escape(str(reviewed["date"]))))
    if stale:
        out.append(stale)
    out.append('<p class="lede">%s</p>' % inline(sub(data["summary"])))
    verbs = facts["verbs"]
    out.append(
        '<div class="facts"><span><b>%s</b> crates</span><span><b>~%s</b> lines of library '
        'source</span><span><b>%d</b> CLI verbs: %s</span><span><b>%s</b> test functions</span></div>'
        % (facts["crates"], facts["lines"], len(verbs), ", ".join(verbs), facts["tests"]))
    out.append('<div class="legend" aria-label="Legend">')
    out += ['<span class="k"><i class="sw %s"></i>%s</span>' % kv for kv in STATUSES.items()]
    out.append("</div>")

    out.append("<h2>The ladder</h2>")
    out.append('<div class="fig">%s</div>' % ladder(data))
    out.append('<p class="figcap">%s</p>' % inline(sub(data["ladder_caption"])))

    rbv = data["rung_by_verb"]
    names = {r["id"]: r for r in data["rungs"]}
    rows = []
    for rid, cells in rbv["rows"].items():
        if rid not in names:
            raise DataError("rung_by_verb.rows: unknown rung %r" % rid)
        r = names[rid]
        header = '<span class="mono">%s</span><small>%s</small>' % (
            html.escape(r.get("label", rid)), html.escape(r["name"]))
        rows.append((header, cells, "rung_by_verb." + rid))
    out.append("<h2>Rung by verb</h2>")
    out.append("<p>%s</p>" % inline(sub(rbv["intro"])))
    out.append(table(rbv["columns"], rows, "Rung"))

    api = data["api_surface"]
    rows = [(inline(row["name"]), row, "api_surface." + row["name"]) for row in api["rows"]]
    out.append("<h2>API surface</h2>")
    out.append("<p>%s</p>" % inline(sub(api["intro"])))
    out.append(table(api["columns"], rows, "Capability"))

    out.append("<h2>Potential: what the next steps open up</h2>")
    out.append('<div class="cols">')
    for card in data["potential"]:
        body = ("<p>%s</p>" % inline(card["body"]) if "body" in card else
                "<ul>%s</ul>" % "".join("<li>%s</li>" % inline(i) for i in card["items"]))
        out.append('<div class="card"><span class="tag">%s</span><h3>%s</h3>%s</div>'
                   % (inline(card["tag"]), inline(card["title"]), body))
    out.append("</div>")
    out.append('<p class="foot">%s Edit <a href="https://github.com/wxylib/docs/blob/main/'
               'capabilities/capabilities.yml">capabilities.yml</a> to update this page.</p>'
               % inline(sub(data["footnote"])))
    return "\n".join(out)


def main():
    with open(os.path.join(HERE, "capabilities.yml"), encoding="utf-8") as fh:
        data = yaml.safe_load(fh)
    try:
        body = build(data)
    except (DataError, KeyError, ValueError) as e:
        sys.exit("capabilities.yml: %s" % e)
    # Headings become real page sections, so they show in the table of
    # contents and search; the rest is raw HTML, all in one styled div.
    parts = re.split(r"<h2>(.*?)</h2>", body)
    md = ["<!-- Generated by capabilities/build.py from capabilities.yml; do not edit. -->", "",
          "::: {.capmap}", ""]
    for i, part in enumerate(parts):
        if i % 2:
            md += ["## " + re.sub(r"<[^>]+>", "", html.unescape(part)), ""]
        elif part.strip():
            md += ["```{=html}", part.strip(), "```", ""]
    md.append(":::")
    with open(os.path.join(HERE, "_generated.md"), "w", encoding="utf-8") as fh:
        fh.write("\n".join(md))


if __name__ == "__main__":
    main()
