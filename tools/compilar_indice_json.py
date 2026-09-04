#!/usr/bin/env python3
"""Compila todos os CSVs de Indices/ num único JSON minificado para busca client-side.

Formato de saída: {"colunas": [...], "registros": [[...], [...], ...]}
Cada registro tem os mesmos campos na mesma ordem das colunas, evitando
repetir as chaves em cada objeto (o que infla bastante o tamanho do JSON).

Os CSVs são lidos por posição de coluna, não pelo nome do cabeçalho: o texto
dos cabeçalhos varia entre os arquivos (com ou sem dois-pontos, "Categoria"
vs "Categorias" etc.), mas a ordem das 8 colunas é sempre a mesma:
Artigo, Autor, Página, Edição, Categoria, Componentes, Notas, Data.

Todos os campos são mantidos como string: além de "Eletrônica Popular" e
"Antenna" (Edição no formato "volume,edição"), várias revistas têm Edição ou
Página não numéricas (faixas como "11-13", "Especial 1", "3ª Capa" etc.).
"""

import csv
import json
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
INDICES_DIR = BASE_DIR / "Indices"
OUTPUT_PATH = BASE_DIR / "dist" / "indice-compilado.json"

SKIP_FILES = {"modelo.csv"}
CAMPOS_CSV = ["Artigo", "Autor", "Página", "Edição", "Categoria", "Componentes", "Notas", "Data"]
COLUNAS = ["Revista"] + CAMPOS_CSV


def compilar():
    registros = []
    for path in sorted(INDICES_DIR.glob("*.csv")):
        if path.name in SKIP_FILES:
            continue
        revista = path.stem
        with path.open(encoding="utf-8-sig", newline="") as f:
            reader = csv.reader(f)
            next(reader, None)  # cabeçalho
            for row in reader:
                if not any(campo.strip() for campo in row):
                    continue
                if len(row) != len(CAMPOS_CSV):
                    raise ValueError(f"{path.name}: linha com {len(row)} campos (esperado {len(CAMPOS_CSV)}): {row}")
                registros.append([revista] + row)
    return registros


def main():
    registros = compilar()
    dados = {"colunas": COLUNAS, "registros": registros}

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with OUTPUT_PATH.open("w", encoding="utf-8") as f:
        json.dump(dados, f, ensure_ascii=False, separators=(",", ":"))

    tamanho_kb = OUTPUT_PATH.stat().st_size / 1024
    revistas = sorted({r[0] for r in registros})
    print(f"Registros: {len(registros)}")
    print(f"Revistas: {len(revistas)}")
    print(f"Arquivo: {OUTPUT_PATH.relative_to(BASE_DIR)} ({tamanho_kb:.1f} KB)")
    print(f"Exemplo: {registros[0]}")


if __name__ == "__main__":
    main()
