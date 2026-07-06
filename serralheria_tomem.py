#!/usr/bin/env python3
"""
Serralheria Totem - App Flask na porta 5003
Dados do MariaDB (sistema :5002) - PCP classifica/libera, totem apenas consulta.
Auto-login, 4 telas touch:
  S0: Dashboard KPIs + lotes ativos + producoes
  S1: Lista de lotes liberados/em producao
  S2: Pecas (OFs filhas) de um lote com selecao por setor
  S3: Selecao de operador (serra1-serra9)

SYNC ERP: A cada 5 minutos, sincroniza lotes/OFs/operacoes do PostgreSQL
para o MariaDB. Se o PCP cancelar um lote no ERP, ele some do totem.
"""

import os
import re
import json
import logging
import threading
import time
from decimal import Decimal
from flask import Flask, jsonify, request, render_template
import pymysql
from pymysql.cursors import DictCursor

# ── Config ────────────────────────────────────────────────────────────
MYSQL_HOST = 'localhost'
MYSQL_PORT = 3306
MYSQL_DB = 'producao_db'
MYSQL_USER = 'producao'
MYSQL_PASS = 'senha123'

# PostgreSQL (ERP Logica)
PG_HOST = '192.168.1.17'
PG_PORT = 5432
PG_DB = 'salutem'
PG_USER = 'postgres'
PG_PASS = 'postgres'

# Sync interval in seconds
SYNC_INTERVAL = 300  # 5 minutes

# In-memory cache for product names (loaded from PostgreSQL at startup)
_produto_cache = {}

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
_fh = logging.FileHandler('/tmp/serralheria_tomem.log')
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

# ── PostgreSQL helpers ───────────────────────────────────────────────

def _pg_conn():
    import psycopg2
    return psycopg2.connect(
        host=PG_HOST, port=PG_PORT, dbname=PG_DB,
        user=PG_USER, password=PG_PASS,
        connect_timeout=10
    )

def _pg_query(sql, params=None):
    """Run query and return list of dicts."""
    import psycopg2
    from psycopg2.extras import RealDictCursor
    conn = _pg_conn()
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(sql, params or ())
            rows = cur.fetchall()
            return [dict(r) for r in rows]
    finally:
        conn.close()

def _pg_query_one(sql, params=None):
    """Run query and return one dict or None."""
    import psycopg2
    from psycopg2.extras import RealDictCursor
    conn = _pg_conn()
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(sql, params or ())
            r = cur.fetchone()
            return dict(r) if r else None
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

def _extract_s_code(codigo_produto):
    """Extract S-XXXX from strings like 'PRODUCAO DE S-0240'."""
    if not codigo_produto:
        return ''
    m = re.search(r'S-\d+', str(codigo_produto))
    return m.group(0) if m else str(codigo_produto).strip()


# ── Produto name cache (in-memory from PostgreSQL) ──────────────────

def _get_produto_nome(codigo_produto):
    """Get real product name from in-memory cache. No MariaDB table needed."""
    if not codigo_produto:
        return ''
    key = str(codigo_produto).strip()
    return _produto_cache.get(key, '')


def _load_produto_cache():
    """Load all product names from PostgreSQL into memory."""
    global _produto_cache
    try:
        rows = _pg_query(
            "SELECT produto, pronome FROM public.produto "
            "WHERE pronome IS NOT NULL AND pronome != ''"
        )
        _produto_cache = {}
        for r in rows:
            codigo = r.get('produto', '')
            nome = r.get('pronome', '')
            if codigo:
                _produto_cache[str(codigo).strip()] = str(nome).strip()[:200]
        app.logger.info('Cache produtos carregado: %d produtos do ERP', len(_produto_cache))
    except Exception as e:
        app.logger.warning('Cache produtos falhou: %s', e)


# ── ERP Sync: PostgreSQL -> MariaDB ─────────────────────────────────

