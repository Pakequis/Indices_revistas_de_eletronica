#!/usr/bin/env python3
"""Renderiza páginas de índice (2 colunas), roda OCR local e usa um LLM
local (Ollama) pra limpar o lixo de líder de pontos e separar título/página.

Não gasta tokens de API — tudo roda na máquina (tesseract + Ollama/GPU local).

Uso:
    python3 tools/ocr_llm_parse.py "revista.pdf" 5 6 7 --out /tmp/saida.tsv

Pré-requisito: servidor Ollama rodando em localhost:11434 com um modelo
puxado (ex.: `ollama pull qwen2.5:7b-instruct`). Ver docs/... ou o README
de tools/ pra como subir o Ollama sem systemd/sudo.

Saída: TSV Título<TAB>Categoria<TAB>Página (Categoria vazia se a página não
tiver cabeçalhos de seção reconhecíveis). Página fica vazia quando o OCR
não permite recuperar o número com confiança — nunca é inventada.
"""
import argparse
import json
import re
import subprocess
import sys
import tempfile
import urllib.request
from pathlib import Path

from PIL import Image, ImageOps

OLLAMA_URL = "http://localhost:11434/api/generate"
MODEL = "qwen2.5:7b-instruct"

CATEGORY_HEADERS = {
    "circuitos": "Circuitos",
    "fórmulas": "Fórmulas", "formulas": "Fórmulas",
    "componentes": "Componentes",
    "características de componentes": "Componentes",
    "caracteristicas de componentes": "Componentes",
    "tabelas e códigos": "Tabelas e Códigos", "tabelas e codigos": "Tabelas e Códigos",
    "informações diversas": "Informações Diversas", "informacoes diversas": "Informações Diversas",
    "informática": "Informática", "informatica": "Informática",
    "válvulas": "Válvulas", "valvulas": "Válvulas",
    "tabelas & códigos": "Tabelas e Códigos", "tabelas & codigos": "Tabelas e Códigos",
    "radioamadorismo": "Radioamadorismo",
    "a eletrônica no tempo": "A Eletrônica no Tempo", "a eletronica no tempo": "A Eletrônica no Tempo",
}

PROMPT_TEMPLATE = """Você limpa texto de OCR ruidoso de um índice de revista de eletrônica. Entre o título e o número de página impresso original havia um líder de pontos (....) que o OCR errou, virando sequências de letras como "c v r s z" ou dígitos trocados por letras parecidas (O/D/o -> 0, I/l -> 1, B -> 8, S -> 5).

Cada linha de entrada vem numerada "N: texto". Pra CADA N de entrada, produza EXATAMENTE UMA linha de saída no formato:
N|TITULO|PAGINA

Regras:
1. Remova todo o lixo de OCR do líder de pontos do título (pontos, "c", "v", "r", "s", "z" soltos), mas preserve o texto real do título.
2. O número de página é o ÚLTIMO token da linha, formado só por dígitos e/ou pelas letras O/D/o/I/l/B/S (nada mais). Converta essas letras pra dígito (O/D/o->0, I/l->1, B->8, S->5).
3. Se o último token contiver QUALQUER letra fora desse conjunto (Á,J,c,v,r,z,x etc.), ou se a linha não tiver nenhum número no fim, a página é ilegível/ausente: deixe PAGINA vazio. NUNCA invente um número. Proibido chutar.
4. Se a linha tiver DOIS números separados por espaço no final (ex: "...21 3"), o segundo é ruído solto — use o PRIMEIRO como página.
5. OBRIGATÓRIO: a saída tem que ter exatamente uma linha "N|..." pra cada N que apareceu na entrada, nunca pulando nenhum N, mesmo quando TITULO ou PAGINA ficam vazios. NUNCA junte duas entradas numeradas numa única linha de saída.
6. Não escreva nada além das linhas "N|TITULO|PAGINA", sem comentário nenhum.

Exemplo de entrada:
1: Amplificador (BD135/6) +... .... 13
2: Estabilizador 723. . . cc ccccco. DB?
3: Chave Estática Com Triac
4: (40429/40430) . ..............25

Exemplo de saída (note: linha 3 não tem página nenhuma no fim -> vazio; linha 4 é continuação de outro título mas mesmo assim vira sua própria linha, sem juntar com a 3):
1|Amplificador (BD135/6)|13
2|Estabilizador 723|
3|Chave Estática Com Triac|
4|(40429/40430)|25

Agora processe este texto:
{text}
"""


def render_and_ocr(pdf: str, page: int, crop: tuple[float, float, float, float], dpi: int = 300) -> str:
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        prefix = tmp_path / "pg"
        subprocess.run(
            ["pdftoppm", "-png", "-r", str(dpi), "-f", str(page), "-l", str(page), pdf, str(prefix)],
            check=True,
        )
        png = sorted(tmp_path.glob("pg-*.png"))[0]
        im = Image.open(png)
        w, h = im.size
        l, t, r, b = crop
        im = im.crop((int(w * l), int(h * t), int(w * r), int(h * b)))
        gray = ImageOps.autocontrast(im.convert("L"))
        bw = gray.point(lambda p: 255 if p > 140 else 0)
        bw_path = tmp_path / "bw.png"
        bw.save(bw_path)
        result = subprocess.run(
            ["tesseract", str(bw_path), "stdout", "--psm", "6", "-l", "por"],
            capture_output=True, text=True, check=True,
        )
        return result.stdout


