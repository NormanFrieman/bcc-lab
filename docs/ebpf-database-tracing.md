# eBPF & USDT — Tracing de Performance em Bancos de Dados

> Resumo da pesquisa sobre ferramentas de rastreamento de queries MySQL e PostgreSQL usando eBPF, USDT e estratégias similares.

---

## Repositório BCC (BPF Compiler Collection)

[iovisor/bcc](https://github.com/iovisor/bcc) é um toolkit para criação de programas de rastreamento e manipulação eficiente do kernel Linux usando eBPF.

### Tools relacionadas a banco de dados

| Tool | Bancos suportados | Descrição |
|---|---|---|
| [`dbslower`](https://github.com/iovisor/bcc/blob/master/tools/dbslower.py) | MySQL, PostgreSQL | Rastreia queries acima de um threshold de latência |
| [`dbstat`](https://github.com/iovisor/bcc/blob/master/tools/dbstat.py) | MySQL, PostgreSQL | Resume latência de queries em histograma |
| [`mysqld_qslower`](https://github.com/iovisor/bcc/blob/master/tools/mysqld_qslower.py) | MySQL | Queries lentas específicas do processo `mysqld` |

Há também o exemplo `examples/tracing/mysqld_query.py`, que demonstra rastreamento de queries MySQL via sondas USDT.

---

## USDT vs uprobes — Modos de rastreamento

### `dbstat` — Exclusivamente USDT

Requer MySQL ou PostgreSQL compilado com suporte a DTrace/USDT. Conecta-se nas sondas:

- `query__start` — disparada no início de uma query
- `query__done` — disparada ao fim de uma query

### `dbslower` — USDT ou uprobes

Suporta dois modos dependendo dos argumentos:

**Modo USDT** (padrão, via PID):
```bash
dbslower mysql -p 480 -m 30
```

**Modo uprobes** (via binário, apenas MySQL):
```bash
dbslower mysql -x $(which mysqld)
```

> PostgreSQL **não suporta** o modo uprobe no `dbslower`. Tentar usar `-x` com postgres resulta em erro.

No modo uprobe, o script hookeia diretamente a função `dispatch_command` do binário `mysqld`, com suporte a MySQL 5.6 e 5.7.

---

## Suporte por banco de dados

| Banco | `dbslower` | `dbstat` | Observação |
|---|---|---|---|
| MySQL | Sim (USDT + uprobes) | Sim (USDT) | — |
| PostgreSQL | Sim (USDT) | Sim (USDT) | Sem suporte a uprobes |
| **SQL Server** | **Não** | **Não** | Sem sondas USDT públicas; binário fechado |
| MariaDB | Não | Não | Tem USDT, contribuição possível |
| Oracle DB | Não | Não | — |

### Por que SQL Server não é suportado?

1. **SQL Server no Linux é recente** — disponível apenas a partir de 2017; as tools do BCC foram criadas antes disso.
2. **Sem USDT público** — o SQL Server para Linux não expõe sondas USDT, e usar uprobes exigiria engenharia reversa dos símbolos internos do `sqlservr`.

Para SQL Server, a alternativa são as ferramentas nativas da Microsoft: **DMVs** (`sys.dm_exec_query_stats`) e **Extended Events**.

---

## Outras ferramentas com estratégia similar

### [Pixie](https://px.dev) — CNCF / New Relic

Plataforma de observabilidade open source para Kubernetes. Usa eBPF para interceptar o **protocolo de rede** do MySQL e PostgreSQL diretamente nas syscalls do kernel, sem precisar de USDT nem modificação do banco.

**Protocolos suportados:** MySQL, PostgreSQL, Redis, Cassandra, Kafka, MongoDB, HTTP, DNS, AMQP.

**Criptografia suportada:** OpenSSL 1.1.x / 3.x, Go TLS, BoringSSL.

### [BCC tools](https://github.com/iovisor/bcc) — `dbslower` / `dbstat`

Detalhado acima. Focado em diagnóstico pontual via linha de comando.

### [mysqlperformance/bpf_tools](https://github.com/mysqlperformance/bpf_tools)

Scripts eBPF mantidos pela equipe de performance do MySQL (Alibaba/PolarDB). Foco exclusivo em MySQL com análises de I/O, lock contention e latência de queries via uprobes e USDT.

### [Groundcover](https://groundcover.com)

Plataforma comercial de observabilidade baseada em eBPF para Kubernetes. Auto-detecção de tráfego de banco, geração de traces distribuídos. Cobra por nó, não por volume de eventos.

### [pg_plan_alternatives](https://github.com/jnidzwetzki/pg_plan_alternatives)

Ferramenta experimental (2026) para PostgreSQL 17/18. Usa eBPF para revelar **todos os planos de execução considerados** pelo otimizador, não apenas o escolhido. Requer binários com símbolos DWARF.

### Comparativo geral

| Ferramenta | MySQL | PostgreSQL | Estratégia | Ambiente |
|---|---|---|---|---|
| BCC (`dbslower`/`dbstat`) | Sim | Sim | USDT + uprobes | Bare metal / VM |
| Pixie | Sim | Sim | eBPF (protocolo de rede) | Kubernetes |
| bpf_tools (MySQL) | Sim | Não | uprobes + USDT | Bare metal / VM |
| Groundcover | Sim | Sim | eBPF (rede) | Kubernetes |
| pg_plan_alternatives | Não | Sim | eBPF (uprobes internos) | Bare metal / VM |

---

## Como o Pixie funciona

### Arquitetura

```
┌─────────────────────────────────────────────────────┐
│                    Kubernetes Node                   │
│                                                      │
│  ┌──────────────┐        ┌──────────────────────┐   │
│  │  Pod: App    │        │  Pod: MySQL/Postgres  │   │
│  │              │        │                       │   │
│  │  send() ─────┼────────┼──► recv()             │   │
│  │  recv() ◄────┼────────┼─── send()             │   │
│  └──────────────┘        └──────────────────────┘   │
│         │                          │                 │
│    eBPF kprobes nas syscalls de rede (kernel)        │
│         │                          │                 │
│         ▼                          ▼                 │
│  ┌─────────────────────────────────────────────┐    │
│  │         PEM - Pixie Edge Module              │    │
│  │  (agente por nó, armazena dados localmente)  │    │
│  └─────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────┘
                         │
                         ▼
              ┌──────────────────┐
              │   Vizier         │  ← por cluster
              │ (query engine)   │
              └──────────────────┘
                         │
                         ▼
              ┌──────────────────┐
              │   Pixie Cloud /  │
              │   UI / CLI / API │
              └──────────────────┘
```

### Componentes

- **PEM (Pixie Edge Module):** agente instalado por nó. Coleta dados via eBPF e armazena localmente.
- **Vizier:** instalado por cluster. Responsável pela execução de queries e gerenciamento dos PEMs.
- **Pixie Cloud:** gerenciamento de usuários, autenticação e proxy de dados. Pode ser self-hosted.

### Como rastreia queries de banco de dados

#### 1. kprobes nas syscalls de rede

Quando uma aplicação envia uma query, usa syscalls como `send()` e `recv()`. O Pixie instala kprobes nessas syscalls e intercepta os dados brutos:

```
App → send("SELECT * FROM users WHERE id = 1") → kernel → MySQL
                    ↑
              kprobe captura aqui
```

#### 2. Parsing do protocolo

O dado capturado é binário. O Pixie identifica o protocolo pela porta e estrutura dos pacotes e extrai query SQL, latência e status de resposta.

#### 3. Tráfego TLS/SSL

Para conexões criptografadas, uprobes são instaladas diretamente na API da biblioteca TLS, capturando os dados **antes** da cifragem:

```
App → TLS encrypt → send() → rede
        ↑
   uprobe na API do OpenSSL/BoringSSL
   captura ANTES de criptografar
```

#### 4. Armazenamento local (in-cluster)

Os dados **não saem do cluster**. O Pixie usa menos de 5% de CPU do cluster (geralmente menos de 2%).

### Consultas com PxL

O Pixie usa **PxL**, uma linguagem similar a Python/Pandas:

```python
import px

df = px.DataFrame(table='postgres_events', start_time='-5m')
df = df[df.latency > 100]  # queries acima de 100ms
df = df.groupby(['req_body']).agg(
    latency_mean=('latency', px.mean),
    count=('latency', px.count)
)
px.display(df)
```

### BCC/USDT vs Pixie

| Aspecto | BCC (USDT/uprobes) | Pixie (eBPF na rede) |
|---|---|---|
| Ponto de captura | Dentro do processo do banco | Syscalls de rede do kernel |
| Requer recompilar banco? | Sim (modo USDT) | Não |
| Funciona em RDS/Cloud SQL? | Não | Sim |
| Ambiente | Bare metal / VM | Kubernetes |
| Overhead | Muito baixo | < 2% de CPU do cluster |
| Dados armazenados onde? | Saída no terminal | Localmente no nó |

### Limitação

Por interceptar na camada de rede, o Pixie **não captura** queries executadas internamente no banco (ex: stored procedures chamadas por triggers), ao contrário do USDT que hookeia dentro do próprio processo.
