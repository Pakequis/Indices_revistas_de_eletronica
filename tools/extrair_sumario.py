#!/usr/bin/env python3
"""Renderiza uma página de um PDF e roda OCR local (Tesseract) nela.

Uso:
    python3 extrair_sumario.py "revista.pdf" 124
    python3 extrair_sumario.py "revista.pdf" 2 --crop 0.35,0.30,0.95,0.85
    python3 extrair_sumario.py "revista.pdf" 1 --dpi 300 --threshold 140 --debug-dir /tmp/debug

Faz: pdftoppm (render) -> Pillow (cinza + binarização) -> tesseract (OCR) -> stdout.
Não precisa de nenhuma biblioteca Python além do Pillow; usa os binários
`pdftoppm` e `tesseract` já instalados no sistema. Não gasta tokens de API.

--crop recebe frações (0 a 1) da página no formato left,top,right,bottom —
use para isolar só a caixa do índice/sumário e evitar que outros textos da
página (propaganda, expediente) atrapalhem o OCR. Sem --crop, roda na
página inteira.
"""
import argparse
import subprocess
import sys
import tempfile
from pathlib import Path

from PIL import Image, ImageOps


def render_page(pdf_path: str, page: int, dpi: int, out_dir: Path) -> Path:
    prefix = out_dir / "pg"
    subprocess.run(
        ["pdftoppm", "-png", "-r", str(dpi), "-f", str(page), "-l", str(page), pdf_path, str(prefix)],
        check=True,
    )
    candidates = sorted(out_dir.glob("pg-*.png"))
    if not candidates:
        raise RuntimeError("pdftoppm não gerou nenhuma imagem — confira o número da página e o caminho do PDF")
    return candidates[0]


def preprocess(png_path: Path, crop: tuple[float, float, float, float] | None, threshold: int, debug_dir: Path | None) -> Path:
    im = Image.open(png_path)
    if crop:
        w, h = im.size
        l, t, r, b = crop
        im = im.crop((int(w * l), int(h * t), int(w * r), int(h * b)))
    gray = ImageOps.autocontrast(im.convert("L"))
    bw = gray.point(lambda p: 255 if p > threshold else 0)
    out_path = png_path.with_name(png_path.stem + "-bw.png")
    bw.save(out_path)
    if debug_dir:
        debug_dir.mkdir(parents=True, exist_ok=True)
        im.save(debug_dir / "recorte.png")
        bw.save(debug_dir / "recorte-bw.png")
    return out_path


def run_ocr(image_path: Path, lang: str, psm: int) -> str:
    result = subprocess.run(
        ["tesseract", str(image_path), "stdout", "--psm", str(psm), "-l", lang],
        capture_output=True, text=True, check=True,
    )
    return result.stdout


def parse_crop(value: str) -> tuple[float, float, float, float]:
    parts = [float(x) for x in value.split(",")]
    if len(parts) != 4:
        raise argparse.ArgumentTypeError("--crop precisa de 4 números: left,top,right,bottom (frações de 0 a 1)")
    return tuple(parts)  # type: ignore[return-value]


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("pdf", help="caminho do PDF da edição")
    ap.add_argument("page", type=int, help="número da página dentro do PDF (1-indexed)")
    ap.add_argument("--dpi", type=int, default=300, help="resolução de render (padrão 300)")
    ap.add_argument("--crop", type=parse_crop, default=None, help="left,top,right,bottom em frações 0-1 da página")
    ap.add_argument("--threshold", type=int, default=140, help="limiar de binarização 0-255 (padrão 140)")
    ap.add_argument("--lang", default="por", help="idioma do tesseract (padrão por)")
    ap.add_argument("--psm", type=int, default=3, help="modo de segmentação do tesseract (padrão 3 — automático; psm 6 assume bloco uniforme e pode PULAR linhas inteiras em colunas com espaçamento irregular, ver docs/registro-indices.md)")
    ap.add_argument("--debug-dir", type=Path, default=None, help="se passado, salva as imagens intermediárias aí")
    args = ap.parse_args()

    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        png = render_page(args.pdf, args.page, args.dpi, tmp_path)
        bw = preprocess(png, args.crop, args.threshold, args.debug_dir)
        text = run_ocr(bw, args.lang, args.psm)

    sys.stdout.write(text)


if __name__ == "__main__":
    main()
