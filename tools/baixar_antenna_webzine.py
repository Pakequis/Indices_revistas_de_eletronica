#!/usr/bin/env python3
"""Download the Antenna Webzine editions missing from the local archive.

Reads revistaantenna.com.br/edicoes/, finds each monthly edition page and its
PDF, and saves it as "Antenna Webzine AAAA-MM.pdf" in the archive folder.
Skips months already present.

Usage: baixar_antenna_webzine.py [JOBS] [--dry]   (JOBS defaults to 4, to be
gentle with the site)
"""
import re, sys, os, html, urllib.request
from concurrent.futures import ThreadPoolExecutor
UA = {"User-Agent": "Mozilla/5.0 (X11; Linux x86_64; rv:130.0) Gecko/20100101 Firefox/130.0"}
DEST = "/run/media/rodrigo/Backup-4tb/revistas/Antenna 2020"
MESES = ["janeiro","fevereiro","março","abril","maio","junho","julho","agosto","setembro","outubro","novembro","dezembro"]
def get(url, binary=False):
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=60) as r:
        d = r.read()
    return d if binary else d.decode("utf-8", "ignore")
def listing():
    t = get("https://revistaantenna.com.br/edicoes/")
    body = re.sub(r"<(script|style)[^>]*>.*?</\1>", "", t, flags=re.S)
    out = {}
    for h, tx in re.findall(r'<a [^>]*href="(https?://revistaantenna\.com\.br/[^"]+)"[^>]*>(.*?)</a>', body, re.S):
        tx = html.unescape(re.sub(r"<[^>]+>", " ", tx)); tx = re.sub(r"\s+", " ", tx).strip().lower()
        m = re.match(r"^(%s) (\d{4})" % "|".join(MESES), tx)
        if m:
            out[(int(m.group(2)), MESES.index(m.group(1)) + 1)] = h
    return out
def pdf_url(page):
    t = get(page)
    c = re.findall(r'https?://revistaantenna\.com\.br/wp-content/uploads/[^"\'\s?&]+\.pdf', t)
    c = [u for u in dict.fromkeys(c)]
    return c
def baixa(item):
    (y, m), page = item
    name = "Antenna Webzine %d-%02d.pdf" % (y, m)
    dest = os.path.join(DEST, name)
    if os.path.exists(dest) and os.path.getsize(dest) > 100000:
        return name, "ja existe"
    try:
        c = pdf_url(page)
        if not c: return name, "SEM PDF em " + page
        data = get(c[0], binary=True)
        if not data.startswith(b"%PDF"): return name, "NAO E PDF " + c[0]
        tmp = dest + ".part"
        open(tmp, "wb").write(data); os.replace(tmp, dest)
        return name, "ok %.1f MB %s" % (len(data)/1e6, c[0].rsplit("/", 1)[1])
    except Exception as e:
        return name, "ERRO %s" % e
if __name__ == "__main__":
    jobs = int(sys.argv[1]) if len(sys.argv) > 1 else 4
    dry = "--dry" in sys.argv
    L = listing()
    falt = {k: v for k, v in sorted(L.items()) if not os.path.exists(os.path.join(DEST, "Antenna Webzine %d-%02d.pdf" % k))}
    print("no site:", len(L), "| faltando local:", len(falt))
    for k, v in falt.items(): print(k, v)
    if dry: sys.exit()
    with ThreadPoolExecutor(jobs) as ex:
        for name, st in ex.map(baixa, list(falt.items())): print(name, "->", st, flush=True)
