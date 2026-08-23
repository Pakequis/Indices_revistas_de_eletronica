#!/usr/bin/env python3
"""Extrai o índice de uma edição de Eletrônica Total (ou Saber Eletrônica,
mesmo padrão de masthead da Editora Saber): localiza a página de índice
automaticamente (tools/localizar_indice.py), corta a partir da palavra
"índice" até o fim da página, e reaproveita o pipeline OCR+LLM de
tools/ocr_llm_parse.py pra separar título/página.

Diferença do ocr_llm_parse.py puro: aqui a Categoria NUNCA é escrita no
TSV de saída (o .csv desta revista não usa a coluna Categoria — todas as
2 mil+ linhas já existentes estão com Categoria em branco), mesmo que a
página tenha cabeçalhos de seção.

Uso:
    python3 tools/extrair_eletronica_total.py "edicao.pdf" --out /tmp/saida.tsv [--page N] [--yfrac F]

Sem --page/--yfrac, localiza automaticamente testando páginas 1-6.
"""
import argparse
import subprocess
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from ocr_llm_parse import (  # noqa: E402
    render_and_ocr, split_by_category, parse_lines, recover_glued_page,
    fix_page, clean_title, merge_paren_continuations, CATEGORY_HEADERS,
)
from localizar_indice import render as render_locate, ocr_tsv, find_keyword_y  # noqa: E402
from PIL import Image  # noqa: E402

ET_CATEGORY_HEADERS = {
    "seguranca eletronica": "x", "segurança eletrônica": "x",
    "tecnologia": "x", "microcontrolador": "x", "montagem": "x",
    "service": "x", "controle remoto": "x", "secoes": "x", "seções": "x",
    "solucoes praticas": "x", "soluções práticas": "x",
    "audio": "x", "áudio": "x", "informatica": "x", "informática": "x",
    "telefonia": "x", "robotica": "x", "robótica": "x",
    "automacao": "x", "automação": "x", "kit do leitor": "x",
}


def locate(pdf: str, page_range: tuple[int, int] = (1, 6), dpis: tuple[int, ...] = (100, 120, 200, 150, 300)):
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        for page in range(page_range[0], page_range[1] + 1):
            for dpi in dpis:
                png = render_locate(pdf, page, dpi, tmp_path)
                if png is None:
                    continue
                im = Image.open(png)
                h = im.size[1]
                tsv = ocr_tsv(png)
                yfrac = find_keyword_y(tsv, h)
                if yfrac is not None:
                    return page, yfrac
    return None, None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("pdf")
    ap.add_argument("--out", required=True, type=Path)
    ap.add_argument("--page", type=int)
    ap.add_argument("--yfrac", type=float)
    ap.add_argument("--cols", default="0.22-0.65,0.60-0.98",
                     help="colunas horizontais 'esq-dir' separadas por vírgula, ex.: "
                          "'0.35-0.62,0.62-0.80,0.80-0.98' pra índice em 3 colunas")
    ap.add_argument("--bottom", type=float, default=0.97)
    args = ap.parse_args()

    page, yfrac = args.page, args.yfrac
    if page is None:
        page, yfrac = locate(args.pdf)
        if page is None:
            print("# ERRO: página de índice não localizada automaticamente — "
                  "use --page/--yfrac manual", file=sys.stderr)
            sys.exit(1)
        print(f"# localizado: página {page}, yfrac {yfrac:.3f}", file=sys.stderr)
    if yfrac is None:
        yfrac = 0.05

    top = max(0.02, yfrac - 0.03)

    col_crops = []
    for spec in args.cols.split(","):
        left, right = (float(x) for x in spec.split("-"))
        col_crops.append((left, top, right, args.bottom))

    # injeta cabeçalhos desta revista (sem sobrescrever os de Circuitos e
    # Informações, caso o processo importe os dois em algum outro contexto)
    CATEGORY_HEADERS.update(ET_CATEGORY_HEADERS)

    full_text_parts = []
    for crop in col_crops:
        full_text_parts.append(render_and_ocr(args.pdf, page, crop))

    rows: list[list[str]] = []
    for _cat, lines in split_by_category("\n".join(full_text_parts)):
        parsed = parse_lines(lines)
        for title, pg in parsed:
            title, pg = recover_glued_page(title, fix_page(pg))
            title = clean_title(title)
            if title:
                rows.append([title, "", pg])

    rows = merge_paren_continuations(rows)
    rows = [r for r in rows if r[0]]

    with open(args.out, "w", encoding="utf-8") as f:
        for title, cat, pg in rows:
            f.write(f"{title}\t{pg}\n")
    n_blank = sum(1 for r in rows if not r[2])
    print(f"# total: {len(rows)} linhas -> {args.out} ({n_blank} com página vazia)", file=sys.stderr)


if __name__ == "__main__":
    main()
