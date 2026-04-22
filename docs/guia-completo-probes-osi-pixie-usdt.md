# Guia Completo: Probes, Camadas OSI e Observabilidade de Banco de Dados

> Este documento consolida os conceitos discutidos sobre probes USDT, localização no modelo OSI, comparação entre Pixie (Camada 4) e USDT/BCC (Camada 7), e a jornada completa de uma query do backend ao banco de dados.

---

## 1. O Que São Probes?

**Probes** (sondas) são pontos de instrumentação no código que permitem observar a execução de um programa sem modificá-lo. Eles são a base do tracing dinâmico em Linux.

### Características Fundamentais

- **Estáticos**: Definidos em tempo de compilação (USDT)
- **Dinâmicos**: Inseridos em tempo de execução (uprobes, kprobes)
- **Baixo overhead**: Quando inativos, executam como `NOP` (instrução nula) — zero custo de performance
- **Ativação dinâmica**: Ferramentas podem "ligar" os probes sem reiniciar o processo

### Por Que São Adicionados?

1. **Diagnóstico em produção**: Identificar problemas sem interromper o sistema
2. **Zero overhead inativo**: Não afetam performance quando não usados
3. **Segurança**: Não requer modificação do processo alvo
4. **Precisão**: Capturam dados estruturados diretamente da aplicação

---

## 2. Tipos de Probes

### 2.1 USDT (User Statically Defined Tracing)

Sondas definidas em tempo de **compilação** em programas de userspace.

**Como funcionam:**
```c
// Código MySQL com USDT probe
void execute_query(const char* sql) {
    DTRACE_PROBE1(mysql, query__exec__start, sql);  // Probe ativado aqui
    // ... executa a query ...
    DTRACE_PROBE1(mysql, query__exec__done, thread_id);
}
```

**Estados:**
```
┌─────────────┐      Ferramenta ativa       ┌─────────────┐
│   INATIVO   │ ◀────────────────────────── │    ATIVO    │
│   (NOP)     │                             │  (breakpoint)│
│  ~0 overhead│      Ferramenta desativa    │  Com handler │
└─────────────┘                             └─────────────┘
```

**Softwares com USDT:**
- MySQL 5.7: `query__exec__start`, `query__exec__done`
- PostgreSQL: `query__start`, `transaction__start`
- Node.js: `http__server__request`, `gc__start`
- CPython: `function__entry`, `gc__start`

### 2.2 Uprobes (User-space Probes)

Sondas dinâmicas inseridas em qualquer função de um binário, sem suporte de compilação.

```bash
# Rastreia função específica do mysqld
dbslower mysql -x $(which mysqld)  # Hook em dispatch_command
```

### 2.3 Kprobes (Kernel Probes)

Sondas no espaço do kernel, para rastrear syscalls e funções internas.

```
App → send() → kprobe captura aqui → kernel → rede
```

### 2.4 Tracepoints

Pontos de instrumentação estáticos e estáveis no kernel Linux — APIs oficiais que não mudam entre versões.

---

## 3. Localização no Modelo OSI

```
┌─────────────────────────────────────────────────────────────────────────┐
│  MODELO OSI                    │  LOCALIZAÇÃO DOS PROBES                │
├─────────────────────────────────────────────────────────────────────────┤
│  7. APLICAÇÃO                  │  ████████████████████ USDT Probes      │
│     (HTTP, SQL, DNS)           │  • MySQL, PostgreSQL, Node.js         │
│                                │  • Código-fonte da aplicação            │
├─────────────────────────────────────────────────────────────────────────┤
│  6. APRESENTAÇÃO               │  Pixie (uprobe em TLS API)            │
│     (SSL/TLS, codificação)     │  • OpenSSL, BoringSSL                 │
├─────────────────────────────────────────────────────────────────────────┤
│  5. SESSÃO                     │                                        │
│     (Gerenciamento de sessão)  │                                        │
├─────────────────────────────────────────────────────────────────────────┤
│  4. TRANSPORTE                 │  ████████████████████ Pixie (kprobes) │
│     (TCP, UDP)                 │  • send(), recv(), connect()            │
│                                │  • Decodificação de protocolo           │
├─────────────────────────────────────────────────────────────────────────┤
│  3. REDE                       │                                        │
│     (IP, ICMP)                 │                                        │
├─────────────────────────────────────────────────────────────────────────┤
│  2. ENLACE                     │                                        │
│     (Ethernet, WiFi)           │                                        │
├─────────────────────────────────────────────────────────────────────────┤
│  1. FÍSICA                     │                                        │
│     (Cabos, sinais)            │                                        │
└─────────────────────────────────────────────────────────────────────────┘
```