def _sync_erp_to_mariadb():
    """
    Sincroniza dados do ERP (PostgreSQL) para o MariaDB.
    - Lotes abertos (EP, ES) do loteprod -> lotes_producao
    - OFs de cada lote (ordem) -> ordens_fabricacao
    - Processos de cada OF (respror + fases) -> operacoes_producao
    - Lotes que nao existem mais no ERP sao marcados 'cancelado_erp'
    """
    t0 = time.time()
    lotes_synced = 0
    ofs_synced = 0
    ops_synced = 0

    try:
        # 1. Buscar lotes abertos no ERP
        lotes_erp = _pg_query("""
            SELECT
                lp.lotcod AS lote_codigo,
                lp.lotdes AS lote_descricao,
                lp.lotdtini AS data_abertura,
                lp.lotdtpre AS data_previsao,
                lp.lotstatus AS status_erp
            FROM public.loteprod lp
            WHERE lp.lotcod IS NOT NULL
              AND lp.lotcod <> ''
              AND (lp.lotstatus IS NULL OR lp.lotstatus IN ('EP', 'ES', ''))
            ORDER BY lp.lotcod DESC
        """)

        # Coletar codigos dos lotes ativos no ERP
        lotes_erp_codigos = set()
        for lote_erp in lotes_erp:
            lotcod = _str(lote_erp['lote_codigo'])
            if not lotcod:
                continue
            lotes_erp_codigos.add(lotcod)

            # Buscar OFs deste lote no ERP (tabela ordem)
            ordens_erp = _pg_query("""
                SELECT
                    o.ordem,
                    o.tipoord AS tipo_ordem,
                    o.ordquanti AS quantidade,
                    o.ordproduto AS produto,
                    o.lotcod AS lote_codigo,
                    o.ordnivprod AS nivel_producao
                FROM public.ordem o
                WHERE o.lotcod = %s
                ORDER BY o.ordem
            """, (lotcod,))

            # Maior ordem numerica do lote (usado como 'ordem' no sistema local)
            maior_ordem = 0
            for o in ordens_erp:
                ordem_val = o.get('ordem')
                if ordem_val is not None:
                    try:
                        num = int(float(ordem_val))
                        if num > maior_ordem:
                            maior_ordem = num
                    except (ValueError, TypeError):
                        pass

            # Produto final (OF pai via ordem3)
            produto_final = ''
            descricao_final = ''
            qtd_final = 0
            try:
                pai = _pg_query_one("""
                    SELECT
                        o3.ordproof AS codigo_produto,
                        p.pronome AS nome_produto,
                        (SELECT o2.ordquanti FROM public.ordem o2
                         WHERE o2.ordem = o3.ordem LIMIT 1) AS quantidade
                    FROM public.ordem3 o3
                    LEFT JOIN public.produto p ON o3.ordproof::TEXT = p.produto::TEXT
                    WHERE o3.ordoflote = %s AND o3.ordem != 0
                    LIMIT 1
                """, (lotcod,))
                if pai:
                    produto_final = _str(pai.get('codigo_produto'))
                    descricao_final = _str(pai.get('nome_produto'))
                    qtd_final = _int(pai.get('quantidade'))
            except Exception:
                pass

            if not produto_final and ordens_erp:
                # Fallback: usar a primeira OF
                produto_final = _str(ordens_erp[0].get('produto'))

            # Upsert lote no MariaDB
            lote_desc = _str(lote_erp['lote_descricao'])
            if not lote_desc and descricao_final:
                lote_desc = descricao_final
            if not lote_desc:
                lote_desc = produto_final

            try:
                db_execute("""
                    INSERT INTO lotes_producao
                        (ordem, lote_codigo, codigo_produto, descricao_produto, qtde_ordem,
                         unidade_medida, status_erp, data_previsao_erp, data_abertura_erp,
                         status, data_ultima_sync)
                    VALUES (%s, %s, %s, %s, %s, 'PC', %s, %s, %s, 'importado', NOW())
                    ON DUPLICATE KEY UPDATE
                        descricao_produto = VALUES(descricao_produto),
                        codigo_produto = VALUES(codigo_produto),
                        qtde_ordem = VALUES(qtde_ordem),
                        status_erp = VALUES(status_erp),
                        data_previsao_erp = VALUES(data_previsao_erp),
                        data_abertura_erp = VALUES(data_abertura_erp),
                        data_ultima_sync = NOW(),
                        status = IF(status = 'cancelado_erp', 'importado', status)
                """, (
                    maior_ordem, lotcod, produto_final, lote_desc,
                    qtd_final if qtd_final else 0,
                    _str(lote_erp.get('status_erp')),
                    lote_erp.get('data_previsao'),
                    lote_erp.get('data_abertura'),
                ))
                lotes_synced += 1
            except Exception as e:
                app.logger.warning('Sync lote %s falhou: %s', lotcod, e)

            # Sincronizar OFs deste lote
            for o in ordens_erp:
                of_num = o.get('ordem')
                if of_num is None:
                    continue
                of_num_str = str(int(float(of_num)))
                cod_produto = _str(o.get('produto'))
                nivel = _str(o.get('nivel_producao'))
                tipo = 'pai' if nivel == '1' else 'filho'
                qtd = _int(o.get('quantidade'))

                # Descricao: usar nome do produto do cache se disponivel
                of_desc = _get_produto_nome(cod_produto) or cod_produto

                try:
                    db_execute("""
                        INSERT INTO ordens_fabricacao
                            (lote_ordem, of_numero, codigo_produto, descricao_produto,
                             qtde_ordem, unidade_medida, tipo, data_previsao)
                        VALUES (%s, %s, %s, %s, %s, 'PC', %s, NULL)
                        ON DUPLICATE KEY UPDATE
                            codigo_produto = VALUES(codigo_produto),
                            descricao_produto = VALUES(descricao_produto),
                            qtde_ordem = VALUES(qtde_ordem),
                            tipo = VALUES(tipo)
                    """, (maior_ordem, of_num_str, cod_produto, of_desc, qtd, tipo))
                    ofs_synced += 1
                except Exception as e:
                    app.logger.warning('Sync OF %s falhou: %s', of_num_str, e)

                # Buscar processos (roteiro) desta OF
                try:
                    processos = _pg_query("""
                        SELECT
                            rpr.rprnumero AS numero_sequencial,
                            rpr.rprordem AS ordem,
                            rpr.rprproce AS processo,
                            rpr.rproper AS operacao,
                            rpr.rproped AS descricao_processo,
                            rpr.rprfase AS fase,
                            f.fasnome AS nome_departamento
                        FROM public.respror rpr
                        INNER JOIN public.fases f ON rpr.rprfase::TEXT = f.fase::TEXT
                        WHERE rpr.rprordem::TEXT = %s::TEXT
                        ORDER BY rpr.rprproce
                    """, (of_num_str,))
                except Exception:
                    # Fallback sem JOIN com fases
                    try:
                        processos = _pg_query("""
                            SELECT
                                rpr.rprnumero AS numero_sequencial,
                                rpr.rprordem AS ordem,
                                rpr.rprproce AS processo,
                                rpr.rproper AS operacao,
                                rpr.rproped AS descricao_processo,
                                rpr.rprfase AS fase,
                                NULL AS nome_departamento
                            FROM public.respror rpr
                            WHERE rpr.rprordem::TEXT = %s::TEXT
                            ORDER BY rpr.rprproce
                        """, (of_num_str,))
                    except Exception as e2:
                        app.logger.warning('Sync processos OF %s falhou: %s', of_num_str, e2)
                        processos = []

                for proc in processos:
                    dept_original = (_str(proc.get('nome_departamento'))).upper().strip()
                    dept = MAPEAMENTO_SETORES.get(dept_original, dept_original)
                    if not dept:
                        continue
                    desc_op = _str(proc.get('descricao_processo')) or _str(proc.get('operacao'))

                    try:
                        db_execute("""
                            INSERT INTO operacoes_producao
                                (of_numero, lote_ordem, sequencia, fase,
                                 descricao_operacao, departamento, codigo_barras)
                            VALUES (%s, %s, %s, %s, %s, %s, NULL)
                            ON DUPLICATE KEY UPDATE
                                descricao_operacao = VALUES(descricao_operacao),
                                departamento = VALUES(departamento),
                                fase = VALUES(fase)
                        """, (
                            of_num_str, maior_ordem,
                            _int(proc.get('numero_sequencial')),
                            _str(proc.get('fase')),
                            desc_op, dept
                        ))
                        ops_synced += 1
                    except Exception as e:
                        app.logger.warning('Sync op OF %s falhou: %s', of_num_str, e)

        # 2. Marcar lotes que NAO existem mais no ERP como 'cancelado_erp'
        if lotes_erp_codigos:
            placeholders = ','.join(['%s'] * len(lotes_erp_codigos))
            db_execute(
                "UPDATE lotes_producao SET status = 'cancelado_erp' "
                "WHERE status != 'cancelado_erp' "
                "AND lote_codigo NOT IN (" + placeholders + ")",
                list(lotes_erp_codigos)
            )
        else:
            # Nenhum lote aberto no ERP: cancelar todos
            db_execute(
                "UPDATE lotes_producao SET status = 'cancelado_erp' "
                "WHERE status != 'cancelado_erp'"
            )

        # 3. Reload product names cache
        _load_produto_cache()

        elapsed = time.time() - t0
        app.logger.info(
            'Sync ERP completo em %.1fs: %d lotes, %d OFs, %d ops',
            elapsed, lotes_synced, ofs_synced, ops_synced
        )

    except Exception as e:
        app.logger.error('Sync ERP falhou: %s', e)


