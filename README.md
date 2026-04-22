# BCC Lab — Rastreamento de Queries MySQL

Laboratório Docker para explorar ferramentas BPF (Berkeley Packet Filter) voltadas à observabilidade de banco de dados MySQL 5.7.

> ⚠️ **Nota importante**: As ferramentas BCC oficiais (`mysqld_qslower-bpfcc`, `dbslower-bpfcc`, `dbstat-bpfcc`) **não funcionam** com a imagem Docker `mysql:5.7` devido a incompatibilidades nos probes USDT. Este projeto inclui versões corrigidas que utilizam `query__exec__start`/`query__exec__done` em vez de `query__start`/`query__done`.

---

## Status Atual

✅ **Todas as ferramentas de tracing estão funcionando:**

| Comando | Descrição | Status |
|---------|-----------|--------|
| `make trace-query` | Rastreia todas as queries em tempo real | ✅ Funcionando |
| `make trace-slow` | Rastreia queries > 1ms | ✅ Funcionando |
| `make trace-slow-10ms` | Rastreia queries > 10ms | ✅ Funcionando |
| `make trace-stat` | Histograma de latências (5s) | ✅ Funcionando |
| `make trace-stat-10s` | Histograma de latências (10s) | ✅ Funcionando |

**Versão corrigida:** d6d6d66 - `fix: Corrige ferramentas BPF de rastreamento MySQL para usar probes USDT corretos`

---

## Ferramentas Implementadas

| Ferramenta | O que faz | Base |
|------------|-----------|------|
| `mysqld_query_fixed` | Rastreia **todas** as queries MySQL em tempo real | Original: `mysqld_qslower` (2016) |
| `dbslower_fixed` | Filtra queries acima de um **limiar de latência** | Original: `dbslower` (2017) |
| `dbstat_fixed` | Exibe **histograma** de distribuição de latências | Original: `dbstat` (2017) |

As ferramentas utilizam probes USDT (`query__exec__start` / `query__exec__done`) que funcionam corretamente com o MySQL 5.7 da imagem Docker oficial.

> **Documentação comparativa**: Veja [docs/comparacao-mysqld-qslower.md](docs/comparacao-mysqld-qslower.md), [docs/comparacao-dbslower.md](docs/comparacao-dbslower.md) e [docs/comparacao-dbstat.md](docs/comparacao-dbstat.md) para comparação detalhada entre as implementações originais do BCC e nossas versões corrigidas.

---

## Pré-requisitos

- Docker Engine ≥ 24 e Docker Compose v2
- Kernel Linux com `CONFIG_BPF=y` e `CONFIG_DEBUG_FS=y` (padrão no Ubuntu 22.04+)
- `/sys/kernel/debug` montado no host (`mount -t debugfs debugfs /sys/kernel/debug`)

Verifique:
```bash
ls /sys/kernel/debug/tracing
```

---

## Estrutura

```
bcc-lab/
├── docker-compose.yml          # orquestra mysql, workload e bcc
├── Makefile                    # atalhos de uso
├── README.md                   # este arquivo
├── bcc/
│   ├── Dockerfile              # Ubuntu 24.04 + bpfcc-tools
│   └── scripts/
│       ├── mysqld_query_fixed.py    # versão corrigida do mysqld_qslower
│       ├── dbslower_fixed.py        # versão corrigida do dbslower
│       ├── dbstat_fixed.py          # versão corrigida do dbstat
│       ├── run_mysqld_query.sh
│       ├── run_dbslower.sh
│       └── run_dbstat.sh
├── mysql/
│   └── init.sql                # cria banco `lab`, tabelas e 200 produtos
├── workload/
│   ├── Dockerfile
│   └── workload.py             # gerador de carga: queries rápidas, lentas e escritas
└── docs/                       # documentação técnica
    ├── comparacao-dbslower.md
    ├── comparacao-dbstat.md
    ├── comparacao-mysqld-qslower.md
    └── resumo-bcc-mysql-troubleshooting.md
```

---

## Início rápido

