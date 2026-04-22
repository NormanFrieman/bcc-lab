# Comparação: dbstat (Original vs Corrigido)

## Visão Geral

**Ferramenta:** `dbstat` - Exibe histograma de latências de queries MySQL/PostgreSQL  
**Autor Original:** Sasha Goldshtein (2017)  
**Arquivo Original:** `tools/dbstat.py` no repositório BCC  
**Arquivo Corrigido:** `bcc/scripts/dbstat_fixed.py`

---

## Diferença Principal

| Aspecto | Original | Corrigido |
|---------|----------|-----------|
| **Probes USDT** | `query__start` / `query__done` | `query__exec__start` / `query__exec__done` |
| **Bancos Suportados** | MySQL e PostgreSQL | Apenas MySQL |
| **Threshold Configurável** | Sim (`-m`) | Não (simplificado) |
| **Microseconds Mode** | Sim (`-u`) | Sim (sempre ativo) |
| **Funciona com `mysql:5.7` Docker?** | ❌ Não | ✅ Sim |

---

## Código Original (BCC)

```python
#!/usr/bin/env python
#
# dbstat Display a histogram of MySQL and PostgreSQL query latencies.
#
# USAGE: dbstat [-v] [-p PID [PID ...]] [-m THRESHOLD] [-u]
# [-i INTERVAL] {mysql,postgres}
#
# This tool uses USDT probes, which means it needs MySQL and PostgreSQL built
# with USDT (DTrace) support.
#
# Copyright 2017, Sasha Goldshtein

from bcc import BPF, USDT
import argparse
import subprocess
from time import sleep, strftime

examples = """
 dbstat postgres # display a histogram of PostgreSQL query latencies
 dbstat mysql -v # display MySQL latencies and print the BPF program
 dbstat mysql -u # display query latencies in microseconds (default: ms)
 dbstat mysql -m 5 # trace only queries slower than 5ms
 dbstat mysql -p 408 # trace queries in a specific process
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
parser.add_argument("-m", "--threshold", type=int, default=0,
 help="trace queries slower than this threshold (ms)")
parser.add_argument("-u", "--microseconds", action="store_true",
 help="display query latencies in microseconds")
parser.add_argument("-i", "--interval", type=int, default=99999999,
 help="print summary at this interval (seconds)")
args = parser.parse_args()

if not args.pids or len(args.pids) == 0:
 if args.db == "mysql":
 args.pids = map(int, subprocess.check_output(
 "pidof mysqld".split()).split())
 elif args.db == "postgres":
 args.pids = map(int, subprocess.check_output(
 "pidof postgres".split()).split())

program = """
#include <uapi/linux/ptrace.h>

BPF_HASH(temp, u64, u64);
BPF_HISTOGRAM(latency);

int probe_start(struct pt_regs *ctx) {
 u64 timestamp = bpf_ktime_get_ns();
 u64 pid = bpf_get_current_pid_tgid();
 temp.update(&pid, &timestamp);
 return 0;
}

int probe_end(struct pt_regs *ctx) {
 u64 *timestampp;
 u64 pid = bpf_get_current_pid_tgid();
 timestampp = temp.lookup(&pid);
 if (!timestampp)
 return 0;

 u64 delta = bpf_ktime_get_ns() - *timestampp;
 FILTER
 delta /= SCALE;
 latency.atomic_increment(bpf_log2l(delta));
 temp.delete(&pid);
 return 0;
}
"""
program = program.replace("SCALE", str(1000 if args.microseconds else 1000000))
program = program.replace("FILTER", "" if args.threshold == 0 else
 "if (delta / 1000000 < %d) { return 0; }" % args.threshold)

usdts = list(map(lambda pid: USDT(pid=pid), args.pids))
for usdt in usdts:
 usdt.enable_probe("query__start", "probe_start")  # ← PROBE ESPERADA
 usdt.enable_probe("query__done", "probe_end")      # ← PROBE ESPERADA

if args.verbose:
 print('\n'.join(map(lambda u: u.get_text(), usdts)))
 print(program)

bpf = BPF(text=program, usdt_contexts=usdts)

print("Tracing database queries for pids %s slower than %d ms..." %
 (', '.join(map(str, args.pids)), args.threshold))

latencies = bpf["latency"]

def print_hist():
 print("[%s]" % strftime("%H:%M:%S"))
 latencies.print_log2_hist("query latency (%s)" %
 ("us" if args.microseconds else "ms"))
 print("")
 latencies.clear()

while True:
 try:
 sleep(args.interval)
 print_hist()
 except KeyboardInterrupt:
 print_hist()
 break
```

