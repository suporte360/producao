#!/usr/bin/env python3
"""
Diagnóstico 3 — tenta achar o critério que produz 458 pedidos.

Testa:
  1. Janelas de data específicas por dia (1 a 365 dias) — vê quantos dias produzem 458
  2. Janelas por pedprevi (previsão) em vez de peddata
  3. MariaDB local: lotes_producao com data_previsao_erp nos últimos 180 dias
  4. MariaDB: lotes por status
  5. Cruzamento: pedidos do ERP que têm lote no MariaDB
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database.postgresql_db import DatabasePostgreSQL


def separador(t):
    print("\n" + "=" * 70)
    print(f"  {t}")
    print("=" * 70)


def main():
    # ═════════════════════════════════════════════════════════════
    # PARTE 1: Janelas de data no PostgreSQL (procurando 458)
    # ═════════════════════════════════════════════════════════════
    pg = DatabasePostgreSQL()
    print("Conectando ao PostgreSQL (ERP)...")
    ok = pg.query_one("SELECT 1 AS ok")
    if not ok:
        print("ERRO: PostgreSQL offline")
        return
    print("OK.\n")

    # ───────────────────────────────────────────────────────────
    separador("1. BUSCA EXATA POR 458 — janelas por peddata (1 a 365 dias)")
    # ───────────────────────────────────────────────────────────
    print("  Procurando quantos dias (1-365) produzem exatamente 458 pedidos...\n")
    print(f"  {'dias':<6} {'bruto':>8} {'A':>6} {'A+P':>6} {'A+P-sem_vazio_vazio':>22}")
    print(f"  {'-'*6} {'-'*8} {'-'*6} {'-'*6} {'-'*22}")
    encontrou_458 = []
    for dias in [10, 20, 30, 45, 60, 75, 90, 105, 120, 135, 150, 165, 180,
                 195, 210, 225, 240, 255, 270, 285, 300, 315, 330, 345, 365]:
        r = pg.query_one(f"""
            SELECT
                COUNT(DISTINCT pedido) AS bruto,
                COUNT(DISTINCT CASE WHEN TRIM(CAST(COALESCE(pedsitua,'') AS TEXT)) = 'A' THEN pedido END) AS aprov,
                COUNT(DISTINCT CASE WHEN TRIM(CAST(COALESCE(pedsitua,'') AS TEXT)) IN ('A','P') THEN pedido END) AS ap,
                COUNT(DISTINCT CASE WHEN TRIM(CAST(COALESCE(pedsitua,'') AS TEXT)) IN ('A','P')
                                     AND NOT (TRIM(CAST(COALESCE(pedsitua,'') AS TEXT)) = ''
                                              AND TRIM(CAST(COALESCE(pedsitsit,'') AS TEXT)) = '')
                                    THEN pedido END) AS ap_sem_fantasma
            FROM public.pedido
            WHERE peddata >= CURRENT_DATE - INTERVAL '{dias} days'
        """)
        if r:
            linha = f"  {dias:<6} {r['bruto']:>8} {r['aprov']:>6} {r['ap']:>6} {r['ap_sem_fantasma']:>22}"
            marcadores = []
            if r['bruto'] == 458: marcadores.append("bruto=458!")
            if r['aprov'] == 458: marcadores.append("A=458!")
            if r['ap'] == 458: marcadores.append("A+P=458!")
            if r['ap_sem_fantasma'] == 458: marcadores.append("A+P-sem_fant=458!")
            if marcadores:
                linha += "  <-- " + " / ".join(marcadores)
                encontrou_458.append((dias, marcadores))
            print(linha)

    if encontrou_458:
        print(f"\n  *** ACHOU! Critério que dá 458: ***")
        for dias, m in encontrou_458:
            print(f"  - {dias} dias: {m}")
    else:
        print(f"\n  Nenhuma janela de 10-365 dias por peddata produz 458.")

    # ───────────────────────────────────────────────────────────
    separador("2. BUSCA EXATA POR 458 — janelas por pedprevi (previsão)")
    # ───────────────────────────────────────────────────────────
    print("  Procurando janelas por pedprevi (previsão de entrega)...\n")
    print(f"  {'dias':<6} {'bruto':>8} {'A':>6} {'A+P':>6}")
    print(f"  {'-'*6} {'-'*8} {'-'*6} {'-'*6}")
    encontrou_458 = []
    for dias in [10, 20, 30, 45, 60, 75, 90, 105, 120, 135, 150, 165, 180,
                 195, 210, 225, 240, 255, 270, 285, 300, 365]:
        r = pg.query_one(f"""
            SELECT
                COUNT(DISTINCT pedido) AS bruto,
                COUNT(DISTINCT CASE WHEN TRIM(CAST(COALESCE(pedsitua,'') AS TEXT)) = 'A' THEN pedido END) AS aprov,
                COUNT(DISTINCT CASE WHEN TRIM(CAST(COALESCE(pedsitua,'') AS TEXT)) IN ('A','P') THEN pedido END) AS ap
            FROM public.pedido
            WHERE pedprevi >= CURRENT_DATE - INTERVAL '{dias} days'
              AND pedprevi > '2000-01-01'
        """)
        if r:
            linha = f"  {dias:<6} {r['bruto']:>8} {r['aprov']:>6} {r['ap']:>6}"
            marcadores = []
            if r['bruto'] == 458: marcadores.append("bruto=458!")
            if r['aprov'] == 458: marcadores.append("A=458!")
            if r['ap'] == 458: marcadores.append("A+P=458!")
            if marcadores:
                linha += "  <-- " + " / ".join(marcadores)
                encontrou_458.append((dias, marcadores))
            print(linha)

    if not encontrou_458:
        print(f"\n  Nenhuma janela por pedprevi produz 458.")

    # ───────────────────────────────────────────────────────────
    separador("3. BUSCA POR PEDIDOS COM DATA DE PREVISÃO FUTURA")
    # ───────────────────────────────────────────────────────────
    print("  Pedidos com previsão >= hoje (ainda a entregar):\n")
    r = pg.query_one("""
        SELECT
            COUNT(DISTINCT pedido) AS n
        FROM public.pedido
        WHERE pedprevi >= CURRENT_DATE
          AND pedprevi > '2000-01-01'
    """)
    n = r['n'] if r else 0
    marker = "  <-- BATE COM 458!" if n == 458 else ""
    print(f"  Total pedidos a entregar (previsão futura): {n}{marker}\n")

    r = pg.query_one("""
        SELECT
            COUNT(DISTINCT pedido) AS n
        FROM public.pedido
        WHERE pedprevi >= CURRENT_DATE
          AND pedprevi > '2000-01-01'
          AND TRIM(CAST(COALESCE(pedsitua,'') AS TEXT)) IN ('A','P')
    """)
    n = r['n'] if r else 0
    marker = "  <-- BATE COM 458!" if n == 458 else ""
    print(f"  Pedidos a entregar E aprovados/parciais: {n}{marker}\n")

    r = pg.query_one("""
        SELECT
            COUNT(DISTINCT pedido) AS n
        FROM public.pedido
        WHERE pedprevi >= CURRENT_DATE
          AND pedprevi > '2000-01-01'
          AND TRIM(CAST(COALESCE(pedsitsit,'') AS TEXT)) NOT IN ('008','009','010')
    """)
    n = r['n'] if r else 0
    marker = "  <-- BATE COM 458!" if n == 458 else ""
    print(f"  Pedidos a entregar E não atendidos/cancelados: {n}{marker}\n")

    # ───────────────────────────────────────────────────────────
    separador("4. PEDIDOS A ENTREGAR (previsão futura) — por janela")
    # ───────────────────────────────────────────────────────────
    print(f"  {'dias_futuro':<12} {'qtd':>8}")
    print(f"  {'-'*12} {'-'*8}")
    for dias in [7, 15, 30, 45, 60, 90, 120, 150, 180, 365]:
        r = pg.query_one(f"""
            SELECT COUNT(DISTINCT pedido) AS n
            FROM public.pedido
            WHERE pedprevi >= CURRENT_DATE
              AND pedprevi <= CURRENT_DATE + INTERVAL '{dias} days'
              AND pedprevi > '2000-01-01'
              AND TRIM(CAST(COALESCE(pedsitua,'') AS TEXT)) IN ('A','P')
        """)
        n = r['n'] if r else 0
        marker = "  <-- 458!" if n == 458 else ""
        print(f"  {dias:<12} {n:>8}{marker}")

    # ═════════════════════════════════════════════════════════════
    # PARTE 2: MariaDB local (sistema de produção)
    # ═════════════════════════════════════════════════════════════
    print("\n" + "#" * 70)
    print("# PARTE 2: MariaDB local (sistema de produção)")
    print("#" * 70)

    try:
        from database.mysql_db import DatabaseMySQL
        mysql = DatabaseMySQL()
        mysql_ok = mysql.query_one("SELECT 1 AS ok")
        if not mysql_ok:
            print("MariaDB offline. Pulando parte 2.")
            return
        print("MariaDB conectado.\n")

        # Total de lotes
        separador("5. MariaDB — Total de lotes_producao")
        r = mysql.query_one("SELECT COUNT(*) AS n FROM lotes_producao")
        print(f"  Total de lotes_producao: {r['n'] if r else 0}")

        r = mysql.query_one("""
            SELECT COUNT(*) AS n
            FROM lotes_producao
            WHERE data_previsao_erp >= CURDATE() - INTERVAL 180 DAY
        """)
        n = r['n'] if r else 0
        marker = "  <-- 458!" if n == 458 else ""
        print(f"  Lotes com data_previsao_erp nos últimos 180 dias: {n}{marker}")

        r = mysql.query_one("""
            SELECT COUNT(*) AS n
            FROM lotes_producao
            WHERE data_previsao_erp >= CURDATE() - INTERVAL 180 DAY
              AND status NOT IN ('finalizado','cancelado')
        """)
        n = r['n'] if r else 0
        marker = "  <-- 458!" if n == 458 else ""
        print(f"  Lotes (180d) E status NOT IN ('finalizado','cancelado'): {n}{marker}")

        # Por status
        separador("6. MariaDB — Por status")
        rows = mysql.query("""
            SELECT status, COUNT(*) AS qtd
            FROM lotes_producao
            GROUP BY status
            ORDER BY qtd DESC
        """)
        print(f"  {'status':<25} {'qtd':>8}")
        print(f"  {'-'*25} {'-'*8}")
        for r in rows:
            marker = "  <-- 458!" if r['qtd'] == 458 else ""
            print(f"  {r['status']:<25} {r['qtd']:>8}{marker}")

        # Por status com filtro 180 dias
        separador("7. MariaDB — Por status (últimos 180 dias por data_previsao_erp)")
        rows = mysql.query("""
            SELECT status, COUNT(*) AS qtd
            FROM lotes_producao
            WHERE data_previsao_erp >= CURDATE() - INTERVAL 180 DAY
            GROUP BY status
            ORDER BY qtd DESC
        """)
        print(f"  {'status':<25} {'qtd':>8}")
        print(f"  {'-'*25} {'-'*8}")
        for r in rows:
            marker = "  <-- 458!" if r['qtd'] == 458 else ""
            print(f"  {r['status']:<25} {r['qtd']:>8}{marker}")

        # Por data_cadastro
        separador("8. MariaDB — Por data_cadastro (últimos 180 dias)")
        try:
            r = mysql.query_one("""
                SELECT COUNT(*) AS n
                FROM lotes_producao
                WHERE data_cadastro >= CURDATE() - INTERVAL 180 DAY
            """)
            n = r['n'] if r else 0
            marker = "  <-- 458!" if n == 458 else ""
            print(f"  Lotes cadastrados nos últimos 180 dias: {n}{marker}")
        except Exception as e:
            print(f"  (coluna data_cadastro não existe: {e})")

        # Cruzamento: pedidos do ERP que têm lote no MariaDB
        separador("9. CRUZAMENTO: Pedidos ERP que possuem lote no MariaDB")
        # Verificar coluna que faz o link
        cols = mysql.query("""
            SELECT column_name
            FROM information_schema.columns
            WHERE table_name = 'lotes_producao'
              AND (column_name LIKE '%pedido%' OR column_name LIKE '%erp%' OR column_name LIKE '%numero%')
        """)
        print(f"  Colunas candidatas a link com ERP em lotes_producao:")
        for c in cols:
            print(f"    - {c['column_name']}")

    except Exception as e:
        print(f"ERRO MariaDB: {e}")
        import traceback
        traceback.print_exc()

    print("\n" + "=" * 70)
    print("  FIM — cole TUDO aqui. Se 458 apareceu, ótimo!")
    print("  Se não apareceu, me responde: ONDE você vê 458?")
    print("=" * 70)


if __name__ == "__main__":
    main()
