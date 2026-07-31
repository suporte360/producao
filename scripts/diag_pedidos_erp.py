#!/usr/bin/env python3
"""
Diagnóstico de contagem de pedidos do ERP (PostgreSQL) — últimos 180 dias.

Roda no servidor (192.168.1.14) dentro do venv do projeto:
    cd /home/suporte/producao_muito/producao
    source venv/bin/activate
    export PYTHONPATH=.
    python3 scripts/diag_pedidos_erp.py

Mostra:
  - Total bruto (qualquer status) nos últimos 180 dias
  - Quebra por pedsitua (situação: A/P/C/I/NULL)
  - Quebra por pedsitsit (status sit: 001..010/NULL)
  - Combinações mais comuns (pedsitua, pedsitsit) -> count
  - Os 3 critérios candidatos a "total correto" para comparar com 458
  - O que a SQL ATUAL do get_resumo_pedidos_erp() retorna
  - O que a SQL ANTIGA retornava (para confirmar o 3804)
"""
import sys
import os
from collections import Counter

# Garantir que o diretório do projeto está no path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database.postgresql_db import DatabasePostgreSQL


def separador(titulo):
    print("\n" + "=" * 70)
    print(f"  {titulo}")
    print("=" * 70)


def main():
    pg = DatabasePostgreSQL()
    print("Conectando ao PostgreSQL (ERP)...")

    # Teste de conexão
    ok = pg.query_one("SELECT 1 AS ok")
    if not ok:
        print("ERRO: não consegui conectar ao PostgreSQL")
        return
    print("Conexão OK.")

    # ───────────────────────────────────────────────────────────
    separador("1. TOTAL BRUTO (qualquer status) — últimos 180 dias")
    # ───────────────────────────────────────────────────────────
    row = pg.query_one("""
        SELECT COUNT(DISTINCT pedido) AS total
        FROM public.pedido
        WHERE peddata >= CURRENT_DATE - INTERVAL '180 days'
    """)
    print(f"  Total bruto de pedidos distintos (180 dias): {row['total']}")

    # ───────────────────────────────────────────────────────────
    separador("2. QUEBRA POR pedsitua (situação)")
    # ───────────────────────────────────────────────────────────
    rows = pg.query("""
        SELECT
            COALESCE(TRIM(CAST(pedsitua AS TEXT)), '<NULL>') AS pedsitua,
            COUNT(DISTINCT pedido) AS qtd
        FROM public.pedido
        WHERE peddata >= CURRENT_DATE - INTERVAL '180 days'
        GROUP BY 1
        ORDER BY qtd DESC
    """)
    print(f"  {'pedsitua':<15} {'qtd':>8}")
    print(f"  {'-'*15} {'-'*8}")
    for r in rows:
        print(f"  {r['pedsitua']:<15} {r['qtd']:>8}")

    # ───────────────────────────────────────────────────────────
    separador("3. QUEBRA POR pedsitsit (status sit)")
    # ───────────────────────────────────────────────────────────
    rows = pg.query("""
        SELECT
            COALESCE(TRIM(CAST(COALESCE(pedsitsit,'') AS TEXT)), '<NULL>') AS pedsitsit,
            COUNT(DISTINCT pedido) AS qtd
        FROM public.pedido
        WHERE peddata >= CURRENT_DATE - INTERVAL '180 days'
        GROUP BY 1
        ORDER BY qtd DESC
    """)
    print(f"  {'pedsitsit':<15} {'qtd':>8}")
    print(f"  {'-'*15} {'-'*8}")
    for r in rows:
        print(f"  {r['pedsitsit']:<15} {r['qtd']:>8}")

    # ───────────────────────────────────────────────────────────
    separador("4. COMBINAÇÕES (pedsitua, pedsitsit) -> qtd")
    # ───────────────────────────────────────────────────────────
    rows = pg.query("""
        SELECT
            COALESCE(TRIM(CAST(COALESCE(pedsitua,'') AS TEXT)), '<NULL>') AS pedsitua,
            COALESCE(TRIM(CAST(COALESCE(pedsitsit,'') AS TEXT)), '<NULL>') AS pedsitsit,
            COUNT(DISTINCT pedido) AS qtd
        FROM public.pedido
        WHERE peddata >= CURRENT_DATE - INTERVAL '180 days'
        GROUP BY 1, 2
        ORDER BY qtd DESC
    """)
    print(f"  {'pedsitua':<12} {'pedsitsit':<12} {'qtd':>8}")
    print(f"  {'-'*12} {'-'*12} {'-'*8}")
    for r in rows:
        print(f"  {r['pedsitua']:<12} {r['pedsitsit']:<12} {r['qtd']:>8}")

    # ───────────────────────────────────────────────────────────
    separador("5. CRITÉRIOS CANDIDATOS PARA 'TOTAL'")
    # ───────────────────────────────────────────────────────────
    candidatos = [
        ("A. Total bruto (sem filtro)",
         "SELECT COUNT(DISTINCT pedido) AS n FROM public.pedido WHERE peddata >= CURRENT_DATE - INTERVAL '180 days'"),
        ("B. pedsitua IN ('A','P','')  (mesmo critério da TV)",
         "SELECT COUNT(DISTINCT pedido) AS n FROM public.pedido WHERE peddata >= CURRENT_DATE - INTERVAL '180 days' AND TRIM(CAST(COALESCE(pedsitua,'') AS TEXT)) IN ('A','P','')"),
        ("C. pedsitua IN ('A','P','') AND pedsitsit NOT IN ('008','009','010')  (SQL ATUAL)",
         "SELECT COUNT(DISTINCT pedido) AS n FROM public.pedido WHERE peddata >= CURRENT_DATE - INTERVAL '180 days' AND TRIM(CAST(COALESCE(pedsitua,'') AS TEXT)) IN ('A','P','') AND TRIM(CAST(COALESCE(pedsitsit,'') AS TEXT)) NOT IN ('008','009','010')"),
        ("D. pedsitsit IN ('001','002','','007')  (SQL ANTIGA — esperado 3804)",
         "SELECT COUNT(DISTINCT pedido) AS n FROM public.pedido WHERE peddata >= CURRENT_DATE - INTERVAL '180 days' AND TRIM(CAST(COALESCE(pedsitsit,'') AS TEXT)) IN ('001','002','','007')"),
        ("E. pedsitua IN ('A','P')  (só Aprovado + Parcial, sem NULL)",
         "SELECT COUNT(DISTINCT pedido) AS n FROM public.pedido WHERE peddata >= CURRENT_DATE - INTERVAL '180 days' AND TRIM(CAST(COALESCE(pedsitua,'') AS TEXT)) IN ('A','P')"),
        ("F. pedsitsit IN ('001','002','007')  (sem o '')",
         "SELECT COUNT(DISTINCT pedido) AS n FROM public.pedido WHERE peddata >= CURRENT_DATE - INTERVAL '180 days' AND TRIM(CAST(COALESCE(pedsitsit,'') AS TEXT)) IN ('001','002','007')"),
        ("G. pedsitua IN ('A','P') AND pedsitsit IN ('001','002','007')",
         "SELECT COUNT(DISTINCT pedido) AS n FROM public.pedido WHERE peddata >= CURRENT_DATE - INTERVAL '180 days' AND TRIM(CAST(COALESCE(pedsitua,'') AS TEXT)) IN ('A','P') AND TRIM(CAST(COALESCE(pedsitsit,'') AS TEXT)) IN ('001','002','007')"),
    ]
    for label, sql in candidatos:
        r = pg.query_one(sql)
        n = r['n'] if r else 0
        marker = "  <-- bate com 458?" if n == 458 else ""
        print(f"  {label}")
        print(f"      -> {n}{marker}")
        print()

    # ───────────────────────────────────────────────────────────
    separador("6. SAÍDA DA FUNÇÃO get_resumo_pedidos_erp() ATUAL")
    # ───────────────────────────────────────────────────────────
    resumo = pg.get_resumo_pedidos_erp()
    for k, v in resumo.items():
        print(f"  {k:<22} {v}")

    # ───────────────────────────────────────────────────────────
    separador("7. EM_ABERTO — distintos critérios")
    # ───────────────────────────────────────────────────────────
    abertos_cand = [
        ("Em aberto (sem OF) — SQL atual",
         "SELECT COUNT(DISTINCT pedido) AS n FROM public.pedido WHERE peddata >= CURRENT_DATE - INTERVAL '180 days' AND TRIM(CAST(COALESCE(pedsitua,'') AS TEXT)) IN ('A','P','') AND TRIM(CAST(COALESCE(pedsitsit,'') AS TEXT)) NOT IN ('008','009','010') AND NULLIF(TRIM(CAST(pedoflote AS TEXT)), '') IS NULL"),
        ("pedsitsit IN ('001','002')",
         "SELECT COUNT(DISTINCT pedido) AS n FROM public.pedido WHERE peddata >= CURRENT_DATE - INTERVAL '180 days' AND TRIM(CAST(COALESCE(pedsitsit,'') AS TEXT)) IN ('001','002')"),
        ("pedsitua='A' AND pedsitsit IN ('001','002','')",
         "SELECT COUNT(DISTINCT pedido) AS n FROM public.pedido WHERE peddata >= CURRENT_DATE - INTERVAL '180 days' AND TRIM(CAST(COALESCE(pedsitua,'') AS TEXT)) = 'A' AND TRIM(CAST(COALESCE(pedsitsit,'') AS TEXT)) IN ('001','002','')"),
        ("pedsitsit='002'",
         "SELECT COUNT(DISTINCT pedido) AS n FROM public.pedido WHERE peddata >= CURRENT_DATE - INTERVAL '180 days' AND TRIM(CAST(COALESCE(pedsitsit,'') AS TEXT)) = '002'"),
    ]
    print(f"  (Usuário espera 135 em aberto)")
    for label, sql in abertos_cand:
        r = pg.query_one(sql)
        n = r['n'] if r else 0
        marker = "  <-- bate com 135?" if n == 135 else ""
        print(f"  {label}: {n}{marker}")

    # ───────────────────────────────────────────────────────────
    separador("8. PARCIAL — distintos critérios")
    # ───────────────────────────────────────────────────────────
    print(f"  (Usuário espera 2 parcial)")
    parc_cand = [
        ("pedsitsit='007'",
         "SELECT COUNT(DISTINCT pedido) AS n FROM public.pedido WHERE peddata >= CURRENT_DATE - INTERVAL '180 days' AND TRIM(CAST(COALESCE(pedsitsit,'') AS TEXT)) = '007'"),
        ("pedsitua='P'",
         "SELECT COUNT(DISTINCT pedido) AS n FROM public.pedido WHERE peddata >= CURRENT_DATE - INTERVAL '180 days' AND TRIM(CAST(COALESCE(pedsitua,'') AS TEXT)) = 'P'"),
    ]
    for label, sql in parc_cand:
        r = pg.query_one(sql)
        n = r['n'] if r else 0
        marker = "  <-- bate com 2?" if n == 2 else ""
        print(f"  {label}: {n}{marker}")

    print("\n" + "=" * 70)
    print("  FIM DO DIAGNÓSTICO")
    print("=" * 70)
    print("\nCole TODO este output aqui no chat para eu calibrar o SQL.")
    print("Especialmente a seção 4 (combinações) e 5 (candidatos).")


if __name__ == "__main__":
    main()
