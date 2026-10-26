# Changelog

O que mudou no Transfermed, do mais novo para o mais antigo. O detalhe de cada verificação fica no `QA.md`.
As atualizações automáticas diárias do robô e do monitor não entram aqui (estão no histórico do Git).

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
