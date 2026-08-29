#!/usr/bin/env python3
"""Gera docs/mapa-edicoes.html: uma tabela estilo BINGO por revista com a
numeracao das edicoes. Celula azul = existe PDF da edicao na pasta
revistas/. Celula branca = sem PDF (edicao a procurar).

Rode sem argumentos sempre que a pasta revistas/ mudar:

    python3 tools/gerar_mapa_edicoes.py

A leitura e feita so pelos nomes dos arquivos .pdf; nada e aberto. O
intervalo de cada revista vai de `inicio` ate o maior entre o total
conhecido (coluna 3 de CFG) e a maior edicao encontrada na pasta.
Revistas por data (Antenna) ou por bienio (Eletronica Popular) ficam de
fora. As series paralelas Fora de Serie / Especial entram como titulos
proprios (via o 7o campo `include` do CFG).
"""
import os
import re
import html

HERE = os.path.dirname(os.path.abspath(__file__))
PROJ = os.path.dirname(HERE)
REV = os.path.normpath(os.path.join(PROJ, os.pardir, "revistas"))
OUT = os.path.join(PROJ, "docs", "mapa-edicoes.html")

NUM = re.compile(r"\d+(?:-\d+)*")
COLS = 20  # celulas por linha na grade

# pasta em revistas/ -> (titulo, total conhecido, edicao inicial,
#                        [regex de arquivos a ignorar], {arquivo: edicao}
#                        [, regex de arquivos a INCLUIR (so esses contam)])
CFG = [
    ("ABC da Eletronica", "ABC da Eletrônica", 20, 1, [], {}),
    ("Aprendendo e Praticando Eletronica", "Aprendendo e Praticando Eletrônica", 85, 1, [], {}),
    ("Be-a-ba", "Be-a-bá da Eletrônica", 32, 1, [], {}),
    ("CQ Radioamadorismo", "CQ Radioamadorismo", 15, 1, [], {}),
    ("Circuito Fechado", "Circuito Fechado", 14, 1, [], {}),
    ("Circuitos de audio", "Circuitos de Áudio", 3, 1, [], {}),
    ("Circuitos Integrados", "Circuitos Integrados", 11, 1, [], {}),
    ("Circuitos e Informacoes", "Circuitos e Informações", 7, 1, [], {}),
    ("Circuitos e Solucoes", "Circuitos e Soluções", 6, 1, [], {}),
    ("Divirta-se com a eletronica", "Divirta-se com a Eletrônica", 52, 1, [], {}),
    ("Electron", "Electron (Etegil / Fitippaldi)", 64, 1, [r"^Electron e"], {}),
    ("Electron 1", "Electron (Rádio Sociedade, 1926)", 20, 1, [], {}),
    ("Elektor", "Elektor — 1ª série", 31, 1, [], {}),
    ("Eletronica Avancada", "Eletrônica Avançada", 1, 1, [], {}),
    ("Eletronica Coletaneas", "Eletrônica Coletâneas", 31, 1, [], {}),
    ("Eletronica para todos", "Eletrônica para Todos — 1ª coleção", 33, 1,
        [r"coletaneas", r"coletâneas"], {}),
    ("Eletronica para todos 2", "Eletrônica para Todos — 2ª coleção", 33, 0,
        [r"projetos"], {}),
    ("Eletronica Passo a Passo", "Eletrônica Passo a Passo", 52, 1, [], {}),
    ("Eletrônica Pratica", "Eletrônica Prática", 6, 1, [], {}),
    ("Eletronica Total", "Eletrônica Total", 159, 1, [r"\bfs\d"], {}),
    ("Experiencias e Brincadeira com Eletronica",
        "Experiências e Brincadeiras com Eletrônica", 12, 1, [r"especial"], {}),
    ("Experiencias e Brincadeira com Eletronica Jr",
        "Experiências e Brincadeiras com Eletrônica Jr", 25, 1, [r"^ebejr12\.pdf$"], {}),
    ("INCBEletronica", "INCB Eletrônica", 27, 1, [], {}),
    ("IUB", "Revista do Instituto Universal Brasileiro", 72, 1, [], {}),
    ("Informatica eletronica Digital", "Informática Eletrônica Digital", 24, 1, [], {}),
    ("Monitor de Radio e TV", "Revista Monitor de Rádio e Televisão", 429, 1, [r"^indice_"], {}),
    ("Mundo Eletronico", "Mundo Eletrônico", 6, 1, [r"^me_", r"^mee\d"], {}),
    ("Nova Eletronica", "Nova Eletrônica", 114, 1, [], {}),
    ("Novidades Eletrônicas", "Novidades Eletrônicas", 5, 1, [], {}),
    ("QSL Magazine", "QSL Magazine", 1, 1, [], {}),
    ("Radio e TV Tecnico", "Rádio-TV Técnico", 58, 1, [r"retrospectiva"], {}),
    ("Radioamadorismo", "Radioamadorismo em Fascículos", 24, 1, [], {"revista.pdf": 1}),
    ("Saber Eletronica", "Saber Eletrônica", 475, 1,
        [r"fora de serie", r"fora de série", r"^rsee", r"^indice\.pdf$"], {}),
    ("Tecnico Reparador", "Técnico Reparador", 5, 1, [], {}),
    # sub-séries paralelas (CSV próprio) — só contam os arquivos do `include`
    ("Eletronica Total", "Eletrônica Total — Fora de Série", 3, 1, [], {}, r"\bfs\d"),
    ("Saber Eletronica", "Saber Eletrônica — Especial", 11, 1, [], {}, r"^rsee\d"),
    ("Saber Eletronica", "Saber Eletrônica — Fora de Série", 28, 1, [], {},
        r"fora de serie|fora de série"),
]


