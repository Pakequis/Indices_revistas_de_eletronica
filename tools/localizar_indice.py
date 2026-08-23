#!/usr/bin/env python3
"""Localiza automaticamente a página de índice/sumário dentro de um PDF de
edição, testando um intervalo de páginas com OCR rápido (baixa resolução,
sem LLM) e procurando a palavra "índice"/"sumário". Também tenta extrair
o número da edição e mês/ano a partir da página informada (tipicamente a
capa).

Uso:
    python3 tools/localizar_indice.py "edicao.pdf" [--pages 1-6]

Saída (stdout, uma linha por página testada):
    pagina<TAB>achou_palavra<TAB>y_frac_da_palavra_ou_vazio

`y_frac_da_palavra` é a fração vertical (0-1) do topo da palavra
"índice"/"sumário" encontrada nessa página — útil pra decidir onde
cortar o índice do resto da página (ex.: editorial acima).
"""
import argparse
import re
import subprocess
import sys
import tempfile
from pathlib import Path

from PIL import Image

KEYWORDS = ("indice", "índice", "sumario", "sumário")


def render(pdf: str, page: int, dpi: int, tmp_path: Path) -> Path:
    prefix = tmp_path / f"p{page}"
    subprocess.run(
        ["pdftoppm", "-png", "-r", str(dpi), "-f", str(page), "-l", str(page), pdf, str(prefix)],
        check=True, capture_output=True,
    )
    matches = sorted(tmp_path.glob(f"p{page}-*.png"))
    return matches[0] if matches else None


def ocr_tsv(png: Path) -> str:
    result = subprocess.run(
        ["tesseract", str(png), "stdout", "--psm", "3", "-l", "por", "tsv"],
        capture_output=True, text=True, check=True,
    )
    return result.stdout


def find_keyword_y(tsv_text: str, img_height: int) -> float | None:
    lines = tsv_text.splitlines()[1:]
    best_y = None
    for line in lines:
        parts = line.split("\t")
        if len(parts) < 12:
            continue
        text = parts[11].strip().lower()
        text_norm = text.replace("í", "i").replace("Í", "i")
        if any(k.replace("í", "i") in text_norm for k in KEYWORDS) and len(text) <= 12:
            top = int(parts[7])
            if best_y is None or top < best_y:
                best_y = top
    if best_y is None:
        return None
    return best_y / img_height


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("pdf")
    ap.add_argument("--pages", default="1-6", help="intervalo 'a-b' de páginas a testar")
    ap.add_argument("--dpi", type=int, default=120)
    args = ap.parse_args()

    a, b = (int(x) for x in args.pages.split("-"))

    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        for page in range(a, b + 1):
            png = render(args.pdf, page, args.dpi, tmp_path)
            if png is None:
                print(f"{page}\tERRO\t")
                continue
            im = Image.open(png)
            h = im.size[1]
            tsv = ocr_tsv(png)
            yfrac = find_keyword_y(tsv, h)
            achou = "sim" if yfrac is not None else "nao"
            print(f"{page}\t{achou}\t{yfrac if yfrac is not None else ''}")


if __name__ == "__main__":
    main()
