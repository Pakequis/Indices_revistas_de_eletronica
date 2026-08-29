# Ferramentas locais de extração de índice (sem gastar tokens)

Scripts pra fazer a primeira passada da extração de índice/sumário
usando só OCR local (Tesseract), sem gastar tokens de API. Nasceram de
um teste comparado em 3 casos (Electron, Monitor de Rádio e TV, Saber
Eletrônica — ver `docs/registro-indices.md`):
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

## Índice em 2 colunas com muito ruído: `ocr_llm_parse.py`

Quando a página de índice tem 2 colunas e o OCR sai com "líder de
pontos" (....) lido como sequências de letras soltas ("c v r s z") em
vez de pontos — caso de Circuitos e Informações, por exemplo — o
`extrair_sumario.py`/`parsear_sumario.py` sozinhos não dão conta bem.
Pra esse caso existe `tools/ocr_llm_parse.py`, que soma OCR local com
um LLM local (Ollama, sem gastar tokens de API) pra separar
título/página e detectar categoria pelos cabeçalhos de seção.

Requer o servidor Ollama no ar (`localhost:11434`) com o modelo
`qwen2.5:7b-instruct` já baixado — ver a instalação em modo usuário
(sem sudo/systemd) descrita na memória do projeto ou reinstalar com o
script de instalação padrão do Ollama caso a máquina tenha mudado.

```
python3 tools/ocr_llm_parse.py "edicao.pdf" 5 6 7 --out /tmp/saida.tsv
```

Saída: TSV `Título<TAB>Categoria<TAB>Página`. Ainda erra uma fração
pequena de páginas genuinamente ambíguas (garboso demais mesmo pro
LLM) — nesses casos o campo Página fica vazio em vez de um número
inventado; vale rodar uma conferência por amostragem no resultado antes
de acrescentar ao `.csv` da revista, como já é prática no resto do
projeto.

## Edição sem página de índice: `gerar_folha_contato.py`

Quando a edição não tem página de índice/sumário nenhuma (ex.:
Circuito Fechado, Electron 26, Eletrônica Avançada, Revista Eletrônica
16/17/18), a extração exige ler a edição inteira página a página. Pra
não gastar uma leitura de imagem por página, `gerar_folha_contato.py`
monta folhas de contato (grade NxN configurável) a partir das páginas
renderizadas com `pdftoppm`, escrevendo o número de cada página na
célula correspondente:

```
pdftoppm -r 150 -png "edicao.pdf" /tmp/pag
python3 tools/gerar_folha_contato.py /tmp "pag" --grid 3 --width 900 --out /tmp/folhas
```

Uma grade 3×3 reduz em ~9x o número de imagens lidas. Use `--width`
maior (800-900) se o número de página impresso no rodapé ficar
ilegível na folha — em compensação, cada folha fica maior. **Não
confiar no número de página impresso pequeno sem conferir**: já
aconteceu de ler errado a um dígito de distância (6↔8) numa folha
compacta; na dúvida, abrir a página individual renderizada.

## Curso em fascículos com seções fixas: `extrair_epp.py`

Feito para a **Eletrônica Passo a Passo** (Abril, 1984): curso colecionável
sem página de sumário, com seções fixas de tarja colorida (`COMPONENTES`,
`MONTAGEM`, `INSTRUMENTAÇÃO`, `NOÇÕES TEÓRICAS`). Cada artigo abre numa
página com a tarja no alto + título em caixa-alta + uma frase-chamada em
itálico; as de continuação repetem a tarja sem título.

```
python3 tools/extrair_epp.py "revistas/.../epp25.pdf" 25 --dump --no-vlm
```

O modo `--dump` renderiza as páginas (`pdftoppm`), roda `tesseract -l por` e
imprime, por página, `PDFnn [Seção] <início do texto OCR>`. A partir desse
texto dá pra montar o índice: a tarja + a frase-chamada dizem onde cada
artigo começa, e o título quase sempre sai legível no OCR da página de
abertura. Sem `--dump` o script tenta montar o índice sozinho (com um
número de página impresso pela régua contínua `20*N - 11`), mas a detecção
de "abre artigo × continuação" ainda erra — o `--dump` + montagem manual do
`data.py` foi o que funcionou bem.

O modelo de visão local `qwen2.5vl:3b` foi testado como desempate para os
títulos em fonte decorativa que não saem no OCR e **não serve** — alucina
títulos plausíveis em vez de ler a imagem. Para esses poucos casos, o
fallback é uma conferência visual de um recorte só das faixas de título.

## Mapa de edições faltantes: `gerar_mapa_edicoes.py`

Não tem a ver com extração de índice — serve pra enxergar, revista por
revista, quais **edições ainda não têm PDF** no acervo. Gera
`docs/mapa-edicoes.html` com uma tabela estilo BINGO por revista: célula
azul = existe o PDF, célula branca = edição a procurar.

```
python3 tools/gerar_mapa_edicoes.py
```

Lê só os nomes dos arquivos `.pdf` em `revistas/` (nada é aberto). Rodar
de novo sempre que a pasta mudar. Revistas por data (Antenna) e por
biênio (Eletrônica Popular) ficam de fora; séries paralelas Fora de
Série / Especial não entram (ver `docs/plano-extracao-fora-de-serie.md`).
O intervalo e os totais conhecidos de cada revista estão na lista `CFG`
no topo do script — ajustar lá se algum total mudar.

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
