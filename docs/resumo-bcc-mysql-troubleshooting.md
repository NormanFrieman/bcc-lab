# Resumo: Troubleshooting BCC/MySQL USDT Probes

## Histórico do Problema

Durante o desenvolvimento do projeto bcc-lab, o comando `make trace-query` falhou inicialmente com o erro:

```
/scripts/run_mysqld_query.sh: line 19: /usr/sbin/mysqld_query-bpfcc: No such file or directory
```

Após correção inicial, as ferramentas BCC (`mysqld_qslower-bpfcc`, `dbslower-bpfcc`, `dbstat-bpfcc`) falhavam silenciosamente ou não reportavam queries mesmo com o MySQL 5.7 processando queries normalmente.

---

## Causa Raiz

### 1. Incompatibilidade de Probes USDT

O MySQL 5.7 possui **dois conjuntos** de probes para rastreamento de queries:

| Probe | Quando Disparado | Funciona com BCC? |
|-------|-----------------|-------------------|
| `query-start` / `query-done` | Quando query é recebida do cliente | ❌ Não na imagem Docker |
| `query-exec-start` / `query-exec-done` | Quando execução real começa (após parsing) | ✅ Sim |

As ferramentas BCC oficiais esperam `query__start` e `query__done`, mas na imagem `mysql:5.7` (Oracle Linux) esses probes **existem mas não funcionam corretamente** com o BCC.

### 2. systemtap-sdt-dev

O pacote `systemtap-sdt-dev` fornece o header `sys/sdt.h` que define como os probes USDT são estruturados no binário.

**Com systemtap-sdt-dev:**
- Probes são criados com formato padronizado SystemTap/BCC
- BCC consegue ler argumentos corretamente
- Funciona conforme documentação

**Sem systemtap-sdt-dev (imagem Docker mysql:5.7):**
- Probes existem, mas formato dos argumentos é diferente
- BCC não consegue ler corretamente
- Falha silenciosa ou erro de ativação

### 3. Evidências de Issues Públicos