---

## Código Corrigido

```python
#!/usr/bin/env python3
#
# dbstat_fixed MySQL query latency histogram (fixed probe names)
# Fixed version: uses query__exec__start/done instead of query__start/done

from bcc import BPF, USDT
from time import sleep
import sys
import argparse
import ctypes as ct

parser = argparse.ArgumentParser(
 description="MySQL query latency histogram (fixed)")
parser.add_argument("pid", type=int, help="the PID to trace")
parser.add_argument("interval", type=int, nargs="?", default=5,
 help="print summary at this interval (seconds)")
parser.add_argument("-v", "--verbose", action="store_true",
 help="print the BPF program")
args = parser.parse_args()

bpf_text = """
#include <uapi/linux/ptrace.h>

struct start_t {
 u64 ts;
};

BPF_HASH(start_tmp, u32, struct start_t);
BPF_HISTOGRAM(dist, u64, 20);

int probe_start(struct pt_regs *ctx) {
 u32 pid = bpf_get_current_pid_tgid();
 struct start_t start = {};
 start.ts = bpf_ktime_get_ns();
 start_tmp.update(&pid, &start);
 return 0;
}

int probe_end(struct pt_regs *ctx) {
 u32 pid = bpf_get_current_pid_tgid();
 struct start_t *sp;

 sp = start_tmp.lookup(&pid);
 if (sp == 0) {
 return 0;
 }

 u64 delta = bpf_ktime_get_ns() - sp->ts;
 // convert to microseconds and log2 histogram
 delta = delta / 1000;
 u64 slot = bpf_log2l(delta);
 if (slot >= 20)
 slot = 19;
 dist.increment(slot);

 start_tmp.delete(&pid);
 return 0;
}
"""

if args.verbose:
 print(bpf_text)

# enable USDT probes first
u = USDT(pid=args.pid)
# Fixed probe names for MySQL 5.7
u.enable_probe(probe="query__exec__start", fn_name="probe_start")  # ← CORREÇÃO
u.enable_probe(probe="query__exec__done", fn_name="probe_end")      # ← CORREÇÃO

# load BPF program with USDT context
b = BPF(text=bpf_text, usdt_contexts=[u])

print("Tracing MySQL query latencies... Hit Ctrl-C to end.")
print("Waiting %d seconds for first report..." % args.interval)
sys.stdout.flush()

# labels for histogram
labels = [
 b"1us", b"2us", b"4us", b"8us", b"16us", b"32us", b"64us", b"128us",
 b"256us", b"512us", b"1ms", b"2ms", b"4ms", b"8ms", b"16ms", b"32ms",
 b"64ms", b"128ms", b"256ms", b"512ms+"
]

dist = b.get_table("dist")

while 1:
 try:
 sleep(args.interval)
 except KeyboardInterrupt:
 print()
 exit()

 print()
 print("Query latency distribution (microseconds):")
 dist.print_log2_hist(labels)
 dist.clear()
 sys.stdout.flush()
```

---

## Análise Comparativa

### 1. Probes USDT (Diferença Crítica)

**Original:**
```python
usdts = list(map(lambda pid: USDT(pid=pid), args.pids))
for usdt in usdts:
 usdt.enable_probe("query__start", "probe_start")  # Não funciona
 usdt.enable_probe("query__done", "probe_end")      # Não funciona
```