def _is_all_caps_word_line(line: str) -> bool:
    """Linha só de letras maiúsculas/espaço (candidata a cabeçalho de
    categoria partido em 2 linhas pelo OCR, ex. 'CARACTERISTICAS' /
    'DE COMPONENTES')."""
    letters = re.sub(r"[^A-Za-zÀ-Úà-ú]", "", line)
    return bool(letters) and letters == letters.upper() and len(line) <= 40


def split_by_category(text: str) -> list[tuple[str, list[str]]]:
    """Retorna [(categoria, [linhas...]), ...]. Cabeçalhos de categoria que o
    OCR partiu em 2 linhas (tudo maiúsculo) são rejuntados antes de checar
    contra CATEGORY_HEADERS."""
    raw_lines = [l.strip() for l in text.splitlines() if l.strip()]
    # rejunta sequências CURTAS de linhas 100% maiúsculas (cabeçalho de
    # categoria que o OCR partiu em 2-3 linhas, ex. "CARACTERISTICAS" /
    # "DE COMPONENTES") — teste incremental, no máx. 3 linhas, pra não
    # engolir linhas de conteúdo que por acaso também saem 100% maiúsculas
    # (códigos de componente).
    MAX_HEADER_JOIN = 3
    lines: list[str] = []
    i = 0
    while i < len(raw_lines):
        if _is_all_caps_word_line(raw_lines[i]):
            matched = None
            buf = []
            for k in range(MAX_HEADER_JOIN):
                if i + k >= len(raw_lines) or not _is_all_caps_word_line(raw_lines[i + k]):
                    break
                buf.append(raw_lines[i + k])
                joined = " ".join(buf)
                if joined.lower().strip(" :") in CATEGORY_HEADERS:
                    matched = (joined, i + k + 1)
                    break
            if matched:
                lines.append(matched[0])
                i = matched[1]
                continue
        lines.append(raw_lines[i])
        i += 1

    chunks: list[tuple[str, list[str]]] = []
    cur_cat = ""
    cur_lines: list[str] = []
    for line in lines:
        # normaliza pontuação solta que o OCR às vezes gruda no cabeçalho
        # (ex. "CIRCUITOS (", "CIRCUITOS |") antes de comparar
        low = re.sub(r"[^\wà-úÀ-Ú ]+$", "", line.lower().strip(" :")).strip()
        matched_cat = CATEGORY_HEADERS.get(low)
        if matched_cat is None:
            for key, val in CATEGORY_HEADERS.items():
                if low.startswith(key) and len(low) <= len(key) + 3:
                    matched_cat = val
                    break
        if matched_cat is not None:
            if cur_lines:
                chunks.append((cur_cat, cur_lines))
            cur_cat = matched_cat
            cur_lines = []
            continue
        if line.upper() in ("LD NU", "ILE", "LI NU", "INDI", "CE", "INDICE", "ÍNDICE"):
            continue
        cur_lines.append(line)
    if cur_lines:
        chunks.append((cur_cat, cur_lines))
    return chunks


def call_llm_numbered(numbered_lines: list[str]) -> dict[int, tuple[str, str]]:
    """numbered_lines: linhas já no formato 'N: texto'. Retorna {N: (titulo, pagina)}."""
    prompt = PROMPT_TEMPLATE.format(text="\n".join(numbered_lines))
    data = json.dumps({
        "model": MODEL, "prompt": prompt, "stream": False,
        "options": {"temperature": 0.0, "num_predict": 4096, "num_ctx": 8192},
    }).encode()
    req = urllib.request.Request(OLLAMA_URL, data=data, headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=300) as r:
        resp = json.loads(r.read())
    out: dict[int, tuple[str, str]] = {}
    for line in resp["response"].splitlines():
        line = line.strip()
        if not line or "|" not in line:
            continue
        parts = line.split("|", 2)
        if len(parts) != 3:
            continue
        n_str, title, page = parts
        try:
            n = int(n_str.strip())
        except ValueError:
            continue
        out[n] = (title.strip(), page.strip())
    return out