### USDT na Camada 7 vs Pixie na Camada 4

| Aspecto | USDT (Camada 7) | Pixie (Camada 4) |
|---------|-----------------|------------------|
| **Local físico** | Dentro do processo | Kernel, syscalls de rede |
| **Momento** | Antes da serialização | Durante a transmissão |
| **Formato** | Strings/estruturas | Pacotes binários |
| **Overhead** | Mínimo | < 2% CPU do cluster |
| **Independência** | Requer suporte da aplicação | Funciona com qualquer app |

---

## 4. Pixie vs USDT/BCC: Quando Usar Cada Um?

### Pixie (Camada 4 - Transporte)

**Por que captura na camada 4:**

1. **Independência da aplicação**: Não requer USDT embutido
2. **Múltiplos protocolos**: Um mecanismo para MySQL, PostgreSQL, Redis, MongoDB, HTTP, etc.
3. **Funciona na nuvem**: RDS, Cloud SQL, bancos gerenciados
4. **Captura TLS**: Via uprobes na API do OpenSSL (antes da criptografia)
5. **Visão holística**: Distributed tracing no cluster Kubernetes

**Arquitetura Pixie:**
```
┌─────────────────────────────────────────────────────────────────┐
│  Kubernetes Node                                                │
│  ┌──────────────┐      ┌──────────────────────┐                │
│  │  Pod: App    │      │  Pod: MySQL          │                │
│  │              │      │                      │                │
│  │  send() ─────┼──────┼──► recv()           │                │
│  │       ▲      │      │                      │                │
│  │       │      │      │        ┌─────────────┘                │
│  │  ┌────┴────┐ │      │        │                              │
│  │  │  TLS    │─┘      │        │  ❌ Sem acesso (RDS)         │
│  │  │ uprobe  │        │        │                              │
│  │  └─────────┘        │        ▼                              │
│  │                     │  ┌──────────────┐                      │
│  │                     │  │  mysqld      │                      │
│  │                     │  │  (processo)  │                      │
│  │                     │  └──────────────┘                      │
│  │                     │                                        │
│  └─────────────────────┼────────────────────────────────────────┘
│                        │                                       │
│                   ┌────┴────┐                                   │
│                   │  kprobe │◀── send()/recv()                  │
│                   │ (kernel)│    (Camada 4)                      │
│                   └────┬────┘                                   │
│                        │                                       │
│                   ┌────┴──────────────────┐                    │
│                   │  Pixie Agent (eBPF)    │                    │
│                   │  • Decodifica protocolo │                    │
│                   │  • Extrai SQL           │                    │
│                   │  • Armazena localmente    │                    │
│                   └─────────────────────────┘                    │
└──────────────────────────────────────────────────────────────────┘
```

### USDT/BCC (Camada 7 - Aplicação)

**Vantagens:**

1. **Precisão absoluta**: Latência real de execução (parse + optimize + execute)
2. **Queries internas**: Stored procedures, triggers, queries do sistema
3. **Detalhes do plano**: Acesso a estruturas internas do otimizador
4. **Zero rede**: Não depende de capturar pacotes

**Limitações:**
- Requer acesso ao processo (`privileged: true`, namespace PID)
- MySQL 8.0+ removeu USDT
- Não funciona em RDS/Cloud SQL (sem acesso ao `mysqld`)

---

