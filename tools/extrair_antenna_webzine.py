#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Extrai o índice da Antenna Webzine (2020) do texto nativo do PDF.
Gera Indices/Antenna 2020.csv. Edição = AAAA-MM (do nome do arquivo)."""
import csv
import re
import subprocess
import sys
from pathlib import Path

SRC = Path("/run/media/rodrigo/B9A7D66C46B9B631/Projects/revistas/Antenna 2020")
OUT = Path("/run/media/rodrigo/B9A7D66C46B9B631/Projects/Indices_revistas_de_eletronica/Indices/Antenna 2020.csv")
HDR = ["Artigo:", "Autor:", "Página", "Edição:", "Categoria:", "Componentes:", "Notas:", "Data:"]
MESES = ["janeiro", "fevereiro", "março", "abril", "maio", "junho", "julho",
         "agosto", "setembro", "outubro", "novembro", "dezembro"]

ENTRY = re.compile(r"^\s*(\d{1,3})\s*[-–]?\s+(.+?)[\.\s]*\.{3,}\s*$")
ENTRY2 = re.compile(r"^\s*(\d{1,3})\s*[-–]?\s+([A-Za-zÀ-ÿ“].+)$")  # título que continua na linha seguinte


def text(pdf, first=None, last=None):
    cmd = ["pdftotext", "-layout"]
    if first: cmd += ["-f", str(first)]
    if last: cmd += ["-l", str(last)]
    cmd += [pdf, "-"]
    return subprocess.run(cmd, capture_output=True, text=True).stdout


def get_data(pdf, ym):
    y, mo = ym.split("-")
    return f"{MESES[int(mo)-1].capitalize()}/{y}"


def parse_sumario(pdf):
    t = text(pdf, 1, 4)
    lines = t.splitlines()
    # localizar SUMÁRIO
    start = next((i for i, l in enumerate(lines) if re.match(r"^\s*SUM[ÁA]RIO\s*$", l)), None)
    if start is None:
        return None
    rows = []
    i = start + 1
    pending_title = None
    pending_page = None
    blanks = 0
    while i < len(lines):
        l = lines[i]
        if not l.strip():
            blanks += 1
            if blanks > 6 and rows:
                break
            i += 1
            continue
        blanks = 0
        m = ENTRY.match(l)
        if m:
            pg, tit = int(m.group(1)), m.group(2).strip(" .–-")
            # título pode ter começado na linha anterior sem número? raro; tratamos simples
            rows.append([pg, clean(tit), ""])
            pending_title = None
            i += 1
            continue
        m2 = ENTRY2.match(l)
        if m2 and "...." not in l:
            # entrada cujo título continua abaixo (com os pontos)
            pg = int(m2.group(1)); rest = m2.group(2).strip()
            j = i + 1
            buf = [rest]
            while j < len(lines) and "..." not in lines[j] and lines[j].strip() and not ENTRY.match(lines[j]) and not ENTRY2.match(lines[j]):
                buf.append(lines[j].strip()); j += 1
            if j < len(lines) and "..." in lines[j]:
                buf.append(re.sub(r"[\.\s]*\.{3,}.*$", "", lines[j]).strip())
                rows.append([pg, clean(" ".join(x for x in buf if x)), ""])
                i = j + 1
                continue
        # linha de autor: vem logo após um item, indentada, sem número inicial
        if rows and not rows[-1][2] and re.match(r"^\s{6,}\S", l) and not re.match(r"^\s*\d", l):
            rows[-1][2] = clean_author(l)
            i += 1
            continue
        i += 1
    return rows


def clean(s):
    s = re.sub(r"\s+", " ", s).strip(" .–-")
    return s


def clean_author(s):
    s = re.sub(r"\s+", " ", s).strip()
    s = s.strip(" .*·–-–")
    s = re.sub(r"\*+$", "", s).strip()
    return s


# nºs sem página de índice (jul-out/2020) — reconstruídos das chamadas de capa
# e dos títulos de abertura. Página = pág. do PDF, exceto 2020-10 que tem
# numeração impressa (pág. do PDF = pág. impressa).
EARLY = {
 "2020-07": ("Julho/2020", [
   (5, "Eletrônica Básica: o que é a Eletrônica?", "Alfredo Manhães"),
   (13, "Eletrônica I: projetando um estágio seguidor de emissor (transistor bipolar de junção em coletor comum)", "Álvaro Neiva"),
   (31, "Análise do amplificador Cygnus PA1800D", "Marcelo Yared"),
   (46, "Engenharia de Áudio: distorções em medições de amplificadores Classe D - filtro AES-17", "Francisco Monteiro"),
   (62, "Uma pequena história, não oficial, do começo da Gradiente", "Marcelo Yared"),
   (71, "Você sabe o que são as Equações de Maxwell?", ""),
 ]),
 "2020-08": ("Agosto/2020", [
   (2, "Realimentação negativa em amplificadores", "João Yazbek"),
   (5, "Parâmetros de Thiele/Small para alto-falantes Novik", "Marcelo Yared"),
   (13, "Projeto de pré-amplificadores e equalizadores RIAA para toca-discos - Parte I", "Álvaro Neiva"),
   (19, "Análise do amplificador Polyvox PM 5000", "Marcelo Yared"),
   (29, "Projeto de fonte de alimentação em corrente contínua (conversor CA/CC) com regulador linear - Parte I", "Álvaro Neiva"),
   (43, "Alan Blumlein - o inventor do som estereofônico", "Marcelo Yared"),
 ]),
 "2020-09": ("Setembro/2020", [
   (2, "Palitar ou não palitar, eis a questão!", "Josué Paz"),
   (6, "(D)Efeito Doppler em alto-falantes", "Francisco Monteiro"),
   (21, "Potência de saída: uma guerra de números e siglas", "João Yazbek"),
   (27, "Análise do amplificador Gradiente A1", "Marcelo Yared"),
   (48, "Projeto de fonte de alimentação em corrente contínua (conversor CA/CC) com regulador linear - Parte II", "Álvaro Neiva"),
   (57, "Projeto de pré-amplificadores e equalizadores RIAA para toca-discos - Parte II", "Álvaro Neiva"),
 ]),
 "2020-10": ("Outubro/2020", [
   (4, "Como ligar um transformador 110/220 V sem identificação dos fios", "Paulo Brites"),
   (13, "Sobre o projeto de pré-amplificadores e equalizadores RIAA para toca-discos - Parte III", "Álvaro Neiva"),
   (36, "Amplificadores de potência: classes e especificações", "João Yazbek"),
   (43, "Análise do amplificador Gradiente HA-II", "Marcelo Yared"),
   (63, "Fundamentos de Eletrônica - Parte II", "Alfredo Manhães"),
   (72, "Transistores falsos: como reconhecê-los?", "Marcelo Yared"),
   (80, "Eletrônica I: projetando um estágio seguidor de fonte (FET em dreno comum)", "Álvaro Neiva"),
 ]),
}


def main():
    pdfs = sorted(SRC.glob("Antenna Webzine *.pdf"))
    allrows = []
    for ym, (data, items) in EARLY.items():
        for pg, tit, aut in items:
            nota = "Página da revista" if ym == "2020-10" else "Página do PDF (edição sem numeração impressa)"
            allrows.append([tit, aut, pg, ym, "", "", nota, data])
        print(f"  {ym} ({data}): {len(items)} matérias [reconstruído]", file=sys.stderr)
    for pdf in pdfs:
        ym = re.search(r"(\d{4}-\d{2})", pdf.name).group(1)
        data = get_data(str(pdf), ym)
        sm = parse_sumario(str(pdf))
        if sm is None:
            print(f"  {ym}: SEM SUMÁRIO ({len(sm) if sm else 0})", file=sys.stderr)
            continue
        for pg, tit, aut in sm:
            allrows.append([tit, aut, pg, ym, "", "", "", data])
        print(f"  {ym} ({data}): {len(sm)} matérias", file=sys.stderr)
    if len(sys.argv) > 1 and sys.argv[1] == "--write":
        with open(OUT, "w", newline="", encoding="utf-8") as f:
            c = csv.writer(f, lineterminator="\n")
            c.writerow(HDR)
            c.writerows(allrows)
        print(f"\n{OUT.name}: {len(allrows)} linhas")
    else:
        for r in allrows[:40]:
            print(r)
        print(f"... total {len(allrows)}")


if __name__ == "__main__":
    main()
