#!/usr/bin/env python3
"""
Serralheria Totem - App Flask na porta 5003
Dados do MariaDB (sistema :5002) - PCP classifica/libera, totem apenas consulta.
Auto-login, 4 telas touch:
  S0: Dashboard KPIs + lotes ativos + producoes
  S1: Lista de lotes liberados/em producao
  S2: Pecas (OFs filhas) de um lote com selecao por setor
  S3: Selecao de operador (serra1-serra9)
"""

import os
import re
import json
import logging
import time
import threading
from decimal import Decimal
from flask import Flask, jsonify, request, render_template
import pymysql
import psycopg2
from pymysql.cursors import DictCursor

# ── Config ────────────────────────────────────────────────────────────
MYSQL_HOST = 'localhost'
MYSQL_PORT = 3306
MYSQL_DB = 'producao_db'
MYSQL_USER = 'producao'
MYSQL_PASS = 'senha123'

# PostgreSQL config (same as config/config.py)
PG_HOST = os.environ.get('PG_HOST', '192.168.1.17')
PG_PORT = int(os.environ.get('PG_PORT', '5432'))
PG_DB   = os.environ.get('PG_DATABASE', 'salutem')
PG_USER = os.environ.get('PG_USERNAME', 'postgres')
PG_PASS = os.environ.get('PG_PASSWORD', 'postgres')

# In-memory cache for product names (loaded from PostgreSQL produto.pronome)
_produto_cache = {}

# Set of lote_codigo ativos (loaded from MariaDB, no ERP needed)
_lotes_ativos = set()

# Setores que aparecem no totem da serralheria
SETORES_SERRALHERIA = ('CORTE', 'DOBRA', 'SOLDA', 'ACABAMENTO')

# Mapeamento de setores ERP -> Sistema Local (mesmo do app.py)
MAPEAMENTO_SETORES = {
    'ALMOXARIFADO': 'ALMOXARIFADO',
    'SERRALHERIA':  'CORTE',
    'FUNILARIA':    'FUNILARIA',
    'PINTURA':      'PINTURA',
    'POLIMENTO':    'ACABAMENTO',
    'MARCENARIA':   'MARCENARIA',
    'COSTURA':      'COSTURA',
    'TAPECARIA':    'TAPECARIA',
    'MONTAGEM':     'MONTAGEM',
    'EMBALAGEM':    'EMBALAGEM',
    'USINAGEM':     'USINAGEM',
    'EXPEDIÇÃO':    'EXPEDIÇÃO',
    'EXPEDICAO':    'EXPEDIÇÃO',
}

app = Flask(__name__, template_folder='templates/serralheria', static_folder='static')
app.logger.setLevel(logging.INFO)
_log_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'totem_5003.log')
_fh = logging.FileHandler(_log_path)
_fh.setFormatter(logging.Formatter('%(asctime)s %(levelname)s %(message)s'))
app.logger.addHandler(_fh)

# ── MariaDB helpers ──────────────────────────────────────────────────

def _conn():
    return pymysql.connect(
        host=MYSQL_HOST, port=MYSQL_PORT, db=MYSQL_DB,
        user=MYSQL_USER, password=MYSQL_PASS,
        charset='utf8mb4', cursorclass=DictCursor,
        connect_timeout=10, autocommit=True
    )

def db_query(sql, params=None):
    conn = _conn()
    try:
        with conn.cursor() as cur:
            cur.execute(sql, params or ())
            return cur.fetchall()
    finally:
        conn.close()

def db_query_one(sql, params=None):
    conn = _conn()
    try:
        with conn.cursor() as cur:
            cur.execute(sql, params or ())
            return cur.fetchone()
    finally:
        conn.close()

def db_execute(sql, params=None):
    conn = _conn()
    try:
        with conn.cursor() as cur:
            cur.execute(sql, params or ())
            return cur.lastrowid or cur.rowcount
    finally:
        conn.close()

# ── Helpers ───────────────────────────────────────────────────────────

def _int(val):
    """Safely convert to int (handles Decimal, None, str)."""
    if val is None:
        return 0
    return int(float(val))

def _str(val):
    """Safely convert to stripped string."""
    if val is None:
        return ''
    return str(val).strip()

def _is_sob_medida(codigo):
    """Verifica se o produto codigo termina com -X (sob medida)."""
    if not codigo:
        return False
    c = str(codigo).strip().upper()
    return c.endswith('-X')

def _extract_s_code(codigo_produto):
    """Extract S-XXXX from strings like 'PRODUCAO DE S-0240'."""
    if not codigo_produto:
        return ''
    m = re.search(r'S-\d+', str(codigo_produto))
    return m.group(0) if m else str(codigo_produto).strip()


# ── Produto name cache (from MariaDB) ──────────────────────────────

def _get_produto_nome(codigo_produto):
    """Get real product name from in-memory cache (PostgreSQL produto.pronome)."""
    if not codigo_produto:
        return ''
    key = str(codigo_produto).strip()
    return _produto_cache.get(key, '')


def _pg_query_one(sql, params=None):
    """Query PostgreSQL and return one row as dict."""
    conn = psycopg2.connect(host=PG_HOST, port=PG_PORT, dbname=PG_DB,
                            user=PG_USER, password=PG_PASS, connect_timeout=5)
    conn.autocommit = True
    try:
        with conn.cursor() as cur:
            cur.execute(sql, params or ())
            cols = [d[0] for d in cur.description] if cur.description else []
            row = cur.fetchone()
            if row:
                return dict(zip(cols, row))
            return None
    finally:
        conn.close()