def parse_lines(lines: list[str], batch: int = 35) -> list[tuple[str, str]]:
    """Manda `lines` (1-indexed internamente) pro LLM em lotes numerados.
    Qualquer índice que não voltar na resposta é reprocessado sozinho (retry
    individual) — garante que nenhuma linha de entrada é perdida em silêncio."""
    results: dict[int, tuple[str, str]] = {}
    for i in range(0, len(lines), batch):
        chunk = lines[i:i + batch]
        numbered = [f"{i + j + 1}: {l}" for j, l in enumerate(chunk)]
        got = call_llm_numbered(numbered)
        results.update(got)

    missing = [n for n in range(1, len(lines) + 1) if n not in results]
    for n in missing:
        got = call_llm_numbered([f"{n}: {lines[n - 1]}"])
        if n in got:
            results[n] = got[n]
        else:
            results[n] = (lines[n - 1], "")  # LLM falhou de novo: guarda a linha crua p/ conferência manual
            print(f"# aviso: linha {n} não resolvida pelo LLM nem no retry — texto cru mantido "
                  f"({lines[n - 1]!r})", file=sys.stderr)

    return [results[n] for n in range(1, len(lines) + 1)]


PAGE_CONFUSABLE = str.maketrans({"O": "0", "o": "0", "D": "0", "I": "1", "l": "1", "B": "8"})
_TITLE_PUNCT = ".,+<>«»'\""


def fix_page(page: str) -> str:
    """Normaliza confusões de OCR na página (O/D/o->0, I/l->1, B->8) e
    descarta o que não virar um número plausível de 1-3 dígitos."""
    p = page.strip()
    if " " in p:
        p = p.split()[0]  # 2 números soltos no fim: o 1o é a página, 2o é ruído
    p2 = p.translate(PAGE_CONFUSABLE)
    if re.fullmatch(r"\d{1,3}", p2) and 1 <= int(p2) <= 300:
        return str(int(p2))
    return ""


def _is_junk_token(tok: str) -> bool:
    core = tok.strip(_TITLE_PUNCT)
    if core == "":
        return True
    # token só de consoantes c/v/r/s/z (sem vogal) não existe em português
    # -> resíduo de líder de pontos; dígito solto também é resíduo (a
    # página real já foi extraída à parte)
    return bool(re.fullmatch(r"[cvrszCVRSZ]+", core)) or bool(re.fullmatch(r"\d{1,2}", core))


def recover_glued_page(title: str, page: str) -> tuple[str, str]:
    """Quando o LLM funde uma linha de continuação com a anterior, às vezes
    deixa PAGINA vazio e gruda o número no fim do próprio título (ex.:
    "Amplificadores Darlington (10/5BOW) 051"). Se página já veio
    preenchida, não mexe."""
    if page:
        return title, page
    tokens = title.rsplit(None, 1)
    if len(tokens) != 2:
        return title, page
    rest, last = tokens
    candidate = fix_page(last)
    if candidate:
        return rest.strip(), candidate
    return title, page


def clean_title(title: str) -> str:
    t = re.sub(r"-\s+(?=\w)", "", title)  # hífen de quebra de linha ("mo- tor" -> "motor")
    tokens = t.split(" ")
    while tokens and _is_junk_token(tokens[-1]):
        tokens.pop()
    t = " ".join(tokens).rstrip(",.")
    return re.sub(r"\s{2,}", " ", t).strip()


def merge_paren_continuations(rows: list[list[str]]) -> list[list[str]]:
    """Quando uma linha ficou sem página e a próxima começa com '(' (código
    de componente que estourou pra linha seguinte), junta as duas."""
    out = []
    i = 0
    while i < len(rows):
        title, cat, page = rows[i]
        if page == "" and i + 1 < len(rows) and rows[i + 1][0].startswith("("):
            ntitle, ncat, npage = rows[i + 1]
            out.append([f"{title} {ntitle}".strip(), cat, npage])
            i += 2
            continue
        out.append(rows[i])
        i += 1
    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("pdf")
    ap.add_argument("pages", type=int, nargs="+")
    ap.add_argument("--out", required=True, type=Path)
    ap.add_argument("--crop-esq", default="0.03,0.06,0.50,0.97")
    ap.add_argument("--crop-dir", default="0.50,0.06,0.98,0.97")
    args = ap.parse_args()
    crop_esq = tuple(float(x) for x in args.crop_esq.split(","))
    crop_dir = tuple(float(x) for x in args.crop_dir.split(","))

    full_text_parts = []
    for p in args.pages:
        for crop in (crop_esq, crop_dir):
            full_text_parts.append(render_and_ocr(args.pdf, p, crop))
            print(f"# OCR pág {p} ok", file=sys.stderr)

    rows: list[list[str]] = []
    for cat, lines in split_by_category("\n".join(full_text_parts)):
        parsed = parse_lines(lines)
        for title, page in parsed:
            title, page = recover_glued_page(title, fix_page(page))
            rows.append([clean_title(title), cat, page])

    rows = merge_paren_continuations(rows)
    rows = [r for r in rows if r[0]]  # descarta título vazio residual

    with open(args.out, "w", encoding="utf-8") as f:
        for title, cat, page in rows:
            f.write(f"{title}\t{cat}\t{page}\n")
    n_blank = sum(1 for r in rows if not r[2])
    print(f"# total: {len(rows)} linhas -> {args.out} ({n_blank} com página vazia, "
          f"conferir por amostragem)", file=sys.stderr)


if __name__ == "__main__":
    main()
