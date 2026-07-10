#!/usr/bin/env python3
"""
Script de correcao one-shot: sincroniza lotes_producao com producoes ativas
do totem que nao foram refletidas no 5002.
Rodar no servidor: python3 scripts/fix_sync_existing.py
"""

import pymysql
from pymysql.cursors import DictCursor

MYSQL_HOST = 'localhost'
MYSQL_PORT = 3306
MYSQL_DB = 'producao_db'
MYSQL_USER = 'producao'
MYSQL_PASS = 'senha123'

def conn():
    return pymysql.connect(
        host=MYSQL_HOST, port=MYSQL_PORT, db=MYSQL_DB,
        user=MYSQL_USER, password=MYSQL_PASS,
        charset='utf8mb4', cursorclass=DictCursor,
        connect_timeout=10, autocommit=True
    )

def query(sql, params=None):
    c = conn()
    try:
        with c.cursor() as cur:
            cur.execute(sql, params or ())
            return cur.fetchall()
    finally:
        c.close()

def query_one(sql, params=None):
    c = conn()
    try:
        with c.cursor() as cur:
            cur.execute(sql, params or ())
            return cur.fetchone()
    finally:
        c.close()

def execute(sql, params=None):
    c = conn()
    try:
        with c.cursor() as cur:
            cur.execute(sql, params or ())
            return cur.rowcount
    finally:
        c.close()

def atualizar_departamento_lote(lote_ordem):
    total = query_one(
        "SELECT COUNT(DISTINCT op.departamento) as t FROM operacoes_producao op "
        "INNER JOIN ordens_fabricacao of2 ON op.of_numero = of2.of_numero "
        "WHERE of2.lote_ordem = %s AND op.departamento IS NOT NULL AND op.departamento != ''",
        (lote_ordem,)
    )
    total_setores = int(total['t'] or 0) if total else 0

    primeira = query_one(
        "SELECT op.departamento, op.sequencia FROM operacoes_producao op "
        "INNER JOIN ordens_fabricacao of2 ON op.of_numero = of2.of_numero "
        "WHERE of2.lote_ordem = %s AND op.status != 'concluido' "
        "ORDER BY op.sequencia ASC LIMIT 1",
        (lote_ordem,)
    )
    dept = primeira['departamento'] if primeira else None
    seq = int(primeira['sequencia']) if primeira else 0

    execute(
        "UPDATE lotes_producao "
        "SET departamento_atual = %s, setor_atual_seq = %s, total_setores = %s "
        "WHERE ordem = %s",
        (dept, seq, total_setores, lote_ordem)
    )
    return dept

def main():
    print("=== Correcao de Sync: Totem -> PCP ===")
    print()

    # 1. Busca todas as producoes ativas no totem
    ativas = query(
        "SELECT DISTINCT lote, of_numero, setor FROM serralheria_producao WHERE status = 'em_producao'"
    )
    print(f"Producoes ativas no totem: {len(ativas)}")

    lotes_atualizados = set()
    for a in ativas:
        lote_cod = a['lote']
        of_num = a['of_numero']
        setor = a['setor']

        setor_map = {
            'CORTE': 'CORTE', 'DOBRA': 'DOBRA', 'SOLDA': 'SOLDA',
            'ACABAMENTO': 'ACABAMENTO', 'FUNILARIA': 'FUNILARIA',
            'PINTURA': 'PINTURA', 'MONTAGEM': 'MONTAGEM',
        }
        dept = setor_map.get(setor, setor)

        rows = execute(
            "UPDATE operacoes_producao SET status = 'em_andamento', data_inicio = COALESCE(data_inicio, NOW()) "
            "WHERE of_numero = %s AND departamento = %s AND status != 'concluido'",
            (of_num, dept)
        )
        if rows > 0:
            print(f"  OF {of_num}: {dept} -> em_andamento ({rows} row(s))")

        execute(
            "UPDATE kanban_cards SET etapa = 'em_producao', atualizado_em = NOW() "
            "WHERE of_numero = %s AND departamento = %s AND etapa != 'concluido'",
            (of_num, dept)
        )

        of_row = query_one(
            "SELECT lote_ordem FROM ordens_fabricacao WHERE of_numero = %s LIMIT 1",
            (of_num,)
        )
        if of_row and of_row.get('lote_ordem'):
            lote_ordem = of_row['lote_ordem']
            r = execute(
                "UPDATE lotes_producao SET status = 'em_producao' "
                "WHERE ordem = %s AND status = 'liberado'",
                (lote_ordem,)
            )
            if r > 0:
                print(f"  Lote {lote_cod} (ordem {lote_ordem}): liberado -> em_producao")
            lotes_atualizados.add(lote_ordem)

    # 2. Recalcula departamento_atual
    print()
    print("Recalculando departamento_atual...")
    for lote_ordem in lotes_atualizados:
        dept = atualizar_departamento_lote(lote_ordem)
        lote = query_one("SELECT lote_codigo FROM lotes_producao WHERE ordem = %s", (lote_ordem,))
        cod = lote['lote_codigo'] if lote else lote_ordem
        print(f"  Lote {cod}: departamento_atual = {dept or 'TODAS CONCLUIDAS'}")

    # 3. Verificacao geral
    print()
    print("Verificacao geral de lotes em_producao...")
    todos_lotes = query("SELECT ordem, lote_codigo FROM lotes_producao WHERE status = 'em_producao'")
    for l in todos_lotes:
        if l['ordem'] not in lotes_atualizados:
            dept = atualizar_departamento_lote(l['ordem'])
            print(f"  Lote {l['lote_codigo']}: dept_atual = {dept or 'TODAS CONCLUIDAS'}")

    print()
    print("=== Correcao concluida! ===")

if __name__ == '__main__':
    main()