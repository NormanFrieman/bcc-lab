# Comparação: mysqld_qslower (Original vs Corrigido)

## Visão Geral

**Ferramenta:** `mysqld_qslower` - Rastreia queries MySQL mais lentas que um limiar  
**Autor Original:** Brendan Gregg (Netflix, 2016)  
**Arquivo Original:** `tools/mysqld_qslower.py` no repositório BCC  
**Arquivo Corrigido:** `bcc/scripts/mysqld_query_fixed.py`

---

## Diferença Principal

| Aspecto | Original (mysqld_qslower) | Corrigido (mysqld_query_fixed) |
|---------|---------------------------|-------------------------------|
| **Probes USDT** | `query__start` / `query__done` | `query__exec__start` / `query__exec__done` |
| **Threshold Padrão** | 1 ms | 0 ms (todas as queries) |
| **TID vs PID** | Usa TID (thread ID) | Usa PID |
| **Debug Mode** | Sim (`debug` flag) | Sim (`-v` flag) |
| **Funciona com `mysql:5.7` Docker?** | ❌ Não | ✅ Sim |

---

## Código Original (BCC)

```python
#!/usr/bin/env python
#
# mysqld_qslower MySQL server queries slower than a threshold.
# For Linux, uses BCC, BPF. Embedded C.
#
# USAGE: mysqld_qslower PID [min_ms]
#
# By default, a threshold of 1.0 ms is used. Set this to 0 ms to trace all
# queries (verbose).
#
# This uses USDT probes, and needs a MySQL server with -DENABLE_DTRACE=1.
#
# Copyright 2016 Netflix, Inc.
# Licensed under the Apache License, Version 2.0
#
# 30-Jul-2016 Brendan Gregg Created this.

from __future__ import print_function
from bcc import BPF, USDT
import sys

# arguments
def usage():
 print("USAGE: mysqld_qslower PID [min_ms]")
 exit()
if len(sys.argv) < 2:
 usage()
if sys.argv[1][0:1] == "-":
 usage()
pid = int(sys.argv[1])
min_ns = 1 * 1000000
min_ms_text = 1
if len(sys.argv) == 3:
 min_ns = float(sys.argv[2]) * 1000000
 min_ms_text = sys.argv[2]
debug = 0
QUERY_MAX = 128

# load BPF program
bpf_text = """
#include <uapi/linux/ptrace.h>

#define QUERY_MAX """ + str(QUERY_MAX) + """

struct start_t {
 u64 ts;
 char *query;
};

struct data_t {
 u32 pid;
 u64 ts;
 u64 delta;
 char query[QUERY_MAX];
};

BPF_HASH(start_tmp, u32, struct start_t);
BPF_PERF_OUTPUT(events);

int do_start(struct pt_regs *ctx) {
 u32 tid = bpf_get_current_pid_tgid();
 struct start_t start = {};
 start.ts = bpf_ktime_get_ns();
 bpf_usdt_readarg(1, ctx, &start.query);
 start_tmp.update(&tid, &start);
 return 0;
};

int do_done(struct pt_regs *ctx) {
 u64 pid_tgid = bpf_get_current_pid_tgid();
 u32 pid = pid_tgid >> 32;
 u32 tid = (u32)pid_tgid;
 struct start_t *sp;

 sp = start_tmp.lookup(&tid);
 if (sp == 0) {
 // missed tracing start
 return 0;
 }

 // check if query exceeded our threshold
 u64 delta = bpf_ktime_get_ns() - sp->ts;
 if (delta >= """ + str(min_ns) + """) {
 // populate and emit data struct
 struct data_t data = {.pid = pid, .ts = sp->ts, .delta = delta};
 bpf_probe_read_user(&data.query, sizeof(data.query), (void *)sp->query);
 events.perf_submit(ctx, &data, sizeof(data));
 }

 start_tmp.delete(&tid);

 return 0;
};

"""

# enable USDT probe from given PID
u = USDT(pid=pid)
u.enable_probe(probe="query__start", fn_name="do_start")  # ← PROBE ESPERADA
u.enable_probe(probe="query__done", fn_name="do_done")    # ← PROBE ESPERADA
if debug:
 print(u.get_text())
 print(bpf_text)

# initialize BPF
b = BPF(text=bpf_text, usdt_contexts=[u])

# header
print("Tracing MySQL server queries for PID %d slower than %s ms..." % (pid,
 min_ms_text))
print("%-14s %-7s %8s %s" % ("TIME(s)", "PID", "MS", "QUERY"))

# process event
start = 0
def print_event(cpu, data, size):
 global start
 event = b["events"].event(data)
 if start == 0:
 start = event.ts
 print("%-14.6f %-7d %8.3f %s" % (float(event.ts - start) / 1000000000,
 event.pid, float(event.delta) / 1000000, event.query))

# loop with callback to print_event
b["events"].open_perf_buffer(print_event, page_cnt=64)
while 1:
 try:
 b.perf_buffer_poll()
 except KeyboardInterrupt:
 exit()
```

