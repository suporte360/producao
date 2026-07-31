#!/usr/bin/env python3
"""
Validação da REGRA NOVA do usuário para os KPIs.

Regra:
  Total      = 001 + 002 + 007 (180d) + 008 (30d)
  Em Aberto  = 001 + 002 (sem OF)
  Em Produção= 003 + 004 + 005 + 006 + 007 (não soma no total)
  Atendidos  = 008 (30d)
  Cancelados = 010 (30d)
  Atrasados  = 001 + 002 + 007 com pedprevi < hoje
  Próx 3 dias= 001 + 002 + 007 com pedprevi entre hoje e hoje+3
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from database.postgresql_db import DatabasePostgreSQL


def main():
    pg = DatabasePostgreSQL()
    print("Conectando ao PostgreSQL...\n")

    sql = """
        SELECT
            -- TOTAL: 001+002+007 (180d) + 008 (30d)
            COUNT(DISTINCT CASE
                WHEN TRIM(CAST(COALESCE(pedsitsit,'') AS TEXT)) IN ('001','002','007') THEN pedido
                WHEN TRIM(CAST(COALESCE(pedsitsit,'') AS TEXT)) = '008'
                 AND peddata >= CURRENT_DATE - INTERVAL '30 days' THEN pedido
            END) AS total,

            -- EM ABERTO: 001+002 sem OF
            COUNT(DISTINCT CASE
                WHEN TRIM(CAST(COALESCE(pedsitsit,'') AS TEXT)) IN ('001','002')
                 AND NULLIF(TRIM(CAST(pedoflote AS TEXT)), '') IS NULL
                THEN pedido
            END) AS em_aberto,

            -- EM PRODUÇÃO: 003+004+005+006+007 (não soma no total)
            COUNT(DISTINCT CASE
                WHEN TRIM(CAST(COALESCE(pedsitsit,'') AS TEXT)) IN ('003','004','005','006','007')
                THEN pedido
            END) AS em_producao,

            -- ATRASADOS: 001+002+007 com pedprevi < hoje
            COUNT(DISTINCT CASE
                WHEN TRIM(CAST(COALESCE(pedsitsit,'') AS TEXT)) IN ('001','002','007')
                 AND pedprevi < CURRENT_DATE
                 AND pedprevi > '2000-01-01'
                THEN pedido
            END) AS atrasados,

            -- PRÓX 3 DIAS: 001+002+007 com pedprevi entre hoje e +3
            COUNT(DISTINCT CASE
                WHEN TRIM(CAST(COALESCE(pedsitsit,'') AS TEXT)) IN ('001','002','007')
                 AND pedprevi >= CURRENT_DATE
                 AND pedprevi <= (CURRENT_DATE + INTERVAL '3 days')
                THEN pedido
            END) AS prox_3_dias,

            -- ATENDIDOS: 008 (30d)
            COUNT(DISTINCT CASE
                WHEN TRIM(CAST(COALESCE(pedsitsit,'') AS TEXT)) = '008'
                 AND peddata >= CURRENT_DATE - INTERVAL '30 days'
                THEN pedido
            END) AS atendidos,

            -- CANCELADOS: 010 (30d)
            COUNT(DISTINCT CASE
                WHEN TRIM(CAST(COALESCE(pedsitsit,'') AS TEXT)) = '010'
                 AND peddata >= CURRENT_DATE - INTERVAL '30 days'
                THEN pedido
            END) AS cancelados,

            -- BREAKDOWN por pedsitsit (180d) para auditoria
            COUNT(DISTINCT CASE WHEN TRIM(CAST(COALESCE(pedsitsit,'') AS TEXT)) = '001' THEN pedido END) AS n_001,
            COUNT(DISTINCT CASE WHEN TRIM(CAST(COALESCE(pedsitsit,'') AS TEXT)) = '002' THEN pedido END) AS n_002,
            COUNT(DISTINCT CASE WHEN TRIM(CAST(COALESCE(pedsitsit,'') AS TEXT)) = '003' THEN pedido END) AS n_003,
            COUNT(DISTINCT CASE WHEN TRIM(CAST(COALESCE(pedsitsit,'') AS TEXT)) = '004' THEN pedido END) AS n_004,
            COUNT(DISTINCT CASE WHEN TRIM(CAST(COALESCE(pedsitsit,'') AS TEXT)) = '005' THEN pedido END) AS n_005,
            COUNT(DISTINCT CASE WHEN TRIM(CAST(COALESCE(pedsitsit,'') AS TEXT)) = '006' THEN pedido END) AS n_006,
            COUNT(DISTINCT CASE WHEN TRIM(CAST(COALESCE(pedsitsit,'') AS TEXT)) = '007' THEN pedido END) AS n_007,
            COUNT(DISTINCT CASE WHEN TRIM(CAST(COALESCE(pedsitsit,'') AS TEXT)) = '008' THEN pedido END) AS n_008_total,
            COUNT(DISTINCT CASE WHEN TRIM(CAST(COALESCE(pedsitsit,'') AS TEXT)) = '008'
                                 AND peddata >= CURRENT_DATE - INTERVAL '30 days' THEN pedido END) AS n_008_30d,
            COUNT(DISTINCT CASE WHEN TRIM(CAST(COALESCE(pedsitsit,'') AS TEXT)) = '009' THEN pedido END) AS n_009,
            COUNT(DISTINCT CASE WHEN TRIM(CAST(COALESCE(pedsitsit,'') AS TEXT)) = '010' THEN pedido END) AS n_010_total,
            COUNT(DISTINCT CASE WHEN TRIM(CAST(COALESCE(pedsitsit,'') AS TEXT)) = '010'
                                 AND peddata >= CURRENT_DATE - INTERVAL '30 days' THEN pedido END) AS n_010_30d,
            COUNT(DISTINCT CASE WHEN TRIM(CAST(COALESCE(pedsitsit,'') AS TEXT)) = '' THEN pedido END) AS n_vazio,
            COUNT(DISTINCT CASE WHEN pedsitsit IS NULL THEN pedido END) AS n_null
        FROM public.pedido
        WHERE peddata >= CURRENT_DATE - INTERVAL '180 days'
    """
    res = pg.query_one(sql)
    if not res:
        print("Sem resultados")
        return

    print("=" * 60)
    print("  KPIs COM A REGRA NOVA")
    print("=" * 60)
    print(f"  total_pedidos      : {res['total']}")
    print(f"  em_aberto          : {res['em_aberto']}    (esperado ~135)")
    print(f"  em_producao (OF)   : {res['em_producao']}")
    print(f"  atrasados          : {res['atrasados']}")
    print(f"  proximos_3dias     : {res['prox_3_dias']}")
    print(f"  atendidos          : {res['atendidos']}")
    print(f"  cancelados         : {res['cancelados']}")
    print()
    print("=" * 60)
    print("  BREAKDOWN POR pedsitsit (180 dias)")
    print("=" * 60)
    print(f"  001 (Não Aprovado)       : {res['n_001']}")
    print(f"  002 (Em Aberto)          : {res['n_002']}")
    print(f"  003 (OF Estática)        : {res['n_003']}")
    print(f"  004 (OF em Processo)     : {res['n_004']}")
    print(f"  005 (OF Encerrada)       : {res['n_005']}")
    print(f"  006 (OF c/ Problema)     : {res['n_006']}")
    print(f"  007 (Atendido Parcial)   : {res['n_007']}    (esperado ~2)")
    print(f"  008 (Atendido Total 180d): {res['n_008_total']}")
    print(f"  008 (Atendido Total 30d) : {res['n_008_30d']}")
    print(f"  009 (Vínculo Expedição)  : {res['n_009']}")
    print(f"  010 (Cancelado 180d)     : {res['n_010_total']}")
    print(f"  010 (Cancelado 30d)      : {res['n_010_30d']}")
    print(f"  '' (vazio)               : {res['n_vazio']}")
    print(f"  NULL                     : {res['n_null']}")
    print()
    print(f"  Soma 001+002+007 = {res['n_001'] + res['n_002'] + res['n_007']}")
    print(f"  Soma 001+002+007+008(30d) = {res['n_001'] + res['n_002'] + res['n_007'] + res['n_008_30d']}")


if __name__ == "__main__":
    main()
