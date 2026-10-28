# Changelog

O que mudou no Transfermed, do mais novo para o mais antigo. O detalhe de cada verificação fica no `QA.md`.
As atualizações automáticas diárias do robô e do monitor não entram aqui (estão no histórico do Git).

## 28/10/2026 · Cópia antiga do site e Google
- **Sem versão velha na tela:** o HTML vem sempre da rede (sem a cópia do navegador), e o service worker novo
  assume na hora e apaga os caches antigos, mesmo que a cópia de algum arquivo falhe.
- **Checagem diária:** `qa/interacoes.mjs` clica em "Buscar pelo nome" e nos botões "Brasil" e dos estados e confere
  o service worker; falha vira issue `qualidade`.
- **Google:** título e descrição únicos em todas as páginas (editais da mesma faculdade levam o semestre e o número
  do edital) e schema.org do edital com a data de encerramento (`applicationDeadline`). O sitemap.xml e o
  robots.txt continuam gerados a cada atualização.

## 27/10/2026 · Mapa e robô
- **Mapa do início:** abre no Brasil inteiro, com atalhos para os estados cobertos logo abaixo.
- **Robô:** `python radar.py --faculdades id1 id2 ...` visita só as fichas escolhidas.

## 27/10/2026 · Rodada de melhoria 1
- **Mato Grosso do Sul:** 7 faculdades novas (177 no total): UFMS Campo Grande, UFGD, UEMS, Uniderp (Campo Grande,
  Dourados e Ponta Porã) e Unicesumar Corumbá, com histórico de 2026. As públicas têm aviso de como fazem a
  transferência (UEMS 2027: sem vaga de Medicina).
- **Histórico das faculdades:** o mais novo aparece primeiro mesmo quando falta a data de um edital.
- **Robô:** anexo (quadro de vagas, cronograma, calendário) não vira mais "edital novo".
- **Monitor:** passa a vigiar também os anexos de onde vieram datas e vagas (IDOMED e UFSJ); a UNILAGO (pedido
  contínuo, sem edital) deixa de gerar issue de conferência.

## 26/10/2026
- **Monitoramento contínuo:** monitor diário de editais e prazos (retratos das páginas e PDFs, prazos de 7 dias,
  datas incoerentes, editais para conferir), verificação diária de qualidade (testes, HTML, links, acessibilidade;
  Lighthouse semanal) e issues automáticas no GitHub, sem duplicar. Roteiro da rodada de melhoria em `MELHORIA.md`.
- **Bahia completa:** 31 faculdades novas (170 no total). Abertos: Unime, Pitágoras Eunápolis, IDOMED
  (Alagoinhas, Juazeiro e Ribeirão Preto, para quem estuda no Brasil e no exterior) e UNEX Itabuna.
  As 11 públicas da Bahia têm aviso de como fazem a transferência.
- **UFSJ:** quadro atualizado (São João del-Rei 5 vagas, Divinópolis 4).
- **Correções do QA:** aviso certo nas fichas com pendência (eram ~60 dizendo "falta descobrir"), mapa acessível a
  leitores de tela, botões e caixas maiores no celular, títulos que cabem no Google, HTML válido em todas as páginas,
  sites da UNIMAX, UNASP e UNIMAR corrigidos.

## 25/10/2026
- Todas as escolas médicas de SP e MG (39 → 139 faculdades) e busca por faculdade.
- Públicas de SP e MG conferidas; endereços corrigidos; o robô só aceita PDF que cita Medicina.
- Federais de MG: UFSJ aberta (até 29/10) publicada; UFOP, UFV, UFU e UFTM com aviso e histórico.
- Diagnóstico: só para Medicina; cidade repetida em vários estados não é mais adivinhada; quem estuda no exterior vê
  faculdades do exterior nas sugestões.
- Revisão de textos: linha do tempo calculada no dia da visita, vagas, fluxo contínuo, faculdade e resultado.
- Alertas por e-mail: formulário nunca falha em silêncio; teste real ponta a ponta.

## 24/10/2026
- Lançamento: radar de transferência de Medicina em www.transfermed.com.br, robô diário, diagnóstico, páginas de
  faculdade e de edital, calendário .ics e alertas por e-mail.
