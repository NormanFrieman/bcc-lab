#!/usr/bin/env bash
# Exibe histograma de latências de queries MySQL em intervalos regulares.
# Uso: ./run_dbstat.sh [intervalo_em_segundos]
#
# Exemplos:
#   ./run_dbstat.sh       -> atualiza a cada 5s
#   ./run_dbstat.sh 10    -> atualiza a cada 10s

set -euo pipefail

INTERVAL=${1:-5}

MYSQLD_PID=$(pgrep -x mysqld | head -1)

if [[ -z "$MYSQLD_PID" ]]; then
    echo "ERRO: processo mysqld não encontrado. Verifique se o MySQL está rodando." >&2
    exit 1
fi

echo "==> mysqld PID: $MYSQLD_PID"
echo "==> Coletando histograma de latências com dbstat (intervalo: ${INTERVAL}s)..."
echo "    (Ctrl+C para encerrar)"
echo ""

exec /usr/sbin/dbstat-bpfcc mysql -p "$MYSQLD_PID" "$INTERVAL"