```bash
# 1. Sobe o ambiente completo
make up

# 2. Rastreia TODAS as queries (em outro terminal)
make trace-query

# 3. Rastreia queries lentas > 1ms
make trace-slow

# 4. Rastreia queries lentas > 10ms
make trace-slow-10ms

# 5. Histograma de latências (atualiza a cada 5s)
make trace-stat

# 6. Histograma de latências (atualiza a cada 10s)
make trace-stat-10s
```

---

## Comandos disponíveis

```
make up               Sobe todos os containers com build
make down             Derruba e remove volumes
make restart          Reinicia o ambiente

make trace-query      mysqld_query_fixed — todas as queries
make trace-slow       dbslower_fixed — queries > 1ms
make trace-slow-10ms  dbslower_fixed — queries > 10ms
make trace-stat       dbstat_fixed — histograma (5s)
make trace-stat-10s   dbstat_fixed — histograma (10s)

make shell-bcc        Shell interativo no container BCC
make mysql-cli        Cliente MySQL interativo

make logs-workload    Logs do gerador de carga
make logs-mysql       Logs do MySQL
make ps               Status dos containers
```

---

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
que as ferramentas BPF vejam o processo `mysqld` e anexem probes USDT
diretamente ao binário, mesmo estando em containers separados.

### Por que as ferramentas originais não funcionam?

As ferramentas BCC oficiais esperam os probes `query__start`/`query__done`,
que na imagem `mysql:5.7` Docker possuem formato de argumentos incompatível
com o BCC (compilado sem `systemtap-sdt-dev`).

Nossas ferramentas corrigidas usam `query__exec__start`/`query__exec__done`,
que funcionam corretamente.

Para mais detalhes, consulte: [docs/resumo-bcc-mysql-troubleshooting.md](docs/resumo-bcc-mysql-troubleshooting.md)

---

## Gerador de carga

O `workload.py` gera tráfego contínuo com três padrões:

- **Queries rápidas** (10/ciclo): SELECTs por índice, JOINs simples — tipicamente < 1ms
- **Queries lentas** (1/ciclo): SELECTs com `SLEEP(0.15–0.5s)` — visíveis no `dbslower_fixed`
- **Escritas** (1/ciclo): INSERTs e UPDATEs nas tabelas `pedidos` e `eventos_trace`

Acompanhe o tráfego:
```bash
make logs-workload
```

---

## Exemplos de saída esperada

### `make trace-query`
```
==> mysqld PID: 1
==> Rastreando queries MySQL com mysqld_query_fixed.py...
    (Ctrl+C para encerrar)

Tracing MySQL queries slower than 0 ms...
TIME(s)        PID          MS QUERY
6916.068146    40757     0.107 SELECT preco FROM produtos WHERE id = 183
6916.068588    40757     0.140 INSERT INTO pedidos (produto_id, quantidade, valor_total, status) VALUES (183, 5, 2900.15, 'pendente')
6916.068868    40757     5.928 commit
6916.275621    40757     0.243 SELECT COUNT(*) FROM pedidos WHERE status = 'concluido'
```

### `make trace-slow`
```
==> mysqld PID: 1
==> Rastreando queries mais lentas que 1ms...
    (Ctrl+C para encerrar)

Tracing MySQL queries slower than 1.0 ms...
TIME(s)        PID          MS QUERY
6916.499541    40757   150.326 SELECT SLEEP(0.15), nome FROM produtos WHERE id = 87
6917.082631    40757     6.098 commit
```

### `make trace-stat`
```
==> mysqld PID: 1
==> Coletando histograma de latências (intervalo: 5s)...
    (Ctrl+C para encerrar)

Tracing MySQL query latencies... Hit Ctrl-C to end.
Waiting 5 seconds for first report...

Query latency distribution (microseconds):
     [b'1us', b'2us', b'4us', b'8us', b'16us', b'32us', b'64us', b'128us', b'256us', b'512us', b'1ms', b'2ms', b'4ms', b'8ms', b'16ms', b'32ms', b'64ms', b'128ms', b'256ms', b'512ms+'] : count     distribution
         0 -> 1          : 0        |                                        |
         2 -> 3          : 0        |                                        |
         4 -> 7          : 0        |                                        |
         8 -> 15         : 0        |                                        |
        16 -> 31         : 0        |                                        |
        32 -> 63         : 4        |**********                              |
        64 -> 127        : 9        |**********************                  |
       128 -> 255        : 16       |****************************************|
       256 -> 511        : 2        |*****                                   |
       512 -> 1023       : 2        |*****                                   |
      1024 -> 2047       : 0        |                                        |
      2048 -> 4095       : 0        |                                        |
      4096 -> 8191       : 3        |*******                                 |
     81920 -> 16383      : 0        |                                        |
    131072 -> 262143     : 1        |**                                      |
    262144 -> 524287     : 1        |**                                      |
```

