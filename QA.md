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

## Revisão de textos e erros: início, edital, faculdade e resultado (26/10/2026)
| Onde | Achado | Correção |
|---|---|---|
| Edital | **Falhou:** o marcador "Hoje" e as etapas feitas/futuras da linha do tempo ficavam com a data em que o robô gerou a página (quem visitava no dia seguinte via o "Hoje" no lugar errado) | Recalculados no navegador no dia da visita |
| Edital | No último dia, o contador dizia "0 dias para o fim das inscrições"; depois do prazo continuava aparecendo; quando um marco era hoje, apareciam dois pontos ("Hoje" e o marco) | "Hoje: é o último dia de inscrição"; some depois do fim; o marco vira "Hoje · Último dia de inscrição" |
| Todos | "vagas no 2º ao 7º", "4 vagas · 2º · 1 vaga · 3º" | "vagas do 2º ao 7º", "4 vagas no 2º · 1 vaga no 3º"; sem número: "(quantidade: confira no edital)" |
| Cartões | Etiqueta "leia o aviso" sem dizer onde está o aviso | "tem aviso: veja o resumo" |
| Edital sem edital (fluxo contínuo) | Falava em "Confira no edital", "O edital não diz", "p. é a página do PDF", "Edital oficial" | Textos da página oficial e "confirme com a faculdade"; link "Página oficial" |
| Faculdade | Endereço cru na ficha (`?s=transfer%C3%AAncia`); "Aceite de quem estuda no exterior varia" | "página de editais (famerp.br)"; "Quem estuda no exterior: depende do edital" |
| Faculdade | Sem edital aberto, a página não dizia o que fazer | Link para o diagnóstico com aviso por e-mail |
| Faculdade | Faculdades sem edital recente mostravam "falta descobrir onde publica os editais" (errado: a página é conhecida) | Aviso com o motivo certo (sem edital em 2 anos; não lista os editais; página desconhecida) |
| Faculdade (Google) | "Transferência para Medicina na Centro Universitário…" | "no Centro Universitário…", "na Universidade…" |
| Resultado | "0 km de você" e "o mais perto: 0 km" | "na sua cidade" e "Na cidade" |
| Resultado | "Encerrados (24)" repetia a mesma faculdade 7 vezes | Só o último de cada faculdade e modalidade (12); o histórico completo fica na página da faculdade |
| Início | "4 perguntas curtas" (o diagnóstico fala em etapas) | "4 etapas curtas" |

Conferido: linha do tempo simulando 27/10, 29/10 e 30/10 no navegador; resultado com Fernandópolis até 600 km; 8 páginas
a 375 px sem rolagem lateral (tabelas rolam dentro da caixa); console sem erros; testes: 35 passando.

## Diagnóstico só para Medicina e arquivos sempre atualizados (26/10/2026)
| Achado | Correção |
|---|---|
| Pergunta "Qual curso você faz?" desnecessária por enquanto | Removida; o perfil vai sempre como Medicina (perfis antigos salvos com "outro curso" também viram Medicina). A lógica de outro curso continua no código para voltar no futuro |
| **Falhou:** o botão "Voltar" aparecia na etapa 1, e o contador do edital não sumia depois do prazo: o estilo dos botões e do contador passava por cima do "escondido" | Regra global: o que está escondido fica escondido |
| **Falhou:** depois de uma publicação, o navegador podia usar o estilo e o código antigos guardados (até 10 min), misturados com a página nova | Estilo, código e dados com versão no endereço (`?v=` com a impressão digital do conteúdo): mudou, o navegador baixa na hora |

Conferido: etapa 1 com uma pergunta, "Voltar" só a partir da etapa 2, perfil antigo "outro curso" vira Medicina,
contador escondido de verdade após o prazo (simulando 30/10), endereços com versão em todas as páginas; testes: 35 passando.

## Expansão: todas as escolas médicas de SP e MG + busca por faculdade (26/10/2026)

### Cobertura
- Lista de referência: portal Escolas Médicas do Brasil (425 escolas; 76 em SP e 53 em MG). O cadastro do MEC (e-MEC e
  dados abertos) bloqueia acesso automático com verificação anti-robô, por isso não foi usado.
- Erros da fonte corrigidos à mão: UNESP listada em "São Paulo" (é Botucatu), FAMECA duplicada (é a UNIFIPA), UNISEB
  (é o IDOMED Ribeirão Preto, já na base), Sírio-Libanês e UNINOVE Osasco listadas como públicas (são privadas).
  Faltava na fonte: UNINOVE Bauru. Confirmados por busca: Mackenzie Alphaville (Medicina desde 2025), São Judas Cubatão,
  UNASP Hortolândia (autorizado em 2024), Anhembi Piracicaba, UNIFADRA.
- **100 faculdades novas** (base de 39 para 139). Coordenadas do centro da cidade, da mesma lista de municípios do site.
- Varredura em 2 etapas (página inicial, caminhos comuns de transferência, busca interna e biblioteca do WordPress):
  61 fichas com página ou biblioteca para o robô; as outras ficam pendentes com o motivo (sem página achada, site que
  bloqueia ou não respondeu, ou página que carrega os editais por script, como Afya, rede Ânima, UNINOVE e PUC Minas).

### Robô e conferência
- 51 PDFs novos encontrados. **Falhou:** a leitura automática errou muitas datas e trouxe manuais, editais de matrícula,
  notícias e editais de 2024–2025; o site mostraria dezenas de "novo edital detectado" falsos, e o alerta por e-mail os
  enviaria. Correção: "novo" só com sinal de ser do ciclo atual (inscrição ainda não acabou, ingresso no próximo
  semestre ou PDF publicado nos últimos 60 dias). 14 documentos que não são edital foram tirados da base.
- Lidos à mão e publicados: **UNIFACCAMP 2027.1** (28/09/2026 a 12/03/2027; 20 vagas do 2º ao 8º período; por ordem de
  envio; não aceita curso no exterior) e **USF Bragança 2027.1** (Edital 45/2026; até 03/11/2026; 3 vagas; R$ 250;
  histórico + entrevista; aceita exterior).
- Conferidos e descartados (excluem Medicina): UNIVALE 117/2026, UFSCar 8/2026 (2027) e Uni-FACEF 2027. Anotado nas fichas.

### Busca por faculdade
- Lupa "Buscar" no topo de todas as páginas e atalho "Já sabe para qual faculdade quer ir?" no início. Busca por nome,
  sigla ou cidade (sem acento), mostra se há inscrições abertas e leva à página da faculdade. Enter abre a primeira,
  setas navegam, Esc fecha, "/" abre.
- Conferido: 8 buscas (sigla, cidade, nome composto, inexistente), Enter levando à página da USF, 375 px sem rolagem lateral.
- Histórico da faculdade: sem data de início, a coluna diz "até 03/11/2026" (antes mostrava só a data).
- Testes: 36 passando.

## Públicas de SP e MG e conferência dos endereços (26/10/2026)

