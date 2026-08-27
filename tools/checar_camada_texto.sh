#!/usr/bin/env bash
# Levantamento em massa: pra cada PDF de uma pasta, reporta nº de páginas,
# caracteres extraídos via pdftotext e se pdffonts acusa fonte embutida.
# Uso: tools/checar_camada_texto.sh "pasta/da/revista"
set -u
DIR="$1"
find "$DIR" -iname "*.pdf" | sort | while read -r f; do
  pages=$(pdfinfo "$f" 2>/dev/null | awk '/^Pages:/{print $2}')
  chars=$(pdftotext "$f" - 2>/dev/null | wc -c)
  fonts=$(pdffonts "$f" 2>/dev/null | tail -n +3 | wc -l)
  base=$(basename "$f")
  if [ -z "$pages" ] || [ "$pages" -eq 0 ]; then
    ratio="?"
  else
    ratio=$((chars / pages))
  fi
  echo -e "$base\tpaginas=$pages\tchars=$chars\tchars/pag=$ratio\tfontes=$fonts"
done
