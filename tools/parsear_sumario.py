#!/usr/bin/env python3
"""Converte o texto bruto do OCR (saída de extrair_sumario.py) em linhas
Artigo/Página, no formato que entra no .csv de Indices/.

Uso:
    python3 extrair_sumario.py revista.pdf 124 | python3 parsear_sumario.py
    python3 parsear_sumario.py --in texto_ocr.txt --out linhas.csv

Cada linha do índice normalmente vem como "Título .......... 42" (o líder
de pontos e o espaçamento variam e o OCR nunca reproduz isso de forma
perfeita). Este script:
  1. Ignora linhas vazias ou claramente não são item de índice (ex.:
     "ÍNDICE", "SUMÁRIO" sozinho).
  2. Extrai o número de página do final da linha.
  3. Limpa o título (remove pontos de preenchimento e lixo de OCR nas
     bordas).
  4. Marca como "revisar" toda linha sem um número de página plausível
     (1-999) no final — nesses casos o número provavelmente foi perdido
     pelo OCR (líder de pontos compacto demais, mancha/rabisco na página
     física, etc.) e precisa de conferência manual ou visual antes de
     entrar no .csv.

Isso NÃO substitui a revisão do plano de extração (docs/plano-extracao-
indices.md) — é só a primeira passada, pensada para reduzir a maior parte
do trabalho manual/de tokens, deixando só as linhas sinalizadas como
"revisar" para checagem visual.
"""
import argparse
import csv
import re
import sys

IGNORAR = re.compile(r"^(índice|indice|sumário|sumario)\W*$", re.IGNORECASE)
PAGINA_NO_FIM = re.compile(r"(\d{1,3})\s*[\.\|\!\]\s]*$")
LIXO_DE_PONTOS = re.compile(r"[\.\s·,\-–_]{2,}$")


def limpar_titulo(titulo: str) -> str:
    titulo = LIXO_DE_PONTOS.sub("", titulo).strip()
    titulo = re.sub(r"\s{2,}", " ", titulo)
    return titulo


def parsear_linha(linha: str) -> tuple[str, str, bool]:
    """Retorna (titulo, pagina, ok). ok=False quando precisa revisar."""
    m = PAGINA_NO_FIM.search(linha)
    if not m:
        return limpar_titulo(linha), "", False
    pagina = m.group(1)
    titulo = limpar_titulo(linha[: m.start()])
    if not titulo:
        return limpar_titulo(linha), "", False
    return titulo, pagina, True


def processar(texto: str):
    linhas_saida = []
    for linha_bruta in texto.splitlines():
        linha = linha_bruta.strip()
        if not linha or IGNORAR.match(linha):
            continue
        titulo, pagina, ok = parsear_linha(linha)
        if not titulo:
            continue
        linhas_saida.append((titulo, pagina, "ok" if ok else "revisar"))
    return linhas_saida


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--in", dest="entrada", default=None, help="arquivo de texto do OCR (padrão: stdin)")
    ap.add_argument("--out", dest="saida", default=None, help="arquivo .csv de saída (padrão: stdout)")
    args = ap.parse_args()

    texto = open(args.entrada, encoding="utf-8").read() if args.entrada else sys.stdin.read()
    linhas = processar(texto)

    saida = open(args.saida, "w", encoding="utf-8", newline="") if args.saida else sys.stdout
    writer = csv.writer(saida)
    writer.writerow(["Artigo", "Página", "Status"])
    for titulo, pagina, status in linhas:
        writer.writerow([titulo, pagina, status])
    if args.saida:
        saida.close()

    total = len(linhas)
    revisar = sum(1 for _, _, s in linhas if s == "revisar")
    print(f"{total} linhas, {revisar} para revisar ({total - revisar} ok)", file=sys.stderr)


if __name__ == "__main__":
    main()