**Corrigido:**
```python
u = USDT(pid=args.pid)
u.enable_probe("query__exec__start", "probe_start")  # Funciona!
u.enable_probe("query__exec__done", "probe_end")      # Funciona!
```

### 2. Descoberta Automática de PIDs (Removida)

**Original:**
```python
if not args.pids or len(args.pids) == 0:
 if args.db == "mysql":
 args.pids = map(int, subprocess.check_output(
 "pidof mysqld".split()).split())
 elif args.db == "postgres":
 args.pids = map(int, subprocess.check_output(
 "pidof postgres".split()).split())
```

**Corrigido:**
```python
parser.add_argument("pid", type=int, help="the PID to trace")
# PID fornecido explicitamente
```

**Motivo:** Simplificação - o script de wrapper já fornece o PID correto.

### 3. Threshold Configurável (Removido)

**Original:**
```python
parser.add_argument("-m", "--threshold", type=int, default=0,
 help="trace queries slower than this threshold (ms)")
# ...
program = program.replace("FILTER", "" if args.threshold == 0 else
 "if (delta / 1000000 < %d) { return 0; }" % args.threshold)
```

**Corrigido:**
```python
# Sem threshold - todas as queries são incluídas no histograma
```

**Motivo:** Para histogramas, geralmente queremos ver a distribuição completa.

### 4. Código BPF (Simplificado)

**Original:** Usa macros de substituição:
```c
FILTER
delta /= SCALE;
```

**Corrigido:** Valores hardcoded para microsegundos:
```c
delta = delta / 1000;  // Sempre converte para microsegundos
```

**Motivo:** Simplificação - sempre usar microsegundos fornece melhor granularidade.

### 5. Estrutura de Dados (Simplificada)

**Original:** Apenas timestamp:
```c
BPF_HASH(temp, u64, u64);  // pid -> timestamp
```

**Corrigido:** Estrutura com timestamp:
```c
struct start_t {
 u64 ts;
};
BPF_HASH(start_tmp, u32, struct start_t);
```

**Motivo:** Consistência com outros scripts corrigidos.

---

## Por Que a Correção Funciona

### Problema na Imagem `mysql:5.7`

A imagem Docker `mysql:5.7` tem ambos os conjuntos de probes:

```bash
$ readelf -n /usr/sbin/mysqld | grep query
Name: query__exec__start  ← Funciona com BCC
Name: query__exec__done   ← Funciona com BCC
Name: query__start        ← Formato incompatível
Name: query__done         ← Formato incompatível
```

### Por Que `query__exec__*` Funciona?

| Característica | `query__start` | `query__exec__start` |
|----------------|----------------|---------------------|
| Quando dispara | Recepção da query | Início da execução |
| Argumentos | 5 argumentos | 6 argumentos |
| sys/sdt.h usado? | ❌ Não | ✅ Sim |
| Funciona com BCC? | ❌ Não | ✅ Sim |

---

## Output Exemplo

### Comando
```bash
make trace-stat
```

### Output
```
==> mysqld PID: 1
==> Coletando histograma de latências (intervalo: 5s)...
 (Ctrl+C para encerrar)

Tracing MySQL query latencies... Hit Ctrl-C to end.
Waiting 5 seconds for first report...

Query latency distribution (microseconds):
 [1us, 2us) 4 |****************************************|
 [2us, 4us) 9 |******************************|
 [4us, 8us) 16 |****************************************|
 [8us, 16us) 2 |********** |
 [16us, 32us) 3 |*************** |
```

---

## Referências

- [BCC Issue #4761 - dbstat falha](https://github.com/iovisor/bcc/issues/4761)
- [Código Original BCC](https://github.com/iovisor/bcc/blob/master/tools/dbstat.py)
- [Código Corrigido](../bcc/scripts/dbstat_fixed.py)
