# USDT Probes e Ferramentas BCC

## O que são USDT Probes?

USDT (User Statically Defined Tracing) é uma tecnologia de instrumentação de rastreamento para programas em espaço de usuário (userspace). Faz parte do ecossistema de observabilidade do Linux, integrado ao **eBPF** e ferramentas como **BCC**, **bpftrace** e **SystemTap**.

### Características

- **Estático**: definido em tempo de compilação, embutido no binário como metadados na seção `.note.stapsdt` do ELF
- **Baixo overhead quando inativo**: quando nenhuma ferramenta está rastreando, o probe é executado como um `NOP` (instrução nula)
- **Ativado dinamicamente**: ferramentas como `bpftrace` ou BCC "ligam" o probe em tempo de execução, sem reiniciar o processo

### Como funcionam

1. O desenvolvedor insere macros USDT no código-fonte (ex: `DTRACE_PROBE`)
2. O compilador emite metadados no binário
3. Uma ferramenta de tracing lê esses metadados e injeta um breakpoint/uprobe no endereço do probe
4. Quando a execução passa pelo ponto, o handler eBPF é ativado

### Exemplo em C

```c
#include <sys/sdt.h>

void processa_requisicao(int id, int tamanho) {
    DTRACE_PROBE2(minha_app, requisicao_iniciada, id, tamanho);
    // ... lógica ...
    DTRACE_PROBE1(minha_app, requisicao_finalizada, id);
}
```

### Rastreamento com bpftrace

```bash
bpftrace -e 'usdt:/usr/bin/minha_app:minha_app:requisicao_iniciada { printf("id=%d tamanho=%d\n", arg0, arg1); }'
```

### Projetos com USDT probes embutidos

| Projeto | Exemplos de probes |
|---|---|
| CPython | `function__entry`, `function__return`, `gc__start` |
| Node.js | `http__server__request`, `gc__start` |
| PostgreSQL | `query__start`, `transaction__start` |
| MySQL 5.7 | `query__start`, `query__done` |
| Ruby | `method__entry`, `object__create` |

> O MySQL 8.0+ removeu o suporte a USDT probes. As ferramentas deste laboratório requerem MySQL 5.7.

---

## As ferramentas do laboratório

As três ferramentas usadas neste projeto — `mysqld_query`, `dbslower` e `dbstat` — são **softwares já implementados**, distribuídos pelo pacote `bpfcc-tools` do projeto [iovisor/bcc](https://github.com/iovisor/bcc). Elas são instaladas via `apt` no Dockerfile do container BCC e não foram implementadas neste repositório.

| Ferramenta | O que faz |
|---|---|
| `mysqld_query` | Rastreia todas as queries MySQL em tempo real via USDT probes |
| `dbslower` | Filtra queries acima de um limiar de latência configurável |
| `dbstat` | Exibe histograma de distribuição de latências em intervalos |

Todas usam os probes USDT `query__start` e `query__done` presentes no binário `mysqld` do MySQL 5.7.

---

## O que este repositório implementa

Este projeto é um **laboratório de uso** das ferramentas BCC, não de desenvolvimento delas. O que foi criado aqui é a infraestrutura para executá-las em ambiente controlado:

| Arquivo | Papel |
|---|---|
| `bcc/Dockerfile` | Imagem Ubuntu 22.04 com `bpfcc-tools` instalado |
| `bcc/scripts/run_mysqld_query.sh` | Descobre o PID do `mysqld` e invoca `mysqld_query-bpfcc` |
| `bcc/scripts/run_dbslower.sh` | Descobre o PID do `mysqld` e invoca `dbslower-bpfcc` com limiar configurável |
| `bcc/scripts/run_dbstat.sh` | Descobre o PID do `mysqld` e invoca `dbstat-bpfcc` com intervalo configurável |
| `docker-compose.yml` | Orquestra os containers MySQL, workload e BCC |
| `workload/workload.py` | Gerador de carga sintética com queries rápidas, lentas e escritas |
| `mysql/init.sql` | Banco de dados inicial para os experimentos |

### Como o rastreamento funciona entre containers

O container `bcc` compartilha o **namespace PID** do container `mysql`. Isso permite que as ferramentas BPF enxerguem o processo `mysqld` e anexem probes USDT/uprobes diretamente ao binário, mesmo estando em containers separados.

```
Container BCC (privileged)
    │
    ├─ pid: "service:mysql"  ← compartilha o namespace PID do MySQL
    │
    ├─ /sys/kernel/debug     ← acesso ao tracefs do host
    ├─ /lib/modules          ← módulos do kernel
    └─ /usr/src              ← headers do kernel
```