def editions_present(folder, excludes, special, include=None):
    d = os.path.join(REV, folder)
    have = set()
    exq = [re.compile(p, re.I) for p in excludes]
    inc = re.compile(include, re.I) if include else None
    for f in sorted(os.listdir(d)):
        if not f.lower().endswith(".pdf"):
            continue
        if inc and not inc.search(f):
            continue
        if any(p.search(f) for p in exq):
            continue
        if f in special:
            have.add(special[f])
            continue
        stem = os.path.splitext(f)[0]
        stem = re.sub(r"^Elektor 1 ", "", stem)  # tira o marcador de serie
        m = NUM.search(stem)
        if not m:
            continue
        for tok in m.group(0).split("-"):
            have.add(int(tok))
    return have


def anchor(title):
    return re.sub(r"[^a-z0-9]+", "-", title.lower()).strip("-")


def section_html(folder, title, total, start, excludes, special, include=None):
    have = editions_present(folder, excludes, special, include)
    n = max([total] + list(have)) if have else total
    nums = list(range(start, n + 1))
    missing = [x for x in nums if x not in have]
    rows = []
    for i in range(0, len(nums), COLS):
        tds = "".join(
            f'<td class="{"y" if x in have else "n"}">{x}</td>'
            for x in nums[i:i + COLS]
        )
        rows.append(f"<tr>{tds}</tr>")
    miss_txt = "nenhuma" if not missing else ", ".join(map(str, missing))
    return f"""<section id="{anchor(title)}">
<h2>{html.escape(title)}</h2>
<p class="meta">Intervalo {start}–{n} &middot; {len(nums) - len(missing)} com PDF &middot;
<strong>{len(missing)} sem PDF</strong></p>
<table class="bingo">{''.join(rows)}</table>
<p class="miss"><span>Faltando:</span> {html.escape(miss_txt)}</p>
</section>"""


