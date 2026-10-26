# QA: registro de conferências

## Fase 1 (24/10/2026)

### Dados: o que foi lido à mão

21 editais novos lidos direto dos PDFs oficiais, com a página de cada informação em `evidencias`:

| Faculdade | Editais |
|---|---|
| Universidade Brasil (Fernandópolis) | UB 034/2026 (2027.1, **aberto**), 027/2026, 024/2026, 017/2026 (2026.2), 028/2026 (**interna**, PDF escaneado lido por imagem) |
| FAMERP | GDG 051/2025 (ano letivo 2026) |
| UNIFUNEC | 2026-2 (+ Retificação I), 2026-1 (2 processos), 2025-1 |
| UNILAGO | sem edital: formulário contínuo de transferência |
| UNIFIPA | 41/2026 (5º ano 2027, **aberto**) |
| UNIUBE | Transferência 2027.1 (**aberto**) |
| UNOESTE Jaú e Guarujá | Portaria 24/2026 (2027.1, **aberto**; externa + outro curso da saúde/portador de diploma) |
| UNIFAI | 23/2026 e 36/2025 |
| FAMEMA | Edital 2024 (ano letivo 2025) |
| FacMais | Suplementar 01 ao Edital 08/2025 |

Os 21 editais antigos receberam `modalidade` (18 externa e 3 IDOMED como `exterior`, um por campus) e `faculdade_id`.

### Dados: reconferência de 3 editais sorteados

Sorteio feito por código (`random`). Quando o PDF sorteado estava inacessível, foi sorteado outro.

| Sorteado | Resultado |
|---|---|
| UB 028/2026 (interna) | Páginas 1 a 4, 7 e 8 relidas por imagem: tudo bate. Ambiguidade mantida ("8º semestre" no anexo). |
| UNITAU (Caraguatatuba e Cruzeiro) | **Falhou:** o PDF responde 403 (bloqueado) para o robô e no navegador. Os 2 registros foram para "conferir", com o motivo anotado. |
| FACSETE 05/2026 | Vagas, taxa e prazo batem. **Achados novos:** resultado final (18/06/2026) antes do preliminar (04/08/2026), e o texto diz "não se aplica a transferência externa". Status ok → **conferir**. |
| FUNCESI 04/2026 (substituto) | **Falhou:** 403 no robô e no navegador. Motivo anotado. |
| Estácio IDOMED 2026.2 (substituto) | Taxa, critério, exterior e requisitos batem. Datas e vagas por campus ficam em anexos que não estão no PDF, então o "conferir" está correto. |

### Dados: inconsistências encontradas nos próprios editais

- UB 034/2026: "65 (duzentas e vinte) vagas" e "1º ao 7º" (p. 2) contra a distribuição do 2º ao 7º (p. 9).
- FAMEMA 2024: cronograma com "21 e 22/11/2022" no meio de datas de 2024.
- UNOESTE 2027-1: "3 (duas Vagas)".
- UNIFUNEC 2026-2: a notícia do site diz 7º semestre, o edital diz 8º (vale o edital).

### Robô

- `python -m unittest discover tests`: 16 testes passando.
- 1ª execução: **travou** num PDF protegido por senha (UNICEPLAC). Correção: cada link é processado em
  `try/except`, e `cryptography` foi adicionada ao `requirements.txt`.
- Na 1ª execução também apareceram: duplicatas por "www" (SUPREMA), editais de 2024 fora da janela, edital de
  "demais cursos" (UNIFOR) e aditivos lidos como edital (UNEX). Correções: `chave_url`, `antigo_demais`,
  `EDITAL_GERAL` e `eh_retificacao`.
- 2ª execução: UNEX "Externa" classificada como interna, e retificações antigas marcando editais abertos.
  Correções: a modalidade usa primeiro o nome do link, e a retificação só marca o edital que ela cita (`cita_edital`).
- Editais lidos só por regras (sem IA) ficam sempre como "conferir". Exemplo real: a regra leu UNISA 59/2025
  (para 2026) como "2025.2".
- PDFs de campi que dividem o mesmo site (UNEX) agora vão para o campus certo (`exigir_links` / `excluir_links`).
- Execuções finais: 74 editais, 8 abertos, nenhuma página com erro. Uma nova rodada não acrescentou nada (sem duplicatas).

### Site (ajuste mínimo da Fase 1)