### Endereços (pedido do usuário: "o site está errado")
- **Falhou:** fichas com site errado ou inexistente: UNIFADRA (unifadra.edu.br não existe; certo: fundec.edu.br/unifadra),
  Atenas Passos e Sete Lagoas (subdomínios inexistentes), UFJF Governador Valadares (página removida), FAM (domínio
  antigo), IDOMED x3 e UNITAU Caraguatatuba/Cruzeiro (sem site). Causa: os endereços da lista de referência não foram
  testados. Correção: teste automático dos 139 sites (abre? para onde vai? o título bate com a faculdade?) e das 124
  páginas que o robô visita; os casos duvidosos foram abertos no navegador. Ficaram fora do "ok" só sites que recusam
  robôs ou não respondem a esta rede, conferidos como certos (CEUNSP, UNIFRAN, UNICID, FAM, UNEC, UNITAU, UNIFESP etc.).
- Páginas de editais erradas: UFLA (mudou para dips.ufla.br) e FACSETE (biblioteca do WordPress passou a pedir login;
  agora usa facsete.edu.br/transferencia).
- Script para repetir a conferência: `.trabalho/checar_sites.py` (local).

### Públicas
| Universidade | Achado (fonte oficial) |
|---|---|
| USP (FMUSP, FMRP, FMBRU) | Transferência pelo exame da Fuvest; no processo 2026/2027 nenhuma das três ofereceu vaga de Medicina (manual da Fuvest) |
| UNICAMP | Vagas Remanescentes da Comvest (Res. GR-021/2026): 2 vagas de Medicina para 2027, inscrições 17–28/08/2026, R$ 235, aceita exterior; registrado no histórico |
| UNIFESP | Edital 587/2026 (ingresso 2027) sem vaga de Medicina |
| UNESP Botucatu | Portal único da Unesp; nada de Medicina aberto. O robô passa a exigir "Botucatu" no PDF |
| **UFLA** | **Aberta:** Edital 14/DIPS/PROGRAD/2026, 16/10 a 04/11/2026, 8 vagas de transferência (só quem cursa Medicina no Brasil, 10% a 50% do curso) + 2 de novo título; classificação pelo ENEM; R$ 90. Publicado |
| UFJF, UFVJM, UFMS | Editais gerais de vagas ociosas/remanescentes; o robô passa a vigiar os portais |
| UNIFADRA | Página oficial: sem inscrições abertas; só Medicina no Brasil, até o 7º semestre |
| UNITAU | Editais em unitau.br/concursos (2026 reaberto 29/06–14/07); o site bloqueia acesso automático |

Cada uma ganhou um **aviso público** na página da faculdade explicando como faz a transferência.

### Robô
- **Falhou:** um edital geral só de outros cursos entraria como se fosse de Medicina. Agora o PDF precisa citar Medicina
  (palavra inteira: "Biomedicina" não conta; caso real: edital da Unesp Assis que cita Medicina só como curso de origem).
- Ficha pode exigir um texto no PDF (`exigir_texto`), para portais com vários câmpus.
- "8 vagas: não informado" virou "8 vagas".
- Testes: 37 passando.

## Federais restantes de MG: UFSJ, UFOP, UFV, UFU, UFTM (26/10/2026)
| Universidade | Achado (fonte oficial) | No site |
|---|---|---|
| **UFSJ** | **Aberta:** Edital 7/2026/COPEVE/PROEN (PVR 2027/1), Transferência Voluntária de 26 a 29/10/2026 (até 20h), R$ 150, nota do ENEM (2013–2025), só quem cursa Medicina no Brasil com ao menos 15% do curso. Quadro inicial: 4 vagas em Divinópolis e 6 em São João del-Rei (o atualizado sai em 26/10) | Publicado nos dois campi |
| UFOP | Vagas Residuais 2026/1 (Edital Prograd 87/2025): Medicina sem vaga de transferência | Aviso + página da Prograd |
| UFU | Vagas Ociosas – Transferência Facultativa 2025-2: 10 vagas de Medicina (inscrições 14–28/07/2025, prova 17/08/2025) | Histórico + "costuma abrir em julho" |
| UFV | Vagas Ociosas da PRE, semestral, por ENEM; o portal pse.ufv.br não abriu nesta rede | Aviso + endereço; pendente |
| UFTM | Transferência de Alunos semestral, por ENEM (2026/2: 5–12/05/2026); o site não abriu nesta rede | Aviso; pendente |

Observação: o PSVO da UFSJ não é transferência (preenche vagas de calouro do SiSU); a transferência é o PVR.

## UFSJ: quadro de vagas atualizado (26/10/2026)
O quadro de vagas da Transferência Voluntária saiu hoje (já descontadas as etapas anteriores): Divinópolis continua com
**4** vagas de Medicina, São João del-Rei caiu de 6 para **5**. Corrigido nas duas fichas.

## Expansão: todas as escolas médicas da Bahia (26/10/2026)

### Cobertura
- Lista de referência: portal Escolas Médicas do Brasil (33 cursos na BA). **Falhou:** a lista estava incompleta e com
  erros. Faltavam UNIFAN e UNEF (Feira de Santana, autorizadas em 2024), Zarns Salvador, UNESULBAHIA (Eunápolis),
  UniFTC Feira de Santana, UNINASSAU Barreiras e UNEX Itabuna (achados na tabela do Enamed 2025 e nos editais). A fonte
  também dava Estácio Juazeiro como Juazeiro do Norte (é Juazeiro/BA), o site da Afya Itabuna como o de Ipatinga e um
  domínio de Goiás para a UNIFAN.
- Ficaram de fora, sem fonte oficial de que a Medicina funciona: Faculdade Sulamérica (Luís Eduardo Magalhães, que tem
  autorização de 2024 em recurso) e UNIFAAHF.
- **31 faculdades novas** (base de 139 para 170). Coordenadas do centro da cidade, da lista de municípios do site.

### Públicas: conferidas uma por uma na fonte oficial
| Universidade | Achado | No site |
|---|---|---|
| UFBA (Salvador e Vitória da Conquista) | Vagas Residuais 2026 para 2027.1: transferência externa de 21 a 26/10/2026, **sem vaga de Medicina** | Aviso |
| UESC | Edital 153/2026 (2027.1, inscrições de 05 a 09/10): sem Medicina (só Biomedicina) | Aviso |
| UESB (2 câmpus) | Edital 151/2026 (2026.2): sem Medicina | Aviso |
| UNEB | Edital 047/2026 (2026.2): as 5 vagas de Medicina eram **só para rematrícula** | Aviso |
| UFRB | Vagas Ociosas 2027.1 (Edital 031/2026): o centro de Santo Antônio de Jesus nem aparece no quadro | Aviso |
| UNIVASF Paulo Afonso | PS-PVO 2027 (Edital 22/2026): sem Medicina (quadro em imagem, lido página por página) | Aviso |
| UFSB, UFOB | Editais 31/2026 e 01/2026: sem Medicina | Aviso |
| UEFS | Edital semestral; a lista de seleções (csa.uefs.br) é carregada por script | Aviso; pendente |

