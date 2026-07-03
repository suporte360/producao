#!/usr/bin/env python3
"""
Serralheria Totem - App Flask separada na porta 5003
Auto-login (sem tela de login), 4 telas touch:
  S1: Dashboard KPIs + lotes ativos
  S2: Lista de lotes agrupados
  S3: Pecas/conjuntos para fabricar (PC-/CJ-, sem S-)
  S4: Selecao de usuario (serra1-serra9) -> salva SQLite local
"""

import os
import json
import logging
import sqlite3
from datetime import datetime
from flask import Flask, jsonify, request, render_template
import psycopg2

# Config
PG_HOST = '192.168.1.17'
PG_PORT = 5432
PG_DB = 'salutem'
PG_USER = 'postgres'
PG_PASS = 'postgres'

SQLITE_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'serralheria.db')

app = Flask(__name__, template_folder='templates/serralheria', static_folder='static')
app.logger.setLevel(logging.INFO)
# Log to file
fh = logging.FileHandler('/tmp/serralheria_tomem.log')
fh.setFormatter(logging.Formatter('%(asctime)s %(levelname)s %(message)s'))
app.logger.addHandler(fh)

# ── PostgreSQL helpers ──────────────────────────────────────────────────

def get_pg():
    return psycopg2.connect(host=PG_HOST, port=PG_PORT, dbname=PG_DB,
                            user=PG_USER, password=PG_PASS,
                            connect_timeout=10)

def pg_query(sql, params=None):
    conn = get_pg()
    try:
        with conn.cursor() as cur:
            cur.execute(sql, params or ())
            cols = [d[0] for d in cur.description] if cur.description else []
            rows = cur.fetchall()
        return [dict(zip(cols, r)) for r in rows]
    except Exception as e:
        app.logger.error('PG query error: %s', e, exc_info=True)
        raise
    finally:
        conn.close()

def pg_execute(sql, params=None):
    conn = get_pg()
    try:
        with conn.cursor() as cur:
            cur.execute(sql, params or ())
        conn.commit()
    except Exception as e:
        app.logger.error('PG execute error: %s', e, exc_info=True)
        raise
    finally:
        conn.close()

# ── SQLite helpers ──────────────────────────────────────────────────────

