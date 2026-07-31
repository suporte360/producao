#!/usr/bin/env python3
"""Valida a regra NOVA v2 — Em Aberto = só 001, Atrasados/Prox3dias = só 001."""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from database.postgresql_db import DatabasePostgreSQL


def main():
    pg = DatabasePostgreSQL()
    print("Conectando ao PostgreSQL...\n")

    # Roda a função real
    resumo = pg.get_resumo_pedidos_erp()
    print("=" * 60)
    print("  SAÍDA DA FUNÇÃO get_resumo_pedidos_erp() — REGRA NOVA v2")
    print("=" * 60)
    for k, v in resumo.items():
        print(f"  {k:<22} {v}")

    # Breakdown por status para auditoria
    print("\n" + "=" * 60)
    print("  BREAKDOWN POR pedsitsit (180 dias) — auditoria")
    print("=" * 60)
    sql = """
        SELECT
            COALESCE(TRIM(CAST(COALESCE(pedsitsit,'') AS TEXT)), '<NULL>') AS stat,
            COUNT(DISTINCT pedido) AS qtd,
            COUNT(DISTINCT CASE WHEN pedprevi < CURRENT_DATE AND pedprevi > '2000-01-01' THEN pedido END) AS atrasados,
            COUNT(DISTINCT CASE WHEN pedprevi >= CURRENT_DATE AND pedprevi <= (CURRENT_DATE + INTERVAL '3 days') THEN pedido END) AS prox3
        FROM public.pedido
        WHERE peddata >= CURRENT_DATE - INTERVAL '180 days'
        GROUP BY 1
        ORDER BY qtd DESC
    """
    rows = pg.query(sql)
    print(f"  {'stat':<10} {'qtd':>8} {'atrasados':>10} {'prox3':>8}")
    print(f"  {'-'*10} {'-'*8} {'-'*10} {'-'*8}")
    for r in rows:
        print(f"  {r['stat']:<10} {r['qtd']:>8} {r['atrasados']:>10} {r['prox3']:>8}")

    print("\n" + "=" * 60)
    print("  RESUMO DA REGRA NOVA v2")
    print("=" * 60)
    print(f"  total_pedidos  = 001+002+007 (180d) = {resumo['total_pedidos']}")
    print(f"  em_aberto      = 001 sem OF       = {resumo['em_aberto']}")
    print(f"  em_producao    = 003+004+005+006+007 = {resumo['em_producao']}")
    print(f"  atrasados      = 001 c/ prev<hoje = {resumo['atrasados']}")
    print(f"  proximos_3dias = 001 c/ prev<=+3d = {resumo['proximos_3dias']}")
    print(f"  atendidos      = 008 (30d)        = {resumo['atendidos']}")
    print(f"  cancelados     = 010 (30d)        = {resumo['cancelados']}")


if __name__ == "__main__":
    main()
