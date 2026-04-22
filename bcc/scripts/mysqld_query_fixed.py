#!/usr/bin/env python3
#
# mysqld_query_fixed    MySQL server queries tracer (fixed probe names)
#                      For Linux, uses BCC, BPF. Embedded C.
#
# USAGE: mysqld_query_fixed PID [min_ms]
#
# By default, a threshold of 0 ms is used (trace all queries).
#
# This uses USDT probes, and needs a MySQL server with -DENABLE_DTRACE=1.
#
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
u.enable_probe(probe="query__exec__start", fn_name="do_start")
u.enable_probe(probe="query__exec__done", fn_name="do_done")

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
