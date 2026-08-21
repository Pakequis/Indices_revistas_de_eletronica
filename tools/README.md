# Ferramentas locais de extração de índice (sem gastar tokens)

Scripts pra fazer a primeira passada da extração de índice/sumário
usando só OCR local (Tesseract), sem gastar tokens de API. Nasceram de
um teste comparado em 3 casos (Electron, Monitor de Rádio e TV, Saber
Eletrônica — ver `docs/registro-indices.md` na entrada de 2026-08-21):
em média **~80% das linhas saem 100% corretas** (título + número de
página); as outras ficam sinalizadas para conferência.

Cobre só o caso onde a revista **tem uma página de índice/sumário**
(compilada à parte ou em posição fixa/localizável dentro da edição).
**Não cobre** o caso de revista sem página de índice nenhuma (ex.:
Circuito Fechado, Electron edição 26) — esse ainda exige leitura
página a página com julgamento sobre onde cada artigo começa, o que
o OCR sozinho não resolve.

## Requisitos

Já instalados neste ambiente: `pdftoppm` (poppler), `tesseract` +
pacote de idioma `por`, Pillow (Python). Nenhuma dependência nova.

## Uso

1. Achar a página do índice dentro do PDF da edição (Fase 0 do plano
   já orienta onde procurar: perto do fim, antes de capa
   interna/contracapa; ou no início/capa, como no caso de Saber
   Eletrônica).

2. Rodar o OCR nela:

   ```
   python3 tools/extrair_sumario.py "caminho/da/edicao.pdf" 124
   ```

   Se a página tiver muito conteúdo além do índice (propaganda,
   expediente), recorte só a caixa do índice com `--crop
   left,top,right,bottom` (frações de 0 a 1 da página — dá pra
   estimar olhando a página renderizada uma vez):

   ```
   python3 tools/extrair_sumario.py "edicao.pdf" 2 --crop 0.34,0.29,0.94,0.76
   ```

3. Passar a saída pelo parser, que separa título/página e sinaliza o
   que precisa de revisão:

   ```
   python3 tools/extrair_sumario.py "edicao.pdf" 124 | python3 tools/parsear_sumario.py --out /tmp/linhas.csv
   ```

   O `.csv` de saída tem `Artigo,Página,Status` — linhas com
   `Status=revisar` são as que o OCR não conseguiu extrair um número
   de página plausível (geralmente por líder de pontos compacto
   demais, ou mancha/rabisco na página física cobrindo o número).

4. Conferir as linhas `revisar` olhando a imagem da página, ajustar
   manualmente, e só então acrescentar ao `.csv` da revista em
   `Indices/`, seguindo as regras fixas do
   `docs/plano-extracao-indices.md` (nunca alterar linha existente,
   conferir nome exato das colunas daquele arquivo, etc.).

## Limitações conhecidas (não resolvidas de propósito, pra manter simples)

- Títulos que ocupam duas linhas no índice original viram duas linhas
  separadas na saída (a primeira sem página, sinalizada `revisar`) —
  precisa juntar manualmente.
- O título pode sair com pequeno lixo de OCR nas bordas (pontuação
  perdida, 1 caractere trocado) mesmo nas linhas marcadas `ok` — vale
  uma conferência rápida por amostragem, como já previsto na Fase 3 do
  plano de extração.
- `--threshold` (padrão 140) pode precisar de ajuste em scans muito
  claros ou muito escurecidos — se o OCR sair vazio ou ilegível,
  tentar valores entre 120 e 160.
