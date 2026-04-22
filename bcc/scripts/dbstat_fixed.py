#!/usr/bin/env python3
#
# dbstat_fixed    MySQL query latency histogram (fixed probe names)
#                 For Linux, uses BCC, BPF. Embedded C.
#
# USAGE: dbstat_fixed PID [interval_seconds]
#
# Fixed version: uses query__exec__start/done instead of query__start/done

from bcc import BPF, USDT
from time import sleep
import sys
import argparse
import ctypes as ct

# arguments
parser = argparse.ArgumentParser(
    description="MySQL query latency histogram (fixed)")
parser.add_argument("pid", type=int, help="the PID to trace")
parser.add_argument("interval", type=int, nargs="?", default=5,
    help="print summary at this interval (seconds)")
parser.add_argument("-v", "--verbose", action="store_true",
    help="print the BPF program")
args = parser.parse_args()

# define BPF program
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
u.enable_probe(probe="query__exec__start", fn_name="probe_start")
u.enable_probe(probe="query__exec__done", fn_name="probe_end")

# load BPF program with USDT context
b = BPF(text=bpf_text, usdt_contexts=[u])

# header
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

# loop
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