---

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

---

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

**Ferramentas BCC originais não funcionam**
Este é um problema conhecido. As ferramentas oficiais (`mysqld_qslower-bpfcc`,
`dbslower-bpfcc`, `dbstat-bpfcc`) não funcionam com a imagem `mysql:5.7` Docker.
Use nossas versões corrigidas via `make trace-*`.

Consulte [docs/resumo-bcc-mysql-troubleshooting.md](docs/resumo-bcc-mysql-troubleshooting.md) para detalhes completos.

---

## Documentação Técnica

A pasta `docs/` contém documentação detalhada comparando as ferramentas BCC originais com nossas versões corrigidas:

| Documento | Ferramenta | Original | Corrigido | Descrição |
|-----------|------------|----------|-----------| -----------|
| [comparacao-mysqld-qslower.md](docs/comparacao-mysqld-qslower.md) | `mysqld_qslower` | Original (2016) | `mysqld_query_fixed.py` | Comparação detalhada do rastreador de queries |
| [comparacao-dbslower.md](docs/comparacao-dbslower.md) | `dbslower` | Original (2017) | `dbslower_fixed.py` | Comparação do filtro de queries lentas |
| [comparacao-dbstat.md](docs/comparacao-dbstat.md) | `dbstat` | Original (2017) | `dbstat_fixed.py` | Comparação do histograma de latências |
| [resumo-bcc-mysql-troubleshooting.md](docs/resumo-bcc-mysql-troubleshooting.md) | - | - | - | Resumo completo do troubleshooting realizado |
| [ebpf-database-tracing.md](docs/ebpf-database-tracing.md) | - | - | - | Conceitos de eBPF para tracing de banco de dados |
| [usdt-probes-e-ferramentas-bcc.md](docs/usdt-probes-e-ferramentas-bcc.md) | - | - | - | USDT probes e ferramentas BCC |
| [implementando-ferramentas-usdt-customizadas.md](docs/implementando-ferramentas-usdt-customizadas.md) | - | - | - | Guia de implementação de ferramentas customizadas |

## Histórico de Correções

**Commit com as correções:** `d6d6d66` — `fix: Corrige ferramentas BPF de rastreamento MySQL para usar probes USDT corretos`

### Resumo do Problema Resolvido

**Erro Original:**
```
/scripts/run_mysqld_query.sh: line 19: /usr/sbin/mysqld_query-bpfcc: No such file or directory
```

As ferramentas BCC oficiais (`mysqld_qslower-bpfcc`, `dbslower-bpfcc`, `dbstat-bpfcc`) falhavam silenciosamente com a imagem `mysql:5.7` Docker.

**Causa Raiz:**
As ferramentas BCC originais usam os probes `query__start`/`query__done`, que **não funcionam** com a imagem `mysql:5.7` (Oracle Linux) devido a diferenças no formato de compilação dos probes USDT.

**Solução:**
Scripts Python personalizados usando os probes `query__exec__start`/`query__exec__done`, que funcionam corretamente.

## Referências

- [BCC - BPF Compiler Collection](https://github.com/iovisor/bcc)
- [Linux MySQL Slow Query Tracing with BCC](http://www.brendangregg.com/blog/2016-10-04/linux-bcc-mysqld-qslower.html)
- [MySQL 5.7 DTrace Documentation](https://dev.mysql.com/doc/refman/5.7/en/dba-dtrace-server.html)
- [BCC Issue #4761 - mysqld_qslower não funciona](https://github.com/iovisor/bcc/issues/4761)