def _load_produto_cache():
    """Load product names from PostgreSQL produto.pronome + MariaDB fallback."""
    global _produto_cache
    _produto_cache = {}
    # 1) PostgreSQL: tabela produto (pronome real)
    try:
        conn = psycopg2.connect(host=PG_HOST, port=PG_PORT, dbname=PG_DB,
                                user=PG_USER, password=PG_PASS, connect_timeout=5)
        conn.autocommit = True
        try:
            with conn.cursor() as cur:
                cur.execute("SELECT produto, pronome FROM public.produto WHERE produto IS NOT NULL AND pronome IS NOT NULL")
                cols = [d[0] for d in cur.description]
                for row in cur.fetchall():
                    r = dict(zip(cols, row))
                    cod = str(r.get('produto', '')).strip()
                    nome = str(r.get('pronome', '')).strip()
                    if cod and nome:
                        _produto_cache[cod] = nome[:200]
                print('[OK] Cache de produtos (PostgreSQL): %d' % len(_produto_cache))
        finally:
            conn.close()
    except Exception as e:
        print('[WARN] Cache PostgreSQL falhou: %s' % e)
    # 2) Fallback MariaDB: lotes_producao (preenche codigos que o PG nao tem)
    try:
        rows = db_query(
            "SELECT codigo_produto, descricao_produto FROM lotes_producao "
            "WHERE codigo_produto IS NOT NULL AND descricao_produto IS NOT NULL"
        )
        added = 0
        for r in rows:
            cod = str(r.get('codigo_produto', '')).strip()
            nome = str(r.get('descricao_produto', '')).strip()
            if cod and cod not in _produto_cache and nome:
                _produto_cache[cod] = nome[:200]
                added += 1
        print('[OK] Cache produtos (MariaDB fallback): +%d' % added)
    except Exception as e:
        print('[WARN] Cache MariaDB falhou: %s' % e)


# ── Lotes ativos (from MariaDB, no ERP) ────────────────────────────

def _refresh_lotes_ativos():
    """Carrega lotes ativos do MariaDB (liberado, em_producao, pausado)."""
    global _lotes_ativos
    try:
        rows = db_query(
            "SELECT DISTINCT lote_codigo FROM lotes_producao "
            "WHERE status IN ('liberado','em_producao','pausado')"
        )
        _lotes_ativos = set()
        for r in rows:
            if r.get('lote_codigo'):
                _lotes_ativos.add(str(r['lote_codigo']).strip())
        print('[OK] Lotes ativos: %d (MariaDB)' % len(_lotes_ativos))
    except Exception as e:
        print('[WARN] Lotes ativos falhou: %s' % e)


def _build_lotes_filter():
    """Retorna (where_clause, join_clause, params) para filtrar lotes ativos."""
    if _lotes_ativos:
        ph = ','.join(['%s'] * len(_lotes_ativos))
        where = 'WHERE lote_codigo IN (' + ph + ')'
        join = ' AND lp.lote_codigo IN (' + ph + ')'
        params = tuple(_lotes_ativos)
    else:
        where = 'WHERE 1=0'
        join = ' AND 1=0'
        params = ()
    return where, join, params


def init_db():
    """Create serralheria tables if not exist, seed serra1-9."""
    db_execute("""
        CREATE TABLE IF NOT EXISTS serralheria_usuarios (
            id INT AUTO_INCREMENT PRIMARY KEY,
            nome VARCHAR(100) NOT NULL,
            setor VARCHAR(100) DEFAULT 'Serralheria',
            ativo TINYINT(1) DEFAULT 1
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
    """)
    db_execute("""
        CREATE TABLE IF NOT EXISTS serralheria_producao (
            id INT AUTO_INCREMENT PRIMARY KEY,
            ordem_id INT DEFAULT NULL,
            lote VARCHAR(50) NOT NULL,
            produto VARCHAR(50) NOT NULL,
            of_numero INT DEFAULT NULL,
            usuario_id INT DEFAULT NULL,
            usuario_nome VARCHAR(100) DEFAULT NULL,
            setor VARCHAR(50) DEFAULT '',
            status VARCHAR(20) DEFAULT 'em_producao',
            data_inicio DATETIME DEFAULT NULL,
            data_fim DATETIME DEFAULT NULL,
            qtd_produzida INT DEFAULT NULL,
            INDEX idx_sp_lote (lote),
            INDEX idx_sp_status (status)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
    """)
    # Garante coluna qtd_produzida existe (tabelas criadas antes)
    try:
        db_execute("ALTER TABLE serralheria_producao ADD COLUMN qtd_produzida INT DEFAULT 0")
        print('[OK] Coluna qtd_produzida adicionada')
    except Exception as e:
        if 'Duplicate column' in str(e):
            print('[OK] Coluna qtd_produzida ja existe')
        else:
            print('[ERRO] Falha ao adicionar qtd_produzida: %s' % e)

    # Seed serra1-9 — DESABILITADO: operadores agora gerenciados pelo admin (5002)
    # for i in range(1, 10):
    #     nome = 'serra' + str(i)
    #     existing = db_query_one("SELECT id FROM serralheria_usuarios WHERE nome = %s", (nome,))
    #     if not existing:
    #         db_execute(
    #             "INSERT INTO serralheria_usuarios (nome, setor, ativo) VALUES (%s, 'Serralheria', 1)",
    #             (nome,)
    #         )
    # Cleanup: remove qualquer usuario serra* restante
    try:
        db_execute("DELETE FROM serralheria_usuarios WHERE nome LIKE 'serra%' OR nome LIKE 'serral%'")
    except Exception:
        pass
    # Migration: add missing columns if table already existed
    for col, col_def in [
        ('setor', "VARCHAR(50) DEFAULT ''"),
        ('of_numero', 'INT DEFAULT NULL'),
        ('ordem_id', 'INT DEFAULT NULL'),
    ]:
        try:
            db_query_one('SELECT ' + col + ' FROM serralheria_producao LIMIT 1')
        except Exception:
            db_execute('ALTER TABLE serralheria_producao ADD COLUMN ' + col + ' ' + col_def)

    _load_produto_cache()
    _refresh_lotes_ativos()
    print('[OK] Tabelas serralheria verificadas no MariaDB')


