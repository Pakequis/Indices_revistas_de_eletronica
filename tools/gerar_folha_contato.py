#!/usr/bin/env python3
"""Monta folhas de contato (grade NxN) a partir de páginas de um PDF já
renderizadas com pdftoppm, escrevendo o número da página em cada célula.
Usado para localizar onde cada artigo começa em edições sem página de
índice/sumário (ex.: Circuito Fechado, Electron 26, Eletrônica Avançada),
reduzindo o número de imagens que precisam ser lidas.

Uso:
    pdftoppm -r 150 -png "edicao.pdf" /tmp/pag
    python3 tools/gerar_folha_contato.py /tmp "edicao_" --grid 3 --out /tmp/folhas
"""
import argparse
import glob
import os
import re

from PIL import Image, ImageDraw, ImageFont


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("pages_dir", help="pasta com as páginas renderizadas (pdftoppm -png)")
    ap.add_argument("prefix", help="prefixo dos arquivos gerados pelo pdftoppm (ex.: 'edicao_')")
    ap.add_argument("--grid", type=int, default=2, help="grade NxN por folha (padrão 2)")
    ap.add_argument("--out", required=True, help="pasta de saída das folhas de contato")
    ap.add_argument("--width", type=int, default=500, help="largura de cada célula em pixels")
    args = ap.parse_args()

    os.makedirs(args.out, exist_ok=True)

    files = sorted(
        glob.glob(os.path.join(args.pages_dir, f"{args.prefix}*.png")),
        key=lambda f: int(re.search(r"(\d+)\.png$", f).group(1)),
    )
    if not files:
        raise SystemExit(f"Nenhuma página encontrada em {args.pages_dir} com prefixo {args.prefix}")

    n = args.grid
    per_sheet = n * n
    cell_w = args.width
    font = ImageFont.load_default()

    for sheet_idx in range(0, len(files), per_sheet):
        chunk = files[sheet_idx : sheet_idx + per_sheet]
        first_img = Image.open(chunk[0])
        ratio = first_img.height / first_img.width
        cell_h = int(cell_w * ratio)

        sheet = Image.new("RGB", (cell_w * n, cell_h * n), "white")
        draw = ImageDraw.Draw(sheet)

        for i, path in enumerate(chunk):
            page_num = int(re.search(r"(\d+)\.png$", path).group(1))
            img = Image.open(path).resize((cell_w, cell_h))
            row, col = divmod(i, n)
            x, y = col * cell_w, row * cell_h
            sheet.paste(img, (x, y))
            label = str(page_num)
            draw.rectangle([x, y, x + 34, y + 16], fill="yellow")
            draw.text((x + 2, y + 2), label, fill="black", font=font)

        out_path = os.path.join(args.out, f"folha_{sheet_idx // per_sheet + 1:03d}.png")
        sheet.save(out_path)
        print(out_path)


if __name__ == "__main__":
    main()
