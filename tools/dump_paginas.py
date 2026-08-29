#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Dump de OCR local, página a página, para revistas SEM página de sumário.

Pensado para as publicações da Editora Signo (Eletrônica Coletâneas,
Eletrônica Para Todos 1ª coleção, Rádio-TV Técnico, Mundo Eletrônico,
Circuito Fechado, Circuitos Integrados): o índice precisa ser
reconstruído página a página, cruzando com as chamadas da capa.

Fluxo 100% local (sem API):
  1. pdftoppm renderiza as páginas (se ainda não existirem no --workdir).
  2. tesseract -l por faz OCR de cada página (cache em .txt no workdir).
  3. imprime, por página: índice do PDF, um palpite de que a página ABRE
     um artigo (linha de título em caixa-alta no topo) e as primeiras
     linhas úteis do texto (assunto do artigo).

A numeração de página impressa NÃO é inferida aqui (raramente sai no OCR):
o offset PDF->impressa é decidido à mão a partir de poucas páginas.

Uso:
    python3 tools/dump_paginas.py "revistas/.../edicao.pdf" --workdir /tmp/ec13
    python3 tools/dump_paginas.py --workdir /tmp/ec13          # reaproveita PNG/txt
"""
import argparse
import glob
import multiprocessing
import os
import re
import subprocess
import sys

MEANINGLESS = re.compile(r"^[\W_]*$")

# ruído recorrente de anúncio/expediente da Editora Signo — não é título de artigo
AD_NOISE = re.compile(
    r"(EDITORA SIGNO|RUA GOIÁS|QUINTINO|CHINAGLIA|EM TODAS AS BANCAS|"
    r"PEDIDOS PARA|C\.?\s*POSTAL|CADASTRO|CR\$|REGISTRO DPF|DIRETOR|"
    r"DISTRIBUI|ORIENTAÇÃO TÉCNICA|ASSINATURA|REEMBOLSO|ATENÇÃO ASSINANTE|"
    r"^NO PRÓXIMO|^NESTE NÚMERO|FANZERES$|BARBOSA)",
    re.I,
)


def norm(s):
    tbl = str.maketrans("ÁÂÃÀÄÉÊËÍÎÓÔÕÖÚÛÇ", "AAAAAEEEIIOOOOUUC")
    return s.upper().translate(tbl)


def titleish(line):
    """Heurística: a linha parece um título de abertura de artigo?"""
    s = line.strip(" |—-_.·\"'")
    if not (4 <= len(s) <= 58):
        return False
    letters = [c for c in s if c.isalpha()]
    if len(letters) < 4:
        return False
    up = sum(1 for c in letters if c.isupper()) / len(letters)
    if up < 0.75:
        return False
    if AD_NOISE.search(norm(s)):
        return False
    if re.search(r"\d{3,}", s):          # números longos = tabela/anúncio
        return False
    return True


# tesseract usa OpenMP: sem este limite, N processos paralelos criam N*Ncpu
# threads e o load explode (oversubscription). 1 thread por processo + Pool.
_ENV = {**os.environ, "OMP_THREAD_LIMIT": "1"}


def ocr_page(png):
    txt = os.path.splitext(png)[0] + ".txt"
    if not os.path.exists(txt) or os.path.getsize(txt) == 0:
        r = subprocess.run(
            ["tesseract", png, "-", "-l", "por", "--psm", "3"],
            capture_output=True, text=True, env=_ENV,
        )
        with open(txt, "w", encoding="utf-8") as fh:
            fh.write(r.stdout)
    with open(txt, encoding="utf-8") as fh:
        return fh.read()


def page_idx(path):
    return int(re.search(r"(\d+)\.png$", path).group(1))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("pdf", nargs="?")
    ap.add_argument("--workdir", required=True)
    ap.add_argument("--dpi", type=int, default=150)
    ap.add_argument("--lines", type=int, default=7, help="linhas de corpo por página")
    args = ap.parse_args()

    os.makedirs(args.workdir, exist_ok=True)
    pages = sorted(glob.glob(os.path.join(args.workdir, "pg-*.png")), key=page_idx)
    if not pages:
        if not args.pdf:
            sys.exit("workdir vazio e nenhum PDF informado")
        subprocess.run(["pdftoppm", "-r", str(args.dpi), "-png", args.pdf,
                        os.path.join(args.workdir, "pg")], check=True)
        pages = sorted(glob.glob(os.path.join(args.workdir, "pg-*.png")), key=page_idx)

    with multiprocessing.Pool(min(10, len(pages))) as pool:
        texts = pool.map(ocr_page, pages)

    for png, text in zip(pages, texts):
        idx = page_idx(png)
        lines = [l.strip() for l in text.splitlines()
                 if l.strip() and not MEANINGLESS.match(l)]
        head = lines[:args.lines]
        flag = "  "
        for ln in head[:3]:
            if titleish(ln):
                flag = "T>"
                break
        body = re.sub(r"\s+", " ", " ".join(head))[:300]
        print(f"{flag} PDF{idx:03d} | {body}")

    print(f"# {len(pages)} páginas | workdir={args.workdir}", file=sys.stderr)


if __name__ == "__main__":
    main()