# ── Rotas ────────────────────────────────────────────────────────────

@app.route('/')
def index():
    return render_template('dashboard.html')


@app.route('/api/kpis')
def api_kpis():
    """KPIs da serralheria: lotes ativos, pecas, total qtd, producoes."""
    try:
        lwhere, ljoin, lparams = _build_lotes_filter()

        total_lotes = _int(db_query_one(
            'SELECT COUNT(*) as t FROM lotes_producao ' + lwhere,
            lparams
        )['t'])

        total_pecas = _int(db_query_one(
            "SELECT COUNT(*) as t "
            "FROM ordens_fabricacao of2 "
            "INNER JOIN lotes_producao lp ON of2.lote_ordem = lp.ordem "
            "WHERE of2.tipo = 'filho' " + ljoin,
            lparams
        )['t'])

        total_qtd = _int(db_query_one(
            'SELECT COALESCE(SUM(qtde_ordem), 0) as t FROM lotes_producao ' + lwhere,
            lparams
        )['t'])

        em_andamento = _int(db_query_one(
            "SELECT COUNT(*) as t FROM serralheria_producao WHERE status = 'em_producao'"
        )['t'])

        hoje = _int(db_query_one(
            "SELECT COUNT(*) as t FROM serralheria_producao WHERE DATE(data_inicio) = CURDATE()"
        )['t'])

        return jsonify({
            'total_lotes': total_lotes,
            'total_pecas': total_pecas,
            'total_qtd': total_qtd,
            'em_andamento': em_andamento,
            'hoje': hoje
        })
    except Exception as e:
        app.logger.error('Erro KPIs: %s', e)
        return jsonify({'error': str(e)}), 500