- Cada card mostra a modalidade e quem pode se inscrever, além de "conferido em" e o motivo quando está em "conferir".
- Edital interno só é compatível para quem é da mesma faculdade; edital de exterior, só para quem estuda fora.
- Textos vindos dos PDFs passam por escape de HTML.
- Testado em 375 px e 1280 px: sem texto cortado, sem rolagem lateral, console sem erros.
  Perfil de teste: Fernandópolis, 300 km, 2º semestre → 5 compatíveis abertos, começando pela UB (0 km).

### Pendências conhecidas

- Faculdades com Medicina confirmada, mas sem página de editais localizada: UNIFEV, FACERES, FACISB, FUNEPE,
  UFMS Três Lagoas, UFTM.
- Não confirmadas no site oficial (ficaram fora): UNIMAR e UNIFADAP (Dracena). A UNIP Rio Preto não aparece
  na lista de campi com Medicina, e a UFTM Iturama não tem Medicina.
- 32 editais achados pelo robô sem IA estão em "conferir" até alguém ler ou a `ANTHROPIC_API_KEY` ser configurada.
- Os 21 editais antigos ainda não têm a página do PDF de cada campo (`evidencias` vazio).

## Fase 2 (24/10/2026)

### O que foi feito

- Identidade: verde-petróleo #0F5C4D, fundos em cinza quente, âmbar só para prazo próximo, vermelho só para
  48 h ou "não se encaixa", verde claro para "pode se inscrever". Fonte Inter (Google Fonts, sem bloquear a página),
  logo SVG (radar + cruz). Modo escuro automático.
- Páginas geradas por `gerar_site.py`: início, diagnóstico em 4 etapas, estudo no exterior,
  39 páginas de faculdade e 74 de edital, cada edital com `prazos.ics`.
- Gatilhos só com dado real: prazo calculado das datas, vagas do edital, "conferido em" com link, sem cadastro.
  Não há prova social, porque ainda não existe número real para mostrar.
- Minha jornada (localStorage): perfil salvo, "N editais novos compatíveis desde a última visita",
  editais acompanhados, checklist com progresso, calendário com todos os prazos e botão "apagar meus dados".

### Verificações

| Verificação | Resultado |
|---|---|
| Diagnóstico de ponta a ponta (Fernandópolis, 300 km, 2º semestre) | 4 abertos compatíveis (UB, UNIUBE, UNOESTE Jaú, UNILAGO); previsão pelo histórico (FAMERP outubro, UNIFUNEC novembro) |
| **Falhou:** cidade não era reconhecida | A lista de municípios só carregava com o foco no campo. Agora carrega ao entrar na etapa, e a validação espera |
| **Falhou:** UNIFIPA aparecia como "costuma abrir em outubro" apesar de ter edital aberto | Faculdade com edital vivo (mesmo incompatível) não entra mais na previsão |
| **Falhou:** erro no console da página inicial (ordenação sem distância) | Corrigido; console limpo em início, diagnóstico, faculdade, edital e exterior |
| **Falhou:** menu marcava "Início" nas páginas internas; cabeçalho fixo alto demais no celular | Corrigido |
| Jornada: edital novo desde a última visita, acompanhado, checklist 1 de 3 | OK |
| `.ics`: 63 arquivos, linhas de no máximo 75 bytes (RFC 5545) | OK depois de adicionar a quebra de linha |
| 375 px e 1280 px, claro e escuro | Sem texto cortado, sem rolagem lateral |
| Testes do robô | 16 passando |
| Lighthouse | **Pendente:** precisa do Node.js instalado (aguardando autorização) |

## Fase 2, rodada "acima do profissional" (24/10/2026)

### Dados visíveis
- Regra nova: só editais conferidos à mão entram nas listas, no diagnóstico e nas páginas de edital. Os lidos só
  pelo robô ficam no histórico da faculdade com a etiqueta "não revisado: confira no PDF".
- Revisei à mão o único edital do robô que aparecia aberto: **UNIFOR 2027.1**. O robô errou: leu o fim das
  inscrições como 18/11, mas foram de 07 a 22/10/2026 (18/11 é o resultado). Agora aparece como encerrado.
- Revisei o UNEX 2027.1, que estava sem datas: está **aberto** (Feira de Santana até 08/03/2027, Jequié até 04/12/2026).
- Revisei os 10 editais anteriores da Universidade Brasil (2025.1 a 2026.1), com a página de cada informação.
- Resultado: 55 editais conferidos à mão e publicados; 20 do robô só no histórico (todos encerrados).

