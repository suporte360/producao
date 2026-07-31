#!/usr/bin/env python3
"""
Diagnóstico 4 — compara status da tabela pedido.pedsitsit vs pestatus.pesstatus.

Descoberta: o gerador de PDF usa JOIN com pestatus, mas get_resumo_pedidos_erp
usa pedsitsit direto da tabela pedido. São fontes diferentes!
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from database.postgresql_db import DatabasePostgreSQL


def main():
    pg = DatabasePostgreSQL()
    print("Conectando ao PostgreSQL...\n")

    # 1. Verificar se a tabela pestatus existe
    print("=" * 70)
    print("1. Verificando tabela pestatus")
    print("=" * 70)
    try:
        r = pg.query_one("SELECT COUNT(*) AS n FROM public.pestatus")
        print(f"  Total registros na tabela pestatus: {r['n'] if r else 0}")
    except Exception as e:
        print(f"  ERRO: {e}")
        return

    # 2. Quebra por pesstatus (180 dias)
    print("\n" + "=" * 70)
    print("2. Breakdown por pesstatus (180 dias)")
    print("=" * 70)
    rows = pg.query("""
        SELECT
            COALESCE(TRIM(CAST(ps.pesstatus AS TEXT)), '<NULL>') AS pesstatus,
            COUNT(DISTINCT p.pedido) AS qtd
        FROM public.pedido p
        LEFT JOIN public.pestatus ps ON p.pedido::TEXT = ps.pespedido::TEXT
        WHERE p.peddata >= CURRENT_DATE - INTERVAL '180 days'
        GROUP BY 1
        ORDER BY qtd DESC
    """)
    print(f"  {'pesstatus':<15} {'qtd':>8}")
    print(f"  {'-'*15} {'-'*8}")
    for r in rows:
        marker = ""
        if r['pesstatus'] == '02': marker = "  <-- Em Aberto"
        elif r['pesstatus'] == '07': marker = "  <-- Parcial (esperado 2)"
        elif r['pesstatus'] == '08': marker = "  <-- Atendido Total"
        elif r['pesstatus'] == '10': marker = "  <-- Cancelado"
        print(f"  {r['pesstatus']:<15} {r['qtd']:>8}{marker}")

    # 3. KPIs calculados pela regra CERTA (usando pestatus)
    print("\n" + "=" * 70)
    print("3. KPIs usando pestatus (REGRA CERTA)")
    print("=" * 70)
    sql = """
        SELECT
            -- Total: 001+002+007 (180d) - usando pestatus
            COUNT(DISTINCT CASE
                WHEN TRIM(CAST(ps.pesstatus AS TEXT)) IN ('01','02','07')
                THEN p.pedido
            END) AS total,

            -- Em Aberto: só 002 (PDF 1)
            COUNT(DISTINCT CASE
                WHEN TRIM(CAST(ps.pesstatus AS TEXT)) = '02'
                THEN p.pedido
            END) AS em_aberto,

            -- Parcial: só 007 (PDF 2)
            COUNT(DISTINCT CASE
                WHEN TRIM(CAST(ps.pesstatus AS TEXT)) = '07'
                THEN p.pedido
            END) AS parcial,

            -- Em Produção: 03+04+05+06 (não soma no total)
            COUNT(DISTINCT CASE
                WHEN TRIM(CAST(ps.pesstatus AS TEXT)) IN ('03','04','05','06')
                THEN p.pedido
            END) AS em_producao,

            -- Atrasados: 001+002+007 com pedprevi < hoje
            COUNT(DISTINCT CASE
                WHEN TRIM(CAST(ps.pesstatus AS TEXT)) IN ('01','02','07')
                 AND p.pedprevi < CURRENT_DATE
                 AND p.pedprevi > '2000-01-01'
                THEN p.pedido
            END) AS atrasados,

            -- Próximos 3 dias: 001+002+007 com pedprevi entre hoje e +3
            COUNT(DISTINCT CASE
                WHEN TRIM(CAST(ps.pesstatus AS TEXT)) IN ('01','02','07')
                 AND p.pedprevi >= CURRENT_DATE
                 AND p.pedprevi <= (CURRENT_DATE + INTERVAL '3 days')
                THEN p.pedido
            END) AS prox_3_dias,

            -- Atendidos: 008 (30d) — PDF 4
            COUNT(DISTINCT CASE
                WHEN TRIM(CAST(ps.pesstatus AS TEXT)) = '08'
                 AND p.peddata >= CURRENT_DATE - INTERVAL '30 days'
                THEN p.pedido
            END) AS atendidos,

            -- Cancelados: 010 (30d) — PDF 3
            COUNT(DISTINCT CASE
                WHEN TRIM(CAST(ps.pesstatus AS TEXT)) = '10'
                 AND p.peddata >= CURRENT_DATE - INTERVAL '30 days'
                THEN p.pedido
            END) AS cancelados
        FROM public.pedido p
        LEFT JOIN public.pestatus ps ON p.pedido::TEXT = ps.pespedido::TEXT
        WHERE p.peddata >= CURRENT_DATE - INTERVAL '180 days'
    """
    res = pg.query_one(sql)
    print(f"  total_pedidos  = 001+002+007 (180d) = {res['total']}")
    print(f"  em_aberto      = 002 (PDF 1)       = {res['em_aberto']}")
    print(f"  parcial        = 007 (PDF 2)       = {res['parcial']}")
    print(f"  em_producao    = 003+004+005+006   = {res['em_producao']}")
    print(f"  atrasados      = 001+002+007 vencidos = {res['atrasados']}")
    print(f"  proximos_3dias = 001+002+007 próximos  = {res['prox_3_dias']}")
    print(f"  atendidos      = 008 (30d)         = {res['atendidos']}")
    print(f"  cancelados     = 010 (30d)         = {res['cancelados']}")

    # 4. Verificar inconsistência: pedsitsit vs pesstatus
    print("\n" + "=" * 70)
    print("4. Inconsistência pedsitsit (pedido) vs pesstatus (pestatus)")
    print("=" * 70)
    rows = pg.query("""
        SELECT
            COALESCE(TRIM(CAST(COALESCE(p.pedsitsit,'') AS TEXT)), '<vazio>') AS pedsitsit,
            COALESCE(TRIM(CAST(ps.pesstatus AS TEXT)), '<NULL>') AS pesstatus,
            COUNT(DISTINCT p.pedido) AS qtd
        FROM public.pedido p
        LEFT JOIN public.pestatus ps ON p.pedido::TEXT = ps.pespedido::TEXT
        WHERE p.peddata >= CURRENT_DATE - INTERVAL '180 days'
        GROUP BY 1, 2
        ORDER BY qtd DESC
        LIMIT 15
    """)
    print(f"  {'pedsitsit':<12} {'pesstatus':<12} {'qtd':>8}")
    print(f"  {'-'*12} {'-'*12} {'-'*8}")
    for r in rows:
        print(f"  {r['pedsitsit']:<12} {r['pesstatus']:<12} {r['qtd']:>8}")


if __name__ == "__main__":
    main()