### Editais lidos à mão e publicados (abertos agora)
| Faculdade | Edital | Achado |
|---|---|---|
| Unime (Lauro de Freitas) | TE e Portador de Diploma 2027.1 | 24/09 a 18/11/2026; 10 vagas (1º ao 7º) + 5 de portador de diploma; R$ 250; só faculdades do Brasil. O edital pede vínculo "do ano letivo de 2025" (anotado) |
| Pitágoras Eunápolis | TE e Portador de Diploma 2027.1 | 5 + 5 vagas; R$ 250. **Conferir:** o edital diz até 30/10/2026 e a página da EconRio diz até 18/11/2026 (publicada a data do edital) |
| IDOMED Alagoinhas, Juazeiro e Ribeirão Preto | Unificado IES nacionais 2027.1 | 27/08/2026 a 08/03/2027; 3 + 3 + 1 vagas por período; R$ 250; aceita também alunos de outros cursos da saúde (1 período a 75% do curso) |
| IDOMED Alagoinhas e Juazeiro | Unificado IES estrangeiras 2027.1 | Até 14/01/2027, prova on-line em 17/01; 1 e 2 vagas; R$ 380. **Conferir:** o calendário traz "29/02/2027", data que não existe |
| UNEX Itabuna | Unificado UNEX 2027.1 | 17/09/2026 a 08/03/2027, 2º ao 6º semestre (a ficha de Itabuna não existia; Vitória da Conquista tem 0 vagas, por isso fica de fora) |

As fichas do IDOMED (pendentes desde a Fase 1) e da Unime passaram a apontar para as páginas da EconRio.

### Robô
- Rodada completa: 20 PDFs novos. **Falhou:** 5 eram anexos (4 da UFLA e o quadro de vagas do IDOMED), tratados como
  edital; 4 eram cópias do mesmo edital (São Camilo e Zarns). Saíram da base e ficaram marcados como conhecidos.
- **Falhou:** as retificações do IDOMED marcaram como "conferir" o edital que já foi lido na versão retificada.
  Agora o registro lista as retificações conhecidas.
- São Camilo (SP): o site voltou a responder; os editais 002/2026 e 054/2026 foram corrigidos à mão (o robô tinha lido
  o semestre "2019.2" e datas de um dia só). O 054/2026 se contradiz (título 2026.2, item 1.3 "primeiro semestre"): conferir.
- Os editais antigos achados (UNIFAN, Zarns, UNEX Itabuna) ficam no histórico como "conferir".

### Verificações
| Verificação | Resultado |
|---|---|
| 3 editais sorteados, relidos como imagem do PDF (Unime TE, Unime PD, IDOMED Alagoinhas exterior) | Batem: datas, vagas, taxa. A releitura achou uma regra que faltava (quem já é do grupo IDOMED só entra pelo InterIDOMED), já incluída |
| Cruzamento dos alertas com 3 perfis (Salvador até 400 km; exterior; só públicas) | 6, 6 e 0 editais, coerente com distâncias e vagas por semestre |
| 251 páginas geradas | 0 links internos quebrados, dados estruturados válidos, textos-chave presentes |
| Testes | 37 passando |
| **Não feito:** capturas em 375 px e 1280 px e console do navegador | Sem ferramenta de navegador nesta sessão: precisa ser conferido à mão |

## QA completo antes da publicação (26/10/2026)

### Ferramentas (instaladas em `qa/`, como dependências de desenvolvimento; não vão para o site)
Playwright 1.64 com Chromium (dentro de `qa/node_modules`), @axe-core/playwright 4.14, Lighthouse 13.5,
html-validate 11.17 e linkinator 8.1. Scripts: `qa/verificar.mjs` (capturas, console, requisições, layout e axe),
`qa/etapas.mjs` (etapas do diagnóstico), `qa/alvos.mjs` (alvos de toque) e `qa/.htmlvalidate.json`.
Para repetir: `python -m http.server 8765 --directory docs` e, em `qa/`, `PLAYWRIGHT_BROWSERS_PATH=0 node verificar.mjs`.

### Páginas verificadas (375 px e 1280 px; capturas finais em `qa/screenshots`)
Início, diagnóstico (etapas 1 a 3 e resultado com perfil de Salvador), exterior, faculdades (Pitágoras, FAMERP, UFBA),
editais (Unime, IDOMED exterior), confirmação de alerta e privacidade. O site não tem página por estado; as de filtro e
alerta são o diagnóstico, o resultado e `/alerta/`.

### Achados e correções (todas na origem: gerador, estilo, código ou dados)
| Ferramenta | Achado | Correção |
|---|---|---|
| Capturas | **Falhou:** aviso "Ainda falta descobrir onde esta faculdade publica os editais" em ~60 fichas cuja página é conhecida (carrega por script, bloqueia robôs, página nova da EconRio, pedido direto) | Texto com o motivo certo de cada pendência (`aviso_pendente`) + teste com todas as fichas reais |
| Capturas | Data "26/10/2026" quebrando no meio no celular (bloco de números do início) | Classe própria, sem quebra de linha |
| axe (serious) | `nested-interactive`: mapa com `role="img"` escondia os links dos pontos dos leitores de tela (início e resultado) | `role="group"`; partes decorativas com `aria-hidden` |
| Alvos de toque | Links do rodapé dos cartões (22 px), trilha "Início › …" (17 px) e caixas de marcar (20 px) abaixo de 24 px | 32 px, 25 px e 24 px. Pontos do mapa ficam menores (exceção da WCAG 2.5.8: a mesma faculdade está na lista e na busca); títulos de cartão cumprem a exceção de espaçamento |
| html-validate | 5 `fieldset` sem `legend` (campos únicos do diagnóstico) | Viraram `div` |
| html-validate | `aria-label` sem papel no bloco de números | `role="group"` |
| html-validate | 230 títulos com mais de 70 caracteres (cortados no Google) | `titulo_curto`: nome, depois sigla e cidade, depois sigla |
| html-validate | DOCTYPE minúsculo, 591 espaços no fim da linha, 75 estilos inline | Corrigidos no gerador (e 2 no app.js) |
| html-validate | Barra de progresso com `role="progressbar"` em vez de `<progress>` | Mantida (ARIA válido); exceção registrada na configuração |
| linkinator | Site da UNIMAX com certificado inválido (`www.unimax.edu.br`) e da UNASP sem conexão (`www.unasp.br`) | `unimax.edu.br` e `unasp.edu.br` (conferidos no navegador do curl) |

Nenhuma regra, data ou requisito de edital foi alterado nesta rodada.

### Resultado final
| Verificação | Resultado |
|---|---|
| Console e requisições (22 capturas + etapas) | 0 erros, 0 requisições com falha, 0 rolagem lateral |
| axe (WCAG 2.2 AA), serious/critical | 4 → **0** |
| html-validate (251 páginas) | 1.154 apontamentos em 251 páginas → **0** |
| Links internos | 0 quebrados (327 endereços; e a checagem estática das 251 páginas) |
| Links dos 58 editais publicados | 52 abrem o PDF no mesmo domínio; UNILAGO (formulário contínuo) e Unicamp (página de norma) são HTML por natureza; FUNCESI, UNITAU, CEUNSP e UNIFRAN respondem 403 a robôs (já registrado). Nenhum redirecionamento suspeito |
| Links externos das fichas | Fora os 92 endereços do próprio transfermed.com.br (páginas novas, que só existem depois da publicação), restam bloqueios conhecidos (UNITAU, Fuvest), servidores que esta rede não alcança (UNEC, UNIFACIG, Unifesp) e servidores com cadeia de certificado incompleta que o Node recusa mas o navegador abre (UFBA, UNAERP, Unimontes, Copeve/UFMG). A UFOP responde 404 com a página inicial normal (erro do servidor dela) |
| Testes | 37 → **45** passando (novos: aviso da ficha, títulos, DOCTYPE e espaços, fieldset, mapa, estilo inline) |