@app.route('/api/dashboard')
def api_dashboard():
    """Dados completos para dashboard: KPIs + producoes ativas + lotes."""
    try:
        lwhere, ljoin, lparams = _build_lotes_filter()

        # ── KPIs ──
        total_lotes = _int(db_query_one(
            'SELECT COUNT(*) as t FROM lotes_producao ' + lwhere,
            lparams
        )['t'])

        total_pecas = _int(db_query_one(
            "SELECT COUNT(*) as t "
            "FROM ordens_fabricacao of2 "
            "INNER JOIN lotes_producao lp ON of2.lote_ordem = lp.ordem "
            "WHERE of2.tipo = 'filho' " + ljoin,
            lparams
        )['t'])

        total_qtd = _int(db_query_one(
            'SELECT COALESCE(SUM(qtde_ordem), 0) as t FROM lotes_producao ' + lwhere,
            lparams
        )['t'])

        em_andamento = _int(db_query_one(
            "SELECT COUNT(*) as t FROM serralheria_producao WHERE status = 'em_producao' AND setor IN %s",
            (SETORES_SERRALHERIA,)
        )['t'])

        hoje = _int(db_query_one(
            "SELECT COUNT(*) as t FROM serralheria_producao WHERE DATE(data_inicio) = CURDATE() AND setor IN %s",
            (SETORES_SERRALHERIA,)
        )['t'])

        finalizadas_hoje = _int(db_query_one(
            "SELECT COUNT(*) as t FROM serralheria_producao "
            "WHERE status = 'finalizado' AND DATE(data_fim) = CURDATE() AND setor IN %s",
            (SETORES_SERRALHERIA,)
        )['t'])

        # ── Producoes ativas com detalhes ──
        ativos = db_query("""
            SELECT sp.id, sp.lote, sp.produto, sp.usuario_nome, sp.data_inicio, sp.setor,
                   of2.qtde_ordem
            FROM serralheria_producao sp
            LEFT JOIN ordens_fabricacao of2 ON sp.of_numero = of2.of_numero
            WHERE sp.status = 'em_producao' AND sp.setor IN %s
            ORDER BY sp.data_inicio DESC
        """, (SETORES_SERRALHERIA,))
        for a in ativos:
            r = db_query_one(
                "SELECT descricao_produto FROM lotes_producao WHERE lote_codigo = %s",
                (a['lote'],)
            )
            a['lote_desc'] = _str(r['descricao_produto']) if r else ''

            # produto = codigo_produto (ex: PP-0021), busca nome real
            nome_real = _get_produto_nome(a['produto'])
            if not nome_real and a['produto']:
                # Fallback: consulta direta ao PG se cache falhou
                try:
                    pg_row = _pg_query_one(
                        "SELECT pronome FROM public.produto WHERE TRIM(produto) = %s LIMIT 1",
                        (a['produto'].strip(),)
                    )
                    if pg_row and pg_row.get('pronome'):
                        nome_real = str(pg_row['pronome']).strip()[:200]
                        _produto_cache[a['produto'].strip()] = nome_real
                except Exception:
                    pass
            if not nome_real:
                # Fallback MariaDB: descricao_produto da OF filha
                r = db_query_one(
                    "SELECT descricao_produto FROM ordens_fabricacao WHERE codigo_produto = %s AND tipo = 'filho' LIMIT 1",
                    (a['produto'],)
                )
                nome_real = _str(r['descricao_produto']) if r else ''
            a['produto_nome'] = nome_real if nome_real else _str(a['produto'])

            r = db_query_one(
                "SELECT COUNT(*) as t FROM serralheria_producao "
                "WHERE lote = %s AND usuario_nome = %s AND status = 'em_producao'",
                (a['lote'], a['usuario_nome'])
            )
            a['pecas_count'] = _int(r['t']) if r else 0

        # ── Lotes ativos com detalhes ──
        lotes_raw = []
        if _lotes_ativos:
            ph = ','.join(['%s'] * len(_lotes_ativos))
            lotes_raw = db_query(
                "SELECT ordem, lote_codigo, descricao_produto, status, "
                "codigo_produto, qtde_ordem "
                "FROM lotes_producao WHERE lote_codigo IN (" + ph + ") "
                "ORDER BY lote_codigo DESC",
                tuple(_lotes_ativos)
            )

        lotes = []
        for lp in lotes_raw:
            ofs = db_query_one("""
                SELECT COUNT(*) as qtd_pecas, COALESCE(SUM(qtde_ordem), 0) as qtd_total
                FROM ordens_fabricacao
                WHERE lote_ordem = %s AND tipo = 'filho'
            """, (lp['ordem'],))

            pai = db_query_one("""
                SELECT codigo_produto, descricao_produto, qtde_ordem
                FROM ordens_fabricacao
                WHERE lote_ordem = %s AND tipo = 'pai'
                LIMIT 1
            """, (lp['ordem'],))
            if not pai:
                pai = db_query_one("""
                    SELECT codigo_produto, descricao_produto, qtde_ordem
                    FROM ordens_fabricacao WHERE lote_ordem = %s LIMIT 1
                """, (lp['ordem'],))

            s_code = _extract_s_code(lp['codigo_produto'])

            # Busca pecas filhas para exibir codigos + nomes reais
            filhas = db_query(
                "SELECT codigo_produto FROM ordens_fabricacao "
                "WHERE lote_ordem = %s AND tipo = 'filho' ORDER BY codigo_produto",
                (lp['ordem'],)
            )
            filhas_codigos = [_str(f['codigo_produto']) for f in filhas if _str(f['codigo_produto'])]

            if pai:
                qtd_final = _int(pai['qtde_ordem'])
                produto_final = _str(pai['codigo_produto']) or s_code
                produto_nome = _get_produto_nome(produto_final) or _str(lp['descricao_produto'])
            else:
                qtd_final = _int(lp['qtde_ordem'])
                produto_final = s_code
                produto_nome = _str(lp['descricao_produto'])

            # Texto com codigos das pecas e nome real da primeira
            pecas_texto = ', '.join(filhas_codigos[:4])
            if len(filhas_codigos) > 4:
                pecas_texto += '... (+' + str(len(filhas_codigos) - 4) + ')'
            peca_nome1 = _get_produto_nome(filhas_codigos[0]) if filhas_codigos else ''

            prod = db_query_one(
                "SELECT status, usuario_nome FROM serralheria_producao "
                "WHERE lote = %s AND status = 'em_producao' LIMIT 1",
                (lp['lote_codigo'],)
            )

            lotes.append({
                'lotcod': lp['lote_codigo'],
                'ordem': lp['ordem'],
                'descricao': _str(lp['descricao_produto'])[:49],
                'status': lp['status'],
                'produto_final': produto_final,
                'produto_nome': produto_nome,
                'pecas_codigos': pecas_texto,
                'peca_nome1': peca_nome1,
                'qtd_produto_final': qtd_final,
                'qtd_pecas': _int(ofs['qtd_pecas']) if ofs else 0,
                'qtd_total': _int(ofs['qtd_total']) if ofs else 0,
                'status_producao': prod['status'] if prod else None,
                'operador': prod['usuario_nome'] if prod else None,
                'sob_medida': _is_sob_medida(produto_final) or _is_sob_medida(lp.get('lote_codigo')),
            })

        return jsonify({
            'total_lotes': total_lotes,
            'total_pecas': total_pecas,
            'total_qtd': total_qtd,
            'em_andamento': em_andamento,
            'hoje': hoje,
            'finalizadas_hoje': finalizadas_hoje,
            'ativos': ativos,
            'lotes': lotes,
        })
    except Exception as e:
        app.logger.error('Erro Dashboard: %s', e)
        return jsonify({'error': str(e)}), 500


