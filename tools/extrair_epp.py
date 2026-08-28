#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Extrai o índice de um fascículo da "Eletrônica Passo a Passo" (Abril, 1984).

A revista não tem página de sumário: é um curso com seções fixas
(COMPONENTES, MONTAGEM, INSTRUMENTAÇÃO, NOÇÕES TEÓRICAS). Cada artigo
começa numa página que traz, no alto, a tarja colorida da seção e, logo
abaixo, o título em caixa-alta seguido de uma frase-chamada em itálico.
As páginas de continuação repetem a tarja mas não trazem título novo.

Fluxo (100% local, sem API):
  1. pdftoppm renderiza as páginas (se ainda não existirem).
  2. tesseract (por) faz OCR de cada página.
  3. heurística acha as páginas que ABREM artigo (tarja + linha de título).
  4. qwen2.5vl:3b (Ollama local) só entra como desempate quando a tarja
     aparece mas o título não saiu legível no OCR.
  5. numeração impressa pela régua contínua da coleção:
     fascículo N  ->  primeira página de conteúdo = 20*N - 11.

Uso:
    python3 tools/extrair_epp.py "revistas/Eletronica Passo a Passo/epp25.pdf" 25
    python3 tools/extrair_epp.py .../epp25.pdf 25 --tsv /tmp/epp25.tsv --no-vlm