### Visual e recursos novos
- Mapa-radar com contorno real dos estados (dados abertos, 43 KB, em cache): cada faculdade é um ponto na cor da
  situação de hoje, com varredura de radar, visão "Interior de SP" ou "Brasil" e o marcador "você".
- Resultado do diagnóstico com painel-resumo (abertos, o mais perto, o prazo mais curto, o que deve abrir) e minimapa.
- Página do edital com linha do tempo (inscrição, hoje, fim, prova) e contagem regressiva.
- Prévia de compartilhamento (1200x630) para cada edital, faculdade e página geral; botão "Compartilhar"
  (WhatsApp ou copiar link). As imagens usam datas fixas e não mostram número de vagas contestado.
- Aplicativo instalável (manifest + ícones + service worker que funciona sem internet com a última versão vista).
- Fonte Inter hospedada no próprio site (sem enviar a visita para o Google).

### Verificações
| Verificação | Resultado |
|---|---|
| **Falhou:** contorno do Brasil não aparecia | O `<use>` do símbolo precisava de largura e altura (400). Corrigido |
| **Falhou:** rolagem lateral em tela muito estreita (262 px) | Faixa de números com `minmax(0,1fr)`. Corrigido |
| **Falhou:** pontos pequenos demais na visão Brasil | Tamanho proporcional à área visível |
| **Falhou:** página do edital "pulava" quando a fonte carregava (CLS 0,145) | Fonte hospedada e pré-carregada + fonte de reserva calibrada: CLS 0 |
| Prévia do WhatsApp mostrava "65 vagas" (número contestado) e "5 dias" (envelhece) | Corrigido: datas fixas e sem vagas contestadas |
| Lighthouse (Edge, celular e desktop) em início, diagnóstico, edital, faculdade e exterior | Desempenho 99-100, Acessibilidade 100, Boas práticas 100, SEO 100, CLS 0 |
| Console em início, diagnóstico, faculdade, editais UNEX/UNIFOR e exterior (aba nova) | Sem erros |
| Testes | 21 passando (robô + gerador) |

Observação: o Lighthouse rodou num servidor local sem compressão. No GitHub Pages (com compressão) o desempenho tende a ser igual ou melhor.

## Revisão crítica (24/10/2026)

Releitura de tudo o que foi pedido e entregue. O que estava errado e como foi corrigido:

| # | Problema | Correção |
|---|---|---|
| 1 | O site dizia "55 editais conferidos à mão", mas 17 (da sessão anterior) não tinham página do PDF e 14 traziam "lidos por IA" | Os 17 foram conferidos contra o PDF por script (valor a valor, com página): 12 bateram e ganharam `evidencias` e `conferido_em`. UniSALESIANO (PDF escaneado) foi conferido pela imagem, e a data da prova (26/01/2026) foi acrescentada. 5 não puderam ser reconferidos porque o site bloqueia acesso automático (UNITAU x2, FUNCESI, CEUNSP, UNIFRAN): ficaram com aviso e não contam como conferidos. O número no site agora é **50** |
| 2 | Vagas que o próprio edital contradiz apareciam como fato (UB 034: "65 (duzentas e vinte)"; UNOESTE: "3 (duas)") | O número saiu dos cards e das prévias; o aviso explica a contradição |
| 3 | Tipo (natureza jurídica) afirmado sem confirmação | Pesquisado: UNIFUNEC é pública municipal com mensalidade (FUNEC), UNIFAI é autarquia municipal, UNIFEV é privada comunitária sem fins lucrativos. FUNEPE e FACISB seguem "a conferir" |
| 4 | "39 faculdades monitoradas" exagerava | Agora: "39 faculdades na base (27 com o robô visitando todo dia)" |
| 5 | **Autonomia quebrada:** depois da última rodada, um edital novo achado pelo robô nunca aparecia no site sem revisão humana | O robô grava `detectado_em`. O site mostra "Novo edital detectado em dd/mm: dados ainda não conferidos" com o link oficial, sem afirmar datas ou vagas (60 dias) |
| 6 | Diagnóstico: digitar "UB" marcava a UNIUBE como "sua faculdade atual" | Comparação por sigla exata ou palavras distintivas (sem "universidade", "centro" etc.). Testado: "UB", "Universidade" e "Universidade de Uberaba" |
| 7 | UNILAGO (formulário, sem edital) contava como "edital aberto" | Seção própria "Sem edital: pedidos o ano todo", fora da contagem |
| 8 | Textos de prazo gravados nas páginas envelheciam | Recalculados no navegador no dia da visita |
| 9 | Lista de cidades vinha de repositório externo sem versão fixa | Copiada e compactada para `docs/assets/municipios.json` (5.571 municípios, 220 KB) |
| 10 | Mapa sempre no interior de SP | Com perfil salvo, a visão regional centra no aluno ("Perto de você") |
| 11 | Relatório de qualidade desatualizado | Robô completo rodado de novo; nova seção "Editais novos detectados" |
| 12 | 6 faculdades próximas sem editais | Pesquisadas: FACISB tem convocações de transferência em 2026.1 e 2026.2, mas os editais de abertura não ficam no site (pendência registrada). UNIFEV (último em 2015), FACERES, FUNEPE, UFMS e UFTM: nenhum edital de transferência de Medicina nos últimos 2 anos |