### Lighthouse (celular)
| Página | Antes (site no ar, sem as mudanças) | Depois (local) |
|---|---|---|
| Início | Desempenho 92 · Acessibilidade 100 · Boas práticas 100 · SEO 100 | 95 · 100 · 100 · 100 |
| Faculdade | FAMERP: 87 · 100 · 100 · 100 | Pitágoras: 82 · 100 · 100 · 100 |
O servidor local não comprime os arquivos (o GitHub Pages comprime), então o desempenho local fica abaixo do real.

### Pendências
- UFV (pse.ufv.br) e UFTM: os sites não abriram nesta rede; continuam como aviso.
- UEFS: lista de seleções carregada por script (csa.uefs.br).
- Datas a confirmar: Pitágoras Eunápolis (edital 30/10 × página 18/11/2026), IDOMED exterior ("29/02/2027"),
  São Camilo 054/2026 (2026.2 × "primeiro semestre").
- Fichas Unime, Pitágoras e IDOMED: trocar o endereço da EconRio quando sair o processo 2027.2.

### Lighthouse (celular, no site publicado)
| Página | Antes (no ar, sem as mudanças) | Depois (no ar, após a publicação) |
|---|---|---|
| Início | Desempenho 92 · Acessibilidade 100 · Boas práticas 100 · SEO 100 | 96 · 100 · 100 · 100 |
| FAMERP | 87 · 100 · 100 · 100 | 85 · 100 · 100 · 100 (variação normal entre medições) |
| Pitágoras (nova) | — | 100 · 100 · 100 · 100 |
Meta (90+ em acessibilidade e boas práticas) cumprida em todas. Medidas locais, sem compressão: início 95, Pitágoras 82.

## Monitoramento contínuo: Camadas 1 e 2 (26/10/2026)

### O que foi montado
| Peça | Função |
|---|---|
| `monitor.py` + `monitor.yml` (06:00 e depois do radar) | Retratos das páginas de seleção e dos PDFs em vigor (`data/retratos.json`), prazos de 7 dias, datas incoerentes, editais para conferir, editais novos do robô ainda não conferidos, fichas sem conferência há 30 dias. Corrige sozinho só a situação aberto/encerrado, e só publica se os testes passarem |
| `qa/achados_qualidade.py` + `qualidade.yml` (06:00; Lighthouse às segundas) | Testes, html-validate, linkinator (com `qa/links_excecoes.txt`), axe/console/layout em 375 e 1280 px |
| `issues.py` | Uma issue por problema, com marca invisível (fonte, chave, impressão digital). Atualiza em silêncio, reabre o que o robô fechou se voltar, respeita o fechamento manual, fecha sozinho prazo/link/qualidade resolvidos |
| `radar.yml` | Agora na mesma fila de escrita do monitor, testa de novo depois de gerar o site e faz `pull --rebase` antes de enviar |
| `MELHORIA.md`, `BACKLOG.md`, `CHANGELOG.md` | Roteiro da rodada de melhoria, 5 propostas iniciais e histórico do que mudou |

### Verificações
| Verificação | Resultado |
|---|---|
| Testes novos (`tests/test_monitor.py`) | 14: prazo de 7 dias, só editais conferidos, datas impossíveis, retificação, ficha velha, correção segura só mexe na situação, exceções, página aberta sem link não é falha, e o `issues.py` (cria, nunca duplica, atualiza a contagem sem mudar a identidade, respeita fechamento manual, reabre o que o robô fechou, só fecha sozinho o que pode, cada fonte cuida das suas, ignora PR e issue de pessoa). Total: **59 passando** |
| Monitor completo local (linha de base) | 141 páginas visitadas, 127 abriram; 13 PDFs em vigor com retrato. 14 achados: 5 prazos, 8 conferir, 1 página sem acesso |
| **Falhou:** página sem acesso | Era falso positivo (FMUSP: a Fuvest bloqueia, a página da faculdade abre sem edital agora). Corrigido: só é falha quando todas as fontes da ficha dão erro; teste criado |
| Agregador da qualidade sobre os relatórios do QA | Achou o site da UNIMAR (`www` redireciona e o salto falha no Node): ficha aponta para `portal.unimar.br` |
| Erros vistos pelo robô nos servidores do GitHub (rodada de 26/10) | 24 páginas com 403, certificado ou lentidão: os bloqueios conferidos foram para `qa/links_excecoes.txt`; "fora do ar" só vira issue após 3 dias seguidos numa página que já abriu |

