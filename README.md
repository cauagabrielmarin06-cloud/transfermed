# Transfermed Radar: editais de transferência de Medicina

Robô que visita os sites das faculdades todo dia, encontra editais de transferência de Medicina
(externa, interna e para quem estuda no exterior), lê o PDF e atualiza a base e o site sozinho.

## O que tem aqui

| Arquivo | Para que serve |
|---|---|
| `radar.py` | O robô. |
| `gerar_site.py` | Gera o site em `docs/`: início com mapa-radar, diagnóstico, exterior, uma página por faculdade e por edital (linha do tempo, calendário `.ics` e imagem de prévia para WhatsApp), mais o aplicativo instalável. O robô chama no fim de cada execução. Editais conferidos à mão aparecem completos; os novos que o robô acha aparecem como "novo, ainda não conferido", com link oficial. |
| `data/mapa_brasil.json`, `fontes/Inter.ttf` | Contorno dos estados para o mapa e a fonte usada nas imagens de prévia. |
| `data/faculdades.json` | Uma ficha por faculdade (170, com todas as escolas médicas de SP, MG e BA): onde fica, tipo, páginas de editais, histórico. **Para adicionar uma faculdade, é aqui.** |
| `data/faculdades_exterior.json` | Sugestões do campo "sua faculdade" para quem estuda no exterior (nome e país). Só ajudam a digitar. |
| `data/editais.json` | A base de editais (cada um com modalidade, datas, vagas e a página do PDF de cada informação). |
| `data/relatorio_qualidade.md` | O que falta ou precisa ser conferido (gerado a cada execução). |
| `data/ultima_execucao.json` | Resumo da última rodada: novos, retificações e páginas com erro. |
| `docs/` | O site gerado. Não edite as páginas à mão: mude `gerar_site.py`, `docs/assets/estilo.css` ou `docs/assets/app.js`. |
| `alertas.py` | Envia a confirmação e os alertas por e-mail (GitHub Actions a cada 30 min). |
| `supabase/schema.sql` | Banco dos alertas: tabelas protegidas e funções de inscrever, confirmar e descadastrar. |
| `CREDITOS.md`, `licencas/` | Créditos e licenças da fonte, do mapa e da lista de cidades. |
| `tests/` | Testes do robô, do site e dos alertas. |
| `QA.md` | O que foi conferido à mão, o que falhou e como foi corrigido. |
| `.github/workflows/radar.yml` | Faz o robô rodar sozinho todo dia no GitHub (de graça). |

## Como ele decide

1. Visita as páginas de cada faculdade em `data/faculdades.json` (em sites WordPress, procura PDFs direto na biblioteca de mídia).
2. Pega links de editais de transferência de Medicina, externa ou interna. Ignora resultados, gabaritos,
   convocações e editais de outros cursos.
3. Aditivos, retificações e erratas marcam como **conferir** o edital que eles citam.
4. Se um PDF já lido mudar, o edital vira **conferir** (possível retificação).
5. Extrai os dados e guarda em `evidencias` a página do PDF de cada informação. Sem chave de IA usa regras
   simples (e marca **conferir**); com `ANTHROPIC_API_KEY` usa o Claude (mais preciso, custa centavos por edital).
6. Confere as datas por código: fim antes do início, ano errado, prova antes da inscrição.
7. Guarda só editais dos últimos 2 anos.

## Adicionar uma faculdade em menos de 2 minutos

Abra `data/faculdades.json`, copie uma ficha parecida e troque os campos:

```json
{
  "id": "sigla-cidade",
  "nome": "Nome completo (SIGLA)",
  "sigla": "SIGLA",
  "cidade": "Cidade",
  "uf": "SP",
  "lat": -20.28,
  "lon": -50.24,
  "tipo": "particular",
  "site": "https://site-oficial",
  "paginas_editais": ["https://pagina-onde-saem-os-editais"],
  "modalidades_costuma_abrir": ["externa"],
  "meses_costuma_abrir": [6, 11],
  "aceita_exterior": "varia",
  "medicina_confirmada": true,
  "ultima_conferencia": "2026-10-24",
  "observacoes": ""
}
```