Verificação depois das correções: 24 testes passando; robô completo sem erro de página e sem alterar dados revisados;
console limpo (aba nova) em início, diagnóstico, faculdades, edital e exterior; Lighthouse 99-100 em todas as categorias, CLS 0.

Limitações conhecidas (não são erros, mas o usuário precisa saber):
- Sites que bloqueiam acesso automático (UNITAU, FUNCESI, CEUNSP, UNIFRAN) não podem ser monitorados pelo robô.
- Sem `ANTHROPIC_API_KEY`, o robô lê editais novos por regras simples; eles só ganham dados completos depois de revisados.
- As páginas de faculdade usam o identificador (ex.: `/faculdade/ub-fernandopolis/`), não só a sigla, porque a mesma sigla tem vários campi.
- O endereço canônico e as prévias apontam para www.transfermed.com.br, que ainda mostra o site antigo até a Fase 4.

## Fase 3 (24/10/2026)

### Escolhas (todas gratuitas)
- **Supabase (plano Free)** para guardar os alertas: Postgres com funções seguras. O site usa só a chave pública e
  só consegue inscrever, confirmar e descadastrar; nunca lê a lista de e-mails.
- **Brevo (plano Free, 300 e-mails/dia)** para enviar: permite começar com um remetente verificado, sem domínio
  próprio (o Resend exige domínio). Depois dá para autenticar o transfermed.com.br.
- **GitHub Actions a cada 30 min** (e logo depois do robô diário): confirmação + alertas.

### O que foi construído
- `supabase/schema.sql`: tabelas com RLS e sem acesso público; funções `inscrever`, `confirmar`, `descadastrar`
  (apaga tudo) e `total_alertas` (número agregado para prova social real, exibido só a partir de 10).
- `alertas.py`: dupla confirmação (reenvio no máximo 1 vez por dia), limpeza de cadastros não confirmados em 7 dias,
  alertas só com editais conferidos e compatíveis (mesma regra do diagnóstico, em Python) e editais novos detectados
  como "ainda não conferidos". Nunca repete o mesmo edital, respeita o limite diário e tem o cabeçalho
  List-Unsubscribe. Todo e-mail tem o link de descadastro.
- Site: formulário no resultado do diagnóstico (só e-mail, caixa de consentimento desmarcada, campo-armadilha
  contra robôs), páginas de confirmar e descadastrar (fora do Google), página de Privacidade (LGPD) e link no rodapé.
- SEO: dados estruturados (WebSite, Organization, BreadcrumbList, CollegeOrUniversity, WebPage), `sitemap.xml`
  com 98 páginas e `robots.txt`, gerados a cada execução.
- `PLANO_PAGO.md`: alerta antecipado, comparador e estimativa de aproveitamento (só documentado).

### Verificações
| Verificação | Resultado |
|---|---|
| `schema.sql` num Postgres real em memória (PGlite), 16 checagens | Todas ok: não duplica, valida e-mail e consentimento, chave pública não lê nem insere, descadastro apaga cadastro e histórico |
| Fluxo completo com um imitador local do Supabase (mesmo schema) | Formulário → e-mail de confirmação → link de confirmar no navegador → alerta com 3 editais → nada repetido → link de descadastrar → banco vazio |
| **Falhou:** acentos quebrados no e-mail | O HTML não declarava UTF-8. Corrigido e conferido visualmente |
| Formulário sem os serviços configurados | Fica desativado com aviso claro; o script de alertas só avisa e sai |
| Testes | 29 passando (robô, site, alertas) |
| Lighthouse (início, diagnóstico, privacidade, edital, faculdade) | 99-100 em todas as categorias, CLS 0; console sem erros |

