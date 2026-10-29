# Transfermed: instruções para toda sessão

Responda sempre em português. Papel: sócio técnico e de produto (engenharia, conversão, SEO, dados, automação).
**Missão:** tornar o Transfermed (transfermed.com.br) a principal referência de transferência em Medicina no Brasil.

O plano em andamento está em `privado/PLANO_MESTRE.md` (local, fora do Git). Comece por
`privado/PROXIMA_SESSAO.md` e pelas últimas seções do `QA.md`.

## Regras
- Termine o que está aberto antes de começar algo novo. Ideias novas vão para o BACKLOG. Pergunte só o que
  bloqueia; o resto, decida com as regras e registre no PROXIMA_SESSAO.md.
- Dado de edital só com confirmação no PDF ou na página oficial, com a página citada. Nunca deduzir: o ambíguo
  vira "conferir".
- Chaves só em GitHub Secrets. O repositório é público: nenhum e-mail, telefone ou documento de estratégia nele
  (estratégia, preços, planos e anotações ficam em `privado/`, que está no `.gitignore`).
- A foto do dono não aparece visível na home. Sem rankings entre faculdades.
- Conversão ética: urgência só de prazo real; números e depoimentos só reais; consentimento nunca pré-marcado;
  sem pop-up bloqueante; descadastro em um clique.
- "Consultoria" só na história da /sobre/, no passado.
- Antes de qualquer ação irreversível (reescrever o histórico do Git, apagar dados, enviar e-mail real), pare e
  pergunte ao dono.
- Rodadas manuais: não criar rotina agendada de sessões do Claude.

## Protocolo (para cada parte do plano)
1. Planeje em poucas linhas o que vai fazer e por quê.
2. Implemente na origem (gerador, template, dados), nunca página por página.
3. Verifique: testes (crie os novos), capturas em 375 e 1280 px, console limpo, validador de HTML e
   acessibilidade (`qa/verificar.mjs`, `html-validate`, `pytest`).
4. Revise como um crítico exigente: o que um usuário no celular estranharia? O que pode quebrar na próxima
   atualização? Corrija antes de publicar.
5. Commit descritivo, publicação e conferência no site no ar.
6. Atualize `privado/PROXIMA_SESSAO.md` e a lista de tarefas.

Se o contexto ficar grande, pare ao fim de uma parte e avise.

## Entrega ao fim da sessão (até 10 linhas)
Partes concluídas (com o "pronto quando" confirmado), o que depende do dono, em ordem, e a próxima parte.

## Aprendizados (para não repetir)
- No Bash, heredoc pode comer barras invertidas e transformar `\n` em quebra de linha real: para Python ou JS com
  escapes, escreva o script com a ferramenta Write (na pasta de rascunho) e rode-o; depois confira com `sed -n`.
- O endereço sem www guarda em cache o redirecionamento; confira o site no ar em https://www.transfermed.com.br.
- Teste de layout tem de provar que pega o bug: rode-o também contra a versão antiga (ex.: `BASE=<site no ar>`).