### Execução real no GitHub Actions (26/10/2026)
| Rodada | Monitor | Qualidade |
|---|---|---|
| 1ª (manual) | [run 40402967835](https://github.com/cauagabrielmarin06-cloud/transfermed/actions/runs/40402967835): sucesso; 14 achados → issues #1 a #14; retratos salvos por commit do bot | [run 40402973036](https://github.com/cauagabrielmarin06-cloud/transfermed/actions/runs/40402973036): sucesso; 59 testes, axe/console 0, HTML 0; Lighthouse (no GitHub) início 100/100/100/100 e faculdade 99/100/100/100; 1 issue de links (#15) |
| 2ª (manual) | [run 40405146506](https://github.com/cauagabrielmarin06-cloud/transfermed/actions/runs/40405146506): sucesso; 13 achados, **0 issues criadas ou duplicadas** | [run 40405151012](https://github.com/cauagabrielmarin06-cloud/transfermed/actions/runs/40405151012): sucesso; 0 achados; **#15 fechada sozinha** |

**Falhou na 1ª rodada e foi corrigido:**
- #14 "link novo" na UMC era falso positivo: a página gera âncoras aleatórias (`#collapse-…`). O monitor passou a
  ignorar o que vem depois do `#` (teste criado); issue fechada como "não planejada".
- #15: São Camilo, UEFS e UESB abrem do Brasil (conferido no Node), mas recusam os servidores do GitHub. Foram
  para `qa/links_excecoes.txt`; na 2ª rodada a issue fechou sozinha.

Pendências que continuam: UFV e UFTM (sites não abrem desta rede), UEFS (lista por script), datas a confirmar da
Pitágoras, do IDOMED exterior e da São Camilo 054/2026 — agora também acompanhadas pelas issues `conferir`.

## Rodada de melhoria 1 (26 e 27/10/2026)

### (a) Prazos, editais novos e retificações
| Item | Verificado na fonte oficial | Resultado |
|---|---|---|
| UB 034/2026 (encerra 29/10) | Página de editais da UB | Sem retificação ou prorrogação; PDF igual ao retrato |
| UFSJ PVR 2027/1 (29/10) | Página do PVR 2027/1 | Sem prorrogação |
| Pitágoras Eunápolis (30/10) | Página da EconRio e PDF | Página continua "até 18/11", edital "até 30/10"; nenhum documento novo. Mantido "conferir" com a data do edital |

### (b) Dados a conferir
Nenhuma das contradições foi resolvida pela faculdade: UB ("65 (duzentas e vinte)"), UNOESTE ("3 (duas vagas)"),
IDOMED ("29/02/2027") e Pitágoras. PDFs iguais aos retratos de 26/10; ficam "conferir" (regra: sem confirmação, não
publica palpite). Proposta para não poluir as issues: BACKLOG item 7.

### (c) e (d) Links, erros, acessibilidade e performance
Nenhuma issue aberta. BACKLOG item 4 (primeira pintura lenta) **não procede**: a fonte já é local, pré-carregada e com
`font-display: swap`; no GitHub o Lighthouse dá 100 e 99.

### (e) Cobertura: Mato Grosso do Sul
- Lista de referência com erro: a UFR (Rondonópolis) é de Mato Grosso. Faltavam Unicesumar Corumbá (Enamed) e Uniderp
  Dourados (site da Uniderp). 7 fichas novas; UFMS Três Lagoas já existia (aviso atualizado).
- Públicas: UFMS (Vagas Ociosas semestral; 2027.1 ainda não publicado), UFGD (PSTV: último processo em 2023), UEMS
  (Edital 030/2026/DRA, ingresso 2027, inscrições 19–23/10: 18 páginas, **sem Medicina**).
- Unicesumar Corumbá: editais 01/2026 (2026.1: prova 28/01, 15 vagas na 4ª série) e 04/2026 (2026.2: 23/03 a 22/06,
  prova 27/06, 10 + 10 vagas) lidos no PDF; aceita aluno de faculdade estrangeira.
- **Não concluído:** a rodada local do robô foi encerrada pelo sistema por falta de memória no computador. As fichas
  de MS serão visitadas pelo robô diário do GitHub (06:17). BACKLOG item 6 propõe visitar só fichas escolhidas.

### Verificações antes de publicar
| Verificação | Resultado |
|---|---|
| Testes | **67 passando** (novos: anexo não é edital, anexos vigiados uma vez só, fluxo contínuo não é pendência, ordem do histórico, reconferência) |
| html-validate (260 páginas) | 0 problemas |
| Links internos (260 páginas) | 0 quebrados |
| Capturas, console e axe (início, UFMS, Unicesumar e edital da Unicesumar, 375 e 1280 px) | 0 apontamentos |
| **Falhou nas capturas:** histórico da Unicesumar com 2026.1 acima de 2026.2 | Ordenação por texto misturava "2026.1" e "2026-06-22"; agora ordena por semestre e data (teste criado) |
| **Falhou nos testes:** a pendência nova da Unicesumar caía em "falta descobrir" | O teste da rodada anterior pegou; texto mapeado para "não deixa os editais listados" |
| Reconferência (`qa/reconferir.py`): Unicesumar 2026.1 e 2026.2 + Unime 2027.1 (sorteado) | Datas, vagas e taxa encontradas na página citada |

### Melhorias no processo (passo 7)
- Monitor vigia os **anexos** (`anexos` no edital): datas e vagas do IDOMED e da UFSJ vêm deles e não eram vigiadas.
- Monitor não abre issue de conferência para **fluxo contínuo** (UNILAGO): a #13 fecha sozinha na próxima rodada.
- Robô reconhece **anexos** pelo nome do arquivo (BACKLOG item 1, feito).
- Reconferência por sorteio virou script (`qa/reconferir.py`), e o `verificar.mjs` aceita `PAGINAS` para rodar só
  páginas novas.

### Execução no GitHub depois da publicação (27/10/2026)
| Workflow | Resultado |
|---|---|
| [Monitor 40501559135](https://github.com/cauagabrielmarin06-cloud/transfermed/actions/runs/40501559135) | Sucesso; 67 testes; 13 achados; **#13 (UNILAGO) fechada sozinha**; nenhuma issue nova além do prazo da USF (#16, aberta pela rodada das 06:00) |
| [Qualidade 40501564671](https://github.com/cauagabrielmarin06-cloud/transfermed/actions/runs/40501564671) | Sucesso; 67 testes; axe/console/layout 0; #15 reaberta: UFRB não respondeu ao linkinator |

**Falhou e foi corrigido:** a UFRB abriu no monitor do GitHub no mesmo dia (retrato 27/10 sem falha) e abre daqui: foi
instabilidade, não bloqueio, então não entrou nas exceções. O linkinator passa a tentar 3 vezes, com intervalo
aleatório, antes de dar um link como quebrado. Correção de registro: são 67 testes, não 69.

## 28/10/2026 · Etapa 1: cache do service worker
- **Causa:** o service worker antigo respondia o HTML com a cópia guardada e só assumia depois que todas as abas
  fechassem, então a página nova rodava com o `app.js` velho (ou vice-versa) e os botões não respondiam.
- Já corrigido em 7e3d389 (HTML pela rede, `skipWaiting` + `clients.claim`, caches antigos apagados). Agora também:
  aviso "Nova versão disponível — atualizar" quando um service worker novo assume uma aba aberta, `reg.update()` ao
  voltar para a aba, e teste diário (`qa/interacoes.mjs`) clicando em "Buscar pelo nome", "Brasil" e em **cada**
  estado, mais o aviso. 7/7 ok em 375 e 1280 px; `verificar.mjs` sem apontamentos.

## 28/10/2026 · Correções de regra encontradas no caminho
- **Alerta com dado não conferido:** `alertas.py` mandava editais só detectados pelo robô e editais "conferir"
  (ex.: UB 034/2026) nos e-mails. Agora só vai edital conferido e sem ponto em aberto (teste `SoConferido`).
- **Formulário de alerta saindo do ar:** gerar o site sem as variáveis (sessões locais e o monitor) gravava
  `supabaseUrl` vazio no `dados.js` (aconteceu em caba4f6, b3813a0 e 7e3d389). Agora o gerador mantém a configuração
  pública já publicada e o monitor recebe as variáveis. Teste `test_configuracao_publica_nao_some_sem_variaveis`.
- **Prova social:** o número de alertas aparecia a partir de 10; agora só acima de 100 confirmados.

## 28/10/2026 · Etapa 2: Quem faz, Sobre e Contato
- "Quem faz o Transfermed? →" fechado por padrão no início (abaixo de "Por que dá para confiar"), no fim das
  fichas de edital e de "Estudo no exterior". Celular: painel de baixo (arrastar fecha); computador: expande no
  lugar. Botão real com `aria-expanded`, Esc e toque fora fecham, foco vai ao painel e volta ao botão. A miniatura
  só é baixada ao abrir (conferido no Playwright: nenhuma requisição de `assets/sobre/` antes do clique).
- `/sobre/` com o texto do dono, exato, e o formulário no fim; `/contato/` com motivo pré-selecionável
  (`?motivo=`). Schema.org AboutPage + Person e ContactPage.
- **Foto:** recorte da cabeça à cintura, sem a pessoa da maca, brasão e "Medicina Fernandópolis" desfocados, sem
  EXIF (WebP 20 KB, JPG 39 KB, miniatura 128 px). Fica em `.trabalho/foto/` (fora do Git) **até o dono aprovar**;
  até lá o painel mostra as iniciais e /sobre/ sai sem foto. Para publicar: copiar os 4 arquivos para
  `docs/assets/sobre/` e gerar o site. As capturas com a foto (`qa/screenshots/etapa2/`) ficam só no computador.
- **Contato:** recomendação = o próprio Supabase + Brevo que já servem os alertas (nenhuma conta nova, resposta
  automática pelo mesmo remetente, dados no mesmo operador da privacidade). Formspree e Web3Forms exigiriam conta
  e mais um operador de dados. Antispam: honeypot, limite de 3 mensagens por e-mail por dia e 60 por hora no banco.
  Mensagens apagadas 90 dias depois de encaminhadas. **Desligado até o dono** rodar o `supabase/schema.sql` novo,
  criar o segredo `CONTATO_DESTINO` e a variável `CONTATO_ATIVO=1`; até lá o formulário avisa que está sendo ativado.
- Verificação: 90 testes ok; `verificar.mjs` (375 e 1280 px, console, axe) sem apontamentos em início, sobre,
  contato, exterior e edital; html-validate sem erros; `interacoes.mjs` 7/7.

## 28/10/2026 · Etapa 3D: fichas que o robô ainda não visita todo dia (78 de 177)
Visitadas: 99. Por motivo: carrega por script 27, outro 25, bloqueia robô 16, página nova por semestre 5, sem lista/edital publicado 5. Lista gerada de `com_robo()` e do campo
`pendente` de `data/faculdades.json` (o site mostra um aviso público em cada uma dessas fichas).

| UF | Faculdade | Motivo |
|---|---|---|
| BA | Afya – Faculdade de Ciências Médicas de Itabuna | o site recusa acesso automático (bloqueio anti-robô): conferir os editais à mão no site oficial |
| BA | Afya – Faculdade de Ciências Médicas de Vitória da Conquista (antiga FASA) | o site recusa acesso automático (bloqueio anti-robô): conferir os editais à mão no site oficial |
| BA | Afya – Faculdade de Medicina de Guanambi (antiga FIP Guanambi) | o site recusa acesso automático (bloqueio anti-robô): conferir os editais à mão no site oficial |
| BA | Centro Universitário AGES (UniAGES) | a página de transferência carrega os editais por script (o robô não lê): conferir no site oficial |
| BA | Centro Universitário Dom Pedro II (Afya UniDomPedro) | o site recusa acesso automático (bloqueio anti-robô): conferir os editais à mão no site oficial |
| BA | Centro Universitário Maurício de Nassau (UNINASSAU) – Barreiras | o site recusa acesso automático (bloqueio anti-robô): conferir os editais à mão no site oficial |
| BA | Centro Universitário UniFG | a página de transferência carrega os editais por script (o robô não lê): conferir no site oficial |
| BA | Centro Universitário UniFTC – Feira de Santana | a página de transferência carrega os editais por script (o robô não lê): conferir no site oficial |
| BA | Centro Universitário UniFamec | transferência por pedido direto à faculdade, sem edital publicado: conferir no site oficial |
| BA | Centro Universitário Unime | os editais saem numa página nova da EconRio a cada semestre: trocar o endereço quando sair o de 2027.2 |
| BA | Centro Universitário de Ciências e Empreendedorismo (UNIFACEMP) | transferência por pedido direto à faculdade, sem edital publicado: conferir no site oficial |
| BA | Escola Bahiana de Medicina e Saúde Pública (Bahiana) | o site recusa acesso automático (bloqueio anti-robô): conferir os editais à mão no site oficial |
| BA | Estácio IDOMED – Alagoinhas | os editais unificados do IDOMED saem numa página nova da EconRio a cada semestre: trocar o endereço quando sair o de 2027.2 |
| BA | Estácio IDOMED – Juazeiro | os editais unificados do IDOMED saem numa página nova da EconRio a cada semestre: trocar o endereço quando sair o de 2027.2 |
| BA | Faculdade AGES de Medicina – Irecê | a página de transferência carrega os editais por script (o robô não lê): conferir no site oficial |
| BA | Faculdade AGES de Medicina – Jacobina | a página de transferência carrega os editais por script (o robô não lê): conferir no site oficial |
| BA | Faculdade Pitágoras de Medicina de Eunápolis | os editais saem numa página nova da EconRio a cada semestre: trocar o endereço quando sair o de 2027.2 |
| BA | UNEF Centro Universitário (Grupo Nobre) | transferência por pedido direto à faculdade, sem edital publicado: conferir no site oficial |
| BA | Universidade Estadual de Feira de Santana (UEFS) | a lista de seleções da UEFS (csa.uefs.br) é carregada por script: conferir lá o edital semestral de transferência |
| BA | Universidade Salvador (UNIFACS) | a página de transferência carrega os editais por script (o robô não lê): conferir no site oficial |
| MG | Afya Centro Universitário FIPMoc | a página de transferência carrega os editais por script (o robô não lê): conferir no site oficial |
| MG | Afya Centro Universitário Presidente Tancredo de Almeida Neves (UNIPTAN) | a página de transferência carrega os editais por script (o robô não lê): conferir no site oficial |
| MG | Afya Faculdade de Ciências Médicas de Contagem | a página de transferência carrega os editais por script (o robô não lê): conferir no site oficial |
| MG | Afya Faculdade de Ciências Médicas de Ipatinga | a página de transferência carrega os editais por script (o robô não lê): conferir no site oficial |
| MG | Afya Faculdade de Medicina de Itajubá | a página de transferência carrega os editais por script (o robô não lê): conferir no site oficial |
| MG | Centro Universitário Atenas (UniAtenas) – Paracatu | descobrir a página onde esta faculdade publica os editais de transferência |
| MG | Centro Universitário FAMINAS (UNIFAMINAS) – Muriaé | descobrir a página onde esta faculdade publica os editais de transferência |
| MG | Centro Universitário FUNORTE | a transferência é feita por um sistema de inscrição (virtualclass), sem edital na página: conferir no site oficial |
| MG | Centro Universitário UNIFACIG | o site bloqueia o robô ou não respondeu na varredura de 26/10/2026: conferir à mão |
| MG | Centro Universitário de Belo Horizonte (UNI-BH) | a página de transferência carrega os editais por script (o robô não lê): conferir no site oficial |
| MG | Centro Universitário de Caratinga (UNEC) | o site não respondeu à varredura de 26/10/2026: conferir à mão |
| MG | Centro Universitário de Patos de Minas (UNIPAM) | descobrir a página onde esta faculdade publica os editais de transferência |
| MG | Centro Universitário do Sul de Minas (UNIS) | descobrir a página onde esta faculdade publica os editais de transferência |
| MG | Faculdade Atenas – Passos | descobrir a página onde esta faculdade publica os editais de transferência |
| MG | Faculdade Atenas – Sete Lagoas | descobrir a página onde esta faculdade publica os editais de transferência |
| MG | Faculdade Vértice (UNIVÉRTIX) | descobrir a página onde esta faculdade publica os editais de transferência |
| MG | Faculdade da Saúde e Ecologia Humana (FASEH) | a página de transferência carrega os editais por script (o robô não lê): conferir no site oficial |
| MG | Pontifícia Universidade Católica de Minas Gerais (PUC Minas) – Betim | a página de transferência carrega os editais por script (o robô não lê): conferir no site oficial |
| MG | Pontifícia Universidade Católica de Minas Gerais (PUC Minas) – Contagem | a página de transferência carrega os editais por script (o robô não lê): conferir no site oficial |
| MG | Pontifícia Universidade Católica de Minas Gerais (PUC Minas) – Poços de Caldas | a página de transferência carrega os editais por script (o robô não lê): conferir no site oficial |
| MG | Universidade Federal de Viçosa (UFV) | o portal de seleção (pse.ufv.br) não respondeu à varredura de 26/10/2026: conferir à mão |
| MG | Universidade Federal do Triângulo Mineiro (UFTM) | o site não respondeu à varredura de 26/10/2026; os editais saem como notícias em uftm.edu.br |
| MG | Universidade Presidente Antônio Carlos (UNIPAC) – Juiz de Fora | descobrir a página onde esta faculdade publica os editais de transferência |
| MG | Universidade do Vale do Sapucaí (UNIVÁS) | descobrir a página onde esta faculdade publica os editais de transferência |
| MS | Faculdade Unicesumar de Corumbá | os editais saem na área de vestibular sem uma lista pública que o robô consiga ler: conferir a cada semestre |
| MS | Universidade Anhanguera-Uniderp – Campo Grande | o site recusa acesso automático (bloqueio anti-robô): conferir os editais à mão no site oficial |
| MS | Universidade Anhanguera-Uniderp – Dourados | o site recusa acesso automático (bloqueio anti-robô): conferir os editais à mão no site oficial |
| MS | Universidade Anhanguera-Uniderp – Ponta Porã | o site recusa acesso automático (bloqueio anti-robô): conferir os editais à mão no site oficial |
| SP | Centro Universitário Adventista de São Paulo (UNASP) – Hortolândia | descobrir a página onde esta faculdade publica os editais de transferência |
| SP | Centro Universitário FMABC | descobrir a página onde esta faculdade publica os editais de transferência |
| SP | Centro Universitário FUNVIC (UNIFUNVIC) | descobrir a página onde esta faculdade publica os editais de transferência |
| SP | Centro Universitário Lusíada (UNILUS) | descobrir a página onde esta faculdade publica os editais de transferência |
| SP | Centro Universitário Sudoeste Paulista (UniFSP) | descobrir a página onde esta faculdade publica os editais de transferência |
| SP | Centro Universitário das Américas (FAM) | o site bloqueia o robô (os editais de transferência ficam na biblioteca do WordPress): conferir à mão |
| SP | Centro Universitário de Jaguariúna (UniFAJ) | descobrir a página onde esta faculdade publica os editais de transferência |
| SP | Centro Universitário de Votuporanga (UNIFEV) | nenhum edital de transferência de Medicina encontrado nos últimos 2 anos (busca em 24/10/2026); o último localizado é de 2015 |
| SP | Estácio IDOMED – Ribeirão Preto | os editais unificados do IDOMED saem numa página nova da EconRio a cada semestre: trocar o endereço quando sair o de 2027.2 |
| SP | Faculdade Israelita de Ciências da Saúde Albert Einstein | descobrir a página onde esta faculdade publica os editais de transferência |
| SP | Faculdade Municipal Professor Franco Montoro (FMPFM) | o site bloqueia o robô ou não respondeu na varredura de 26/10/2026: conferir à mão |
| SP | Faculdade de Ciências da Saúde Sírio-Libanês | descobrir a página onde esta faculdade publica os editais de transferência |
| SP | Faculdade de Ciências da Saúde de Barretos Dr. Paulo Prata (FACISB) | editais de abertura de transferência não ficam listados no site (só as convocações): conferir a cada semestre |
| SP | Faculdade de Medicina FACERES | nenhum edital de transferência de Medicina encontrado nos últimos 2 anos (busca em 24/10/2026) |
| SP | Faculdade de Medicina de Penápolis (FUNEPE) | nenhum edital de transferência de Medicina encontrado nos últimos 2 anos (busca em 24/10/2026) |
| SP | Universidade Anhembi Morumbi (UAM) – Piracicaba | a página de transferência carrega os editais por script (o robô não lê): conferir no site oficial |
| SP | Universidade Anhembi Morumbi (UAM) – São José dos Campos | a página de transferência carrega os editais por script (o robô não lê): conferir no site oficial |
| SP | Universidade Anhembi Morumbi (UAM) – São Paulo | a página de transferência carrega os editais por script (o robô não lê): conferir no site oficial |
| SP | Universidade Cidade de São Paulo (UNICID) | o site bloqueia o robô ou não respondeu na varredura de 26/10/2026: conferir à mão |
| SP | Universidade Nove de Julho (UNINOVE) – Bauru | a página de transferência carrega os editais por script (o robô não lê): conferir no site oficial |
| SP | Universidade Nove de Julho (UNINOVE) – Guarulhos | a página de transferência carrega os editais por script (o robô não lê): conferir no site oficial |
| SP | Universidade Nove de Julho (UNINOVE) – Mauá | a página de transferência carrega os editais por script (o robô não lê): conferir no site oficial |
| SP | Universidade Nove de Julho (UNINOVE) – Osasco | a página de transferência carrega os editais por script (o robô não lê): conferir no site oficial |
| SP | Universidade Nove de Julho (UNINOVE) – São Bernardo do Campo | a página de transferência carrega os editais por script (o robô não lê): conferir no site oficial |
| SP | Universidade Nove de Julho (UNINOVE) – São Paulo | a página de transferência carrega os editais por script (o robô não lê): conferir no site oficial |
| SP | Universidade Presbiteriana Mackenzie – Alphaville | descobrir a página onde esta faculdade publica os editais de transferência |
| SP | Universidade São Judas Tadeu (USJT) – Cubatão | a página de transferência carrega os editais por script (o robô não lê): conferir no site oficial |
| SP | Universidade de Taubaté (UNITAU) – Taubaté | o site bloqueia acesso automático (até aos PDFs): conferir à mão em unitau.br/concursos |
| SP | Universidade de Taubaté (UNITAU) – campus Caraguatatuba | o site bloqueia acesso automático (até aos PDFs): conferir à mão em unitau.br/concursos |
| SP | Universidade de Taubaté (UNITAU) – campus Cruzeiro | o site bloqueia acesso automático (até aos PDFs): conferir à mão em unitau.br/concursos |

## 29/10/2026 · Parte A: pendências
### UNILAGO
- Playwright em `unilago.riopreto.br`: os três links do menu ("TRANSFERÊNCIA" ×2 e "TRANSFIRA SEU CURSO PRA UNILAGO")
  levam a `https://transferencia.unilago.edu.br/`, que não responde (ERR_TIMED_OUT no navegador do dono; erro de
  navegação no Playwright). Nenhuma página nova: o link da ficha fica como está.
- Aviso público na ficha e no edital: "A página de transferência da UNILAGO está fora do ar desde 29/10/2026.
  Confirme diretamente com a faculdade." (`aviso_publico` em `faculdades.json`; teste `test_unilago_avisa_pagina_fora_do_ar`).
- `unilago.riopreto.br` entrou em `qa/links_excecoes.txt` (abre no navegador, bloqueia o robô do GitHub). O link de
  `transferencia.unilago.edu.br` continua vigiado: está de fato fora do ar, então a issue #15 segue aberta só com ele
  e fecha sozinha quando a página voltar.
- Verificação: 105 testes; `verificar.mjs` (ficha e edital, 375 e 1280 px) sem apontamentos; html-validate sem erros.

### Recuperação deste arquivo
O commit a72b556 ("QA: notas do Lighthouse no site publicado") colou o mesmo bloco de Lighthouse ~42 mil vezes
(342 mil linhas, 23 MB) e apagou o conteúdo anterior. Reconstruído com o texto de caba4f6 + uma cópia do bloco +
as seções posteriores. Nada se perdeu.

## 29/10/2026 · Parte B: captação e nutrição
| Peça | O que faz |
|---|---|
| `isca.py` | PDF "Checklist de documentos para transferência de Medicina" (`docs/checklist-documentos-transferencia-medicina.pdf`), só com as listas transcritas de 16 editais conferidos (um por PDF), cada item com faculdade, edital e página. Gerado a cada atualização; o arquivo só muda se os dados mudarem |
| `bloco_alerta` (gerar_site) + `app.js` | Inscrição em 2 etapas: e-mail e consentimento (desmarcado), depois o perfil pré-preenchido pelo diagnóstico ("Agora não" pula). Chamadas: fim do diagnóstico, ficha com prazo ("Me lembre 7 e 2 dias antes", só com prazo conferido e mais de 2 dias), ficha sem prazo e faculdade ("Avise-me quando a X abrir"), "Estudo no exterior" (perfil de base exterior) e home (discreta). Barra inferior só nas fichas e no exterior, após 60% de leitura; some quando o formulário aparece; fechada, não volta |
| `nutricao.py` + `alertas.py` | Boas-vindas com o checklist, dias 2/5/9/14 (versões exterior nos dias 2 e 9), lembretes 7 e 2 dias, resumo de segunda (8h, só com edital conferido depois da inscrição), avisos das faculdades seguidas. Atrás de `ALERTAS_ATIVOS=1`; sem ela, só simulação (monta e conta, não envia nem registra). Só recebe dicas e resumo quem aceitou o consentimento novo. O alerta atual não mudou (exceto: perfil sem curso, que só segue faculdades, não recebe o alerta geral) |
| `supabase/schema.sql` | `inscrever` soma faculdades seguidas e lembretes e não apaga o perfil num pedido sem curso. **Precisa ser rodado pelo dono**; até lá, a função antiga substitui o perfil (o site já manda os pedidos anteriores juntos) |

### Verificações
| Verificação | Resultado |
|---|---|
| Testes | 123 passando (novos em `tests/test_nutricao.py`: janela da sequência, consentimento, versões do exterior, lembretes 7/2, sem lembrete em "conferir", resumo só com novidade, simulação não registra, envio único, soma dos pedidos, isca só com itens transcritos) |
| `qa/inscricao.mjs` (Playwright, Supabase interceptado) | 20/20: consentimento desmarcado, passo 2 com semestre obrigatório e pré-preenchido, PDF oferecido, barra que não volta, console limpo |
| `qa/simular_inscricao.py` | Inscrição de teste completa (inscrever → confirmar → 21 dias): 18 e-mails em `privado/emails_exemplos/`, textos em `privado/EMAILS.md` |
| `verificar.mjs` (8 páginas, 375 e 1280 px) | 0 apontamentos do site (1 aviso de WebGL do mapa do OpenStreetMap) |
| html-validate / `interacoes.mjs` | 0 erros / 0 falhas |
| **Falhou e foi corrigido** | Item "Ato de autorização, se não constar no histórico" caía em Histórico (agora vale a 1ª palavra); resumo repetia como novos editais já avisados; frases sem dado nos e-mails ("prazos ainda mais curtos", "os erros que mais…"); lembrete oferecido em edital que encerrava hoje; atributo com aspas simples |

## 29/10/2026 · Conferência por campo
- Regra (decisão do dono): só o campo com problema fica "conferir" (`conferir_campos`: campo → aviso). O resto do
  edital, verificado no PDF, segue normal no site e nos e-mails, com o aviso ao lado do campo. Prazo final
  (`inscricao_fim`) ou o edital inteiro (`edital`) duvidosos tiram o edital dos e-mails e dos lembretes. "conferir" sem
  campos (marcação do robô) vale para o edital inteiro; se o robô marcar um edital que já tinha campos (PDF mudou,
  retificação, data suspeita), entra o campo `edital`.
- IDOMED exterior 2027.1 (Alagoinhas e Juazeiro): página da EconRio conferida em 29/10/2026 pelo Playwright. Só as
  retificações de 29/09 e 07/10, que não mudam o calendário; o Anexo 1 (p. 1) ainda traz 29/02/2027 no resultado da
  análise de isenção de disciplinas. Campo `resultado`, com fonte "Anexo 1, p. 1". O prazo de inscrição (14/01/2027)
  não é afetado: o edital volta aos e-mails, com o aviso.
- 19 editais publicados migrados (teste `test_todo_edital_publicado_conferir_diz_o_campo`). Os demais "conferir" são
  leituras automáticas do robô (`fonte_dados: regras`), que não aparecem no site nem nos e-mails.
- Verificação: 141 testes; `verificar.mjs` (IDOMED, Pitágoras, UB, FAMERP) sem apontamentos depois de corrigir o link
  "UB" da trilha (20 px; agora mínimo de 24 px); html-validate sem erros.

## 29/10/2026 · Celular: alvos de toque e resultado do diagnóstico
| Verificação | Resultado |
|---|---|
| `qa/auditoria_celular.mjs` (11 páginas × 360/390/430/Instagram) | site antigo: 44 páginas com alvos < 44 px; novo e no ar: 0 |
| `qa/resultado.mjs` | site antigo: 4 falhas (formulário aberto acima do resultado); novo e no ar: 0 |
| unittest / html-validate / `verificar.mjs` / `interacoes.mjs` / `funil.mjs` / `inscricao.mjs` / `cabecalho.mjs` | 169 ok / 0 erros / 0 apontamentos / 0 falhas / ok / ok / ok |

## 30/10/2026 · Parte D, lote 1: editais abertos
| Item | Antes → depois |
|---|---|
| Editais abertos (manuais) com documentos transcritos | 22 → 26 (de 26) |
| Com resultado transcrito (data ou regra do edital, com página) | 0 → 26 |
| Com matrícula transcrita (data, período ou regra, com página) | 0 → 26 |
| Prazo de inscrição sem página na ficha | 7 → 0 |
| Leituras automáticas do robô ("conferir", fora do site) | 65 → 64 |

- Ficha: "Resultado" e "Matrícula" em linhas próprias (`etapas_depois` em `gerar_site.py`); sem transcrição continua
  "ainda não transcritos aqui: veja no edital". Campos novos: `data_resultado`, `data_matricula`, `data_matricula_fim`,
  `resultado_texto`, `matricula_texto`, página em `evidencias`. Migração idempotente em `privado/migrar_parte_d.py`.
- **UNEX:** 2º aditivo (28/10/2026) tirou a prova (análise do histórico por ordem de entrega; resultado 1 dia útil
  depois da análise, matrícula 2 dias úteis depois). Edital consolidado A-3 lido e ligado às 4 fichas. **Vitória da
  Conquista entrou** (3º e 5º, 2 vagas); prazo a conferir: o aditivo diz 28/10 a 12/11/2026 e o A-3 escreve "28/10/27 a 12/11/27".
- **Unime:** cronograma (p. 2) diz resultado em 26/11/2026, item 8.1 (p. 7) diz 25/11: campo `resultado` a conferir, com a data mais cedo.
- **IDOMED exterior:** resultado final 02/02/2027 e matrícula 03/02/2027 (Anexo 1, p. 2); o aviso do 29/02/2027 agora diz que é a etapa de isenção (p. 1).

| Verificação | Resultado |
|---|---|
| unittest | 173 ok (novos: linha de resultado/matrícula e "nenhuma data de resultado ou matrícula sem página") |
| `qa/parte_d.mjs` (4 fichas × 375/1280) | site antigo: 8 falhas; novo e no ar: 0. Entrou na Qualidade diária |
| `verificar.mjs` / `interacoes.mjs` / html-validate | 0 apontamentos / 0 falhas / 0 erros |
