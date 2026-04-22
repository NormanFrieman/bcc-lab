# Comparação: dbslower (Original vs Corrigido)

## Visão Geral

**Ferramenta:** `dbslower` - Rastreia queries MySQL/PostgreSQL mais lentas que um limiar  
**Autor Original:** Sasha Goldshtein (2017)  
**Arquivo Original:** `tools/dbslower.py` no repositório BCC  
**Arquivo Corrigido:** `bcc/scripts/dbslower_fixed.py`

---

## Diferença Principal

| Aspecto | Original | Corrigido |
|---------|----------|-----------|
| **Probes USDT** | `query__start` / `query__done` | `query__exec__start` / `query__exec__done` |
| **Bancos Suportados** | MySQL e PostgreSQL | Apenas MySQL (foco no problema) |
| **Modo Uprobe** | Sim (fallback) | Não (simplificado) |
| **Funciona com `mysql:5.7` Docker?** | ❌ Não | ✅ Sim |

---

## Código Original (BCC)

```python
#!/usr/bin/env python
#
# dbslower Trace MySQL and PostgreSQL queries slower than a threshold.
#
# USAGE: dbslower [-v] [-p PID [PID ...]] [-b PATH_TO_BINARY] [-m THRESHOLD]
# {mysql,postgres}
#
# By default, a threshold of 1ms is used. Set the threshold to 0 to trace all
# queries (verbose).
#
# Script works in two different modes:
# 1) USDT probes, which means it needs MySQL and PostgreSQL built with
# USDT (DTrace) support.
# 2) uprobe and uretprobe on exported function of binary specified by
# PATH_TO_BINARY parameter. (At the moment only MySQL support)
#
# Strongly inspired by Brendan Gregg's work on the mysqld_qslower script.
#
# Copyright 2017, Sasha Goldshtein

from bcc import BPF, USDT
import argparse
import re
import subprocess

examples = """examples:
 dbslower postgres # trace PostgreSQL queries slower than 1ms
 dbslower postgres -p 188 322 # trace specific PostgreSQL processes
 dbslower mysql -p 480 -m 30 # trace MySQL queries slower than 30ms
 dbslower mysql -p 480 -v # trace MySQL queries & print the BPF program
 dbslower mysql -x $(which mysqld) # trace MySQL queries with uprobes
"""
parser = argparse.ArgumentParser(
 description="",
 formatter_class=argparse.RawDescriptionHelpFormatter,
 epilog=examples)
parser.add_argument("-v", "--verbose", action="store_true",
 help="print the BPF program")
parser.add_argument("db", choices=["mysql", "postgres"],
 help="the database engine to use")
parser.add_argument("-p", "--pid", type=int, nargs='*',
 dest="pids", metavar="PID", help="the pid(s) to trace")
parser.add_argument("-x", "--exe", type=str,
 dest="path", metavar="PATH", help="path to binary")
parser.add_argument("-m", "--threshold", type=int, default=1,
 help="trace queries slower than this threshold (ms)")
parser.add_argument("--ebpf", action="store_true",
 help=argparse.SUPPRESS)
args = parser.parse_args()

threshold_ns = args.threshold * 1000000

mode = "USDT"
if args.path and not args.pids:
 if args.db == "mysql":
 regex = "\\w+dispatch_command\\w+"
 symbols = BPF.get_user_functions_and_addresses(args.path, regex)

 if len(symbols) == 0:
 print("Can't find function 'dispatch_command' in %s" % (args.path))
 exit(1)

 (mysql_func_name, addr) = symbols[0]

 if mysql_func_name.find(b'COM_DATA') >= 0:
 mode = "MYSQL57"
 else:
 mode = "MYSQL56"
 else:
 print("Sorry at the moment PostgreSQL supports only USDT")
 exit(1)

program = """
#include <uapi/linux/ptrace.h>

DEFINE_THRESHOLD
DEFINE_USDT
DEFINE_MYSQL56
DEFINE_MYSQL57

struct temp_t {
 u64 timestamp;
#ifdef USDT
 char *query;
#else
 char query[256];
#endif
};

struct data_t {
 u32 pid;
 u64 timestamp;
 u64 duration;
 char query[256];
};

BPF_HASH(temp, u64, struct temp_t);
BPF_PERF_OUTPUT(events);

int query_start(struct pt_regs *ctx) {
#if defined(MYSQL56) || defined(MYSQL57)
 #ifdef MYSQL56
 u64 command = (u64) PT_REGS_PARM1(ctx);
 #else
 u64 command = (u64) PT_REGS_PARM3(ctx);
 #endif
 if (command != 3) return 0;
#endif

 struct temp_t tmp = {};
 tmp.timestamp = bpf_ktime_get_ns();

#if defined(MYSQL56)
 bpf_probe_read_user(&tmp.query, sizeof(tmp.query), (void*) PT_REGS_PARM3(ctx));
#elif defined(MYSQL57)
 void* st = (void*) PT_REGS_PARM2(ctx);
 char* query;
 bpf_probe_read_user(&query, sizeof(query), st);
 bpf_probe_read_user(&tmp.query, sizeof(tmp.query), query);
#else
 bpf_usdt_readarg(1, ctx, &tmp.query);
#endif

 u64 pid = bpf_get_current_pid_tgid();
 temp.update(&pid, &tmp);
 return 0;
}

int query_end(struct pt_regs *ctx) {
 struct temp_t *tempp;
 u64 pid = bpf_get_current_pid_tgid();
 tempp = temp.lookup(&pid);
 if (!tempp)
 return 0;

 u64 delta = bpf_ktime_get_ns() - tempp->timestamp;
#ifdef THRESHOLD
 if (delta >= THRESHOLD) {
#endif
 struct data_t data = {};
 data.pid = pid >> 32;
 data.timestamp = tempp->timestamp;
 data.duration = delta;
#if defined(MYSQL56) || defined(MYSQL57)
 bpf_probe_read_kernel(&data.query, sizeof(data.query), tempp->query);
#else
 bpf_probe_read_user(&data.query, sizeof(data.query), tempp->query);
#endif
 events.perf_submit(ctx, &data, sizeof(data));
#ifdef THRESHOLD
 }
#endif
 temp.delete(&pid);
 return 0;
};
""".replace("DEFINE_USDT", "#define USDT" if mode == "USDT" else "") \
 .replace("DEFINE_MYSQL56", "#define MYSQL56" if mode == "MYSQL56" else "") \
 .replace("DEFINE_MYSQL57", "#define MYSQL57" if mode == "MYSQL57" else "") \
 .replace("DEFINE_THRESHOLD",
 "#define THRESHOLD %d" % threshold_ns if threshold_ns > 0 else "")

if mode.startswith("MYSQL"):
 bpf = BPF(text=program)
 bpf.attach_uprobe(name=args.path, sym=mysql_func_name, fn_name="query_start")
 bpf.attach_uretprobe(name=args.path, sym=mysql_func_name, fn_name="query_end")
else:
 usdts = list(map(lambda pid: USDT(pid=pid), args.pids))
 for usdt in usdts:
 usdt.enable_probe("query__start", "query_start")  # ← PROBE ESPERADA
 usdt.enable_probe("query__done", "query_end")      # ← PROBE ESPERADA

 bpf = BPF(text=program, usdt_contexts=usdts)
```