def main():
    secs = [section_html(*c) for c in CFG]
    nav = " · ".join(
        f'<a href="#{anchor(c[1])}">{html.escape(c[1])}</a>' for c in CFG
    )
    doc = f"""<title>Mapa de edições — PDFs no acervo</title>
<style>
  :root {{
    --bg:#faf9f7; --fg:#1a1a1a; --line:#c9c6c0; --card:#fff;
    --blue:#2563cc; --blue-fg:#fff; --muted:#6a6a6a; --link:#1d4ed8;
  }}
  @media (prefers-color-scheme: dark) {{
    :root:not([data-theme="light"]) {{
      --bg:#15171b; --fg:#e8e6e3; --line:#3a3d42; --card:#0f1114;
      --blue:#3b82f6; --blue-fg:#0b1120; --muted:#9aa0a6; --link:#7ca8ff;
    }}
  }}
  :root[data-theme="dark"] {{
    --bg:#15171b; --fg:#e8e6e3; --line:#3a3d42; --card:#0f1114;
    --blue:#3b82f6; --blue-fg:#0b1120; --muted:#9aa0a6; --link:#7ca8ff;
  }}
  body {{ background:var(--bg); color:var(--fg); margin:0;
    padding:2rem clamp(1rem,4vw,3rem);
    font:14px/1.55 -apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,Helvetica,Arial,sans-serif; }}
  h1 {{ font-size:1.5rem; margin:0 0 .3rem; }}
  .intro {{ color:var(--muted); max-width:62ch; margin:0 0 1.5rem; }}
  .legend {{ display:flex; gap:1.4rem; align-items:center; flex-wrap:wrap;
    margin:0 0 1.5rem; }}
  .legend span {{ display:inline-flex; align-items:center; gap:.5rem; }}
  .sw {{ width:1.1rem; height:1.1rem; border:1px solid var(--line);
    display:inline-block; border-radius:3px; }}
  .sw.y {{ background:var(--blue); }}
  .sw.n {{ background:var(--card); }}
  nav {{ font-size:.82rem; line-height:1.9; color:var(--muted);
    border:1px solid var(--line); border-radius:6px; padding:.8rem 1rem;
    margin:0 0 2.5rem; }}
  nav a {{ color:var(--link); text-decoration:none; white-space:nowrap; }}
  nav a:hover {{ text-decoration:underline; }}
  section {{ margin:0 0 2.4rem; scroll-margin-top:1rem; }}
  h2 {{ font-size:1.05rem; margin:0 0 .15rem; }}
  .meta {{ color:var(--muted); margin:0 0 .5rem; font-size:.85rem; }}
  .bingo {{ border-collapse:collapse; }}
  .bingo td {{ border:1px solid var(--line); width:2.5rem; height:2rem;
    text-align:center; font-variant-numeric:tabular-nums; font-size:.78rem; }}
  .bingo td.y {{ background:var(--blue); color:var(--blue-fg); }}
  .bingo td.n {{ background:var(--card); color:var(--muted); }}
  .miss {{ font-size:.82rem; color:var(--muted); margin:.55rem 0 0;
    max-width:110ch; }}
  .miss span {{ font-weight:600; color:var(--fg); }}
  footer {{ margin-top:3rem; color:var(--muted); font-size:.8rem;
    border-top:1px solid var(--line); padding-top:1rem; max-width:72ch; }}
  @media (max-width:640px) {{
    .bingo td {{ width:2.1rem; height:1.8rem; font-size:.72rem; }}
  }}
</style>

<h1>Mapa de edições — o que existe em PDF no acervo</h1>
<p class="intro">Cada número é uma edição. As células azuis já têm PDF na
pasta <code>revistas/</code>; as brancas são as edições a procurar.</p>
<div class="legend">
  <span><i class="sw y"></i> tem o PDF</span>
  <span><i class="sw n"></i> sem o PDF (faltante)</span>
</div>
<nav>{nav}</nav>
{''.join(secs)}
<footer>
Gerado por <code>tools/gerar_mapa_edicoes.py</code> a partir dos nomes dos
arquivos <code>.pdf</code> em <code>revistas/</code>. O intervalo vai de 1
(ou 0, na 2ª coleção da Eletrônica para Todos) até o maior entre o total
conhecido da revista e a maior edição presente na pasta — não garante que
a revista tenha começado em 1 nem terminado nesse número. Algumas edições
marcadas como faltantes existem só dentro de PDFs-coletânea/retrospectiva
(ex.: Saber Eletrônica 25 e 26, Rádio-TV Técnico 22 e 27) e continuam
brancas aqui porque não têm arquivo próprio. Antenna (organizada por data)
e Eletrônica Popular (por biênio) ficam de fora. As três sub-séries
paralelas (Eletrônica Total — Fora de Série, Saber Eletrônica — Especial e
Saber Eletrônica — Fora de Série) entram como títulos próprios, com a
numeração da própria sub-série — ver <code>docs/plano-extracao-fora-de-serie.md</code>.
</footer>
"""
    with open(OUT, "w", encoding="utf-8") as fh:
        fh.write(doc)
    print("ok ->", OUT)


if __name__ == "__main__":
    main()