@app.route('/api/lotes')
def api_lotes():
    """Lotes liberados/em producao com detalhes das OFs filhas."""
    try:
        lotes_raw = []
        if _lotes_ativos:
            ph = ','.join(['%s'] * len(_lotes_ativos))
            lotes_raw = db_query(
                "SELECT ordem, lote_codigo, descricao_produto, status, "
                "codigo_produto, qtde_ordem "
                "FROM lotes_producao WHERE lote_codigo IN (" + ph + ") "
                "ORDER BY lote_codigo DESC",
                tuple(_lotes_ativos)
            )

        lotes = []
        for lp in lotes_raw:
            ofs = db_query_one("""
                SELECT COUNT(*) as qtd_pecas, COALESCE(SUM(qtde_ordem), 0) as qtd_total
                FROM ordens_fabricacao WHERE lote_ordem = %s AND tipo = 'filho'
            """, (lp['ordem'],))

            pai = db_query_one("""
                SELECT codigo_produto, descricao_produto, qtde_ordem
                FROM ordens_fabricacao WHERE lote_ordem = %s AND tipo = 'pai' LIMIT 1
            """, (lp['ordem'],))
            if not pai:
                pai = db_query_one("""
                    SELECT codigo_produto, descricao_produto, qtde_ordem
                    FROM ordens_fabricacao WHERE lote_ordem = %s LIMIT 1
                """, (lp['ordem'],))

            s_code = _extract_s_code(lp['codigo_produto'])

            # Busca pecas filhas
            filhas = db_query(
                "SELECT codigo_produto FROM ordens_fabricacao "
                "WHERE lote_ordem = %s AND tipo = 'filho' ORDER BY codigo_produto",
                (lp['ordem'],)
            )
            filhas_codigos = [_str(f['codigo_produto']) for f in filhas if _str(f['codigo_produto'])]

            if pai:
                qtd_final = _int(pai['qtde_ordem'])
                produto_final = _str(pai['codigo_produto']) or s_code
                produto_nome = _get_produto_nome(produto_final) or _str(lp['descricao_produto'])
            else:
                qtd_final = _int(lp['qtde_ordem'])
                produto_final = s_code
                produto_nome = _str(lp['descricao_produto'])

            pecas_texto = ', '.join(filhas_codigos[:4])
            if len(filhas_codigos) > 4:
                pecas_texto += '... (+' + str(len(filhas_codigos) - 4) + ')'
            peca_nome1 = _get_produto_nome(filhas_codigos[0]) if filhas_codigos else ''

            prod = db_query_one(
                "SELECT status, usuario_nome FROM serralheria_producao "
                "WHERE lote = %s AND status = 'em_producao' LIMIT 1",
                (lp['lote_codigo'],)
            )

            lotes.append({
                'lotcod': lp['lote_codigo'],
                'ordem': lp['ordem'],
                'descricao': _str(lp['descricao_produto'])[:49],
                'status': lp['status'],
                'produto_final': produto_final,
                'produto_nome': produto_nome,
                'pecas_codigos': pecas_texto,
                'peca_nome1': peca_nome1,
                'qtd_produto_final': qtd_final,
                'qtd_pecas': _int(ofs['qtd_pecas']) if ofs else 0,
                'qtd_total': _int(ofs['qtd_total']) if ofs else 0,
                'status_producao': prod['status'] if prod else None,
                'operador': prod['usuario_nome'] if prod else None,
                'sob_medida': _is_sob_medida(produto_final) or _is_sob_medida(lp.get('lote_codigo')),
            })

        return jsonify({'lotes': lotes})
    except Exception as e:
        app.logger.error('Erro lotes: %s', e)
        return jsonify({'error': str(e)}), 500