## 5. Jornada Completa de uma Query

### Cenário: Backend (Região A) → RDS MySQL (Região B)

```
┌─────────────────────────────────────────────────────────────────────────────────────────────┐
│  REGIÃO A: SEU DATA CENTER / CLOUD                                                         │
├─────────────────────────────────────────────────────────────────────────────────────────────┤
│                                                                                             │
│  ┌─────────────────────────────────────────────────────────────────────────────────────┐   │
│  │  BACKEND (Pod/VM)                                                                    │   │
│  │                                                                                     │   │
│  │  ┌─────────────────┐                                                                │   │
│  │  │  Código gera SQL │  "SELECT * FROM users WHERE id = 123"                        │   │
│  │  │       │          │                                                                │   │
│  │  │       ▼          │                                                                │   │
│  │  │  ┌───────────┐   │                                                                │   │
│  │  │  │ MySQL     │   │                                                                │   │
│  │  │  │ Driver    │   │                                                                │   │
│  │  │  └─────┬─────┘   │                                                                │   │
│  │  │        │          │                                                                │   │
│  │  │  ┌─────┴─────┐    │  ◀── PIXIE uprobe (TLS API): captura SQL ANTES de criptografar │   │
│  │  │  │  TLS/SSL  │◀───┼      "SELECT * FROM users..."                                  │   │
│  │  │  │ (OpenSSL) │    │                                                                │   │
│  │  │  └─────┬─────┘    │                                                                │   │
│  │  │        │          │                                                                │   │
│  │  │  ┌─────┴─────┐    │  ◀── PIXIE kprobe: send() syscall (Camada 4)                   │   │
│  │  │  │  send()   │◀───┼      Pacote MySQL protocol (binário)                          │   │
│  │  │  │ (kernel)  │    │                                                                │   │
│  │  │  └─────┬─────┘    │                                                                │   │
│  │  └────────┼──────────┘                                                                │   │
│  │           │                                                                            │   │
│  │  ┌────────┴──────────┐                                                                 │   │
│  │  │  Pixie Agent      │◀── Decodifica protocolo, extrai SQL                             │   │
│  │  │  (armazena local) │                                                                 │   │
│  │  └───────────────────┘                                                                 │   │
│  └───────────────────────────────────────────────────────────────────────────────────────┘   │
│              │                                                                               │
│              │ TCP/IP + TLS (tráfego criptografado)                                          │
│              │ Latência de rede: 5-50ms                                                      │
│              ▼                                                                               │
├─────────────────────────────────────────────────────────────────────────────────────────────┤
│  REGIÃO B: AWS RDS / CLOUD SQL (Banco Gerenciado)                                           │
├─────────────────────────────────────────────────────────────────────────────────────────────┤
│                                                                                             │
│  ┌─────────────────────────────────────────────────────────────────────────────────────┐   │
│  │  RDS MySQL 5.7                                                                      │   │
│  │                                                                                     │   │
│  │  ┌──────────────────────────────────────────────────────────────────────────────┐ │   │
│  │  │  PROCESSO: mysqld                                                             │ │   │
│  │  │                                                                               │ │   │
│  │  │  recv() ──▶ TLS decrypt ──▶ MySQL protocol                                    │ │   │
│  │  │                               │                                               │ │   │
│  │  │                               ▼                                               │ │   │
│  │  │  ❌ USDT NÃO CAPTURÁVEL (sem acesso ao container)                            │ │   │
│  │  │                                                                               │ │   │
│  │  │  ┌──────────┐    ┌──────────┐    ┌──────────┐                                │ │   │
│  │  │  │  Parser  │───▶│ Otimizador│───▶│ Executor │                               │ │   │
│  │  │  │   SQL    │    │ (plano)  │    │          │                               │ │   │
│  │  │  └──────────┘    └──────────┘    └────┬─────┘                                │ │   │
│  │  │                                       │                                      │ │   │
│  │  │                                  Storage                                    │ │   │
│  │  │                                  (InnoDB)                                   │ │   │
│  │  │                                       │                                      │ │   │
│  │  │                                       ▼                                      │ │   │
│  │  │                               Resultado                                      │ │   │
│  │  │                                                                               │ │   │
│  │  │  Criptografa ──▶ send() ──▶ volta para backend                               │ │   │
│  │  │                                                                               │ │   │
│  │  └──────────────────────────────────────────────────────────────────────────────┘ │   │
│  │                                                                                     │   │
│  │  ❌ SEM FERRAMENTAS BCC: banco gerenciado, sem acesso privilegiado                 │   │
│  └─────────────────────────────────────────────────────────────────────────────────────┘   │
│                                                                                             │
└─────────────────────────────────────────────────────────────────────────────────────────────┘
```

