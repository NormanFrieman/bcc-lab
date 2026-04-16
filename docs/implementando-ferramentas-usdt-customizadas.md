# Implementando Ferramentas de Rastreamento USDT Customizadas

Este documento condensa a discussão sobre como implementar ferramentas próprias de rastreamento de queries, similares ao `mysqld_query`, usando probes USDT diretamente — tanto para MySQL 5.7 quanto para PostgreSQL.

---

## É possível implementar uma ferramenta equivalente ao `mysqld_query`?

Sim. O binário `mysqld_query-bpfcc` já usa USDT internamente. É totalmente possível escrever uma ferramenta própria que se acopla aos mesmos probes, com controle total sobre o que capturar e como apresentar.

O MySQL 5.7 expõe dois pontos de rastreamento relevantes:

| Probe | Quando dispara | Argumento |
|---|---|---|
| `mysql:query__start` | Início de uma query | `const char *` — string SQL |
| `mysql:query__done` | Fim de uma query | — |

---

## Suporte USDT no PostgreSQL

Ao contrário do MySQL — que removeu os probes USDT no 8.0 — o **PostgreSQL mantém suporte até a versão mais atual** (18, de fevereiro de 2026). O suporte é habilitado em tempo de compilação com a flag `--enable-dtrace`.

### Probes disponíveis no PostgreSQL 18

| Categoria | Probes |
|---|---|
| **Queries** | `query__start`, `query__done`, `query__parse__start/done`, `query__rewrite__start/done`, `query__plan__start/done`, `query__execute__start/done` |
| **Transações** | `transaction__start`, `transaction__commit`, `transaction__abort` |
| **Locks** | `lwlock__acquire`, `lwlock__release`, `lwlock__wait__start/done`, `lock__wait__start/done`, `deadlock__found` |
| **Buffers** | `buffer__read__start/done`, `buffer__flush__start/done`, `buffer__extend__start/done` |
| **WAL** | `wal__insert`, `wal__switch`, `wal__buffer__write__dirty__start/done` |
| **Checkpoint** | `checkpoint__start`, `checkpoint__done` |
| **Sort** | `sort__start`, `sort__done` |

> Os probes `query__start` e `query__done` têm assinatura `(const char *)` tanto no MySQL 5.7 quanto no PostgreSQL 18, o que torna o código eBPF quase idêntico entre os dois.

### Diferença arquitetural: PostgreSQL é multiprocesso

No PostgreSQL, cada conexão cliente cria um processo filho separado (`postgres` worker). Para rastrear todas as queries, o probe deve ser anexado com `pid = -1`, cobrindo todos os workers, ou ao PID de um worker específico.