---

## Código Corrigido

```python
#!/usr/bin/env python3
#
# dbslower_fixed MySQL queries slower than a threshold (fixed probe names)
# Fixed version: uses query__exec__start/done instead of query__start/done

from bcc import BPF, USDT
import sys
import argparse

parser = argparse.ArgumentParser(
 description="MySQL queries slower than a threshold (fixed)")
parser.add_argument("pid", type=int, help="the PID to trace")
parser.add_argument("threshold", type=float, nargs="?", default=1.0,
 help="trace queries slower than this threshold (ms)")
parser.add_argument("-v", "--verbose", action="store_true",
 help="print the BPF program")
args = parser.parse_args()

min_ns = int(args.threshold * 1000000)

bpf_text = """
#include <uapi/linux/ptrace.h>

struct start_t {
 u64 ts;
 char *query;
};

struct data_t {
 u32 pid;
 u64 ts;
 u64 delta;
 char query[80];
};

BPF_HASH(start_tmp, u32, struct start_t);
BPF_PERF_OUTPUT(events);

int query_start(struct pt_regs *ctx) {
 u32 pid = bpf_get_current_pid_tgid();
 struct start_t start = {};
 start.ts = bpf_ktime_get_ns();
 bpf_usdt_readarg(1, ctx, &start.query);
 start_tmp.update(&pid, &start);
 return 0;
}

int query_end(struct pt_regs *ctx) {
 u32 pid = bpf_get_current_pid_tgid();
 struct start_t *sp;

 sp = start_tmp.lookup(&pid);
 if (sp == 0) {
 return 0;
 }

 u64 delta = bpf_ktime_get_ns() - sp->ts;
 if (delta >= """ + str(min_ns) + """) {
 struct data_t data = {};
 data.pid = pid;
 data.ts = sp->ts;
 data.delta = delta;
 bpf_probe_read_user(&data.query, sizeof(data.query), (void *)(unsigned long)sp->query);
 events.perf_submit(ctx, &data, sizeof(data));
 }

 start_tmp.delete(&pid);
 return 0;
}
"""

if args.verbose:
 print(bpf_text)

# enable USDT probes first
u = USDT(pid=args.pid)
# Fixed probe names for MySQL 5.7
u.enable_probe(probe="query__exec__start", fn_name="query_start")  # ← CORREÇÃO
u.enable_probe(probe="query__exec__done", fn_name="query_end")      # ← CORREÇÃO

# load BPF program with USDT context
b = BPF(text=bpf_text, usdt_contexts=[u])

print("Tracing MySQL queries slower than %.1f ms..." % args.threshold)
print("%-14s %-6s %8s %s" % ("TIME(s)", "PID", "MS", "QUERY"))

def print_event(cpu, data, size):
 event = b["events"].event(data)
 print("%-14.6f %-6d %8.3f %s" % (
 float(event.ts) / 1000000000,
 event.pid,
 float(event.delta) / 1000000,
 event.query.decode('utf-8', 'replace')))

b["events"].open_perf_buffer(print_event)
while 1:
 try:
 b.perf_buffer_poll()
 except KeyboardInterrupt:
 exit()
```