### Timeline da Query

| Tempo | Evento | Pixie (Camada 4) | USDT (Camada 7) |
|-------|--------|------------------|-----------------|
| T0 | Backend gera SQL | ✅ Vê (TLS uprobe) | ❌ Não vê |
| T1 | Envia para rede | ✅ Vê (send()) | ❌ Não vê |
| T2 | Viaja pela Internet | ❌ Não vê (TLS) | ❌ Não vê |
| T3 | Chega no MySQL | ❌ Não vê (RDS) | ✅ `query__exec__start` |
| T4-T6 | Parse/Optimize/Execute | ❌ Não vê | ✅ Captura tudo |
| T7 | Resultado pronto (15ms) | ❌ Não vê | ✅ `query__exec__done` |
| T8 | Envia de volta | ✅ Vê (send()) | ❌ Já terminou |
| T9 | Backend recebe | ✅ Vê (recv()) | ❌ Não vê |

---

## 6. Cenário Híbrido: Backend + MySQL Próprio (Ambos Acessíveis)

Quando você tem acesso ao servidor MySQL (não RDS), pode usar **ambos**:

```
┌─────────────────────────────────────────────────────────────────────────────────────────────┐
│  AMBIENTE PRÓPRIO (Bare Metal / VM / Kubernetes com acesso privilegiado)                   │
├─────────────────────────────────────────────────────────────────────────────────────────────┤
│                                                                                             │
│  ┌─────────────────────────────┐              ┌─────────────────────────────┐               │
│  │  BACKEND                    │              │  MYSQL SERVER               │               │
│  │                             │              │                             │               │
│  │  ┌─────────────────────┐    │              │  ┌─────────────────────┐    │               │
│  │  │  Pixie Agent        │    │              │  │  BCC Tools          │    │               │
│  │  │  • Camada 4 (rede)  │    │              │  │  • dbslower_fixed   │    │               │
│  │  │  • TLS uprobe       │◀───┼── Network ───┼─▶│  • dbstat_fixed     │    │               │
│  │  │  • send()/recv()    │    │              │  │  • USDT probes      │    │               │
│  │  └─────────────────────┘    │              │  └─────────────────────┘    │               │
│  │                             │              │           │               │               │
│  │                             │              │           ▼               │               │
│  │                             │              │  ┌─────────────────────┐    │               │
│  │                             │              │  │  mysqld             │    │               │
│  │                             │              │  │  ┌───────────────┐    │    │               │
│  │                             │              │  │  │ query__exec__ │    │    │               │
│  │                             │              │  │  │ _start        │◀───┼────┼── Captura     │
│  │                             │              │  │  └───────────────┘    │    │               │
│  │                             │              │  │  ┌───────────────┐    │    │               │
│  │                             │              │  │  │ query__exec__ │    │    │               │
│  │                             │              │  │  │ _done         │◀───┼────┼── Latência    │
│  │                             │              │  │  └───────────────┘    │    │    exata      │
│  │                             │              │  └─────────────────────┘    │               │
│  │                             │              │                             │               │
│  └─────────────────────────────┘              └─────────────────────────────┘               │
│                                                                                             │
│  ✅ VISÃO COMPLETA:                                                                         │
│     • Pixie: tráfego de rede, distributed tracing                                           │
│     • USDT/BCC: latência real de execução no banco                                          │
└─────────────────────────────────────────────────────────────────────────────────────────────┘
```

