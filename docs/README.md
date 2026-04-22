# Documentação do Projeto bcc-lab

## Índice de Documentos

### Documentos Principais

| Documento | Descrição | Tamanho |
|-----------|-----------|---------|
| [resumo-bcc-mysql-troubleshooting.md](resumo-bcc-mysql-troubleshooting.md) | Resumo completo do troubleshooting realizado | ~9.4 KB |

### Comparações de Implementação

Documentos detalhados comparando as ferramentas BCC originais com nossas versões corrigidas:

| Documento | Ferramenta | Original | Corrigido | Linhas |
|-----------|------------|----------|-----------|--------|
| [comparacao-dbslower.md](comparacao-dbslower.md) | `dbslower` | Sasha Goldshtein (2017) | `dbslower_fixed.py` | 430 |
| [comparacao-dbstat.md](comparacao-dbstat.md) | `dbstat` | Sasha Goldshtein (2017) | `dbstat_fixed.py` | 394 |
| [comparacao-mysqld-qslower.md](comparacao-mysqld-qslower.md) | `mysqld_qslower` | Brendan Gregg/Netflix (2016) | `mysqld_query_fixed.py` | 463 |

### Documentação de Referência

| Documento | Descrição |
|-----------|-----------|
| [ebpf-database-tracing.md](ebpf-database-tracing.md) | Conceitos de eBPF para tracing de banco de dados |
| [usdt-probes-e-ferramentas-bcc.md](usdt-probes-e-ferramentas-bcc.md) | USDT probes e ferramentas BCC |
| [implementando-ferramentas-usdt-customizadas.md](implementando-ferramentas-usdt-customizadas.md) | Guia de implementação |

---

## Resumo do Problema Resolvido

### Erro Original
```
/scripts/run_mysqld_query.sh: line 19: /usr/sbin/mysqld_query-bpfcc: No such file or directory
```

E subsequentemente, as ferramentas BCC (`mysqld_qslower-bpfcc`, `dbslower-bpfcc`, `dbstat-bpfcc`) falhavam silenciosamente com a imagem `mysql:5.7` Docker.

### Causa Raiz
As ferramentas BCC originais usam os probes `query__start`/`query__done`, que **não funcionam** com a imagem `mysql:5.7` (Oracle Linux) devido a diferenças no formato de compilação dos probes USDT.

### Solução
Scripts Python personalizados usando os probes `query__exec__start`/`query__exec__done`, que funcionam corretamente:

- `mysqld_query_fixed.py`
- `dbslower_fixed.py`
- `dbstat_fixed.py`

### Status
✅ Todas as ferramentas de tracing funcionando:
- `make trace-query` - Rastreia todas as queries
- `make trace-slow` - Queries > 1ms
- `make trace-slow-10ms` - Queries > 10ms
- `make trace-stat` - Histograma (5s)
- `make trace-stat-10s` - Histograma (10s)

---

## Commit com as Correções

```
d6d6d66 fix: Corrige ferramentas BPF de rastreamento MySQL para usar probes USDT corretos
```

---

## Referências Externas

- [BCC GitHub](https://github.com/iovisor/bcc)
- [Brendan Gregg's Blog](http://www.brendangregg.com/blog/2016-10-04/linux-bcc-mysqld-qslower.html)
- [MySQL DTrace Documentation](https://dev.mysql.com/doc/refman/5.7/en/dba-dtrace-server.html)
- [BCC Issue #4761](https://github.com/iovisor/bcc/issues/4761)
