"""
Gerador de carga sintética para o laboratório BCC.

Produz três tipos de tráfego para tornar as ferramentas de rastreamento
observáveis:
  - Queries RÁPIDAS:  SELECTs simples por chave primária ou índice (~< 1ms)
  - Queries LENTAS:   SELECTs com SLEEP() para simular contenção (> 100ms)
  - WRITES:           INSERTs e UPDATEs periódicos
"""

import os
import time
import random
import logging
import mysql.connector
from mysql.connector import Error

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger(__name__)

DB_CONFIG = {
    "host": os.getenv("MYSQL_HOST", "mysql"),
    "port": int(os.getenv("MYSQL_PORT", 3306)),
    "database": os.getenv("MYSQL_DATABASE", "lab"),
    "user": os.getenv("MYSQL_USER", "labuser"),
    "password": os.getenv("MYSQL_PASSWORD", "labpass"),
    "connection_timeout": 10,
}

FAST_QUERIES = [
    "SELECT * FROM produtos WHERE id = %s",
    "SELECT id, nome, preco FROM produtos WHERE categoria = %s",
    "SELECT COUNT(*) FROM pedidos WHERE status = %s",
    "SELECT p.nome, pe.quantidade FROM produtos p JOIN pedidos pe ON p.id = pe.produto_id WHERE p.id = %s",
    "SELECT AVG(preco) FROM produtos WHERE categoria = %s",
    "SELECT * FROM pedidos ORDER BY criado_em DESC LIMIT 10",
    "SELECT categoria, COUNT(*) as total FROM produtos GROUP BY categoria",
]

SLOW_QUERIES = [
    # Simula queries lentas com SLEEP — visíveis no dbslower
    "SELECT SLEEP(0.15), nome FROM produtos WHERE id = %s",
    "SELECT SLEEP(0.3), COUNT(*) FROM pedidos",
    "SELECT SLEEP(0.5), categoria, SUM(preco) FROM produtos GROUP BY categoria",
    # Queries sem índice — podem ser lentas com volume real
    "SELECT * FROM produtos WHERE nome LIKE %s",
    "SELECT * FROM pedidos pe JOIN produtos p ON p.id = pe.produto_id WHERE p.preco > %s",
]

CATEGORIAS = ["Eletrônicos", "Periféricos", "Rede", "Armazenamento", "Acessórios"]
STATUS = ["pendente", "processando", "concluido", "cancelado"]


def connect_with_retry(retries: int = 30, delay: float = 2.0):
    for attempt in range(1, retries + 1):
        try:
            conn = mysql.connector.connect(**DB_CONFIG)
            log.info("Conectado ao MySQL em %s:%s", DB_CONFIG["host"], DB_CONFIG["port"])
            return conn
        except Error as e:
            log.warning("Tentativa %d/%d — aguardando MySQL: %s", attempt, retries, e)
            time.sleep(delay)
    raise RuntimeError("Não foi possível conectar ao MySQL após %d tentativas" % retries)


def run_fast_query(cursor):
    query = random.choice(FAST_QUERIES)
    if "%s" in query:
        if "categoria" in query and "id" not in query.split("WHERE")[1] if "WHERE" in query else False:
            param = (random.choice(CATEGORIAS),)
        elif "status" in query:
            param = (random.choice(STATUS),)
        elif "nome LIKE" in query:
            param = (f"%Produto%",)
        elif "preco >" in query:
            param = (random.uniform(100, 500),)
        else:
            param = (random.randint(1, 200),)
        cursor.execute(query, param)
    else:
        cursor.execute(query)
    cursor.fetchall()


def run_slow_query(cursor):
    query = random.choice(SLOW_QUERIES)
    if "%s" in query:
        if "nome LIKE" in query:
            param = ("%Produto%",)
        elif "preco >" in query:
            param = (random.uniform(100, 500),)
        else:
            param = (random.randint(1, 200),)
        cursor.execute(query, param)
    else:
        cursor.execute(query)
    cursor.fetchall()


def run_write(conn, cursor):
    op = random.choice(["insert_evento", "update_pedido", "insert_pedido"])

    if op == "insert_evento":
        cursor.execute(
            "INSERT INTO eventos_trace (tipo, descricao) VALUES (%s, %s)",
            ("workload", f"ciclo em {time.strftime('%H:%M:%S')}"),
        )

    elif op == "update_pedido":
        cursor.execute(
            "UPDATE pedidos SET status = %s WHERE id = %s",
            (random.choice(STATUS), random.randint(1, 100)),
        )

    elif op == "insert_pedido":
        produto_id = random.randint(1, 200)
        qtd = random.randint(1, 5)
        cursor.execute(
            "SELECT preco FROM produtos WHERE id = %s",
            (produto_id,),
        )
        row = cursor.fetchone()
        if row:
            cursor.execute(
                "INSERT INTO pedidos (produto_id, quantidade, valor_total, status) VALUES (%s, %s, %s, %s)",
                (produto_id, qtd, float(row[0]) * qtd, random.choice(STATUS)),
            )

    conn.commit()


def main():
    conn = connect_with_retry()
    cursor = conn.cursor()

    cycle = 0
    fast_count = 0
    slow_count = 0
    write_count = 0

    log.info("Iniciando geração de carga — Ctrl+C para parar")
    log.info("Padrão: 10 queries rápidas, 1 lenta, 1 escrita por ciclo (a cada ~2s)")

    try:
        while True:
            cycle += 1

            # 10 queries rápidas por ciclo
            for _ in range(10):
                try:
                    run_fast_query(cursor)
                    fast_count += 1
                except Error as e:
                    log.warning("Erro em query rápida: %s", e)
                    conn = connect_with_retry()
                    cursor = conn.cursor()

            # 1 query lenta por ciclo
            try:
                run_slow_query(cursor)
                slow_count += 1
            except Error as e:
                log.warning("Erro em query lenta: %s", e)

            # 1 escrita por ciclo
            try:
                run_write(conn, cursor)
                write_count += 1
            except Error as e:
                log.warning("Erro em escrita: %s", e)
                conn.rollback()

            if cycle % 10 == 0:
                log.info(
                    "Ciclo #%d | rápidas: %d | lentas: %d | escritas: %d",
                    cycle, fast_count, slow_count, write_count,
                )

            time.sleep(0.2)

    except KeyboardInterrupt:
        log.info("Encerrando workload.")
    finally:
        cursor.close()
        conn.close()


if __name__ == "__main__":
    main()