### Pendente para ativar de verdade (Fase 4)
- Criar as contas no Supabase e no Brevo (com você) e cadastrar os segredos no GitHub (passo a passo no README).
- Definir o e-mail remetente e o e-mail de contato da página de privacidade.

## Fase 4: publicação (24 e 25/10/2026)

### No ar
- Repositório público `cauagabrielmarin06-cloud/transfermed`, GitHub Pages a partir de `main /docs`.
- Domínio próprio https://www.transfermed.com.br (Registro.br: 4 registros A do GitHub, CNAME `www`, TXT de
  verificação do GitHub). O endereço sem `www`, o `http://` e o `github.io` redirecionam; certificado HTTPS válido.
- Brevo com o domínio autenticado (DKIM e DMARC) e remetente `alertas@transfermed.com.br`.
- Supabase (São Paulo) com o `schema.sql` aplicado; segredos e variáveis cadastrados no GitHub.
- Robô diário rodando sozinho (rodada manual em 24/10 e agendada em 25/10, ambas com sucesso). Workflow de alertas
  a cada 30 min: 47 execuções, todas sem erro.

### Revisão crítica depois da publicação
| Achado | Correção |
|---|---|
| **Teste real do alerta:** a inscrição não chegou ao banco (todas as rodadas acharam 0 cadastros). A conexão do site com o banco e o formulário funcionam (testado no site real, sem gravar nada); a causa exata depende de saber que frase apareceu para a pessoa | Ver as linhas abaixo: os três jeitos de falhar em silêncio foram fechados, e o formulário agora sempre diz o que houve |
| O campo-armadilha contra robôs, se preenchido pelo preenchimento automático do navegador, descartava a inscrição **sem mensagem nenhuma** | Campo com nome que o navegador não reconhece, ignorado por gerenciadores de senha, e, se preenchido, a pessoa é avisada |
| Navegadores que bloqueiam o armazenamento (aba anônima, navegador do Instagram/WhatsApp) perdiam o perfil e a inscrição respondia "faça o diagnóstico primeiro" | Perfil guardado também em memória enquanto a página está aberta |
| Respostas inesperadas do banco viravam uma frase genérica | Cada resposta tem a sua frase; as desconhecidas mostram o código (sem dados pessoais) |
| A caixa de autorização ficava abaixo do botão, fácil de pular | Ordem: e-mail, autorização, botão |
| A caixa de alerta ficava no fim de uma página longa | Atalho no resumo do resultado, que rola até a caixa e põe o cursor no e-mail |
| O site prometia o e-mail "em até 30 minutos", mas o GitHub atrasa os agendamentos (intervalos de até 57 min observados) | "Em até 1 hora", com o remetente escrito para a pessoa procurar |
| A consulta que mantém a chave do Brevo ativa só rodava entre 9h00 e 9h29 UTC, e com os atrasos do GitHub não rodou em 25/10 | Roda em toda execução; o resultado (código HTTP) aparece no registro |
| Um envio com erro interrompia todos os outros da rodada, e o registro não mostrava quantos cadastros existiam | Cada envio é isolado (para depois de 3 erros); o resumo mostra pendentes, ativos e falhas, **sem e-mails** (o registro do GitHub é público); com falha o workflow fica vermelho e o GitHub avisa o dono por e-mail |
| Os calendários `.ics` mudavam a cada execução (carimbo de hora) | Carimbo fixo por edital |

### Verificações desta rodada
| Verificação | Resultado |
|---|---|
| Formulário (cópia local, envio interceptado): sucesso, campo-armadilha, perfil inválido, erro 500 | Frase certa em cada caso |
| Diagnóstico até o resultado em 375 px e 1280 px | Sem rolagem lateral; atalho e caixa de alerta funcionando |
| Console (início, diagnóstico, exterior, edital, faculdade, privacidade, confirmar) | Sem erros |
| Testes | 30 passando (novo: falha de envio não trava os outros e não vaza e-mail) |
| **Teste real, ponta a ponta (26/10)** | Inscrição pelo site → banco com 1 pendente → e-mail de confirmação enviado pelo Brevo e recebido → link clicado → banco com 1 ativo. Nenhum alerta saiu porque o perfil do teste não se encaixa em nenhum dos 9 editais abertos; o cruzamento foi conferido com 7 perfis variados (de 0 a 6 editais, iguais ao site) |

