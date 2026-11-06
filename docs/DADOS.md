# Dados do Transfermed: formato dos arquivos (contrato)

Este documento descreve o formato dos arquivos de `data/` que alimentam o site, os alertas e o relatório. O formato é um
**contrato estável**: o teste `tests/test_contrato_dados.py` falha se um campo obrigatório ou comum (presente em metade ou mais dos registros) sumir, mudar de nome ou de tipo; `null` (não informado) e int virando decimal não contam como quebra.
Campo novo e opcional é permitido (mudança aditiva). Mudar o formato de propósito exige rodar `python contrato.py --gravar`,
descrever a mudança aqui e subir a versão. O conteúdo de cada dado de edital só existe com a página do PDF oficial (`evidencias`);
o que é ambíguo fica como "conferir". Nada aqui contém dado pessoal de candidato ou de inscrito.

## Arquivos
- **faculdades.json** (lista): uma ficha por faculdade/câmpus: identificação, cidade e UF, tipo, site, páginas de editais que o robô visita, meses em que costuma abrir.
- **editais.json** (lista): um registro por edital. `fonte_dados` = `manual` (conferido à mão no PDF: publicável) ou `robo` (achado pelo robô, ainda não conferido: não é publicado). `evidencias` guarda a página do PDF de cada campo; `conferir_campos`, o motivo de cada dúvida; `versoes`, o que mudou em cada retificação. Edital encerrado nunca é apagado.
- **resultados.json** (lista): números agregados de seleções passadas (`vagas_ofertadas`, `inscritos`, `aprovados`), cada um com `valor`, `pagina` e `grandeza` (o que o número realmente é). Nunca nome, CPF ou e-mail.
- **situacao_resultados.json** (mapa edital → motivo): por que um edital não tem resultado público (confirmado).
- **arquivo_pdfs.json**: por documento, o hash (`sha256`), as versões anteriores e a cópia pública. Nunca apaga versão.
- **cobertura_emec.json** (mapa UF → contagens): cursos do e-MEC e quantos têm ficha.
- **retratos.json**: retrato diário das páginas de editais e dos PDFs vigiados, usado pelo monitor para achar troca silenciosa.
- **quarentena.json** (opcional): editais publicados cujo PDF mudou depois da última conferência; viram "conferir" até serem reconferidos.

Datas em `AAAA-MM-DD`. Os arquivos `docs/editais.json` e `docs/faculdades.json` são cópias de `data/`. O `docs/dados.js` é
uma montagem interna do site, **não** faz parte do contrato.

## Campos
<!-- contrato:inicio -->
Versão do contrato: 1.

### data/arquivo_pdfs.json (objeto)

| Campo | Tipo | Obrigatório |
|---|---|---|
| `atualizado_em` | str | sim |
| `documentos` | dict | sim |
| `documentos.*` | dict | não |
| `documentos.*.arquivado_em` | str | não |
| `documentos.*.bytes` | num | não |
| `documentos.*.copia_publica` | str | não |
| `documentos.*.editais` | list | não |
| `documentos.*.editais[]` | str | não |
| `documentos.*.erro` | str | não |
| `documentos.*.falhas_seguidas` | num | não |
| `documentos.*.nao_e_pdf` | bool | não |
| `documentos.*.primeiro_visto` | str | não |
| `documentos.*.sha256` | str | não |
| `documentos.*.tentativas_arquivo` | num | não |
| `documentos.*.ultimo_erro_em` | str | não |
| `documentos.*.ultimo_visto` | str | não |
| `documentos.*.url` | str | não |

### data/cobertura_emec.json (objeto)

| Campo | Tipo | Obrigatório |
|---|---|---|
| `*` | dict | não |
| `*.correspondentes` | num | não |
| `*.emec` | num | não |

### data/editais.json (lista)

