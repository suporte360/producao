#!/usr/bin/env python3
"""
Diagnóstico 2 — tenta achar o critério que produz 458 pedidos.

Hipóteses testadas:
  - Pedidos com pedoflote preenchido (já tem OP vinculada)
  - Pedidos por deposito (filial)
  - Pedidos com pedprevi preenchida
  - Pedidos por pedrepres (vendedor)
  - Período por pedprevi (previsão) em vez de peddata (emissão)
  - Períodos menores (90, 60, 30 dias)
  - Combinações filtrando vazio + NULL
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database.postgresql_db import DatabasePostgreSQL


def separador(t):
    print("\n" + "=" * 70)
    print(f"  {t}")
    print("=" * 70)


def mostra(label, sql):
    pg = DatabasePostgreSQL()
    r = pg.query_one(sql)
    n = r['n'] if r else 0
    marker = "  <-- BATE COM 458!" if n == 458 else ""
    print(f"  {label}")
    print(f"      -> {n}{marker}")
    print()


def main():
    pg = DatabasePostgreSQL()
    print("Conectando ao PostgreSQL (ERP)...")

    # ───────────────────────────────────────────────────────────
    separador("HIPÓTESE 1: pedoflote (OP vinculada) preenchido")
    # ───────────────────────────────────────────────────────────
    mostra("pedoflote IS NOT NULL (180d)",
           "SELECT COUNT(DISTINCT pedido) AS n FROM public.pedido "
           "WHERE peddata >= CURRENT_DATE - INTERVAL '180 days' "
           "AND NULLIF(TRIM(CAST(pedoflote AS TEXT)), '') IS NOT NULL")
    mostra("pedoflote IS NULL (sem OP, 180d)",
           "SELECT COUNT(DISTINCT pedido) AS n FROM public.pedido "
           "WHERE peddata >= CURRENT_DATE - INTERVAL '180 days' "
           "AND NULLIF(TRIM(CAST(pedoflote AS TEXT)), '') IS NULL")
    mostra("pedoflote IS NOT NULL AND pedsitua='A' (180d)",
           "SELECT COUNT(DISTINCT pedido) AS n FROM public.pedido "
           "WHERE peddata >= CURRENT_DATE - INTERVAL '180 days' "
           "AND NULLIF(TRIM(CAST(pedoflote AS TEXT)), '') IS NOT NULL "
           "AND TRIM(CAST(COALESCE(pedsitua,'') AS TEXT)) = 'A'")

    # ───────────────────────────────────────────────────────────
    separador("HIPÓTESE 2: Por deposito (filial) — 180 dias")
    # ───────────────────────────────────────────────────────────
    rows = pg.query("""
        SELECT COALESCE(TRIM(CAST(deposito AS TEXT)), '<NULL>') AS deposito,
               COUNT(DISTINCT pedido) AS qtd
        FROM public.pedido
        WHERE peddata >= CURRENT_DATE - INTERVAL '180 days'
        GROUP BY 1
        ORDER BY qtd DESC
    """)
    print(f"  {'deposito':<15} {'qtd':>8}")
    print(f"  {'-'*15} {'-'*8}")
    for r in rows:
        marker = "  <-- BATE COM 458!" if r['qtd'] == 458 else ""
        print(f"  {r['deposito']:<15} {r['qtd']:>8}{marker}")

    # ───────────────────────────────────────────────────────────
    separador("HIPÓTESE 3: Com pedprevi preenchida (tem previsão)")
    # ───────────────────────────────────────────────────────────
    mostra("pedprevi > '2000-01-01' (180d, tem previsão)",
           "SELECT COUNT(DISTINCT pedido) AS n FROM public.pedido "
           "WHERE peddata >= CURRENT_DATE - INTERVAL '180 days' "
           "AND pedprevi > '2000-01-01'")
    mostra("pedprevi > '2000-01-01' AND pedsitua='A' (180d)",
           "SELECT COUNT(DISTINCT pedido) AS n FROM public.pedido "
           "WHERE peddata >= CURRENT_DATE - INTERVAL '180 days' "
           "AND pedprevi > '2000-01-01' "
           "AND TRIM(CAST(COALESCE(pedsitua,'') AS TEXT)) = 'A'")
    mostra("pedprevi > '2000-01-01' AND pedsitua IN ('A','P') (180d)",
           "SELECT COUNT(DISTINCT pedido) AS n FROM public.pedido "
           "WHERE peddata >= CURRENT_DATE - INTERVAL '180 days' "
           "AND pedprevi > '2000-01-01' "
           "AND TRIM(CAST(COALESCE(pedsitua,'') AS TEXT)) IN ('A','P')")
    mostra("pedprevi > '2000-01-01' AND pedsitsit NOT IN ('008','009','010','') AND pedsitua IN ('A','P')",
           "SELECT COUNT(DISTINCT pedido) AS n FROM public.pedido "
           "WHERE peddata >= CURRENT_DATE - INTERVAL '180 days' "
           "AND pedprevi > '2000-01-01' "
           "AND TRIM(CAST(COALESCE(pedsitua,'') AS TEXT)) IN ('A','P') "
           "AND TRIM(CAST(COALESCE(pedsitsit,'') AS TEXT)) NOT IN ('008','009','010','')")

    # ───────────────────────────────────────────────────────────
    separador("HIPÓTESE 4: Período por pedprevi (previsão) em vez de peddata")
    # ───────────────────────────────────────────────────────────
    mostra("pedprevi >= hoje - 180d (previsão nos últimos 180 dias)",
           "SELECT COUNT(DISTINCT pedido) AS n FROM public.pedido "
           "WHERE pedprevi >= CURRENT_DATE - INTERVAL '180 days' "
           "AND pedprevi > '2000-01-01'")
    mostra("pedprevi >= hoje - 180d AND pedsitua IN ('A','P')",
           "SELECT COUNT(DISTINCT pedido) AS n FROM public.pedido "
           "WHERE pedprevi >= CURRENT_DATE - INTERVAL '180 days' "
           "AND pedprevi > '2000-01-01' "
           "AND TRIM(CAST(COALESCE(pedsitua,'') AS TEXT)) IN ('A','P')")
    mostra("pedprevi >= hoje - 180d AND pedsitua='A'",
           "SELECT COUNT(DISTINCT pedido) AS n FROM public.pedido "
           "WHERE pedprevi >= CURRENT_DATE - INTERVAL '180 days' "
           "AND pedprevi > '2000-01-01' "
           "AND TRIM(CAST(COALESCE(pedsitua,'') AS TEXT)) = 'A'")

    # ───────────────────────────────────────────────────────────
    separador("HIPÓTESE 5: Períodos menores (sem filtro de status)")
    # ───────────────────────────────────────────────────────────
    for dias in [365, 270, 180, 150, 120, 90, 60, 45, 30]:
        r = pg.query_one(
            "SELECT COUNT(DISTINCT pedido) AS n FROM public.pedido "
            "WHERE peddata >= CURRENT_DATE - INTERVAL '%s days'" % dias
        )
        n = r['n'] if r else 0
        marker = "  <-- BATE COM 458!" if n == 458 else ""
        print(f"  Últimos {dias:>3} dias: {n}{marker}")

    # ───────────────────────────────────────────────────────────
    separador("HIPÓTESE 6: Pedsitua='A' com períodos menores")
    # ───────────────────────────────────────────────────────────
    for dias in [365, 270, 180, 150, 120, 90, 60, 45, 30]:
        r = pg.query_one(
            "SELECT COUNT(DISTINCT pedido) AS n FROM public.pedido "
            "WHERE peddata >= CURRENT_DATE - INTERVAL '%s days' "
            "AND TRIM(CAST(COALESCE(pedsitua,'') AS TEXT)) = 'A'" % dias
        )
        n = r['n'] if r else 0
        marker = "  <-- BATE COM 458!" if n == 458 else ""
        print(f"  Aprovados últimos {dias:>3} dias: {n}{marker}")

    # ───────────────────────────────────────────────────────────
    separador("HIPÓTESE 7: Excluindo combinação (vazio, vazio) [442 pedidos]")
    # ───────────────────────────────────────────────────────────
    mostra("Não (vazio, vazio) — exclui os 442 sem situação nenhuma",
           "SELECT COUNT(DISTINCT pedido) AS n FROM public.pedido "
           "WHERE peddata >= CURRENT_DATE - INTERVAL '180 days' "
           "AND NOT (TRIM(CAST(COALESCE(pedsitua,'') AS TEXT)) = '' "
           "         AND TRIM(CAST(COALESCE(pedsitsit,'') AS TEXT)) = '')")
    mostra("Não (vazio,vazio) AND pedsitua='A'",
           "SELECT COUNT(DISTINCT pedido) AS n FROM public.pedido "
           "WHERE peddata >= CURRENT_DATE - INTERVAL '180 days' "
           "AND NOT (TRIM(CAST(COALESCE(pedsitua,'') AS TEXT)) = '' "
           "         AND TRIM(CAST(COALESCE(pedsitsit,'') AS TEXT)) = '') "
           "AND TRIM(CAST(COALESCE(pedsitua,'') AS TEXT)) = 'A'")

    # ───────────────────────────────────────────────────────────
    separador("HIPÓTESE 8: Amostra de 5 pedidos com pedsitua='A', pedsitsit='001'")
    # ───────────────────────────────────────────────────────────
    print("  Vendo campos desses pedidos para entender o padrão:")
    rows = pg.query("""
        SELECT pedido, peddata, pedprevi, pedcliente, pedoflote,
               TRIM(CAST(COALESCE(pedsitua,'') AS TEXT)) AS sit,
               TRIM(CAST(COALESCE(pedsitsit,'') AS TEXT)) AS stat,
               pedvlrfat, pedrepres, deposito
        FROM public.pedido
        WHERE peddata >= CURRENT_DATE - INTERVAL '180 days'
          AND TRIM(CAST(COALESCE(pedsitua,'') AS TEXT)) = 'A'
          AND TRIM(CAST(COALESCE(pedsitsit,'') AS TEXT)) = '001'
        ORDER BY peddata DESC
        LIMIT 5
    """)
    for r in rows:
        print(f"  pedido={r['pedido']} data={r['peddata']} prev={r['pedprevi']} "
              f"cli={r['pedcliente']} oflote='{r['pedoflote']}' sit={r['sit']} "
              f"stat={r['stat']} vlrfat={r['pedvlrfat']} repres={r['pedrepres']} "
              f"dep={r['deposito']}")

    # ───────────────────────────────────────────────────────────
    separador("HIPÓTESE 9: Amostra de 5 pedidos (vazio, vazio)")
    # ───────────────────────────────────────────────────────────
    print("  Esses são os 442 'fantasmas' sem situação nenhuma:")
    rows = pg.query("""
        SELECT pedido, peddata, pedprevi, pedcliente, pedoflote,
               TRIM(CAST(COALESCE(pedsitua,'') AS TEXT)) AS sit,
               TRIM(CAST(COALESCE(pedsitsit,'') AS TEXT)) AS stat,
               pedvlrfat, pedrepres, deposito
        FROM public.pedido
        WHERE peddata >= CURRENT_DATE - INTERVAL '180 days'
          AND TRIM(CAST(COALESCE(pedsitua,'') AS TEXT)) = ''
          AND TRIM(CAST(COALESCE(pedsitsit,'') AS TEXT)) = ''
        ORDER BY peddata DESC
        LIMIT 5
    """)
    for r in rows:
        print(f"  pedido={r['pedido']} data={r['peddata']} prev={r['pedprevi']} "
              f"cli={r['pedcliente']} oflote='{r['pedoflote']}' sit={r['sit']} "
              f"stat={r['stat']} vlrfat={r['pedvlrfat']} repres={r['pedrepres']} "
              f"dep={r['deposito']}")

    # ───────────────────────────────────────────────────────────
    separador("HIPÓTESE 10: Quantos pedidos têm pedoflote preenchido E são 'A'")
    # ───────────────────────────────────────────────────────────
    rows = pg.query("""
        SELECT
            CASE WHEN NULLIF(TRIM(CAST(pedoflote AS TEXT)), '') IS NULL
                 THEN 'sem_of' ELSE 'com_of' END AS tem_of,
            TRIM(CAST(COALESCE(pedsitua,'') AS TEXT)) AS sit,
            TRIM(CAST(COALESCE(pedsitsit,'') AS TEXT)) AS stat,
            COUNT(DISTINCT pedido) AS qtd
        FROM public.pedido
        WHERE peddata >= CURRENT_DATE - INTERVAL '180 days'
        GROUP BY 1, 2, 3
        ORDER BY qtd DESC
    """)
    print(f"  {'tem_of':<10} {'sit':<8} {'stat':<8} {'qtd':>8}")
    print(f"  {'-'*10} {'-'*8} {'-'*8} {'-'*8}")
    for r in rows:
        marker = "  <-- 458?" if r['qtd'] == 458 else ""
        print(f"  {r['tem_of']:<10} {r['sit']:<8} {r['stat']:<8} {r['qtd']:>8}{marker}")

    print("\n" + "=" * 70)
    print("  FIM — cole TUDO aqui. Se 458 não apareceu em nenhuma hipótese,")
    print("  me diz ONDE você vê esse número 458 (qual sistema/tela do ERP).")
    print("=" * 70)


if __name__ == "__main__":
    main()
