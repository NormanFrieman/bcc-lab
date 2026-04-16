#!/usr/bin/env bash
# Rastreia TODAS as queries MySQL em tempo real usando USDT probes.
# Requer MySQL 5.7 compilado com suporte a DTrace/USDT.

set -euo pipefail

MYSQLD_PID=$(pgrep -x mysqld | head -1)

if [[ -z "$MYSQLD_PID" ]]; then
    echo "ERRO: processo mysqld não encontrado. Verifique se o MySQL está rodando." >&2
    exit 1
fi

echo "==> mysqld PID: $MYSQLD_PID"
echo "==> Rastreando queries MySQL com mysqld_query.py..."
echo "    (Ctrl+C para encerrar)"
echo ""

exec /usr/sbin/mysqld_query-bpfcc -p "$MYSQLD_PID"
