#!/usr/bin/env python3
"""Prepara a página de índice das revistas do IUB (ex.: página 4) para
extração com o mínimo de leitura visual possível.

A página do IUB tem duas fontes na mesma coluna direita:
  - Caixa "índice": lista todas as seções com página, no formato
    "Título .......... página" — mesmo padrão já resolvido por
    extrair_sumario.py/parsear_sumario.py.
  - "Destaques": números grandes decorativos + título real do artigo
    + parágrafo de descrição — o OCR não lê bem o número grande (é
    decorativo, não texto normal), então essa parte ainda precisa de
    conferência visual, mas não precisa ser lida em alta resolução.

Uso:
    python3 extrair_iub.py "edicao.pdf" 4 --out-dir /tmp/saida

Gera dentro de --out-dir:
    indice_ocr.txt   -> saída do parsear_sumario.py (Artigo,Página,Status)
                         já filtrada da caixa índice (via OCR, sem gastar
                         tokens de leitura visual).
    destaques.png    -> recorte só da coluna direita, em resolução baixa
                         (a única imagem que precisa ser lida visualmente,
                         bem menor que a página inteira).

Ajustar --crop se o recorte não pegar a coluna direita inteira (varia
pouco entre edições, mas o padrão cobre a maioria).
"""
import argparse
import csv
import io
import subprocess
import sys
from pathlib import Path

from PIL import Image, ImageOps

THIS_DIR = Path(__file__).resolve().parent


def render(pdf_path: str, page: int, dpi: int, out_dir: Path, tag: str) -> Path:
    prefix = out_dir / tag
    subprocess.run(
        ["pdftoppm", "-png", "-r", str(dpi), "-f", str(page), "-l", str(page), pdf_path, str(prefix)],
        check=True,
    )
    candidates = sorted(out_dir.glob(f"{tag}-*.png"))
    if not candidates:
        raise RuntimeError("pdftoppm não gerou imagem — confira página e caminho do PDF")
    return candidates[0]


def crop_right_column(img_path: Path, crop: tuple[float, float, float, float]) -> Image.Image:
    im = Image.open(img_path)
    w, h = im.size
    l, t, r, b = crop
    return im.crop((int(w * l), int(h * t), int(w * r), int(h * b)))


def ocr_one(image: Image.Image, out_dir: Path, tag: str, threshold: int, lang: str, psm: int) -> str:
    gray = ImageOps.autocontrast(image.convert("L"))
    bw = gray.point(lambda p: 255 if p > threshold else 0)
    bw_path = out_dir / f"_ocr_{tag}.png"
    bw.save(bw_path)
    ocr = subprocess.run(
        ["tesseract", str(bw_path), "stdout", "--psm", str(psm), "-l", lang],
        capture_output=True, text=True, check=True,
    )
    bw_path.unlink(missing_ok=True)
    return ocr.stdout


def run_ocr_and_parse(image: Image.Image, out_dir: Path, threshold: int, lang: str, psm: int, max_page_digits: int) -> str:
    # A caixa "índice" do IUB tem 2 colunas lado a lado. Rodar OCR na
    # imagem inteira faz o Tesseract juntar as duas colunas numa linha só
    # e a extração de página pega só o número da direita, perdendo o da
    # esquerda. Dividir a imagem ao meio (esquerda/direita) antes do OCR
    # resolve isso quase por completo.
    w, h = image.size
    left = image.crop((0, 0, w // 2, h))
    right = image.crop((w // 2, 0, w, h))
    text = ocr_one(left, out_dir, "L", threshold, lang, psm) + "\n" + ocr_one(right, out_dir, "R", threshold, lang, psm)
    parse = subprocess.run(
        ["python3", str(THIS_DIR / "parsear_sumario.py")],
        input=text, capture_output=True, text=True, check=True,
    )
    # Filtro extra: página com mais dígitos que o esperado geralmente é
    # lixo de OCR grudado (ex.: "Editorial" virar página "443" em vez de
    # "3") — marca pra revisão em vez de deixar passar como "ok".
    rows = list(csv.reader(io.StringIO(parse.stdout)))
    out_rows = [rows[0]] if rows else [["Artigo", "Página", "Status"]]
    for r in rows[1:]:
        titulo, pagina, status = r
        if status == "ok" and len(pagina) > max_page_digits:
            status = "revisar"
        out_rows.append([titulo, pagina, status])
    buf = io.StringIO()
    csv.writer(buf).writerows(out_rows)
    return buf.getvalue()


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("pdf")
    ap.add_argument("page", type=int)
    ap.add_argument("--out-dir", type=Path, required=True)
    ap.add_argument("--crop", default="0.37,0.02,1.0,0.97",
                     help="left,top,right,bottom em frações da página (padrão cobre a coluna direita)")
    ap.add_argument("--ocr-dpi", type=int, default=300, help="resolução para o recorte usado no OCR (padrão 300)")
    ap.add_argument("--visual-dpi", type=int, default=110, help="resolução do recorte pra leitura visual (padrão 110, bem mais barato)")
    ap.add_argument("--threshold", type=int, default=140)
    ap.add_argument("--lang", default="por")
    ap.add_argument("--psm", type=int, default=6)
    ap.add_argument("--max-page-digits", type=int, default=2, help="páginas com mais dígitos que isso viram 'revisar' (padrão 2, editions do IUB raramente passam de 99 págs.)")
    args = ap.parse_args()

    crop = tuple(float(x) for x in args.crop.split(","))
    args.out_dir.mkdir(parents=True, exist_ok=True)

    # Passada de alta resolução: só pra alimentar o OCR da caixa índice.
    hi_png = render(args.pdf, args.page, args.ocr_dpi, args.out_dir, "_hi")
    hi_crop = crop_right_column(hi_png, crop)
    parsed = run_ocr_and_parse(hi_crop, args.out_dir, args.threshold, args.lang, args.psm, args.max_page_digits)
    (args.out_dir / "indice_ocr.txt").write_text(parsed, encoding="utf-8")

    # Passada de baixa resolução: a imagem que efetivamente será lida visualmente.
    lo_png = render(args.pdf, args.page, args.visual_dpi, args.out_dir, "_lo")
    lo_crop = crop_right_column(lo_png, crop)
    lo_crop.save(args.out_dir / "destaques.png")

    for f in args.out_dir.glob("_hi-*.png"):
        f.unlink()
    for f in args.out_dir.glob("_lo-*.png"):
        f.unlink()
    (args.out_dir / "_ocr_bw.png").unlink(missing_ok=True)

    print(parsed, file=sys.stderr)
    print(f"destaques.png salvo em {args.out_dir / 'destaques.png'} ({lo_crop.size})", file=sys.stderr)


if __name__ == "__main__":
    main()
