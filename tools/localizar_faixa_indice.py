#!/usr/bin/env python3
"""Localiza a faixa vertical (yfrac) do bloco de índice numa página que
mistura editorial + expediente + índice (caso de Eletrônica Total a partir
de ~ed.119), sem depender de achar a palavra "índice" por OCR (o selo é
gráfico, ilegível pro tesseract) e sem inspeção visual.

Estratégia: OCR de página inteira (psm 3, uma coluna lógica só, o próprio
tesseract já ordena por coluna), agrupa palavras em linhas (block/par/line),
e marca como "candidata a linha de índice" toda linha cujo último token seja
um número de 1-3 dígitos plausível (1-300) — texto de editorial normal
raramente termina assim. A faixa entre a primeira e a última candidata (com
uma margem) é o crop vertical a usar no pipeline de extração.

Uso:
    python3 tools/localizar_faixa_indice.py "edicao.pdf" 3
Saída (stderr): linhas candidatas encontradas, pra conferência rápida.
Saída (stdout): "yfrac_top\tyfrac_bottom" (vazio se não achou candidatas).
"""
import re
import subprocess
import sys
import tempfile
from pathlib import Path

from PIL import Image


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


def group_lines(tsv_text: str):
    """Retorna [(texto, top, bottom), ...] agrupando por (block,par,line)."""
    rows = [l.split("\t") for l in tsv_text.splitlines()[1:] if l.strip()]
    groups: dict[tuple, list] = {}
    for parts in rows:
        if len(parts) < 12:
            continue
        try:
            block, par, line = parts[2], parts[3], parts[4]
            top, height = int(parts[7]), int(parts[9])
        except (ValueError, IndexError):
            continue
        text = parts[11].strip()
        if not text:
            continue
        key = (block, par, line)
        groups.setdefault(key, {"words": [], "top": top, "bottom": top + height})
        groups[key]["words"].append(text)
        groups[key]["top"] = min(groups[key]["top"], top)
        groups[key]["bottom"] = max(groups[key]["bottom"], top + height)
    out = []
    for g in groups.values():
        out.append((" ".join(g["words"]), g["top"], g["bottom"]))
    return out


PAGE_LIKE = re.compile(r"^\d{1,3}$")


def is_index_line(text: str) -> bool:
    tokens = text.split()
    if not tokens:
        return False
    last = tokens[-1].strip(".,;:")
    if not PAGE_LIKE.fullmatch(last):
        return False
    n = int(last)
    if not (1 <= n <= 300):
        return False
    # precisa ter pelo menos 1 token de texto antes do número (título)
    return len(tokens) >= 2


def main():
    pdf = sys.argv[1]
    page = int(sys.argv[2])
    dpi = int(sys.argv[3]) if len(sys.argv) > 3 else 200

    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        png = render(pdf, page, dpi, tmp_path)
        if png is None:
            print("", file=sys.stdout)
            return
        im = Image.open(png)
        h = im.size[1]
        tsv = ocr_tsv(png)
        lines = group_lines(tsv)

    candidates = [(t, top, bot) for t, top, bot in lines if is_index_line(t)]
    candidates.sort(key=lambda x: x[1])
    for t, top, bot in candidates:
        print(f"# {top/h:.3f} {t}", file=sys.stderr)

    if not candidates:
        print("")
        return
    top_frac = max(0.0, candidates[0][1] / h - 0.02)
    bottom_frac = min(1.0, candidates[-1][2] / h + 0.02)
    print(f"{top_frac:.3f}\t{bottom_frac:.3f}")


if __name__ == "__main__":
    main()
