#!/usr/bin/env bash
# Publica o commit da rodada (radar, monitor, guardião) mesmo se alguém publicou no meio da rodada.
# Conflito só pode ocorrer em arquivo GERADO (docs/dados.js, index.html, sw.js...): vale o que esta rodada gerou (-X theirs) e,
# com "regenerar", o site é gerado de novo a partir dos dados já mesclados e do código novo, para não ficar página velha.
# Se o GitHub recusar o push (erro dele), tenta de novo, até 4 vezes. Uso: bash publicar_rodada.sh [regenerar]
for tentativa in 1 2 3 4; do
  if git pull --rebase -X theirs; then
    if [ "$1" = "regenerar" ]; then
      python gerar_site.py > /dev/null && git add data docs && { git diff --cached --quiet || git commit -q --amend --no-edit; }
    fi
    git push && exit 0
  else
    git rebase --abort 2>/dev/null || true
  fi
  echo "push recusado (tentativa $tentativa); aguardando e tentando de novo"
  sleep $((tentativa * 20))
done
exit 1
