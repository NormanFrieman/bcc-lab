# BCC Lab — Rastreamento de Queries MySQL

Laboratório Docker para explorar as ferramentas BCC (BPF Compiler Collection)
voltadas à observabilidade de banco de dados MySQL.

## Ferramentas cobertas

| Ferramenta | O que faz |
|---|---|
| `mysqld_query` | Rastreia **todas** as queries MySQL em tempo real via USDT probes |
| `dbslower` | Filtra queries acima de um **limiar de latência** configurável |
| `dbstat` | Exibe **histograma** de distribuição de latências em intervalos |

> As três ferramentas usam probes USDT (`query__start` / `query__done`)
> presentes apenas no **MySQL 5.7**. O MySQL 8.0+ removeu esse suporte.

## Pré-requisitos

- Docker Engine ≥ 24 e Docker Compose v2
- Kernel Linux com `CONFIG_BPF=y` e `CONFIG_DEBUG_FS=y` (padrão no Ubuntu 22.04+)
- `/sys/kernel/debug` montado no host (`mount -t debugfs debugfs /sys/kernel/debug`)

Verifique:
```bash
ls /sys/kernel/debug/tracing
```

## Estrutura

```
bcc-lab/
├── docker-compose.yml      # orquestra mysql, workload e bcc
├── Makefile                # atalhos de uso
├── bcc/
│   ├── Dockerfile          # Ubuntu 22.04 + bpfcc-tools
│   └── scripts/
│       ├── run_mysqld_query.sh
│       ├── run_dbslower.sh
│       └── run_dbstat.sh
├── mysql/
│   └── init.sql            # cria banco `lab`, tabelas e 200 produtos
└── workload/
    ├── Dockerfile
    └── workload.py         # gerador de carga: queries rápidas, lentas e escritas
```

## Início rápido

```bash
# 1. Sobe o ambiente completo
make up

# 2. Rastreia TODAS as queries (em outro terminal)
make trace-query

# 3. Rastreia queries lentas > 1ms
make trace-slow

# 4. Histograma de latências (atualiza a cada 5s)
make trace-stat
```

## Comandos disponíveis

```
make up               Sobe todos os containers com build
make down             Derruba e remove volumes
make restart          Reinicia o ambiente

make trace-query      mysqld_query — todas as queries
make trace-slow       dbslower — queries > 1ms
make trace-slow-10ms  dbslower — queries > 10ms
make trace-stat       dbstat — histograma (5s)
make trace-stat-10s   dbstat — histograma (10s)

make shell-bcc        Shell interativo no container BCC
make mysql-cli        Cliente MySQL interativo

make logs-workload    Logs do gerador de carga
make logs-mysql       Logs do MySQL
make ps               Status dos containers
```

## Como funciona o rastreamento

```
Container BCC (privileged)
    │
    ├─ pid: "service:mysql"  ← compartilha o namespace PID do MySQL
    │
    ├─ /sys/kernel/debug     ← acesso ao tracefs do host
    ├─ /lib/modules          ← módulos do kernel
    └─ /usr/src              ← headers do kernel
```

O container `bcc` compartilha o namespace PID do `mysql`, o que permite
que as ferramentas BPF vejam o processo `mysqld` e anexem probes USDT/uprobes
diretamente ao binário, mesmo estando em containers separados.

## Gerador de carga

O `workload.py` gera tráfego contínuo com três padrões:

- **Queries rápidas** (10/ciclo): SELECTs por índice, JOINs simples — tipicamente < 1ms
- **Queries lentas** (1/ciclo): SELECTs com `SLEEP(0.15–0.5s)` — visíveis no `dbslower`
- **Escritas** (1/ciclo): INSERTs e UPDATEs nas tabelas `pedidos` e `eventos_trace`

Acompanhe o tráfego:
```bash
make logs-workload
```

## Exemplos de saída esperada

### `make trace-query`
```
TIME(s)     PID    QUERY
0.000       1234   SELECT * FROM produtos WHERE id = 42
0.001       1234   SELECT categoria, COUNT(*) FROM produtos GROUP BY categoria
0.153       1234   SELECT SLEEP(0.15), nome FROM produtos WHERE id = 7
```

### `make trace-slow`
```
TIME(s)     PID    MS        QUERY
0.153       1234   153.41    SELECT SLEEP(0.15), nome FROM produtos WHERE id = 7
0.312       1234   301.88    SELECT SLEEP(0.3), COUNT(*) FROM pedidos
```

### `make trace-stat`
```
     usecs               : count     distribution
         0 -> 1          : 0        |                                        |
         2 -> 3          : 12       |***                                     |
         4 -> 7          : 47       |**************                          |
         8 -> 15         : 89       |**************************              |
        16 -> 31         : 134      |****************************************|
       ...
   131072 -> 262143      : 3        |                                        |
```

## Exploração avançada

Dentro do shell BCC (`make shell-bcc`) você tem acesso a todas as ferramentas
do pacote `bpfcc-tools`. Alguns exemplos úteis:

```bash
# Rastreia chamadas de sistema relacionadas a I/O de disco
biolatency-bpfcc

# Rastreia conexões TCP novas
tcpconnect-bpfcc

# Mostra chamadas de sistema lentas
syscount-bpfcc

# Lista todas as ferramentas disponíveis
ls /usr/sbin/*-bpfcc
```

## Troubleshooting

**"mysqld não encontrado"**
O container `bcc` precisa compartilhar o namespace PID do `mysql`.
Verifique com `make ps` se o serviço `mysql` está `healthy`.

**"Cannot open debugfs"**
```bash
sudo mount -t debugfs debugfs /sys/kernel/debug
```

**"Permission denied / operation not permitted"**
Confirme que o container `bcc` está rodando com `privileged: true`.
Verifique: `docker inspect bcc-tools | grep Privileged`

**MySQL 8.0 / probes não encontradas**
As ferramentas USDT requerem MySQL 5.7. Se você precisar usar MySQL 8+,
consulte o modo uprobe de `dbslower` (opção `-m uprobe`).