@app.route('/api/lotes/<lotcod>/pecas')
def api_pecas(lotcod):
    """Pecas (OFs filhas) de um lote com operacoes por setor."""
    try:
        lote = db_query_one(
            "SELECT ordem, lote_codigo, descricao_produto, qtde_ordem "
            "FROM lotes_producao WHERE lote_codigo = %s",
            (lotcod,)
        )
        if not lote:
            return jsonify({'error': 'Lote nao encontrado'}), 404

        pecas = db_query("""
            SELECT of.of_numero, of.codigo_produto as codigo, of.descricao_produto as descricao,
                   of.qtde_ordem as quantidade, of.tipo
            FROM ordens_fabricacao of
            WHERE of.lote_ordem = %s AND of.tipo = 'filho'
            ORDER BY of.codigo_produto
        """, (lote['ordem'],))

        pai = db_query_one("""
            SELECT codigo_produto, descricao_produto, qtde_ordem
            FROM ordens_fabricacao WHERE lote_ordem = %s AND tipo = 'pai' LIMIT 1
        """, (lote['ordem'],))

        produto_final = None
        if pai:
            pai_nome = _get_produto_nome(pai.get('codigo_produto'))
            produto_final = {
                'codigo': _str(pai['codigo_produto']),
                'descricao': pai_nome or _str(pai['descricao_produto']),
                'quantidade': _int(pai['qtde_ordem']),
            }

        pecas_result = []
        for p in pecas:
            ops = db_query("""
                SELECT id, departamento, descricao_operacao, status, sequencia
                FROM operacoes_producao
                WHERE of_numero = %s
                ORDER BY sequencia
            """, (p['of_numero'],))

            setores = list(set(
                op['departamento'] for op in ops
                if op.get('departamento') and op['departamento'] in SETORES_SERRALHERIA
            ))

            peca_cod = str(p.get('codigo', '')).strip()
            nome_real = _get_produto_nome(peca_cod)
            # Fallback: consulta direta ao PG se cache falhou
            if not nome_real and peca_cod:
                try:
                    pg_row = _pg_query_one(
                        "SELECT pronome FROM public.produto WHERE TRIM(produto) = %s LIMIT 1",
                        (peca_cod,)
                    )
                    if pg_row and pg_row.get('pronome'):
                        nome_real = str(pg_row['pronome']).strip()[:200]
                        _produto_cache[peca_cod] = nome_real
                except Exception:
                    pass
            produto_nome = nome_real if nome_real else _str(p['descricao'])

            pecas_result.append({
                'of_numero': p['of_numero'],
                'ordem': p['of_numero'],
                'codigo': _str(p['codigo']),
                'quantidade': _int(p['quantidade']),
                'produto_nome': produto_nome,
                'setores': setores,
                'operacoes': ops,
            })

        ativas_raw = db_query(
            "SELECT produto, of_numero, setor, usuario_nome, qtd_produzida "
            "FROM serralheria_producao WHERE lote = %s AND status = 'em_producao' AND setor IN %s",
            (lotcod, SETORES_SERRALHERIA)
        )
        pecas_ativas = {}
        for row in ativas_raw:
            peca = row['produto']
            if peca not in pecas_ativas:
                pecas_ativas[peca] = []
            pecas_ativas[peca].append({
                'setor': row['setor'],
                'usuario': row['usuario_nome'],
                'qtd_produzida': _int(row.get('qtd_produzida')),
            })

        return jsonify({
            'lote': lotcod,
            'descricao': _str(lote['descricao_produto']),
            'produto_final': produto_final,
            'pecas': pecas_result,
            'pecas_ativas': pecas_ativas,
        })
    except Exception as e:
        app.logger.error('Erro pecas: %s', e)
        return jsonify({'error': str(e)}), 500


@app.route('/api/usuarios')
def api_usuarios():
    """Lista usuarios ativos da serralheria (serra1-serra9)."""
    try:
        usuarios = db_query(
            "SELECT MIN(id) as id, nome, MAX(setor) as setor "
            "FROM serralheria_usuarios WHERE ativo = 1 GROUP BY nome ORDER BY nome"
        )
        return jsonify({'usuarios': usuarios})
    except Exception as e:
        app.logger.error('Erro usuarios: %s', e)
        return jsonify({'error': str(e)}), 500


@app.route('/api/iniciar', methods=['POST'])
def api_iniciar():
    """Iniciar producao: salva no MariaDB e sincroniza operacoes_producao + kanban."""
    try:
        data = request.get_json()
        lotcod = data.get('lote')
        usuario_id = data.get('usuario_id')
        usuario_nome = data.get('usuario_nome')
        setor = data.get('setor', '')
        pecas = data.get('pecas', [])

        if not lotcod or not usuario_id:
            return jsonify({'error': 'Dados obrigatorios: lote, usuario_id'}), 400

        # Mapeia setor totem -> departamento operacoes_producao
        setor_para_dept = {
            'CORTE': 'CORTE', 'DOBRA': 'DOBRA', 'SOLDA': 'SOLDA',
            'ACABAMENTO': 'ACABAMENTO', 'MONTAGEM': 'MONTAGEM',
            'FUNILARIA': 'FUNILARIA', 'PINTURA': 'PINTURA',
        }
        dept = setor_para_dept.get(setor, setor)

        for peca in pecas:
            db_execute(
                "INSERT INTO serralheria_producao "
                "(ordem_id, lote, produto, of_numero, usuario_id, usuario_nome, setor, status, data_inicio) "
                "VALUES (%s, %s, %s, %s, %s, %s, %s, 'em_producao', NOW())",
                (peca.get('ordem'), lotcod, peca['codigo'], peca.get('ordem'),
                 usuario_id, usuario_nome, setor)
            )
            # Sincroniza operacoes_producao -> em_andamento
            _sync_op_status(peca.get('ordem'), dept, 'em_andamento')

        app.logger.info(
            'Producao iniciada: lote=%s usuario=%s setor=%s pecas=%d',
            lotcod, usuario_nome, setor, len(pecas)
        )
        return jsonify({'success': True, 'mensagem': 'Producao iniciada!'})
    except Exception as e:
        app.logger.error('Erro iniciar: %s', e)
        return jsonify({'error': str(e)}), 500


def _atualizar_departamento_lote(lote_ordem):
    """Recalcula departamento_atual, setor_atual_seq e total_setores de um lote.
    Replica a logica de mysql_db.atualizar_departamento_atual para o totem."""
    if not lote_ordem:
        return
    # Total de departamentos unicos do lote
    total = db_query_one(
        "SELECT COUNT(DISTINCT op.departamento) as t FROM operacoes_producao op "
        "INNER JOIN ordens_fabricacao of2 ON op.of_numero = of2.of_numero "
        "WHERE of2.lote_ordem = %s AND op.departamento IS NOT NULL AND op.departamento != ''",
        (lote_ordem,)
    )
    total_setores = int(total['t'] or 0) if total else 0

    # Primeira operacao pendente (nao concluida) por sequencia
    primeira = db_query_one(
        "SELECT op.departamento, op.sequencia FROM operacoes_producao op "
        "INNER JOIN ordens_fabricacao of2 ON op.of_numero = of2.of_numero "
        "WHERE of2.lote_ordem = %s AND op.status != 'concluido' "
        "ORDER BY op.sequencia ASC LIMIT 1",
        (lote_ordem,)
    )
    dept = primeira['departamento'] if primeira else None
    seq = int(primeira['sequencia']) if primeira else 0

    db_execute(
        "UPDATE lotes_producao "
        "SET departamento_atual = %s, setor_atual_seq = %s, total_setores = %s "
        "WHERE ordem = %s",
        (dept, seq, total_setores, lote_ordem)
    )