---

## 7. Matriz de Decisão: Qual Ferramenta Usar?

| Cenário | Pixie | USDT/BCC | Notas |
|---------|-------|----------|-------|
| **RDS / Cloud SQL / Gerenciado** | ✅ | ❌ | USDT requer acesso ao processo |
| **MySQL 8.0+** | ✅ | ❌ | MySQL 8.0 removeu USDT |
| **MySQL 5.7 próprio** | ✅ | ✅ | Ambos funcionam! |
| **PostgreSQL** | ✅ | ⚠️ | Pixie sempre funciona; USDT depende de compilação |
| **Redis / MongoDB / Kafka** | ✅ | ❌ | Pixie decodifica protocolo; USDT não disponível |
| **Queries internas (SP, triggers)** | ❌ | ✅ | USDT vê dentro do banco |
| **Kubernetes / Microservices** | ✅ | ⚠️ | Pixie feito para K8s; BCC requer privilégios especiais |
| **Análise profunda de performance** | ⚠️ | ✅ | USDT dá métricas exatas de execução |

---

## 8. Arquitetura Comparativa: Pixie vs BCC/USDT

### Pixie

```
┌─────────────────────────────────────────────────────────────────┐
│  Pixie (Camada 4 - Transporte)                                   │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  Ponto de captura: kprobes em syscalls de rede (send/recv)      │
│                    uprobes em TLS API (OpenSSL)                  │
│                                                                  │
│  Fluxo: App → TLS lib ──▶ uprobe (captura) ──▶ criptografia     │
│                    │                                             │
│                    └──▶ send() ──▶ kprobe ──▶ rede             │
│                                                                  │
│  Decodificação: Kernel eBPF analisa protocolo por porta         │
│                                                                  │
│  Vantagens:                                                      │
│  • Funciona com qualquer aplicação                               │
│  • Funciona em cloud (RDS)                                       │
│  • Múltiplos protocolos                                          │
│  • Captura TLS                                                   │
│                                                                  │
│  Desvantagens:                                                   │
│  • Não vê queries internas (SP, triggers)                        │
│  • Latência medida inclui rede                                   │
│  • Precisa decodificar protocolo                                 │
└─────────────────────────────────────────────────────────────────┘
```

### BCC/USDT

```
┌─────────────────────────────────────────────────────────────────┐
│  BCC/USDT (Camada 7 - Aplicação)                                 │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  Ponto de captura: Probes embutidos no código-fonte do MySQL      │
│                                                                  │
│  Fluxo: MySQL → query__exec__start ──▶ BPF handler              │
│                  │                                               │
│                  ├──▶ Parser → Otimizador → Executor → Storage   │
│                  │                                               │
│                  └──▶ query__exec__done ──▶ BPF handler          │
│                                                                  │
│  Decodificação: Direta — argumentos do probe são strings/structs  │
│                                                                  │
│  Vantagens:                                                      │
│  • Latência exata de execução (sem rede)                         │
│  • Vê queries internas (stored procedures, triggers)             │
│  • Acesso a estruturas internas                                  │
│  • Zero overhead inativo                                         │
│                                                                  │
│  Desvantagens:                                                   │
│  • Requer acesso ao processo (privileged)                        │
│  • Não funciona em RDS/Cloud SQL                                 │
│  • Não funciona em MySQL 8.0+                                    │
│  • Um protocolo por vez (específico para MySQL)                  │
└─────────────────────────────────────────────────────────────────┘
```

---

## 9. Resumo Visual: Stack Completa