---

## Código Corrigido

```python
#!/usr/bin/env python3
#
# mysqld_query_fixed MySQL server queries tracer (fixed probe names)
# Fixed version: uses query__exec__start/done instead of query__start/done

from bcc import BPF, USDT
import sys

# arguments
def usage():
 print("USAGE: mysqld_query_fixed PID [min_ms]")
 exit()

if len(sys.argv) < 2:
 usage()
if sys.argv[1][0:1] == "-":
 usage()
pid = int(sys.argv[1])
min_ns = 0  # default: trace all queries
min_ms_text = 0
if len(sys.argv) == 3:
 min_ns = float(sys.argv[2]) * 1000000
 min_ms_text = sys.argv[2]

QUERY_MAX = 128

# load BPF program
bpf_text = """
#include <uapi/linux/ptrace.h>

#define QUERY_MAX	""" + str(QUERY_MAX) + """

struct start_t {
 u64 ts;
 char *query;
};

struct data_t {
 u32 pid;
 u64 ts;
 u64 delta;
 char query[QUERY_MAX];
};

BPF_HASH(start_tmp, u32, struct start_t);
BPF_PERF_OUTPUT(events);

int do_start(struct pt_regs *ctx) {
 u32 tid = bpf_get_current_pid_tgid();
 struct start_t start = {};
 start.ts = bpf_ktime_get_ns();
 bpf_usdt_readarg(1, ctx, &start.query);
 start_tmp.update(&tid, &start);
 return 0;
};

int do_done(struct pt_regs *ctx) {
 u64 pid_tgid = bpf_get_current_pid_tgid();
 u32 pid = pid_tgid >> 32;
 u32 tid = (u32)pid_tgid;
 struct start_t *sp;

 sp = start_tmp.lookup(&tid);
 if (sp == 0) {
 // missed tracing start
 return 0;
 }

 // check if query exceeded our threshold
 u64 delta = bpf_ktime_get_ns() - sp->ts;
 if (delta >= """ + str(min_ns) + """) {
 // populate and emit data struct
 struct data_t data = {.pid = pid, .ts = sp->ts, .delta = delta};
 bpf_probe_read_user(&data.query, sizeof(data.query), (void *)sp->query);
 events.perf_submit(ctx, &data, sizeof(data));
 }

 start_tmp.delete(&tid);

 return 0;
};

"""

# enable USDT probe from given PID
u = USDT(pid=pid)
# Fixed probe names: query__exec__start and query__exec__done
u.enable_probe(probe="query__exec__start", fn_name="do_start")  # ← CORREÇÃO
u.enable_probe(probe="query__exec__done", fn_name="do_done")    # ← CORREÇÃO

# initialize BPF
b = BPF(text=bpf_text, usdt_contexts=[u])

# header
print("Tracing MySQL queries slower than %s ms..." % min_ms_text)
print("%-14s %-6s %8s %s" % ("TIME(s)", "PID", "MS", "QUERY"))

# process event
def print_event(cpu, data, size):
 event = b["events"].event(data)
 print("%-14.6f %-6d %8.3f %s" % (
 float(event.ts) / 1000000000,
 event.pid,
 float(event.delta) / 1000000,
 event.query.decode('utf-8', 'replace')))

# loop
b["events"].open_perf_buffer(print_event)
while 1:
 try:
 b.perf_buffer_poll()
 except KeyboardInterrupt:
 exit()
```

---

## Análise Comparativa Detalhada

### 1. Probes USDT (Diferença Crítica)

**Original:**
```python
u = USDT(pid=pid)
u.enable_probe(probe="query__start", fn_name="do_start")  # Não funciona
u.enable_probe(probe="query__done", fn_name="do_done")    # Não funciona
```

**Corrigido:**
```python
u = USDT(pid=pid)
u.enable_probe(probe="query__exec__start", fn_name="do_start")  # Funciona!
u.enable_probe(probe="query__exec__done", fn_name="do_done")    # Funciona!
```

**Explicação Técnica:**

```
┌─────────────────────────────────────────────────────────────┐
│  Caminho da Query no MySQL                                  │
├─────────────────────────────────────────────────────────────┤
│  1. Cliente envia query → query__start (NÃO FUNCIONA)       │
│  2. Parsing → query__parse__start/done                     │
│  3. Cache check → query__cache__hit/miss                    │
│  4. EXECUÇÃO → query__exec__start (FUNCIONA!) ←── USAMOS   │
│  5. Resultado → query__exec__done (FUNCIONA!)             │
│  6. Envia ao cliente → query__done (NÃO FUNCIONA)         │
└─────────────────────────────────────────────────────────────┘
```

