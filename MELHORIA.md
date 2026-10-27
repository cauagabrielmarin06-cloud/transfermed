# Rodada de melhoria (Camada 2)

Roteiro que o Claude segue sempre que o dono do projeto disser **"rodada de melhoria"**.
A Camada 1 (GitHub Actions, sem IA) vigia o site todo dia e abre issues; a rodada de melhoria resolve o que ela
apontou e melhora o próprio sistema.

## Regras que nunca mudam
1. Nenhuma data, vaga, requisito ou regra de edital é publicada sem confirmação no PDF ou na página oficial.
   Na dúvida, fica `status: "conferir"` com o motivo em `observacao`, nunca um palpite.
2. Em conflito entre fontes, prevalece o edital, e a divergência fica visível para o aluno (`observacao`).
3. Toda publicação passa pelos testes (`python -m unittest discover tests`). Se algum falhar, não publica.
4. Nada de apagar dados históricos: edital encerrado fica arquivado (só sai da base o que **não é** edital:
   anexo, resultado, cópia, outro curso, e nesse caso a URL vira `conhecida` em `data/processados.json`).
5. Mudanças grandes de layout, estrutura ou texto institucional viram proposta no `BACKLOG.md` para o dono
   aprovar; não vão direto ao ar.

## 1. Ler a situação
- Issues abertas: `gh issue list --state open` (ou https://github.com/cauagabrielmarin06-cloud/transfermed/issues).
- `QA.md` (últimas seções e pendências), `BACKLOG.md` e o último `data/relatorio_qualidade.md`.
- Resultado das últimas execuções: `gh run list --limit 10`.

## 2. Ordem de prioridade
| | O quê | Etiquetas |
|---|---|---|
| a | Prazos próximos, editais novos e retificações | `prazo`, `edital-novo`, `retificação` |
| b | Dados a conferir | `conferir` |
| c | Links e erros | `link-quebrado` |
| d | Acessibilidade e performance | `qualidade` |
| e | Cobertura de novos estados (ordem do PROMPT_MESTRE: resto do Brasil, estado por estado) | — |
| f | Melhorias de experiência e de conteúdo (do `BACKLOG.md`, só as aprovadas) | — |

Dentro de cada nível, o que tem prazo mais curto vem primeiro.

## 3. Edital novo ou alterado
1. Baixar o PDF oficial (e as retificações). PDF escaneado: ler por imagem.
2. Preencher ou atualizar o registro em `data/editais.json` com `fonte_dados: "manual"`, `conferido_em` e, em
   `evidencias`, **a página do PDF de cada campo**.
3. Datas impossíveis, contradições ou anexos ausentes: `status: "conferir"` e explicar em `observacao`.
4. Atualizar a ficha da faculdade (`modalidades_costuma_abrir`, `meses_costuma_abrir`, `ultima_conferencia`).
5. O que não for edital sai da base e vira `conhecida` em `data/processados.json`.
6. Gravar as mudanças por script em `.trabalho/` (como `bahia.py`), para ficar reproduzível.

## 4. Verificar antes de publicar
```
python -m unittest discover tests
python gerar_site.py
python -m http.server 8765 --directory docs      # em outro terminal
cd qa
PLAYWRIGHT_BROWSERS_PATH=0 node verificar.mjs    # capturas, console, axe, layout
npx html-validate --config .htmlvalidate.json "../docs/**/*.html"
npx linkinator http://127.0.0.1:8765/ --recurse --concurrency 4 --skip "^(?!http://127\.0\.0\.1)"
```
Olhar as capturas em `qa/screenshots` (375 e 1280 px). Reconferir 3 editais sorteados contra o PDF:
`python qa/reconferir.py --n 3 --faculdade <ids novos>` (datas, taxa e vagas na página citada; texto fica para ler).
Com pouca memória, `PAGINAS="nome:/caminho/,..." node verificar.mjs` roda só as páginas novas.
Só publica (commit + push) se tudo passar; a qualidade e o monitor rodam de novo no dia seguinte.

## 5. Registrar
- `CHANGELOG.md`: o que mudou para o aluno (data, editais, correções, novidades).
- `QA.md`: o que foi verificado, o que falhou e como foi corrigido.
- Fechar as issues resolvidas com um comentário curto (as automáticas fecham sozinhas).

## 6. Propor melhorias
Ao final, de 1 a 3 itens novos no `BACKLOG.md`, com base no que foi observado: o que está lento, confuso,
faltando ou repetitivo de manter. Cada item: problema observado, proposta, esforço (P/M/G) e se precisa de
aprovação.

## 7. Melhorar o processo
- Tarefa manual que se repetiu → automatizar na Camada 1 (monitor, qualidade ou robô).
- Erro que passou despercebido → criar o teste que o pegaria (em `tests/`).
- Site que bloqueia robôs, conferido no navegador → incluir em `qa/links_excecoes.txt` com o motivo no `QA.md`.