```
┌──────────────────────────────────────────────────────────────────────────────┐
│  OBSERVABILIDADE DE BANCO DE DADOS                                           │
├──────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  CAMADA 7 (Aplicação) ───────────────────────────────────────────────────  │
│  ┌──────────────────────────────────────────────────────────────────────┐   │
│  │  MySQL / PostgreSQL / App                                            │   │
│  │  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐               │   │
│  │  │  USDT Probe  │  │  USDT Probe  │  │   Código     │               │   │
│  │  │  (início)    │──│   (fim)      │  │              │               │   │
│  │  └──────┬───────┘  └──────┬───────┘  └──────────────┘               │   │
│  │         │                 │                                         │   │
│  │         └─────────────────┴──▶ BCC Tools (dbslower, dbstat)          │   │
│  │                              • Latência exata                        │   │
│  │                              • Queries internas                        │   │
│  │                              • Requer acesso ao processo             │   │
│  └──────────────────────────────────────────────────────────────────────┘   │
│                                                                              │
│  CAMADA 6 (Apresentação) ──────────────────────────────────────────────────  │
│  ┌──────────────────────────────────────────────────────────────────────┐   │
│  │  TLS/SSL (OpenSSL, BoringSSL, Go TLS)                                │   │
│  │       ▲                                                               │   │
│  │       │ Pixie uprobe (captura ANTES de criptografar)                  │   │
│  └───────┼────────────────────────────────────────────────────────────────┘   │
│          │                                                                   │
│  CAMADA 4 (Transporte) ────────────────────────────────────────────────────  │
│  ┌───────┼────────────────────────────────────────────────────────────────┐   │
│  │       ▼                                                               │   │
│  │  ┌──────────┐    ┌──────────┐                                          │   │
│  │  │  send()  │    │  recv()  │◀── kprobes                               │   │
│  │  │ (syscall)│    │ (syscall)│    (Pixie)                               │   │
│  │  └────┬─────┘    └────┬─────┘                                          │   │
│  │       │               │                                               │   │
│  │       └───────┬───────┘                                               │   │
│  │               ▼                                                        │   │
│  │  ┌────────────────────────────┐                                        │   │
│  │  │  Pixie Agent (eBPF)        │                                        │   │
│  │  │  • Decodifica protocolo    │                                        │   │
│  │  │  • Extrai SQL              │                                        │   │
│  │  │  • Múltiplos bancos        │                                        │   │
│  │  │  • Funciona na cloud       │                                        │   │
│  │  └────────────────────────────┘                                        │   │
│  └────────────────────────────────────────────────────────────────────────┘   │
│                                                                              │
│  REDE (Camadas 3-1) ─────────────────────────────────────────────────────  │
│  ┌──────────────────────────────────────────────────────────────────────┐   │
│  │  Internet / VPC / Cloud Network                                       │   │
│  │  • Dados criptografados (TLS)                                       │   │
│  │  • Latência variável (5-50ms)                                       │   │
│  │  • Inacessível para inspeção direta (sem chave TLS)                 │   │
│  └──────────────────────────────────────────────────────────────────────┘   │
│                                                                              │
└──────────────────────────────────────────────────────────────────────────────┘
```

---

## 10. Conclusão

- **Probes USDT (Camada 7)** oferecem a visão mais profunda e precisa do comportamento interno do banco de dados, mas requerem acesso privilegiado ao processo e suporte da aplicação.

- **Pixie (Camada 4)** oferece visibilidade universal, independente de suporte USDT, funcionando até mesmo com bancos gerenciados em cloud (RDS, Cloud SQL) e múltiplos protocolos.

- **Uso combinado**: Em ambientes onde você controla todo o stack (Kubernetes próprio com MySQL em container), usar ambos oferece a visão mais completa — Pixie para distributed tracing entre serviços e USDT/BCC para análise profunda de performance no banco.

---

## Referências

- [BCC - BPF Compiler Collection](https://github.com/iovisor/bcc)
- [Pixie - Observability for Kubernetes](https://px.dev)
- [MySQL 5.7 DTrace Documentation](https://dev.mysql.com/doc/refman/5.7/en/dba-dtrace-server.html)
- [Brendan Gregg - Linux BPF Superpowers](http://www.brendangregg.com/blog/2016-10-04/linux-bcc-mysqld-qslower.html)
- [eBPF Documentation](https://ebpf.io)
