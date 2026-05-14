#!/usr/bin/env bash
set -euo pipefail

IMAGE="${ACTIONS_IMAGE:-python:3.12.13-slim-bookworm}"
PLATFORM="${ACTIONS_PLATFORM:-linux/amd64}"
CONTAINER_ENGINE="${CONTAINER_ENGINE:-podman}"
RUN_SYNC="${RUN_SYNC:-0}"

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
WORKDIR="/tmp/calendario-mirassolfc-actions"

if ! command -v "$CONTAINER_ENGINE" >/dev/null 2>&1; then
  echo "Erro: $CONTAINER_ENGINE não encontrado no PATH." >&2
  exit 1
fi

echo "============================================================"
echo "Simulando GitHub Actions localmente"
echo "Imagem: $IMAGE"
echo "Plataforma: $PLATFORM"
echo "Engine: $CONTAINER_ENGINE"
echo "Sincronização Google Calendar: $RUN_SYNC"
echo "============================================================"

"$CONTAINER_ENGINE" run --rm \
  --platform "$PLATFORM" \
  -v "$REPO_ROOT:/repo:ro" \
  -e "RUN_SYNC=$RUN_SYNC" \
  -e SERVICE_ACCOUNT_KEY \
  -e "GOOGLE_APPLICATION_CREDENTIALS=$WORKDIR/service-account.json" \
  "$IMAGE" \
  bash -lc "
    set -euo pipefail

    apt-get update >/dev/null
    apt-get install -y --no-install-recommends git rsync ca-certificates >/dev/null
    rm -rf /var/lib/apt/lists/*

    rm -rf '$WORKDIR'
    mkdir -p '$WORKDIR'
    rsync -a --exclude .git --exclude .venv --exclude __pycache__ /repo/ '$WORKDIR'/
    cd '$WORKDIR'

    echo
    echo 'Python:'
    python --version

    echo
    echo 'Instalando dependências'
    python -m pip install --upgrade pip
    pip install -r requirements.txt

    echo
    echo 'Rodando testes'
    python -m unittest discover -s tests -p 'test_*.py'

    echo
    echo 'Rodando scraper'
    python scraper.py

    echo
    echo 'Validando mirassolfc.ics'
    python - <<'PY'
import re
from pathlib import Path

content = Path('mirassolfc.ics').read_text(encoding='utf-8')
uids = re.findall(r'^UID:(.+)$', content, re.M)
events = content.count('BEGIN:VEVENT')
duplicates = len(uids) - len(set(uids))

print(f'events={events}')
print(f'unique_uids={len(set(uids))}')
print(f'duplicates={duplicates}')

if events == 0:
    raise SystemExit('Nenhum evento gerado no .ics')
if duplicates:
    raise SystemExit('UID duplicado encontrado no .ics')
PY

    if [ \"\$RUN_SYNC\" = '1' ]; then
      if [ -z \"\${SERVICE_ACCOUNT_KEY:-}\" ]; then
        echo 'RUN_SYNC=1 exige SERVICE_ACCOUNT_KEY no ambiente.' >&2
        exit 1
      fi

      echo
      echo 'Configurando service-account.json'
      printf '%s' \"\$SERVICE_ACCOUNT_KEY\" > service-account.json

      echo
      echo 'Rodando sincronização'
      python calendar_cli.py update

      echo
      echo 'Conferindo contagem'
      python calendar_cli.py info -e

      rm -f service-account.json
    fi

    echo
    echo 'Simulação concluída com sucesso'
  "