Saída TSV: pdf_pag  pagina_impressa  categoria  titulo  origem
(origem = ocr | vlm | ocr?  — "?" sinaliza título duvidoso p/ conferência)
"""
import argparse
import glob
import os
import re
import subprocess
import sys
import tempfile

OLLAMA = os.path.expanduser("~/.local/ollama-bin/bin/ollama")

BANNERS = {
    "COMPONENTES": "Componentes",
    "MONTAGEM": "Montagem",
    "INSTRUMENTACAO": "Instrumentação",
    "INSTRUMENTAÇÃO": "Instrumentação",
    "NOCOES TEORICAS": "Noções Teóricas",
    "NOÇÕES TEÓRICAS": "Noções Teóricas",
    "NOÇÕES TEORICAS": "Noções Teóricas",
    "NOCOES TEÓRICAS": "Noções Teóricas",
}

# linhas que parecem título mas não são
NOT_TITLE = re.compile(
    r"^(ALGUNS DOS|NO PR|COMPLETE|COLABORE|EDI[ÇC]|ABRIL|VICTOR|ELETR[OÔ]NICA\b|"
    r"PASSO A PASSO|KIT|PE[ÇC]A OS KITS|TABELA|FIGURA|ACIMA|ABAIXO|NESTA|NESTE)",
    re.I,
)


def norm(s):
    return (
        s.upper()
        .replace("Á", "A").replace("Â", "A").replace("Ã", "A").replace("À", "A")
        .replace("É", "E").replace("Ê", "E")
        .replace("Í", "I")
        .replace("Ó", "O").replace("Ô", "O").replace("Õ", "O")
        .replace("Ú", "U").replace("Ç", "C")
    )


def ocr(png, psm=6):
    r = subprocess.run(
        ["tesseract", png, "-", "-l", "por", "--psm", str(psm)],
        capture_output=True, text=True,
    )
    return r.stdout


def is_titleish(line):
    line = line.strip(" |—-_.·")
    if not (4 <= len(line) <= 60):
        return None
    letters = [c for c in line if c.isalpha()]
    if len(letters) < 3:
        return None
    up = sum(1 for c in letters if c.isupper()) / len(letters)
    if up < 0.7:
        return None
    if NOT_TITLE.match(line):
        return None
    # tira lixo de borda comum do OCR
    line = re.sub(r"\s*\|\s*$", "", line).strip()
    line = re.sub(r"^[A-Z]\s+(?=[A-Z])", "", line)  # "O MOTOR" ok, "l O MOTOR" -> ...
    return line


def find_banner(lines):
    for ln in lines[:4]:
        n = norm(ln)
        for key, cat in BANNERS.items():
            if norm(key) in n:
                return cat
    return None


def vlm_title(png_crop):
    prompt = (
        "Parte de cima de uma página de revista de eletrônica dos anos 80. "
        "Se a página ABRE um artigo, há uma faixa colorida com o nome da seção "
        "(COMPONENTES, MONTAGEM, INSTRUMENTAÇÃO ou NOÇÕES TEÓRICAS) e, logo abaixo, "
        "um TÍTULO grande em caixa-alta. Responda em UMA linha, sem explicar:\n"
        "TITULO=<o título grande exatamente como está escrito, ou NONE se a página "
        "não tiver um título grande (página de continuação)>"
    )
    r = subprocess.run(
        [OLLAMA, "run", "qwen2.5vl:3b", prompt, png_crop],
        capture_output=True, text=True,
    )
    m = re.search(r"TITULO\s*=\s*(.+)", r.stdout, re.I)
    if not m:
        return None
    t = m.group(1).strip().strip('"').strip()
    if not t or t.upper() == "NONE":
        return None
    return t


def crop_top(src, dst, frac=0.42, width=1200):
    from PIL import Image

    im = Image.open(src)
    w, h = im.size
    im = im.crop((0, 0, w, int(h * frac)))
    im = im.resize((width, int(width * im.height / im.width)))
    im.save(dst)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("pdf")
    ap.add_argument("edicao", type=int)
    ap.add_argument("--tsv", default="-")
    ap.add_argument("--dpi", type=int, default=150)
    ap.add_argument("--no-vlm", action="store_true")
    ap.add_argument("--dump", action="store_true",
                    help="imprime o miolo do OCR de cada página (p/ montar o índice à mão)")
    ap.add_argument("--workdir", default=None)
    args = ap.parse_args()

    wd = args.workdir or tempfile.mkdtemp(prefix=f"epp{args.edicao}_")
    os.makedirs(wd, exist_ok=True)
    pages = sorted(glob.glob(os.path.join(wd, "pg-*.png")),
                   key=lambda f: int(re.search(r"(\d+)\.png$", f).group(1)))
    if not pages:
        subprocess.run(["pdftoppm", "-r", str(args.dpi), "-png", args.pdf,
                        os.path.join(wd, "pg")], check=True)
        pages = sorted(glob.glob(os.path.join(wd, "pg-*.png")),
                       key=lambda f: int(re.search(r"(\d+)\.png$", f).group(1)))

    base = 20 * args.edicao - 11

    if args.dump:
        for png in pages:
            idx = int(re.search(r"(\d+)\.png$", png).group(1))
            lines = [l for l in (x.strip() for x in ocr(png).splitlines()) if l]
            cat = find_banner(lines) or "-"
            body = " ".join(lines[:8])
            body = re.sub(r"\s+", " ", body)[:260]
            print(f"PDF{idx:02d} [{cat}] {body}")
        print(f"# fascículo {args.edicao} | base impressa {base} | {len(pages)} pág PDF",
              file=sys.stderr)
        return

    starts = []  # (pdf_idx, categoria, titulo, origem)
    first_content_idx = None

    for png in pages:
        idx = int(re.search(r"(\d+)\.png$", png).group(1))
        text = ocr(png)
        lines = [l for l in (x.strip() for x in text.splitlines()) if l]
        cat = find_banner(lines)
        if not cat:
            continue
        # procura linha de título nas primeiras linhas (fora a que tem a tarja)
        title = None
        for ln in lines[:5]:
            if find_banner([ln]):
                continue
            t = is_titleish(ln)
            if t:
                title = t
                break
        origem = "ocr"
        if not title and not args.no_vlm:
            crop = os.path.join(wd, f"crop-{idx}.png")
            crop_top(png, crop)
            title = vlm_title(crop)
            origem = "vlm" if title else origem
        if not title:
            continue
        # dedupe: se o título é ~igual ao anterior, é continuação
        if starts and norm(re.sub(r"\s*\(\d+\)\s*$", "", title)) == \
                norm(re.sub(r"\s*\(\d+\)\s*$", "", starts[-1][2])):
            continue
        if first_content_idx is None:
            first_content_idx = idx
        # marca duvidoso se veio do OCR mas tem dígitos estranhos / muito curto
        if origem == "ocr" and (len(title) < 6 or re.search(r"\d(?!\)$)", title)):
            origem = "ocr?"
        starts.append((idx, cat, title, origem))

    out = sys.stdout if args.tsv == "-" else open(args.tsv, "w", encoding="utf-8")
    for idx, cat, title, origem in starts:
        pg = base + (idx - first_content_idx)
        print(f"{idx}\t{pg}\t{cat}\t{title}\t{origem}", file=out)
    if out is not sys.stdout:
        out.close()
    print(f"# {len(starts)} artigos | fascículo {args.edicao} "
          f"| pág. base {base} | 1ª pág. conteúdo = PDF {first_content_idx} "
          f"| wd={wd}", file=sys.stderr)


if __name__ == "__main__":
    main()
