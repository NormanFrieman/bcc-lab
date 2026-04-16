#!/usr/bin/env bash
# Rastreia queries MySQL mais lentas que um limiar (padrão: 1ms).
# Uso: ./run_dbslower.sh [limiar_em_ms]
#
# Exemplos:
#   ./run_dbslower.sh        -> queries > 1ms
#   ./run_dbslower.sh 10     -> queries > 10ms
#   ./run_dbslower.sh 0      -> todas as queries (sem filtro)

set -euo pipefail

THRESHOLD=${1:-1}

MYSQLD_PID=$(pgrep -x mysqld | head -1)

if [[ -z "$MYSQLD_PID" ]]; then
    echo "ERRO: processo mysqld não encontrado. Verifique se o MySQL está rodando." >&2
    exit 1
fi

echo "==> mysqld PID: $MYSQLD_PID"
echo "==> Rastreando queries mais lentas que ${THRESHOLD}ms com dbslower..."
echo "    (Ctrl+C para encerrar)"
echo ""

exec /usr/sbin/dbslower-bpfcc mysql -p "$MYSQLD_PID" -d "$THRESHOLD"