---

## Análise Comparativa

### 1. Probes USDT (Diferença Crítica)

**Original:**
```python
usdt.enable_probe("query__start", "query_start")  # Não funciona com mysql:5.7
usdt.enable_probe("query__done", "query_end")      # Não funciona com mysql:5.7
```

**Corrigido:**
```python
u.enable_probe("query__exec__start", "query_start")  # Funciona!
u.enable_probe("query__exec__done", "query_end")      # Funciona!
```

**Explicação:**
- `query__start`/`query__done`: Disparados quando a query é **recebida** do cliente
- `query__exec__start`/`query__exec__done`: Disparados quando a **execução real** começa

Na imagem `mysql:5.7` (Oracle Linux), ambos existem, mas apenas os `query__exec__*` funcionam corretamente com BCC.

### 2. Modo Uprobe (Removido)

**Original:** Possui modo fallback usando uprobes:
```python
if args.path and not args.pids:
 regex = "\\w+dispatch_command\\w+"
 symbols = BPF.get_user_functions_and_addresses(args.path, regex)
 # ... modo uprobe
```

**Corrigido:** Apenas modo USDT:
```python
# Simplificado - apenas USDT mode
u = USDT(pid=args.pid)
u.enable_probe("query__exec__start", fn_name="query_start")
```

**Motivo:** O modo uprobe era complexo e frágil. A correção dos probes USDT resolveu o problema.

### 3. Múltiplos PIDs (Simplificado)

**Original:** Suporta múltiplos PIDs:
```python
parser.add_argument("-p", "--pid", type=int, nargs='*', dest="pids")
usdts = list(map(lambda pid: USDT(pid=pid), args.pids))
```

**Corrigido:** Apenas um PID:
```python
parser.add_argument("pid", type=int, help="the PID to trace")
u = USDT(pid=args.pid)
```

**Motivo:** Simplificação para o caso de uso do projeto.

### 4. PostgreSQL (Removido)

**Original:** Suporta MySQL e PostgreSQL:
```python
parser.add_argument("db", choices=["mysql", "postgres"])
```

**Corrigido:** Apenas MySQL:
```python
# Foco no problema específico do MySQL 5.7
```

**Motivo:** O problema era específico do MySQL 5.7 Docker.

### 5. Código BPF (Simplificado)

**Original:** Código BPF complexo com múltiplos modos:
```c
#if defined(MYSQL56)
 bpf_probe_read_user(&tmp.query, sizeof(tmp.query), (void*) PT_REGS_PARM3(ctx));
#elif defined(MYSQL57)
 // ... complexo
#else
 bpf_usdt_readarg(1, ctx, &tmp.query);
#endif
```

**Corrigido:** Código BPF direto:
```c
bpf_usdt_readarg(1, ctx, &start.query);
```

**Motivo:** Sem necessidade de múltiplos modos quando os probes corretos são usados.

---

## Por Que a Correção Funciona

### Situação na Imagem `mysql:5.7`

```bash
# Probes disponíveis no mysqld da imagem Docker
$ readelf -n /proc/1/exe | grep "Name: query"
Name: query__exec__start  ← ✅ Funciona com BCC
Name: query__exec__done   ← ✅ Funciona com BCC
Name: query__start        ← ❌ Não funciona (formato diferente)
Name: query__done         ← ❌ Não funciona (formato diferente)
```

### Diferença de Formato

| Probe | Argumentos | Compilado com sys/sdt.h? |
|-------|-----------|--------------------------|
| `query__exec__start` | 6 argumentos | Sim (Oracle Linux nativo) |
| `query__start` | 5 argumentos | Não (formato diferente) |

A imagem Docker `mysql:5.7` é compilada em Oracle Linux onde os probes existem, mas **não** com `systemtap-sdt-dev` no formato esperado pelo BCC.

---

## Referências

- [BCC Issue #4761 - dbslower não funciona](https://github.com/iovisor/bcc/issues/4761)
- [Código Original BCC](https://github.com/iovisor/bcc/blob/master/tools/dbslower.py)
- [Código Corrigido](../bcc/scripts/dbslower_fixed.py)