def _sync_lote_status(of_numero, novo_status):
    """Atualiza status do lote em lotes_producao conforme operacoes."""
    if not of_numero:
        return
    of_row = db_query_one(
        "SELECT lote_ordem FROM ordens_fabricacao WHERE of_numero = %s LIMIT 1",
        (of_numero,)
    )
    if not of_row or not of_row.get('lote_ordem'):
        return
    lote_ordem = of_row['lote_ordem']

    if novo_status == 'em_andamento':
        # Muda status do lote para em_producao se ainda estiver liberado
        db_execute(
            "UPDATE lotes_producao SET status = 'em_producao' "
            "WHERE ordem = %s AND status = 'liberado'",
            (lote_ordem,)
        )
    elif novo_status == 'concluido':
        # Verifica se TODAS as ops do lote estao concluidas
        total_pend = db_query_one(
            "SELECT COUNT(*) as t FROM operacoes_producao op "
            "INNER JOIN ordens_fabricacao of2 ON op.of_numero = of2.of_numero "
            "WHERE of2.lote_ordem = %s AND op.status != 'concluido'",
            (lote_ordem,)
        )
        if total_pend and int(total_pend['t']) == 0:
            db_execute(
                "UPDATE lotes_producao SET status = 'finalizado' WHERE ordem = %s AND status != 'finalizado'",
                (lote_ordem,)
            )


def _sync_op_status(of_numero, departamento, novo_status):
    """Sincroniza operacoes_producao, kanban_cards e lotes_producao quando totem inicia/finaliza."""
    if not of_numero or not departamento:
        return
    try:
        # 1. Atualiza operacoes_producao
        db_execute(
            "UPDATE operacoes_producao SET status = %s, data_inicio = COALESCE(data_inicio, NOW()), "
            "data_fim = CASE WHEN %s = 'concluido' THEN NOW() ELSE data_fim END "
            "WHERE of_numero = %s AND departamento = %s AND status != 'concluido'",
            (novo_status, novo_status, of_numero, departamento)
        )
        # 2. Atualiza kanban_cards
        etapa_map = {'em_andamento': 'em_producao', 'concluido': 'concluido', 'pendente': 'aguardando'}
        nova_etapa = etapa_map.get(novo_status)
        if nova_etapa:
            db_execute(
                "UPDATE kanban_cards SET etapa = %s, atualizado_em = NOW() "
                "WHERE of_numero = %s AND departamento = %s AND etapa != 'concluido'",
                (nova_etapa, of_numero, departamento)
            )
        # 3. Sincroniza lotes_producao (status + departamento_atual)
        _sync_lote_status(of_numero, novo_status)
        _atualizar_departamento_lote_from_of(of_numero)
    except Exception as e:
        app.logger.warning('Sync op status falhou: %s', e)


def _atualizar_departamento_lote_from_of(of_numero):
    """Recalcula departamento_atual do lote a partir de uma OF."""
    if not of_numero:
        return
    of_row = db_query_one(
        "SELECT lote_ordem FROM ordens_fabricacao WHERE of_numero = %s LIMIT 1",
        (of_numero,)
    )
    if of_row and of_row.get('lote_ordem'):
        _atualizar_departamento_lote(of_row['lote_ordem'])