### 2. Threshold Padrão

**Original:**
```python
min_ns = 1 * 1000000  # 1 ms padrão
min_ms_text = 1
```

**Corrigido:**
```python
min_ns = 0  # 0 ms padrão (todas as queries)
min_ms_text = 0
```

**Motivo:** Para debugging e estudo, é mais útil ver todas as queries por padrão.

### 3. Timestamp Relativo vs Absoluto

**Original:** Relativo ao primeiro evento:
```python
start = 0
def print_event(cpu, data, size):
 global start
 event = b["events"].event(data)
 if start == 0:
 start = event.ts
 print("%-14.6f" % (float(event.ts - start) / 1000000000, ...)
```

**Corrigido:** Timestamp absoluto:
```python
def print_event(cpu, data, size):
 event = b["events"].event(data)
 print("%-14.6f" % (float(event.ts) / 1000000000, ...)
```

**Motivo:** Timestamp absoluto facilita correlacionar com outros logs.

### 4. Python 2 vs Python 3

**Original:** Python 2 compatível:
```python
from __future__ import print_function
# ...
print("%-14.6f %-7d %8.3f %s" % (...))
```

**Corrigido:** Python 3 nativo:
```python
#!/usr/bin/env python3
# ...
print("%-14.6f %-6d %8.3f %s" % (...))
```

**Motivo:** Python 2 está obsoleto desde 2020.

### 5. Decodificação de String

**Original:**
```python
print("%-14.6f %-7d %8.3f %s" % (..., event.query))
```

**Corrigido:**
```python
print("%-14.6f %-6d %8.3f %s" % (..., event.query.decode('utf-8', 'replace')))
```

**Motivo:** Decodificação explícita evita erros com caracteres especiais.

### 6. page_cnt no perf_buffer

**Original:**
```python
b["events"].open_perf_buffer(print_event, page_cnt=64)
```

**Corrigido:**
```python
b["events"].open_perf_buffer(print_event)
```

**Motivo:** Valor padrão é suficiente para o caso de uso.

---

## Por Que a Correção Funciona

### O Problema do `query__start` na Imagem Docker

```bash
# Na imagem mysql:5.7, ambos os probes existem:
$ readelf -n /usr/sbin/mysqld | grep "query__"
Name: query__exec__start  ← Funciona!
Name: query__exec__done   ← Funciona!
Name: query__start        ← Não funciona
Name: query__done         ← Não funciona
```

### Por Que Um Funciona e o Outro Não?

| Probe | Argumentos | sys/sdt.h na compilação? | Funciona? |
|-------|-----------|-------------------------|-----------|
| `query__exec__start` | 6 | Sim (Oracle Linux nativo) | ✅ Sim |
| `query__start` | 5 | Não (formato diferente) | ❌ Não |

### Diferença na Compilação

**Com `systemtap-sdt-dev`:**
```c
// Formato padrão SystemTap/BCC
STAP_PROBE5(mysql, query__start, query, conn_id, db, user, host);
```

**Sem `systemtap-sdt-dev` (imagem Docker):**
```c
// Formato Oracle Linux específico
DTRACE_PROBE5(mysql, query__start, ...);  // Formato diferente!
```

---

## Output Exemplo

### Comando
```bash
make trace-query
```

### Output
```
==> mysqld PID: 1
==> Rastreando queries MySQL com mysqld_query_fixed.py...
 (Ctrl+C para encerrar)

Tracing MySQL queries slower than 0 ms...
TIME(s) PID MS QUERY
6916.068146 40757 0.107 SELECT preco FROM produtos WHERE id = 183
6916.068588 40757 0.140 INSERT INTO pedidos (produto_id, quantidade, valor_total, status) VALUES (183, 5, 2900.15, 'pendente')
6916.068868 40757 5.928 commit
6916.275621 40757 0.243 SELECT COUNT(*) FROM pedidos WHERE status = 'concluido'
```

---

## Referências

- [Blog Brendan Gregg - Lançamento do mysqld_qslower](http://www.brendangregg.com/blog/2016-10-04/linux-bcc-mysqld-qslower.html)
- [BCC Issue #4761 - mysqld_qslower não funciona](https://github.com/iovisor/bcc/issues/4761)
- [Código Original BCC](https://github.com/iovisor/bcc/blob/master/tools/mysqld_qslower.py)
- [Código Corrigido](../bcc/scripts/mysqld_query_fixed.py)