- `tipo`: `pública federal`, `pública estadual`, `municipal com mensalidade`, `particular` ou `filantrópica`.
- Latitude e longitude: procure a cidade no Google Maps, clique com o botão direito e copie os números.
- Se o site for WordPress, acrescente `"wordpress": "https://site-oficial"` (o robô acha PDFs sozinho).
- Se ainda não souber a página dos editais, deixe `"paginas_editais": []` e escreva o que falta em `"pendente"`.
  Ela aparece no relatório de qualidade até alguém completar.

## Rodar no seu computador (Windows)

```powershell
pip install -r requirements.txt
python -m unittest discover tests
python radar.py
```

Para ver o site no computador, gere as páginas e abra um servidor local (o diagnóstico precisa dele):

```powershell
python gerar_site.py
python -m http.server 8765 --directory docs
```

Depois abra http://localhost:8765 no navegador.

## Colocar no ar, rodando sozinho (grátis)

1. Crie uma conta em https://github.com e um repositório novo (ex.: `radar-editais`).
2. Suba esta pasta para o repositório (o Claude Code faz isso com você).
3. No repositório: **Settings > Pages** → Source: *Deploy from a branch* → Branch `main`, pasta `/docs`.
4. Em **Actions**, abra "Radar de editais" e clique em **Run workflow** para testar.
   Depois disso ele roda sozinho todo dia de manhã.
5. (Opcional) Para usar IA na leitura: **Settings > Secrets and variables > Actions >
   New repository secret**, nome `ANTHROPIC_API_KEY`, valor = sua chave da API.

## Ativar os alertas por e-mail (grátis)

Os alertas usam dois serviços gratuitos: **Supabase** (guarda e-mail e perfil) e **Brevo** (envia os e-mails,
até 300 por dia). Sem eles o site funciona normalmente e o formulário avisa que os alertas estão sendo ativados.

1. **Supabase:** crie uma conta em https://supabase.com e um projeto (plano Free). Em **SQL Editor > New query**,
   cole o arquivo `supabase/schema.sql` inteiro e clique em **Run**.
2. Em **Project Settings > API**, copie: o **Project URL**, a chave **anon public** e a chave **service_role**.
   A `service_role` é secreta: nunca coloque no site.
3. **Brevo:** crie uma conta em https://www.brevo.com (plano Free). Em **Senders**, cadastre e confirme o e-mail
   remetente. Em **SMTP & API > API Keys**, gere uma chave.
4. No GitHub: **Settings > Secrets and variables > Actions**:
   - *Secrets*: `SUPABASE_SERVICE_KEY` (service_role) e `BREVO_API_KEY`.
   - *Variables*: `SUPABASE_URL`, `SUPABASE_ANON_KEY` (anon public), `REMETENTE_EMAIL`, `REMETENTE_NOME`
     (ex.: Transfermed) e `CONTATO_EMAIL` (aparece na página de privacidade).
5. Rode o workflow **Radar de editais** (para o site receber a configuração) e depois **Alertas por e-mail**.

Testar sem conta nenhuma: `python alertas.py --simular` usa um banco em arquivo e grava os e-mails como
`.html` em `.trabalho/emails/`.

## Endereço do site e prévias de compartilhamento

As prévias do WhatsApp precisam do endereço completo do site. O padrão é `https://www.transfermed.com.br`.
Se o site ficar em outro endereço (ex.: `https://SEU-USUARIO.github.io/radar-editais`), defina a variável
`SITE_URL` antes de rodar (no GitHub: **Settings > Secrets and variables > Actions > Variables**).

## Importante

- Editais marcados `manual` foram lidos à mão dos PDFs oficiais, com conferência registrada em `QA.md`.
- Editais com vários campi viram um registro por campus, para a distância ficar certa.
- O site deixa claro que a decisão final (vaga e aproveitamento) é sempre da faculdade.