def get_sqlite():
    conn = sqlite3.connect(SQLITE_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def sqlite_query(sql, params=None):
    conn = get_sqlite()
    try:
        cur = conn.cursor()
        cur.execute(sql, params or ())
        rows = cur.fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()

def sqlite_execute(sql, params=None):
    conn = get_sqlite()
    try:
        cur = conn.cursor()
        cur.execute(sql, params or ())
        conn.commit()
    finally:
        conn.close()

# ── Rotas ────────────────────────────────────────────────────────────────

@app.route('/')
def index():
    return render_template('dashboard.html')

@app.route('/api/kpis')
def api_kpis():
    """KPIs da serralheria: lotes EA, total pecas (sem S-), usuarios ativos, producoes hoje"""
    try:
        # Lotes EA com fase serralheria (fsorfase=10)
        sql_lotes = """
            SELECT COUNT(DISTINCT lp.lotcod) as total_lotes
            FROM loteprod lp
            INNER JOIN ordem o ON o.lotcod = lp.lotcod
            INNER JOIN fasord fs ON fs.fsororde::text = o.ordem::text AND fs.fsorfase = 10
            WHERE lp.lotstatus = 'EA'
        """
        r = pg_query(sql_lotes)
        total_lotes = r[0]['total_lotes'] if r else 0

        # Total pecas para fabricar (sem S-)
        sql_pecas = """
            SELECT COUNT(*) as total_pecas, COALESCE(SUM(o.ordquanti),0) as total_qtd
            FROM loteprod lp
            INNER JOIN ordem o ON o.lotcod = lp.lotcod
            INNER JOIN fasord fs ON fs.fsororde::text = o.ordem::text AND fs.fsorfase = 10
            WHERE lp.lotstatus = 'EA'
              AND o.ordproduto NOT LIKE 'S-%%'
        """
        r = pg_query(sql_pecas)
        total_pecas = r[0]['total_pecas'] if r else 0
        total_qtd = float(r[0]['total_qtd']) if r else 0

        # Producoes em andamento (SQLite)
        r = sqlite_query("SELECT COUNT(*) as total FROM serralheria_producao WHERE status = 'em_producao'")
        em_andamento = r[0]['total'] if r else 0

        # Producoes hoje
        r = sqlite_query("SELECT COUNT(*) as total FROM serralheria_producao WHERE DATE(data_inicio) = DATE('now','localtime')")
        hoje = r[0]['total'] if r else 0

        return jsonify({
            'total_lotes': total_lotes,
            'total_pecas': total_pecas,
            'total_qtd': int(total_qtd),
            'em_andamento': em_andamento,
            'hoje': hoje
        })
    except Exception as e:
        app.logger.error('Erro KPIs: %s', e)
        return jsonify({'error': str(e)}), 500

@app.route('/api/lotes')
def api_lotes():
    """Lotes EA com fase serralheria, agrupados por lotcod.
    Mostra: codigo, descricao (max 49 chars), qtd pecas, produto final (S-)"""
    try:
        sql = """
            SELECT
                lp.lotcod,
                SUBSTRING(lp.lotdes, 1, 49) as descricao,
                lp.lotstatus,
                (SELECT COUNT(*)
                 FROM ordem o2
                 INNER JOIN fasord fs2 ON fs2.fsororde::text = o2.ordem::text AND fs2.fsorfase = 10
                 WHERE o2.lotcod = lp.lotcod AND o2.ordproduto NOT LIKE 'S-%%'
                ) as qtd_pecas,
                (SELECT COALESCE(SUM(o3.ordquanti), 0)
                 FROM ordem o3
                 INNER JOIN fasord fs3 ON fs3.fsororde::text = o3.ordem::text AND fs3.fsorfase = 10
                 WHERE o3.lotcod = lp.lotcod AND o3.ordproduto NOT LIKE 'S-%%'
                ) as qtd_total,
                (SELECT o4.ordproduto
                 FROM ordem o4
                 INNER JOIN fasord fs4 ON fs4.fsororde::text = o4.ordem::text AND fs4.fsorfase = 10
                 WHERE o4.lotcod = lp.lotcod AND o4.ordproduto LIKE 'S-%%'
                 LIMIT 1
                ) as produto_final
            FROM loteprod lp
            INNER JOIN ordem o ON o.lotcod = lp.lotcod
            INNER JOIN fasord fs ON fs.fsororde::text = o.ordem::text AND fs.fsorfase = 10
            WHERE lp.lotstatus = 'EA'
            GROUP BY lp.lotcod, lp.lotdes, lp.lotstatus
            ORDER BY lp.lotcod DESC
        """
        lotes = pg_query(sql)

        # Buscar status do SQLite para cada lote
        for lote in lotes:
            r = sqlite_query("SELECT status, usuario_nome FROM serralheria_producao WHERE lote = ? AND status = 'em_producao' LIMIT 1", (lote['lotcod'],))
            if r:
                lote['status_producao'] = r[0]['status']
                lote['operador'] = r[0]['usuario_nome']
            else:
                lote['status_producao'] = None
                lote['operador'] = None

        return jsonify({'lotes': lotes})
    except Exception as e:
        app.logger.error('Erro lotes: %s', e)
        return jsonify({'error': str(e)}), 500

@app.route('/api/lotes/<lotcod>/pecas')
def api_pecas(lotcod):
    """Pecas para fabricar de um lote (PC-/CJ-, sem S-).
    Tambem retorna o produto final (S-) para referencia."""
    try:
        # Pecas para fabricar
        sql = """
            SELECT o.ordem, o.ordproduto as codigo, o.ordquanti as quantidade,
                   fs.fsorfase as fase, o.tipoord
            FROM ordem o
            INNER JOIN fasord fs ON fs.fsororde::text = o.ordem::text AND fs.fsorfase = 10
            WHERE o.lotcod = %s
              AND o.ordproduto NOT LIKE 'S-%%'
            ORDER BY o.ordproduto
        """
        pecas = pg_query(sql, (lotcod,))

        # Produto final (S-) para referencia
        sql_final = """
            SELECT o.ordproduto as codigo, o.ordquanti as quantidade
            FROM ordem o
            INNER JOIN fasord fs ON fs.fsororde::text = o.ordem::text AND fs.fsorfase = 10
            WHERE o.lotcod = %s AND o.ordproduto LIKE 'S-%%'
            LIMIT 1
        """
        r = pg_query(sql_final, (lotcod,))
        produto_final = r[0] if r else None

        # Descricao do lote
        sql_lote = "SELECT lotdes, lotdtini, lotdtpre FROM loteprod WHERE lotcod = %s"
        r = pg_query(sql_lote, (lotcod,))
        info = r[0] if r else {}

        # Verificar se ja esta em producao (SQLite)
        r = sqlite_query("SELECT status, usuario_nome FROM serralheria_producao WHERE lote = ? AND status = 'em_producao' LIMIT 1", (lotcod,))
        producao_ativa = r[0] if r else None

        return jsonify({
            'lote': lotcod,
            'descricao': info.get('lotdes', ''),
            'data_abertura': str(info.get('lotdtini', '')) if info.get('lotdtini') else '',
            'data_previsao': str(info.get('lotdtpre', '')) if info.get('lotdtpre') else '',
            'produto_final': produto_final,
            'pecas': pecas,
            'producao_ativa': producao_ativa
        })
    except Exception as e:
        app.logger.error('Erro pecas: %s', e)
        return jsonify({'error': str(e)}), 500

@app.route('/api/usuarios')
def api_usuarios():
    """Lista usuarios ativos da serralheria (serra1-serra9)."""
    try:
        usuarios = sqlite_query("SELECT id, nome, setor FROM serralheria_usuarios WHERE ativo = 1 ORDER BY nome")
        return jsonify({'usuarios': usuarios})
    except Exception as e:
        app.logger.error('Erro usuarios: %s', e)
        return jsonify({'error': str(e)}), 500

@app.route('/api/iniciar', methods=['POST'])
def api_iniciar():
    """Iniciar producao: salva no SQLite local."""
    try:
        data = request.get_json()
        lotcod = data.get('lote')
        usuario_id = data.get('usuario_id')
        usuario_nome = data.get('usuario_nome')
        pecas = data.get('pecas', [])

        if not lotcod or not usuario_id:
            return jsonify({'error': 'Dados obrigatorios: lote, usuario_id'}), 400

        # Salvar producao para cada peca
        for peca in pecas:
            sqlite_execute(
                "INSERT INTO serralheria_producao (ordem_id, lote, produto, usuario_id, usuario_nome, status, data_inicio) VALUES (?, ?, ?, ?, ?, 'em_producao', datetime('now','localtime'))",
                (peca['ordem'], lotcod, peca['codigo'], usuario_id, usuario_nome)
            )

        app.logger.info('Producao iniciada: lote=%s usuario=%s pecas=%d', lotcod, usuario_nome, len(pecas))
        return jsonify({'success': True, 'mensagem': 'Producao iniciada!'})
    except Exception as e:
        app.logger.error('Erro iniciar: %s', e)
        return jsonify({'error': str(e)}), 500

@app.route('/api/finalizar', methods=['POST'])
def api_finalizar():
    """Finalizar producao: muda status no SQLite e EC no ERP (loteprod)."""
    try:
        data = request.get_json()
        lotcod = data.get('lote')

        if not lotcod:
            return jsonify({'error': 'Lote obrigatorio'}), 400

        # Atualiza SQLite
        sqlite_execute(
            "UPDATE serralheria_producao SET status = 'finalizado', data_fim = datetime('now','localtime') WHERE lote = ? AND status = 'em_producao'",
            (lotcod,)
        )

        # Atualiza ERP - muda lotstatus para EC (Encerrado)
        pg_execute("UPDATE loteprod SET lotstatus = 'EC' WHERE lotcod = %s", (lotcod,))
        app.logger.info('Lote %s finalizado -> EC no ERP', lotcod)

        return jsonify({'success': True, 'mensagem': 'Producao finalizada! Lote encerrado no ERP.'})
    except Exception as e:
        app.logger.error('Erro finalizar: %s', e)
        return jsonify({'error': str(e)}), 500


# ── Init DB (garantir tabelas) ──────────────────────────────────────────

def init_sqlite():
    """Cria tabelas se nao existem e insere usuarios serra1-9."""
    conn = get_sqlite()
    try:
        cur = conn.cursor()
        cur.execute("""
            CREATE TABLE IF NOT EXISTS serralheria_usuarios (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                nome TEXT NOT NULL,
                setor TEXT DEFAULT 'Serralheria',
                ativo INTEGER DEFAULT 1
            )
        """)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS serralheria_producao (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                ordem_id INTEGER,
                lote TEXT,
                produto TEXT,
                usuario_id INTEGER,
                usuario_nome TEXT,
                status TEXT DEFAULT 'em_producao',
                data_inicio TEXT,
                data_fim TEXT
            )
        """)
        cur.execute("CREATE INDEX IF NOT EXISTS idx_sp_lote ON serralheria_producao(lote)")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_sp_status ON serralheria_producao(status)")

        # Inserir usuarios serra1-9 se nao existem
        for i in range(1, 10):
            nome = 'serra' + str(i)
            cur.execute("SELECT id FROM serralheria_usuarios WHERE nome = ?", (nome,))
            if not cur.fetchone():
                cur.execute("INSERT INTO serralheria_usuarios (nome, setor, ativo) VALUES (?, 'Serralheria', 1)", (nome,))

        conn.commit()
        print('[OK] Tabelas SQLite verificadas/criadas em ' + SQLITE_PATH)
    finally:
        conn.close()


if __name__ == '__main__':
    init_sqlite()
    print('[TOTEM] Serralheria Totem rodando em http://0.0.0.0:5003')
    app.run(host='0.0.0.0', port=5003, debug=False, threaded=True)