@app.route('/api/finalizar', methods=['POST'])
def api_finalizar():
    """Finalizar producao de pecas especificas e sincroniza com operacoes_producao."""
    try:
        data = request.get_json()
        lotcod = data.get('lote')
        pecas = data.get('pecas', [])
        setor = data.get('setor', '')
        qtd_informada = data.get('qtd_produzida', 0)

        if not lotcod:
            return jsonify({'error': 'Lote obrigatorio'}), 400

        setor_para_dept = {
            'CORTE': 'CORTE', 'DOBRA': 'DOBRA', 'SOLDA': 'SOLDA',
            'ACABAMENTO': 'ACABAMENTO', 'MONTAGEM': 'MONTAGEM',
            'FUNILARIA': 'FUNILARIA', 'PINTURA': 'PINTURA',
        }

        if pecas and setor:
            # Finalizar pecas em um setor especifico (com suporte a quantidade parcial)
            for pcod in pecas:
                row = db_query_one(
                    "SELECT sp.id, sp.of_numero, sp.qtd_produzida, "
                    "COALESCE(of2.qtde_ordem, 0) as qtde_ordem "
                    "FROM serralheria_producao sp "
                    "LEFT JOIN ordens_fabricacao of2 ON sp.of_numero = of2.of_numero "
                    "WHERE sp.lote = %s AND sp.produto = %s AND sp.setor = %s "
                    "AND sp.status = 'em_producao'",
                    (lotcod, pcod, setor)
                )
                if not row:
                    app.logger.warning('Finalizar: peca %s setor %s nao encontrada em producao', pcod, setor)
                    continue

                qtd_total = _int(row['qtde_ordem'])
                qtd_ja_feita = _int(row['qtd_produzida'])
                restante = qtd_total - qtd_ja_feita

                if qtd_total <= 0:
                    # Sem qtde_ordem, finaliza direto
                    db_execute(
                        "UPDATE serralheria_producao SET status='finalizado', data_fim=NOW() "
                        "WHERE id=%s", (row['id'],)
                    )
                    dept = setor_para_dept.get(setor, setor)
                    _sync_op_status(row['of_numero'], dept, 'concluido')
                    continue

                # Validacao: quantidade nao pode exceder o restante
                if qtd_informada > restante:
                    return jsonify({
                        'error': 'Quantidade maxima permitida: %d (restam %d de %d)' % (restante, restante, qtd_total),
                        'max_qtd': restante
                    }), 400

                if qtd_informada <= 0:
                    return jsonify({'error': 'Informe uma quantidade maior que zero'}), 400

                nova_qtd = qtd_ja_feita + qtd_informada

                if nova_qtd >= qtd_total:
                    # Finalizacao completa
                    db_execute(
                        "UPDATE serralheria_producao "
                        "SET status='finalizado', data_fim=NOW(), qtd_produzida=%s "
                        "WHERE id=%s",
                        (qtd_total, row['id'])
                    )
                    dept = setor_para_dept.get(setor, setor)
                    _sync_op_status(row['of_numero'], dept, 'concluido')
                    app.logger.info('Lote %s peca %s setor %s: FINALIZADA (%d/%d)', lotcod, pcod, setor, nova_qtd, qtd_total)
                else:
                    # Finalizacao parcial: acumula e mantem em_producao
                    db_execute(
                        "UPDATE serralheria_producao SET qtd_produzida=%s WHERE id=%s",
                        (nova_qtd, row['id'])
                    )
                    app.logger.info('Lote %s peca %s setor %s: PARCIAL %d/%d (restam %d)',
                        lotcod, pcod, setor, nova_qtd, qtd_total, qtd_total - nova_qtd)

            return jsonify({'success': True, 'mensagem': 'Producao atualizada!'})
        elif pecas:
            # Finalizar todas as producoes das pecas selecionadas (todos os setores) — sem qtde parcial
            placeholders = ','.join(['%s'] * len(pecas))
            rows = db_query(
                f"SELECT of_numero, setor FROM serralheria_producao "
                f"WHERE lote = %s AND produto IN ({placeholders}) AND status = 'em_producao'",
                [lotcod] + pecas
            )
            db_execute(
                f"UPDATE serralheria_producao "
                f"SET status = 'finalizado', data_fim = NOW() "
                f"WHERE lote = %s AND produto IN ({placeholders}) AND status = 'em_producao'",
                [lotcod] + pecas
            )
            for row in rows:
                dept = setor_para_dept.get(row.get('setor',''), row.get('setor',''))
                _sync_op_status(row.get('of_numero'), dept, 'concluido')
            app.logger.info('Lote %s: %d peca(s) finalizada(s) no totem', lotcod, len(pecas))
        else:
            # Finalizar todas as pecas do lote
            rows = db_query(
                "SELECT of_numero, setor FROM serralheria_producao "
                "WHERE lote = %s AND status = 'em_producao'", (lotcod,)
            )
            db_execute(
                "UPDATE serralheria_producao "
                "SET status = 'finalizado', data_fim = NOW() "
                "WHERE lote = %s AND status = 'em_producao'",
                (lotcod,)
            )
            for row in rows:
                dept = setor_para_dept.get(row.get('setor',''), row.get('setor',''))
                _sync_op_status(row.get('of_numero'), dept, 'concluido')
            app.logger.info('Lote %s finalizado no totem', lotcod)

        return jsonify({'success': True, 'mensagem': 'Producao finalizada!'})
    except Exception as e:
        app.logger.error('Erro finalizar: %s', e)
        return jsonify({'error': str(e)}), 500


@app.route('/api/refresh_lotes')
def api_refresh_lotes():
    """Recarrega lista de lotes ativos do MariaDB."""
    _refresh_lotes_ativos()
    _load_produto_cache()
    return jsonify({'status': 'ok', 'lotes_count': len(_lotes_ativos)})


# ── Auto-refresh em background ────────────────────────────────────

_LOTES_REFRESH_INTERVAL = 30  # segundos

def _background_refresh_loop():
    """Loop que atualiza o cache de lotes ativos periodicamente."""
    while True:
        time.sleep(_LOTES_REFRESH_INTERVAL)
        try:
            _refresh_lotes_ativos()
        except Exception as e:
            print('[WARN] Background refresh falhou: %s' % e)


# ── Main ─────────────────────────────────────────────────────────────

if __name__ == '__main__':
    init_db()
    # Inicia thread de background para atualizar lotes automaticamente
    t = threading.Thread(target=_background_refresh_loop, daemon=True)
    t.start()
    print('[TOTEM] Serralheria Totem rodando em http://0.0.0.0:5003 (auto-refresh lotes a cada %ds)' % _LOTES_REFRESH_INTERVAL)
    app.run(host='0.0.0.0', port=5003, debug=False, threaded=True)