### Limitações conhecidas
- O e-mail de confirmação não sai na hora: depende do agendamento do GitHub (até ~1 h).
- A chave do Brevo vence em 1 ano: gerar outra e trocar o segredo `BREVO_API_KEY`.
- UNITAU, FUNCESI, CEUNSP e UNIFRAN bloqueiam robôs; 6 faculdades da região sem edital nos últimos 2 anos;
  SUPREMA ficou fora do ar na rodada de 25/10 (o robô tenta de novo todo dia).

## Ajuste: faculdade de quem estuda no exterior (26/10/2026)
| Achado | Correção |
|---|---|
| Quem marcava "estudo no exterior" via só faculdades brasileiras nas sugestões, com uma dica sobre transferência interna (que não se aplica) | A lista troca conforme a resposta: 38 universidades com Medicina no Paraguai, Bolívia, Argentina e Uruguai (`data/faculdades_exterior.json`, com o país no nome), exemplo e dica próprios. O campo continua aceitando qualquer nome e não muda o resultado |

Conferência: nomes tirados de reportagens e guias sobre brasileiros que estudam Medicina nesses países; os menos citados
(UNINTER e Universidad Nacional del Este) foram confirmados em documentos das próprias instituições. No navegador: a
troca funciona nos dois sentidos, o perfil salvo volta com a lista certa, o resultado de um perfil do exterior (3 editais)
bate com o cálculo dos alertas, 375 px sem rolagem lateral, console sem erros. Testes: 31 passando.

Teste no site real (26/10/2026), clicando como aluno do exterior: lista com as 38 sugestões e dica própria.
| Achado | Correção |
|---|---|
| **Falhou:** ao trocar "No exterior" ↔ "No Brasil" depois de escolher a faculdade, a escolha antiga ficava no campo. O perfil ficava incoerente, e uma faculdade brasileira esquecida no campo de quem estuda fora esconderia os editais dela | Ao trocar, a faculdade da outra lista sai do campo; um nome digitado livremente fica |

Conferido depois: as 4 combinações de troca; diagnóstico completo do exterior (UBA: 3 editais) e do Brasil (UB: 5, a
própria UB sai do resultado, igual ao cálculo dos alertas); nenhum nome do exterior se confunde com faculdade da base;
console sem erros.

## Revisão do diagnóstico: textos e cidade (26/10/2026)
| Achado | Correção |
|---|---|
| **Falhou:** "Rio Branco" virava Rio Branco - MT (não a capital do Acre), "Palmas" virava Palmas - PR e "Bom Jesus" pegava a primeira de cinco. A distância saía errada em milhares de km, sem aviso | Nome que existe em mais de um estado nunca é adivinhado: o site mostra as opções e pede para escolher. Aceita "Palmas TO", "palmas/to", sem acento e com hífen trocado; depois de reconhecer, escreve o nome oficial no campo |
| "Em qual cidade você mora (ou quer morar)?" era confuso: a cidade só serve para medir distância | "De qual cidade medimos a distância até as faculdades?", com dica explicando que pode ser onde mora ou onde está a família |
| A distância podia ser escolhida sem cidade (e não fazia nada) | Fica desligada até haver cidade, com o aviso "Escolha uma cidade acima para limitar a distância" |
| "Você prefere faculdade: Tanto faz / Pública / Particular" soava como preferência, mas é um filtro que esconde as outras | "Que tipo de faculdade serve para você? Pública ou particular / Só pública / Só particular" |
| Outros textos: "faculdade atual", "semestre", taxa sem moeda, pergunta da transferência sem motivo | Textos diretos; a taxa diz R$; "Alguns editais não aceitam quem já se transferiu uma vez" |
| E-mail de alerta dizia "perto de Fernandópolis" para quem escolheu qualquer distância, e omitia o filtro de tipo | "distâncias a partir de…" e "só faculdades públicas/particulares" |

Conferido: 10 nomes de cidade (inclusive repetidos, com UF, sem acento e inexistente) no navegador e no Node; diagnóstico
completo com Fernandópolis até 300 km (3 editais, igual ao cálculo dos alertas); 375 px sem rolagem lateral; console sem
erros; testes: 32 passando.