| Campo | Tipo | Obrigatório |
|---|---|---|
| `aceita_curso_exterior` | bool ou null | não |
| `anexos` | list | não |
| `anexos[]` | str | não |
| `atualizado_em` | str | sim |
| `cidade_uf` | str | sim |
| `conferido_em` | str | não |
| `conferir_campos` | dict | não |
| `conferir_campos.*` | str | não |
| `contradicao` | bool | não |
| `contradicao_desde` | str | não |
| `criterio_selecao` | str | não |
| `data_matricula` | str | não |
| `data_matricula_fim` | str | não |
| `data_prova` | str | não |
| `data_resultado` | str | não |
| `detectado_em` | str | não |
| `documentos` | list | não |
| `documentos[]` | str | não |
| `evidencias` | dict | sim |
| `evidencias.*` | num ou str | não |
| `exclui_quem_ja_transferiu` | bool ou null | não |
| `faculdade_id` | str | sim |
| `fluxo_continuo` | bool ou str | não |
| `fonte_dados` | str | sim |
| `id` | str | sim |
| `inscricao_fim` | str | não |
| `inscricao_inicio` | null ou str | não |
| `instituicao` | str | sim |
| `lat` | num | sim |
| `lon` | num | sim |
| `matricula_texto` | str | não |
| `modalidade` | str | sim |
| `numero_edital` | str | não |
| `observacao` | str | não |
| `outras_restricoes` | list | não |
| `outras_restricoes[]` | str | não |
| `prazo_divergente` | dict | não |
| `prazo_divergente.edital` | str | não |
| `prazo_divergente.edital_onde` | str | não |
| `prazo_divergente.pagina` | str | não |
| `prazo_divergente.url_pagina` | str | não |
| `quem_pode` | str | não |
| `resultado_texto` | str | não |
| `retificacoes` | list | não |
| `retificacoes[]` | str | não |
| `semestre_ingresso` | str | não |
| `situacao` | str | sim |
| `status` | str | sim |
| `taxa_inscricao` | null ou num | não |
| `tipo` | str | sim |
| `url_edital` | str | sim |
| `vagas` | list | não |
| `vagas[]` | dict | não |
| `vagas[].semestre` | str | não |
| `vagas[].vagas` | null ou num | não |
| `vagas_texto` | list | não |
| `vagas_texto[]` | str | não |
| `versoes` | list | não |
| `versoes[]` | dict | não |
| `versoes[].em` | str | não |
| `versoes[].motivo` | str | não |
| `versoes[].mudou` | dict | não |
| `versoes[].mudou.aceita_curso_exterior` | list | não |
| `versoes[].mudou.aceita_curso_exterior[]` | bool ou null | não |
| `versoes[].mudou.data_prova` | list | não |
| `versoes[].mudou.data_prova[]` | null ou str | não |
| `versoes[].mudou.numero_edital` | list | não |
| `versoes[].mudou.numero_edital[]` | str | não |
| `versoes[].mudou.taxa_inscricao` | list | não |
| `versoes[].mudou.taxa_inscricao[]` | null ou num | não |

### data/faculdades.json (lista)

| Campo | Tipo | Obrigatório |
|---|---|---|
| `aceita_exterior` | str | sim |
| `api_noticias` | dict | não |
| `api_noticias.anexo` | str | não |
| `api_noticias.detalhe` | str | não |
| `api_noticias.lista` | str | não |
| `aviso_publico` | str | não |
| `cidade` | str | sim |
| `econrio_palavras` | list | não |
| `econrio_palavras[]` | str | não |
| `excluir_links` | str | não |
| `exigir_links` | str | não |
| `exigir_texto` | str | não |
| `id` | str | sim |
| `lat` | num | sim |
| `lon` | num | sim |
| `medicina_confirmada` | bool | sim |
| `meses_costuma_abrir` | list | sim |
| `meses_costuma_abrir[]` | num | não |
| `modalidades_costuma_abrir` | list | sim |
| `modalidades_costuma_abrir[]` | str | não |
| `nome` | str | sim |
| `observacoes` | str | sim |
| `paginas_editais` | list | sim |
| `paginas_editais[]` | str | não |
| `pendente` | str | não |
| `prioridade` | str | não |
| `sigla` | str | sim |
| `site` | str | sim |
| `tipo` | str | sim |
| `uf` | str | sim |
| `ultima_conferencia` | str | sim |
| `wordpress` | str | não |

### data/faculdades_exterior.json (objeto)

| Campo | Tipo | Obrigatório |
|---|---|---|
| `_sobre` | str | sim |
| `faculdades` | list | sim |
| `faculdades[]` | dict | não |
| `faculdades[].nome` | str | não |
| `faculdades[].pais` | str | não |

### data/resultados.json (lista)

| Campo | Tipo | Obrigatório |
|---|---|---|
| `conferido_em` | str | sim |
| `edital_id` | str | sim |
| `faculdade_id` | str | sim |
| `fonte_url` | str | sim |
| `numeros` | dict | sim |
| `numeros.aprovados` | dict | não |
| `numeros.aprovados.grandeza` | str | não |
| `numeros.aprovados.pagina` | str | não |
| `numeros.aprovados.valor` | num | não |
| `numeros.inscritos` | dict | não |
| `numeros.inscritos.grandeza` | str | não |
| `numeros.inscritos.pagina` | str | não |
| `numeros.inscritos.valor` | num | não |
| `numeros.vagas_ofertadas` | dict | não |
| `numeros.vagas_ofertadas.grandeza` | str | não |
| `numeros.vagas_ofertadas.pagina` | str | não |
| `numeros.vagas_ofertadas.valor` | num | não |
| `ressalva` | str | sim |
| `status` | str | sim |

### data/retratos.json (objeto)

| Campo | Tipo | Obrigatório |
|---|---|---|
| `atualizado_em` | str | sim |
| `paginas` | dict | sim |
| `paginas.*` | dict | não |
| `paginas.*.falhas_seguidas` | num | não |
| `paginas.*.hash` | str | não |
| `paginas.*.links` | list | não |
| `paginas.*.links[]` | str | não |
| `paginas.*.ultimo_erro` | str | não |
| `paginas.*.ultimo_ok` | str | não |
| `paginas.*.verificado_em` | str | não |
| `pdfs` | dict | sim |
| `pdfs.*` | dict | não |
| `pdfs.*.falhas_seguidas` | num | não |
| `pdfs.*.hash` | str | não |
| `pdfs.*.ultimo_erro` | str | não |
| `pdfs.*.ultimo_ok` | str | não |
| `pdfs.*.verificado_em` | str | não |

### data/situacao_resultados.json (objeto)

| Campo | Tipo | Obrigatório |
|---|---|---|
| `*` | str | não |

<!-- contrato:fim -->