| Issue | Descrição | Status |
|-------|-----------|--------|
| [bcc#4761](https://github.com/iovisor/bcc/issues/4761) | `mysqld_qslower-bpfcc` não funciona no Ubuntu 20.04.1 com MariaDB 10.6 | Aberto desde 2023 |
| [bcc#2233](https://github.com/iovisor/bcc/issues/2233) | `mysqld_query.py` não funciona no CentOS 7 com MySQL 5.7 | Fechado |
| [bcc#1241](https://github.com/iovisor/bcc/issues/1241) | `dbstat` falha com PostgreSQL sem USDT probes | Fechado |
| [MySQL#105741](https://bugs.mysql.com/bug.php?id=105741) | Pedido para reintroduzir DTrace no MySQL 8.0 | Recusado pela Oracle |

---

## Solução Implementada

### Scripts Python Personalizados

Criamos versões corrigidas das ferramentas BCC que usam `query__exec__start` e `query__exec__done`:

- `bcc/scripts/mysqld_query_fixed.py` - Rastreia todas as queries
- `bcc/scripts/dbslower_fixed.py` - Rastreia queries lentas
- `bcc/scripts/dbstat_fixed.py` - Histograma de latências

### Atualizações nos Scripts Shell

- `run_mysqld_query.sh` - Agora usa `mysqld_query_fixed.py`
- `run_dbslower.sh` - Agora usa `dbslower_fixed.py`
- `run_dbstat.sh` - Agora usa `dbstat_fixed.py`

### Atualização do Dockerfile

- Base image: `ubuntu:22.04` → `ubuntu:24.04`
- Adicionado `linux-tools-generic`

---

## Alternativas Consideradas

### 1. Compilar MySQL com ENABLE_DTRACE=1

**Como funcionaria:**
- Criar Dockerfile customizado compilando MySQL com `-DENABLE_DTRACE=1`
- Usar `systemtap-sdt-dev` durante a compilação

**Prós:**
- Usaria ferramentas BPF originais sem modificação
- Solução "pura"

**Contras:**
- Tempo de build: ~30 minutos
- Manutenção de imagem customizada é trabalhosa
- Problema: mesmo compilado, a imagem ainda pode não funcionar se não usar `systemtap-sdt-dev` corretamente

**Veredito:** Não implementado por complexidade vs. benefício para um lab de estudo.

### 2. Migrar para MariaDB

**Como funcionaria:**
- Substituir `mysql:5.7` por `mariadb:10.6` ou `mariadb:10.11`
- MariaDB mantém suporte ativo a DTrace/USDT

**Prós:**
- Funciona com ferramentas BCC originais
- Drop-in replacement (quase 100% compatível)
- Mantido ativamente

**Contras:**
- Pequenas diferenças de comportamento MySQL vs. MariaDB
- Requer teste do workload

**Veredito:** Não implementado para manter MySQL 5.7 conforme requisito do projeto.

### 3. PR para Projeto BCC

**Como funcionaria:**
- Fazer patch no BCC para tentar `query__exec__start` quando `query__start` falhar
- Submeter PR para iovisor/bcc

**Prós:**
- Solução definitiva para toda a comunidade
- Não requer manutenção local

**Contras:**
- Demora meses para ser aceito
- Pode não ser aceito se considerarem workaround

**Veredito:** Fora do escopo de um projeto de lab/estudo.

### 4. Usar Uprobes

**Como funcionaria:**
- Hook em funções como `mysql_execute_command` usando uprobes
- Usar `funccount`, `funclatency` ou scripts BPF customizados

**Prós:**
- Não depende de USDT/DTrace
- Funciona com qualquer versão MySQL

**Contras:**
- Extremamente frágil: nomes de funções mudam entre versões
- Difícil extrair string da query
- Pode quebrar com atualizações menores

**Veredito:** Rejeitado por fragilidade.

---

## Quando Funciona (Casos de Sucesso)

### MySQL Compilado Manualmente com systemtap-sdt-dev

Fonte: [MySQL Bug #105741](https://bugs.mysql.com/bug.php?id=105741)

```bash
# 1. Download MySQL 5.7 source
# 2. Install systemtap-sdt-dev
# 3. Compile com -DENABLE_DTRACE=1
# 4. Ferramentas BCC funcionam!
```

> "MySQL 5.7 with dtrace can be easily compiled in 2021 and works just out of the box via USDT with the installation of the systemtap-sdt-dev package"

### Plataformas Nativas

| Plataforma | Funciona? |
|------------|-----------|
| Solaris 10 Update 5 (SPARC, x86, x86_64) | ✅ Sim |
| OS X / macOS 10.4+ | ✅ Sim |
| Oracle Linux 6+ com UEK kernel | ✅ Sim |
| Outras Linux (compilado manualmente) | ✅ Sim |

### Exemplo Oficial: Blog Brendan Gregg

Fonte: [Linux MySQL Slow Query Tracing](http://www.brendangregg.com/blog/2016-10-04/linux-bcc-mysqld-qslower.html)

```bash
# mysqld_qslower `pgrep -n mysqld`
Tracing MySQL server queries for PID 14371 slower than 1 ms...
TIME(s)        PID          MS QUERY
0.000000       18608   130.751 SELECT * FROM words WHERE word REGEXP '^bre.*n$'
2.921535       18608   130.590 SELECT * FROM words WHERE word REGEXP '^alex.*$'
```

**Contexto:** MySQL compilado de fonte com `--with-dtrace` ou `--enable-dtrace`.

---

## Sobre systemtap-sdt-dev

### O que é

Pacote de desenvolvimento do SystemTap que fornece:
- `sys/sdt.h` - Header C/C++ com macros para definir probes
- `dtrace` - Comando para pré-processar scripts DTrace
- `stap` - Ferramenta SystemTap para tracing

### Macros Fornecidas

| Macro | Função |
|-------|--------|
| `STAP_PROBE(provider, name)` | Cria probe simples |
| `STAP_PROBE1(provider, name, arg1)` | Probe com 1 argumento |
| `STAP_PROBE5(provider, name, ...)` | Probe com 5 argumentos (MySQL) |

### Instalação

**Ubuntu/Debian:**
```bash
sudo apt-get install systemtap-sdt-dev
```

**CentOS/RHEL/Fedora:**
```bash
sudo yum install systemtap-sdt-devel
# ou
sudo dnf install systemtap-sdt-devel
```

---

## Comandos Verificados Após Correção

| Comando | Descrição | Status |
|---------|-----------|--------|
| `make trace-query` | Rastreia todas as queries em tempo real | ✅ Funcionando |
| `make trace-slow` | Rastreia queries > 1ms | ✅ Funcionando |
| `make trace-slow-10ms` | Rastreia queries > 10ms | ✅ Funcionando |
| `make trace-stat` | Histograma de latências (5s) | ✅ Funcionando |
| `make trace-stat-10s` | Histograma de latências (10s) | ✅ Funcionando |

---

## Conclusões

1. **O erro é real e documentado**: Existem 3+ issues oficiais no repositório BCC confirmando o problema com MySQL/MariaDB

2. **A solução atual é pragmática**: Scripts Python personalizados usando `query__exec__*` são uma solução viável para um ambiente de estudo

3. **A compilação manual resolveria**: Compilar MySQL 5.7 com `systemtap-sdt-dev` e `-DENABLE_DTRACE=1` permitiria usar as ferramentas BCC originais, mas adiciona complexidade de manutenção

4. **MariaDB é alternativa**: Migrar para MariaDB 10.6+ eliminaria o problema, mas mudaria o banco de dados do projeto

5. **O problema é específico da imagem Docker**: A imagem `mysql:5.7` (Oracle Linux) não usa `systemtap-sdt-dev` durante a compilação, resultando em probes com formato incompatível

---

## Referências

1. [BCC Issue #4761 - mysqld_qslower não funciona](https://github.com/iovisor/bcc/issues/4761)
2. [BCC Issue #2233 - mysqld_query.py não funciona no CentOS 7](https://github.com/iovisor/bcc/issues/2233)
3. [BCC Issue #1241 - dbstat falha com PostgreSQL](https://github.com/iovisor/bcc/issues/1241)
4. [MySQL Bug #105741 - DTrace removido no 8.0](https://bugs.mysql.com/bug.php?id=105741)
5. [Blog Brendan Gregg - Linux MySQL Slow Query Tracing](http://www.brendangregg.com/blog/2016-10-04/linux-bcc-mysqld-qslower.html)
6. [MySQL 5.7 DTrace Documentation](https://dev.mysql.com/doc/refman/5.7/en/dba-dtrace-server.html)
7. [MariaDB Dynamic Tracing Presentation](https://mariadb.org/wp-content/uploads/2020/09/dynamictracing_serverfest2020.pdf)

---

## Hash do Commit

As correções foram consolidadas no commit:
```
d6d6d66 fix: Corrige ferramentas BPF de rastreamento MySQL para usar probes USDT corretos
```

**Arquivos modificados:**
- `bcc/Dockerfile`
- `bcc/scripts/mysqld_query_fixed.py` (novo)
- `bcc/scripts/dbslower_fixed.py` (novo)
- `bcc/scripts/dbstat_fixed.py` (novo)
- `bcc/scripts/run_mysqld_query.sh`
- `bcc/scripts/run_dbslower.sh`
- `bcc/scripts/run_dbstat.sh`

---

*Documento gerado em: Abril 2026*
*Projeto: bcc-lab*
