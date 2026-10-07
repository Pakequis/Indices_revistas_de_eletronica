#!/usr/bin/env python3
"""Build a single-file, offline HTML checklist of missing magazine issues.

Reads EDICOES-FALTANTES.md and writes docs/lista-sebo.html, meant to be
opened on a phone (checkboxes persist in localStorage) or printed.
"""
import html
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "EDICOES-FALTANTES.md"
OUT = ROOT / "docs" / "lista-sebo.html"
OUT_FRAGMENT = ROOT / "docs" / "lista-sebo-blogger.html"


def expand(spec):
    """'5–12, 14, 23' -> ['5', '6', ..., '12', '14', '23'] (keeps zero padding)."""
    nums = []
    for part in re.split(r"\s*,\s*", spec.strip()):
        m = re.fullmatch(r"(\d+)\s*[–-]\s*(\d+)", part)
        if m:
            a, b = m.groups()
            width = len(a) if a.startswith("0") else 0
            nums += [str(n).zfill(width) for n in range(int(a), int(b) + 1)]
        elif re.fullmatch(r"\d+", part):
            nums.append(part)
        else:
            return None
    return nums


def parse():
    text = SRC.read_text(encoding="utf-8")
    gaps, sparse = [], []
    section = None
    for line in text.splitlines():
        if line.startswith("## "):
            section = line[3:].strip()
        if not line.startswith("|") or line.startswith("|---") or "Revista |" in line:
            continue
        cells = [c.strip() for c in line.strip("|").split("|")]
        if len(cells) != 3 or section != "Revistas com lacunas":
            continue
        name, known, missing = cells
        nums = expand(missing)
        if nums:
            gaps.append((name, known, nums))
        elif missing != "nenhuma" and "Monitor" not in name:
            sparse.append((name, missing))
    monitor = re.search(r"intervalo 9–426\):\*\*\n(.*?)\.\n", text, re.S)
    if monitor:
        nums = expand(monitor.group(1).replace("\n", " "))
        gaps.append(("Monitor de Rádio e TV", "9–426", nums))
    return gaps, sparse


def render(gaps, sparse):
    parts = []
    for i, (name, known, nums) in enumerate(gaps):
        chips = "".join(
            f'<label><input type="checkbox" data-k="{i}-{n}"><span>{n}</span></label>'
            for n in nums
        )
        parts.append(
            f'<section><h2>{html.escape(name)} <small>({len(nums)} {'falta' if len(nums) == 1 else 'faltam'} · '
            f'{html.escape(known)})</small></h2><div class="chips">{chips}</div></section>'
        )
    other = "".join(
        f"<li><b>{html.escape(n)}</b>: {html.escape(t)}</li>" for n, t in sparse
    )
    return f"""<!doctype html>
<html lang="pt-BR"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Lista do sebo</title>
<style>
body{{font:16px/1.4 system-ui,sans-serif;margin:0 auto;padding:12px 16px;max-width:760px;background:#fff;color:#111}}
h1{{font-size:1.3rem;margin:.2em 0}} h2{{font-size:1.05rem;margin:1.2em 0 .4em;border-bottom:1px solid #999}}
small{{font-weight:400;color:#555}}
.chips{{display:flex;flex-wrap:wrap;gap:6px}}
.chips label{{cursor:pointer}} .chips input{{position:absolute;opacity:0}}
.chips span{{display:inline-block;min-width:2.4em;text-align:center;padding:6px 8px;border:1px solid #666;border-radius:6px}}
.chips input:checked+span{{background:#1a7f37;color:#fff;border-color:#1a7f37;text-decoration:line-through}}
.chips input:focus-visible+span{{outline:2px solid #06c}}
ul{{padding-left:1.1em}} button{{font:inherit;padding:6px 10px}}
@media(prefers-color-scheme:dark){{body{{background:#111;color:#eee}}small{{color:#aaa}}h2{{border-color:#666}}.chips span{{border-color:#888}}}}
@media print{{button{{display:none}}body{{font-size:11pt}}.chips span{{padding:2px 5px;border-color:#000}}.chips input:checked+span{{background:none;color:#000;border-color:#000}}section{{break-inside:avoid}}}}
</style></head><body>
<h1>Edições que faltam</h1>
<p>Toque no número ao encontrar. Marcações ficam salvas neste aparelho.
<button id="reset">Limpar marcações</button></p>
{''.join(parts)}
<h2>Acervo esparso (só temos algumas; qualquer outra serve)</h2>
<ul>{other}</ul>
<script>
const KEY="lista-sebo-v1";let s={{}};
try{{s=JSON.parse(localStorage.getItem(KEY)||"{{}}")}}catch(e){{}}
const save=()=>{{try{{localStorage.setItem(KEY,JSON.stringify(s))}}catch(e){{}}}};
document.querySelectorAll("input[data-k]").forEach(i=>{{
  i.checked=!!s[i.dataset.k];
  i.addEventListener("change",()=>{{i.checked?s[i.dataset.k]=1:delete s[i.dataset.k];save()}});
}});
document.getElementById("reset").onclick=()=>{{if(confirm("Limpar tudo?")){{s={{}};save();document.querySelectorAll("input[data-k]").forEach(i=>i.checked=false)}}}};
</script></body></html>
"""


def render_fragment(gaps, sparse):
    """Same checklist as an embeddable fragment (no <html>/<body>), with the
    CSS scoped under #lsb so it does not leak into the host page theme."""
    full = render(gaps, sparse)
    style = re.search(r"<style>(.*?)</style>", full, re.S).group(1)
    body = re.search(r"<body>(.*)</body>", full, re.S).group(1)
    scoped = []
    for sel, rest in re.findall(r"([^{}@]+)\{([^{}]*)\}", style.split("@media", 1)[0]):
        sels = ",".join(
            "#lsb" if s.strip() == "body" else "#lsb " + s.strip() for s in sel.split(",")
        )
        scoped.append(f"{sels}{{{rest}}}")
    # Own background so the host theme colors never make it unreadable.
    scoped.append("#lsb{background:#fff;color:#111;padding:12px 16px;max-width:760px;margin:0 auto}")
    scoped.append("#lsb h1{margin-top:0}")
    scoped.append("@media print{#lsb button{display:none}}")
    return (
        '<meta name="robots" content="noindex,nofollow">\n'
        f'<style>{"".join(scoped)}</style>\n<div id="lsb">{body}</div>\n'
    )


if __name__ == "__main__":
    gaps, sparse = parse()
    OUT.write_text(render(gaps, sparse), encoding="utf-8")
    OUT_FRAGMENT.write_text(render_fragment(gaps, sparse), encoding="utf-8")
    print(f"{OUT}: {len(gaps)} magazines, {sum(len(g[2]) for g in gaps)} issues", file=sys.stderr)
