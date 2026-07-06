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

# PostgreSQL (ERP) - para buscar nomes reais dos produtos
PG_HOST = '192.168.1.17'
PG_PORT = 5432
PG_DB = 'salutem'
PG_USER = 'postgres'
PG_PASS = 'postgres'

# In-memory cache for product names (loaded from PostgreSQL at startup)
_produto_cache = {}

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

# ── Init DB ──────────────────────────────────────────────────────────

# ── Produto name helper (in-memory cache from PostgreSQL) ──

def _get_produto_nome(codigo_produto):
    """Get real product name from in-memory cache. No MariaDB table needed."""
    if not codigo_produto:
        return ''
    key = str(codigo_produto).strip()
    return _produto_cache.get(key, '')


def _load_produto_cache():
    """Load all product names from PostgreSQL into memory. No MariaDB table needed."""
    global _produto_cache
    try:
        import psycopg2
        conn = psycopg2.connect(
            host=PG_HOST, port=PG_PORT, dbname=PG_DB,
            user=PG_USER, password=PG_PASS, connect_timeout=10
        )
        cur = conn.cursor()
        cur.execute("SELECT produto, pronome FROM public.produto WHERE pronome IS NOT NULL AND pronome != ''")
        rows = cur.fetchall()
        cur.close()
        conn.close()
        _produto_cache = {}
        for codigo, nome in rows:
            _produto_cache[str(codigo).strip()] = str(nome).strip()[:200]
        app.logger.info('Cache produtos carregado: %d produtos do ERP', len(_produto_cache))
    except ImportError:
        app.logger.warning('psycopg2 nao instalado, nomes de produtos nao disponiveis')
    except Exception as e:
        app.logger.warning('Cache produtos falhou: %s', e)


def init_db():
    """Create serralheria tables if not exist, seed serra1-9, sync produtos."""
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

    # Load product names from PostgreSQL into memory (no MariaDB table needed)
    _load_produto_cache()

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
            'SELECT COUNT(*) as t FROM lotes_producao'
        )['t'])

        total_pecas = _int(db_query_one("""
            SELECT COUNT(*) as t
            FROM ordens_fabricacao
            WHERE tipo = 'filho'
        """)['t'])

        total_qtd = _int(db_query_one("""
            SELECT COALESCE(SUM(qtde_ordem), 0) as t
            FROM lotes_producao
        """)['t'])

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
            'SELECT COUNT(*) as t FROM lotes_producao'
        )['t'])

        total_pecas = _int(db_query_one("""
            SELECT COUNT(*) as t
            FROM ordens_fabricacao
            WHERE tipo = 'filho'
        """)['t'])

        total_qtd = _int(db_query_one("""
            SELECT COALESCE(SUM(qtde_ordem), 0) as t
            FROM lotes_producao
        """)['t'])

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

        # ── Lotes ativos com detalhes ──
        lotes_raw = db_query("""
            SELECT ordem, lote_codigo, descricao_produto, status, codigo_produto, qtde_ordem
            FROM lotes_producao
            ORDER BY lote_codigo DESC
        """)

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
            ORDER BY lote_codigo DESC
        """)

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


@app.route('/api/sync_produtos', methods=['POST'])
def api_sync_produtos():
    """Forca recarga do cache de nomes de produtos do ERP."""
    try:
        _load_produto_cache()
        return jsonify({'success': True, 'total': len(_produto_cache)})
    except Exception as e:
        app.logger.error('Erro sync produtos: %s', e)
        return jsonify({'error': str(e)}), 500


# ── Main ─────────────────────────────────────────────────────────────

if __name__ == '__main__':
    init_db()
    print('[TOTEM] Serralheria Totem rodando em http://0.0.0.0:5003 (MariaDB)')
    app.run(host='0.0.0.0', port=5003, debug=False, threaded=True)