def _sync_loop():
    """Background thread: sync ERP a cada SYNC_INTERVAL segundos."""
    while True:
        try:
            _sync_erp_to_mariadb()
        except Exception as e:
            app.logger.error('Sync loop erro: %s', e)
        time.sleep(SYNC_INTERVAL)


# ── Init DB ──────────────────────────────────────────────────────────

def init_db():
    """Create serralheria tables if not exist, seed serra1-9, sync ERP."""
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
            INDEX idx_sp_lote (lote),
            INDEX idx_sp_status (status)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
    """)
    # Seed serra1-9
    for i in range(1, 10):
        nome = 'serra' + str(i)
        existing = db_query_one("SELECT id FROM serralheria_usuarios WHERE nome = %s", (nome,))
        if not existing:
            db_execute(
                "INSERT INTO serralheria_usuarios (nome, setor, ativo) VALUES (%s, 'Serralheria', 1)",
                (nome,)
            )
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

    # Migration: ensure lotes_producao has columns needed by sync
    for col, col_def in [
        ('data_ultima_sync', 'DATETIME DEFAULT NULL'),
        ('status_erp', "VARCHAR(20) DEFAULT ''"),
        ('data_abertura_erp', 'DATETIME DEFAULT NULL'),
        ('data_previsao_erp', 'DATETIME DEFAULT NULL'),
        ('unidade_medida', "VARCHAR(10) DEFAULT 'UN'"),
    ]:
        try:
            db_query_one('SELECT ' + col + ' FROM lotes_producao LIMIT 1')
        except Exception:
            db_execute('ALTER TABLE lotes_producao ADD COLUMN ' + col + ' ' + col_def)

    # Migration: ensure status column is VARCHAR (not ENUM) to accept new values
    try:
        db_execute(
            "ALTER TABLE lotes_producao MODIFY COLUMN status VARCHAR(50) DEFAULT 'importado'"
        )
        app.logger.info('Migration: status column changed to VARCHAR(50)')
    except Exception as e:
        app.logger.warning('Migration status column: %s', e)

    # Initial ERP sync (loads lotes, OFs, operacoes, and product names)
    print('[SYNC] Sincronizando com ERP...')
    _sync_erp_to_mariadb()

    # Start background sync thread
    t = threading.Thread(target=_sync_loop, daemon=True)
    t.start()
    print('[SYNC] Thread de sync ativa (a cada %d segundos)' % SYNC_INTERVAL)

    print('[OK] Tabelas serralheria verificadas no MariaDB')


# ── Rotas ────────────────────────────────────────────────────────────

@app.route('/')
def index():
    return render_template('dashboard.html')


@app.route('/api/kpis')
def api_kpis():
    """KPIs da serralheria: lotes ativos, pecas, total qtd, producoes."""
    try:
        total_lotes = _int(db_query_one(
            'SELECT COUNT(*) as t FROM lotes_producao WHERE status != %s', ('cancelado_erp',)
        )['t'])

        total_pecas = _int(db_query_one("""
            SELECT COUNT(*) as t
            FROM ordens_fabricacao of2
            INNER JOIN lotes_producao lp ON of2.lote_ordem = lp.ordem
            WHERE of2.tipo = 'filho' AND lp.status != %s
        """, ('cancelado_erp',))['t'])

        total_qtd = _int(db_query_one("""
            SELECT COALESCE(SUM(qtde_ordem), 0) as t
            FROM lotes_producao WHERE status != %s
        """, ('cancelado_erp',))['t'])

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
        # ── KPIs ──
        total_lotes = _int(db_query_one(
            "SELECT COUNT(*) as t FROM lotes_producao WHERE status != %s",
            ('cancelado_erp',)
        )['t'])

        total_pecas = _int(db_query_one("""
            SELECT COUNT(*) as t
            FROM ordens_fabricacao of2
            INNER JOIN lotes_producao lp ON of2.lote_ordem = lp.ordem
            WHERE of2.tipo = 'filho' AND lp.status != %s
        """, ('cancelado_erp',))['t'])

        total_qtd = _int(db_query_one("""
            SELECT COALESCE(SUM(qtde_ordem), 0) as t
            FROM lotes_producao WHERE status != %s
        """, ('cancelado_erp',))['t'])

        em_andamento = _int(db_query_one(
            "SELECT COUNT(*) as t FROM serralheria_producao WHERE status = 'em_producao'"
        )['t'])

        hoje = _int(db_query_one(
            "SELECT COUNT(*) as t FROM serralheria_producao WHERE DATE(data_inicio) = CURDATE()"
        )['t'])

        finalizadas_hoje = _int(db_query_one(
            "SELECT COUNT(*) as t FROM serralheria_producao WHERE status = 'finalizado' AND DATE(data_fim) = CURDATE()"
        )['t'])

        # ── Producoes ativas com detalhes ──
        ativos = db_query("""
            SELECT sp.id, sp.lote, sp.produto, sp.usuario_nome, sp.data_inicio, sp.setor
            FROM serralheria_producao sp
            WHERE sp.status = 'em_producao'
            ORDER BY sp.data_inicio DESC
        """)
        for a in ativos:
            # Lote description
            r = db_query_one(
                "SELECT descricao_produto FROM lotes_producao WHERE lote_codigo = %s",
                (a['lote'],)
            )
            a['lote_desc'] = _str(r['descricao_produto']) if r else ''

            # Produto name - prefer real name from ERP cache
            r = db_query_one(
                "SELECT descricao_produto, codigo_produto "
                "FROM ordens_fabricacao WHERE of_numero = %s",
                (a['produto'],)
            )
            if r:
                nome_real = _get_produto_nome(r.get('codigo_produto'))
                a['produto_nome'] = nome_real if nome_real else _str(r['descricao_produto'])
            else:
                a['produto_nome'] = _str(a['produto'])

            # Count pecas for this user in this lote
            r = db_query_one(
                "SELECT COUNT(*) as t FROM serralheria_producao "
                "WHERE lote = %s AND usuario_nome = %s AND status = 'em_producao'",
                (a['lote'], a['usuario_nome'])
            )
            a['pecas_count'] = _int(r['t']) if r else 0

        # ── Lotes ativos com detalhes (excluindo cancelados no ERP) ──
        lotes_raw = db_query("""
            SELECT ordem, lote_codigo, descricao_produto, status, codigo_produto, qtde_ordem
            FROM lotes_producao
            WHERE status != %s
            ORDER BY lote_codigo DESC
        """, ('cancelado_erp',))

        lotes = []
        for lp in lotes_raw:
            # OFs filhas (pecas) - count and total qty
            ofs = db_query_one("""
                SELECT COUNT(*) as qtd_pecas, COALESCE(SUM(qtde_ordem), 0) as qtd_total
                FROM ordens_fabricacao
                WHERE lote_ordem = %s AND tipo = 'filho'
            """, (lp['ordem'],))

            # OF pai (produto final S-) - pode nao existir
            pai = db_query_one("""
                SELECT codigo_produto, descricao_produto, qtde_ordem
                FROM ordens_fabricacao
                WHERE lote_ordem = %s AND tipo = 'pai'
                LIMIT 1
            """, (lp['ordem'],))
            if not pai:
                # Fallback: pega primeira OF do lote
                pai = db_query_one("""
                    SELECT codigo_produto, descricao_produto, qtde_ordem
                    FROM ordens_fabricacao WHERE lote_ordem = %s LIMIT 1
                """, (lp['ordem'],))

            # Extract S- code and build product info
            s_code = _extract_s_code(lp['codigo_produto'])
            # Get real name for produto final (S-XXX)
            pai_nome_real = ''
            if pai:
                pai_nome_real = _get_produto_nome(pai.get('codigo_produto'))
                produto_final = _str(pai['codigo_produto']) or s_code
                produto_nome = pai_nome_real or _str(pai['descricao_produto'])
                qtd_final = _int(pai['qtde_ordem'])
            else:
                # Fallback: no OF pai, use lote data
                produto_final = s_code
                produto_nome = _str(lp['descricao_produto'])
                qtd_final = _int(lp['qtde_ordem'])

            # Check serralheria production status
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
                'qtd_produto_final': qtd_final,
                'qtd_pecas': _int(ofs['qtd_pecas']) if ofs else 0,
                'qtd_total': _int(ofs['qtd_total']) if ofs else 0,
                'status_producao': prod['status'] if prod else None,
                'operador': prod['usuario_nome'] if prod else None,
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
        lotes_raw = db_query("""
            SELECT ordem, lote_codigo, descricao_produto, status, codigo_produto, qtde_ordem
            FROM lotes_producao
            WHERE status != %s
            ORDER BY lote_codigo DESC
        """, ('cancelado_erp',))

        lotes = []
        for lp in lotes_raw:
            # OFs filhas (pecas)
            ofs = db_query_one("""
                SELECT COUNT(*) as qtd_pecas, COALESCE(SUM(qtde_ordem), 0) as qtd_total
                FROM ordens_fabricacao WHERE lote_ordem = %s AND tipo = 'filho'
            """, (lp['ordem'],))

            # OF pai (S- product) - pode nao existir
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
            # Get real name for produto final (S-XXX)
            pai_nome_real = ''
            if pai:
                pai_nome_real = _get_produto_nome(pai.get('codigo_produto'))
                produto_final = _str(pai['codigo_produto']) or s_code
                produto_nome = pai_nome_real or _str(pai['descricao_produto'])
                qtd_final = _int(pai['qtde_ordem'])
            else:
                produto_final = s_code
                produto_nome = _str(lp['descricao_produto'])
                qtd_final = _int(lp['qtde_ordem'])

            # Serralheria production tracking
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
                'qtd_produto_final': qtd_final,
                'qtd_pecas': _int(ofs['qtd_pecas']) if ofs else 0,
                'qtd_total': _int(ofs['qtd_total']) if ofs else 0,
                'status_producao': prod['status'] if prod else None,
                'operador': prod['usuario_nome'] if prod else None,
            })

        return jsonify({'lotes': lotes})
    except Exception as e:
        app.logger.error('Erro lotes: %s', e)
        return jsonify({'error': str(e)}), 500


@app.route('/api/lotes/<lotcod>/pecas')
def api_pecas(lotcod):
    """Pecas (OFs filhas) de um lote com operacoes por setor."""
    try:
        # Lote info
        lote = db_query_one(
            "SELECT ordem, lote_codigo, descricao_produto, qtde_ordem "
            "FROM lotes_producao WHERE lote_codigo = %s",
            (lotcod,)
        )
        if not lote:
            return jsonify({'error': 'Lote nao encontrado'}), 404

        # Child OFs (pecas para fabricar - PC-/CJ-)
        pecas = db_query("""
            SELECT of.of_numero, of.codigo_produto as codigo, of.descricao_produto as descricao,
                   of.qtde_ordem as quantidade, of.tipo
            FROM ordens_fabricacao of
            WHERE of.lote_ordem = %s AND of.tipo = 'filho'
            ORDER BY of.codigo_produto
        """, (lote['ordem'],))

        # Parent OF (produto final S-)
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

        # Build pecas with operations info
        pecas_result = []
        for p in pecas:
            ops = db_query("""
                SELECT id, departamento, descricao_operacao, status, sequencia
                FROM operacoes_producao
                WHERE of_numero = %s
                ORDER BY sequencia
            """, (p['of_numero'],))

            # Unique departments (setores) for this OF
            setores = list(set(
                op['departamento'] for op in ops if op.get('departamento')
            ))

            # Use real product name from ERP cache instead of "PRODUCAO DE S-XXX"
            nome_real = _get_produto_nome(p.get('codigo'))
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

        # Active productions in serralheria_producao
        ativas_raw = db_query(
            "SELECT produto, of_numero, setor, usuario_nome "
            "FROM serralheria_producao WHERE lote = %s AND status = 'em_producao'",
            (lotcod,)
        )
        pecas_ativas = {}
        for row in ativas_raw:
            pecas_ativas[row['produto']] = {
                'setor': row['setor'],
                'usuario': row['usuario_nome'],
            }

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
            "SELECT MIN(id) as id, nome, MAX(setor) as setor FROM serralheria_usuarios WHERE ativo = 1 GROUP BY nome ORDER BY nome"
        )
        return jsonify({'usuarios': usuarios})
    except Exception as e:
        app.logger.error('Erro usuarios: %s', e)
        return jsonify({'error': str(e)}), 500


@app.route('/api/iniciar', methods=['POST'])
def api_iniciar():
    """Iniciar producao: salva no MariaDB (serralheria_producao)."""
    try:
        data = request.get_json()
        lotcod = data.get('lote')
        usuario_id = data.get('usuario_id')
        usuario_nome = data.get('usuario_nome')
        setor = data.get('setor', '')
        pecas = data.get('pecas', [])

        if not lotcod or not usuario_id:
            return jsonify({'error': 'Dados obrigatorios: lote, usuario_id'}), 400

        for peca in pecas:
            db_execute(
                """INSERT INTO serralheria_producao
                   (ordem_id, lote, produto, of_numero, usuario_id, usuario_nome, setor, status, data_inicio)
                   VALUES (%s, %s, %s, %s, %s, %s, %s, 'em_producao', NOW())""",
                (peca.get('ordem'), lotcod, peca['codigo'], peca.get('ordem'),
                 usuario_id, usuario_nome, setor)
            )

        app.logger.info(
            'Producao iniciada: lote=%s usuario=%s setor=%s pecas=%d',
            lotcod, usuario_nome, setor, len(pecas)
        )
        return jsonify({'success': True, 'mensagem': 'Producao iniciada!'})
    except Exception as e:
        app.logger.error('Erro iniciar: %s', e)
        return jsonify({'error': str(e)}), 500


@app.route('/api/finalizar', methods=['POST'])
def api_finalizar():
    """Finalizar producao do lote no totem (atualiza serralheria_producao)."""
    try:
        data = request.get_json()
        lotcod = data.get('lote')

        if not lotcod:
            return jsonify({'error': 'Lote obrigatorio'}), 400

        # Finaliza producoes ativas deste lote no totem
        db_execute(
            "UPDATE serralheria_producao "
            "SET status = 'finalizado', data_fim = NOW() "
            "WHERE lote = %s AND status = 'em_producao'",
            (lotcod,)
        )

        app.logger.info('Lote %s finalizado no totem', lotcod)
        return jsonify({'success': True, 'mensagem': 'Producao finalizada!'})
    except Exception as e:
        app.logger.error('Erro finalizar: %s', e)
        return jsonify({'error': str(e)}), 500


@app.route('/api/sync_erp', methods=['POST'])
def api_sync_erp():
    """Forca sincronizacao manual com ERP."""
    try:
        _sync_erp_to_mariadb()
        total = db_query_one(
            "SELECT COUNT(*) as t FROM lotes_producao WHERE status != %s",
            ('cancelado_erp',)
        )['t']
        return jsonify({'success': True, 'lotes_ativos': total})
    except Exception as e:
        app.logger.error('Erro sync ERP manual: %s', e)
        return jsonify({'error': str(e)}), 500


# ── Main ─────────────────────────────────────────────────────────────

if __name__ == '__main__':
    init_db()
    print('[TOTEM] Serralheria Totem rodando em http://0.0.0.0:5003 (MariaDB + Sync ERP)')
    app.run(host='0.0.0.0', port=5003, debug=False, threaded=True)