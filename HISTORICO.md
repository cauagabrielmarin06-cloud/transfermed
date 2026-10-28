# Histórico de editais e previsão de abertura

Preparação técnica de 28/10/2026. Nada aqui muda o site nem os dados dos editais. Ferramenta: `historico.py`
(só lê a base).

## 1. O que cada edital precisa guardar para sempre
| Item | Onde fica hoje | Situação |
|---|---|---|
| Datas de cada etapa | `inscricao_inicio`, `inscricao_fim`, `data_prova` | **Incompleto:** não há campo para resultado, recurso, matrícula nem entrega de documentos. |
| Vagas | `vagas` (por semestre) e `vagas_texto` | 70 de 77 conferidos. |
| Requisitos | `quem_pode`, `outras_restricoes`, `exclui_quem_ja_transferiu`, `aceita_curso_exterior` | `quem_pode` em 58 de 77. |
| Taxa | `taxa_inscricao` | 64 de 77 (alguns editais não citam taxa, e isso fica em `observacao`). |
| Documentos | `documentos` | **27 de 77.** O site usa uma lista genérica quando falta. |
| Formato da seleção | `criterio_selecao` (texto) | 75 de 77, mas em texto livre: não dá para filtrar "só análise de histórico". |
| Retificações | `retificacoes` (lista de links) | **Os valores antigos se perdem:** ao reconferir, o dado novo substitui o antigo, e só o histórico do Git guarda a versão anterior. |
| Página do PDF de cada dado | `evidencias` | 71 de 77. |
| O próprio PDF | `data/retratos.json` (hash) | **Só dos editais em andamento**, e só desde 26/10. 52 conferidos (os encerrados) não têm retrato. Se a faculdade tirar o PDF do ar, a fonte some. |

`python historico.py --auditar` lista, edital por edital, o que falta. Em 28/10: **15 de 77** completos.

Regra que já vale e deve continuar: **edital nunca é apagado** da base. Encerrado continua no histórico da
faculdade.

### Campos propostos (sem quebrar o que existe)
```json
"etapas": [
  {"tipo": "inscricao", "inicio": "2026-10-01", "fim": "2026-10-29", "pagina": 3},
  {"tipo": "prova", "inicio": "2026-11-08", "pagina": 4},
  {"tipo": "resultado", "inicio": "2026-11-19", "pagina": 4},
  {"tipo": "matricula", "inicio": "2026-11-23", "fim": "2026-11-27", "pagina": 5}
],
"formato_selecao": {"prova": true, "analise_historico": false, "entrevista": false},
"versoes": [
  {"em": "2026-10-20", "motivo": "retificação 1", "url": "https://...", "mudou": {"inscricao_fim": ["2026-10-22", "2026-10-29"]}}
],
"arquivo": {"sha256": "c7fe...", "bytes": 482113, "arquivado_em": "2026-10-28", "copia_publica": "https://web.archive.org/web/..."}
```
`inscricao_inicio` e `inscricao_fim` continuam existindo (o site, os alertas e o monitor usam), copiados da etapa
`inscricao`. `tipo` aceita: `inscricao`, `entrega_documentos`, `prova`, `entrevista`, `resultado`, `recurso`,
`matricula`.

### Em sessões de trabalho
1. **Arquivo do PDF** (P): o monitor retrata uma vez **todo** edital conferido, inclusive os encerrados, guarda o
   hash para sempre e pede uma cópia pública no Internet Archive ("Save Page Now"). Sem guardar PDFs no Git (pesaria
   o repositório).
2. **Versões** (P): ao reconferir um edital marcado `conferir`, um comando compara o antes e o depois e grava em
   `versoes` o que mudou. Teste: a retificação não apaga o valor antigo.
3. **Etapas e formato** (M): preencher `etapas` e `formato_selecao` nos 77 conferidos, lendo os PDFs (com a página
   de cada data). Depois, o robô passa a sugerir as etapas nos editais novos.

## 2. Previsão de abertura
`python historico.py --prever` (e `--salvar`, que grava `data/previsao_aberturas.json`; o site não usa ainda).

**Como calcula**
1. Usa só editais conferidos (`fonte_dados = manual`) com data de início das inscrições.
2. Agrupa por faculdade e tipo de ingresso (1º semestre, 2º semestre ou anual).
3. Mede a abertura em dias em relação ao começo do semestre de ingresso. Quando há várias chamadas no mesmo ciclo
   (a UB tem até 4), vale a primeira.
4. A previsão do próximo ciclo é uma **janela**: a mediana dos ciclos ± a maior entre 10 dias e (espalhamento ÷ 2 +
   5 dias).

**Confiança**
| Nível | Regra | Como aparece |
|---|---|---|
| Alta | 3 ciclos ou mais, abrindo com no máximo 30 dias de diferença entre eles | "Costuma abrir entre 01/08 e 20/08" |
| Média | 2 ciclos ou mais, com no máximo 45 dias de diferença | "Abriu perto de agosto nos últimos 2 anos" |
| Baixa | 1 ciclo, ou ciclos muito espalhados | "Abriu em agosto em 2026; ainda é cedo para prever" |
| Sem previsão | Nenhum edital conferido com data | Só os meses da ficha (`meses_costuma_abrir`), se houver, como "costuma abrir em". |

**Resultado em 28/10/2026:** 37 faculdades com previsão: **0 alta, 2 média e 43 baixa** (algumas faculdades têm
previsão para os dois semestres). A base tem só 2024 a 2026, com quase tudo a partir de 2025. A previsão só ganha
valor depois de mais 2 ciclos, ou se buscarmos editais antigos (2022 a 2024) nos sites das faculdades e no Internet
Archive. Essa busca de histórico é a tarefa que mais melhora a previsão.

**Regras para usar no site ou no Pro**
- Nunca mostrar como data certa. Sempre "costuma abrir", com o nível e a base ("com base em 3 ciclos: 2024.2,
  2025.2, 2026.2").
- Quando o edital sair, mostrar a previsão ao lado da data real (é assim que a confiança se mede e se ganha).
- Previsão errada por mais de 30 dias baixa a confiança daquela faculdade no ciclo seguinte.
