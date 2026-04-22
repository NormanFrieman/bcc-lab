#!/usr/bin/env python3
#
# dbslower_fixed    MySQL/PostgreSQL queries slower than a threshold (fixed probe names)
#                  For Linux, uses BCC, BPF. Embedded C.
#
# USAGE: dbslower_fixed mysql PID [min_ms]
#
# Fixed version: uses query__exec__start/done instead of query__start/done

from bcc import BPF, USDT
import sys
import argparse

# arguments
parser = argparse.ArgumentParser(
    description="MySQL queries slower than a threshold (fixed)")
parser.add_argument("pid", type=int, help="the PID to trace")
parser.add_argument("threshold", type=float, nargs="?", default=1.0,
    help="trace queries slower than this threshold (ms)")
parser.add_argument("-v", "--verbose", action="store_true",
    help="print the BPF program")
args = parser.parse_args()

min_ns = int(args.threshold * 1000000)

# define BPF program
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
        // missed tracing start
        return 0;
    }

    // check if query exceeded threshold
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
u.enable_probe(probe="query__exec__start", fn_name="query_start")
u.enable_probe(probe="query__exec__done", fn_name="query_end")

# load BPF program with USDT context
b = BPF(text=bpf_text, usdt_contexts=[u])

# header
print("Tracing MySQL queries slower than %.1f ms..." % args.threshold)
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
