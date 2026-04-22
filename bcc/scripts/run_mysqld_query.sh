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
echo "==> Rastreando queries MySQL com mysqld_query_fixed.py..."
echo "    (Ctrl+C para encerrar)"
echo ""

# Usa o script Python corrigido com threshold de 0ms para capturar todas as queries
# Nota: A ferramenta mysqld_qslower-bpfcc tem um bug - usa nomes de probe incorretos
exec python3 /scripts/mysqld_query_fixed.py "$MYSQLD_PID" 0
