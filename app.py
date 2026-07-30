"""
Sistema de Gerenciamento de Produção SALUTEM
app.py — Ponto de entrada principal v4.2

BANCO DE DADOS:
- MariaDB (MySQL): banco local do sistema. Permite INSERT, UPDATE, DELETE, SELECT
- PostgreSQL: banco do ERP Lógica. SOMENTE LEITURA (SELECT) - nunca modificar

ROTAS PRINCIPAIS:
- / => Dashboard inicial
- /pedidos => Pedidos de Venda do ERP (consulta PostgreSQL)
- /tv => TV Inteligente da Diretoria (rotação automática)
- /kanban => Quadro Kanban
- /gerente => Dashboard gerencial
"""

from flask import Flask, render_template, request, redirect, url_for, flash, session, jsonify
from functools import wraps
from datetime import datetime, timedelta
from collections import defaultdict, OrderedDict, OrderedDict
import time
import re
import sqlite3
import logging
import traceback as _traceback

# =============================================
# Logging estruturado
# =============================================
logging.basicConfig(
    level=logging.INFO,
    format='[%(asctime)s] %(levelname)s %(name)s: %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('app_5002.log', encoding='utf-8')
    ]
)
logger = logging.getLogger('producao')

from config.config import Config
from database.mysql_db import DatabaseMySQL
from database.postgresql_db import DatabasePostgreSQL
from app_apontamentos_tempo import apontamentos_bp

# =============================================
# Inicialização
# =============================================



# =============================================
# Cache de nomes de produtos do ERP (pronome)
# =============================================
_produto_cache = {}

def _load_produto_cache():
    """Carrega nomes reais dos produtos do PostgreSQL."""
    global _produto_cache
    try:
        pg = DatabasePostgreSQL()
        rows = pg.query(
            "SELECT produto, pronome FROM public.produto "
            "WHERE pronome IS NOT NULL AND pronome != ''"
        )
        _produto_cache = {}
        for r in rows:
            cod = str(r.get('produto', '')).strip()
            nome = str(r.get('pronome', '')).strip()
            if cod:
                _produto_cache[cod] = nome[:200]
        print('[OK] Cache de produtos carregado: %d produtos do ERP' % len(_produto_cache))
    except Exception as e:
        print('[WARN] Cache de produtos falhou: %s' % e)

def _get_nome_produto(codigo):
    """Retorna nome real do produto pelo codigo."""
    if not codigo:
        return ''
    return _produto_cache.get(str(codigo).strip(), '')

def _is_sob_medida(codigo):
    """Verifica se o produto codigo termina com -X (sob medida)."""
    if not codigo:
        return False
    c = str(codigo).strip().upper()
    # S-0440-X, CJ-0174-X, qualquer codigo terminado em -X
    return c.endswith('-X')

def _resolver_nome_lote(lote):
    """Resolve nome real para descricao_produto de um lote/OF."""
    desc = lote.get('descricao_produto', '') or ''
    cod = lote.get('codigo_produto', '') or ''
    if not desc or desc.upper().startswith('PRODUCAO DE'):
        nome = _get_nome_produto(cod)
        if nome:
            return nome
    return desc

# Carregar cache na inicializacao
_load_produto_cache()

app = Flask(__name__)
app.config.from_object(Config)
app.config['PERMANENT_SESSION_LIFETIME'] = Config.PERMANENT_SESSION_LIFETIME

db = DatabaseMySQL()

# Migration: adicionar coluna tipo ao estoque_interno
try:
    db.query_one("SELECT tipo FROM estoque_interno LIMIT 1")
except Exception:
    db.execute("ALTER TABLE estoque_interno ADD COLUMN tipo VARCHAR(20) NOT NULL DEFAULT 'fabrica'")

# Migration: garantir que tabela serralheria_usuarios existe (usada pelo totem e admin)
try:
    db.query_one("SELECT id FROM serralheria_usuarios LIMIT 1")
except Exception:
    db.execute("""
        CREATE TABLE IF NOT EXISTS serralheria_usuarios (
            id INT AUTO_INCREMENT PRIMARY KEY,
            nome VARCHAR(100) NOT NULL,
            setor VARCHAR(100) DEFAULT 'Serralheria',
            ativo TINYINT(1) DEFAULT 1
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
    """)

# Operadores da Serralheria — so insere se a tabela estiver vazia
OPERADORES_SERRALHERIA = [
    ('Gabriel',      'CORTE'),
    ('Erivaldo',     'SERRALHERIA'),
    ('Junior',       'CORTE'),
    ('Reverson',     'CORTE'),
    ('José',         'CORTE'),
    ('Juninho',      'CORTE'),
    ('Francisco',    'SOLDA'),
    ('Leonardo',     'SOLDA'),
    ('José Barbosa', 'DOBRA'),
    ('Jhonatas',     'DOBRA'),
]
try:
    total = db.query_one("SELECT COUNT(*) as c FROM serralheria_usuarios")
    if total['c'] == 0:
        for nome, setor in OPERADORES_SERRALHERIA:
            db.execute(
                "INSERT INTO serralheria_usuarios (nome, setor, ativo) VALUES (%s, %s, 1)",
                (nome, setor)
            )
        print('[OK] Operadores serralheria iniciais criados: %d' % len(OPERADORES_SERRALHERIA))
    else:
        print('[OK] Operadores serralheria: %d existentes (preservados)' % total['c'])
except Exception as e:
    print('[WARN] Operadores serralheria: %s' % e)

# Migration: limpar nomes serra* antigos da tabela de producao do totem
try:
    db.execute("UPDATE serralheria_producao SET usuario_nome = 'Operador' WHERE usuario_nome LIKE 'serra%'")
    db.execute("UPDATE serralheria_producao SET usuario_id = NULL WHERE usuario_nome = 'Operador'")
    print('[OK] Nomes serra* limpos da serralheria_producao')
except Exception:
    pass

# Migration: limpar nomes de departamentos com parênteses (ex: "CORTE()" → "CORTE")
try:
    for tabela in ['operacoes_producao', 'kanban_cards']:
        rows = db.query("SELECT id, departamento FROM " + tabela + " WHERE departamento LIKE '%(%)%'")
        for row in rows:
            dept_limpo = re.sub(r'\s*\([^)]*\)\s*$', '', row['departamento']).strip()
            if dept_limpo != row['departamento']:
                db.execute("UPDATE " + tabela + " SET departamento = %s WHERE id = %s", (dept_limpo, row['id']))
except Exception:
    pass

# Registra blueprints
app.register_blueprint(apontamentos_bp)

# =============================================
# Mapeamento de setores ERP → Sistema Local
# =============================================
# Converte nomes de fases do ERP Lógica para os departamentos
# usados pelo sistema de produção local (MySQL).
# Fonte: tabela fases do PostgreSQL (fasnome)
#   1=ALMOXARIFADO, 10=SERRALHERIA, 15=FUNILARIA, 20=PINTURA,
#   30=POLIMENTO, 35=MARCENARIA, 36=COSTURA, 40=TAPECARIA,
#   50=MONTAGEM, 80=EMBALAGEM, 90=USINAGEM, 95=EXPEDIÇÃO
MAPEAMENTO_SETORES = {
    'ALMOXARIFADO': 'ALMOXARIFADO',
    'SERRALHERIA':  'SERRALHERIA',
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
    'CORTE':        'CORTE',
    'SOLDA':        'SOLDA',
}

# =============================================
# Filtros Jinja2
# =============================================

@app.template_filter('formatar_tempo')
def formatar_tempo(segundos):
    """Formata segundos em HH:MM:SS"""
    try:
        seg = int(segundos or 0)
        h = seg // 3600
        m = (seg % 3600) // 60
        s = seg % 60
        return f'{h:02d}:{m:02d}:{s:02d}'
    except Exception:
        return '00:00:00'

@app.template_filter('formatar_data_br')
def formatar_data_br(value):
    """Formata datetime/date para dd/mm/yyyy HH:MM"""
    if not value:
        return '-'
    try:
        if hasattr(value, 'strftime'):
            if hasattr(value, 'hour'):
                return value.strftime('%d/%m/%Y %H:%M')
            return value.strftime('%d/%m/%Y')
        return str(value)
    except Exception:
        return str(value)

@app.template_filter('formatar_data')
def formatar_data(value):
    """Formata date para dd/mm/yyyy"""
    if not value:
        return '-'
    try:
        if hasattr(value, 'strftime'):
            return value.strftime('%d/%m/%Y')
        return str(value)
    except Exception:
        return str(value)

@app.template_filter('formatar_datetime')
def formatar_datetime(value):
    """Formata datetime para dd/mm/yyyy HH:MM:SS"""
    if not value:
        return '-'
    try:
        if hasattr(value, 'strftime'):
            if hasattr(value, 'hour'):
                return value.strftime('%d/%m/%Y %H:%M:%S')
            return value.strftime('%d/%m/%Y')
        return str(value)
    except Exception:
        return str(value)

@app.template_filter('formatar_data_hora_br')
def formatar_data_hora_br(value):
    """Formata datetime para dd/mm/yyyy HH:MM"""
    if not value:
        return '-'
    try:
        if hasattr(value, 'strftime'):
            if hasattr(value, 'hour'):
                return value.strftime('%d/%m/%Y %H:%M')
            return value.strftime('%d/%m/%Y')
        return str(value)
    except Exception:
        return str(value)

# =============================================
# Proteção contra força bruta no login
# Armazena em memória: {ip: {'tentativas': N, 'bloqueado_ate': timestamp}}
# =============================================

_login_attempts = defaultdict(lambda: {'tentativas': 0, 'bloqueado_ate': 0})
MAX_TENTATIVAS  = 5
BLOQUEIO_SEGUNDOS = 600  # 10 minutos

def _get_ip():
    return request.headers.get('X-Forwarded-For', request.remote_addr).split(',')[0].strip()

def _checar_bloqueio(ip):
    dados = _login_attempts[ip]
    if time.time() < dados['bloqueado_ate']:
        restante = int(dados['bloqueado_ate'] - time.time())
        return True, restante
    return False, 0

def _registrar_falha(ip):
    dados = _login_attempts[ip]
    dados['tentativas'] += 1
    if dados['tentativas'] >= MAX_TENTATIVAS:
        dados['bloqueado_ate'] = time.time() + BLOQUEIO_SEGUNDOS
        dados['tentativas'] = 0

def _limpar_tentativas(ip):
    _login_attempts[ip] = {'tentativas': 0, 'bloqueado_ate': 0}

# =============================================
# Decorators
# =============================================

def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if 'usuario_id' not in session:
            flash('Faça login para continuar.', 'warning')
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated

def role_required(*roles):
    def decorator(f):
        @wraps(f)
        def decorated(*args, **kwargs):
            if session.get('usuario_role') not in roles:
                flash('Acesso não autorizado.', 'error')
                return redirect(url_for('dashboard'))
            return f(*args, **kwargs)
        return decorated
    return decorator

# =============================================
# Autenticação
# =============================================

@app.route('/login', methods=['GET', 'POST'])
def login():
    if 'usuario_id' in session:
        return redirect(url_for('dashboard'))

    if request.method == 'POST':
        ip = _get_ip()

        bloqueado, restante = _checar_bloqueio(ip)
        if bloqueado:
            mins = restante // 60
            secs = restante % 60
            flash(f'Muitas tentativas. Tente novamente em {mins}m {secs}s.', 'error')
            return render_template('login.html')

        usuario = request.form.get('usuario', '').strip()
        senha   = request.form.get('senha', '')

        if not usuario or not senha:
            flash('Informe usuário e senha.', 'error')
            return render_template('login.html')

        user = db.verificar_usuario(usuario, senha)

        if user:
            _limpar_tentativas(ip)
            session.permanent = True
            session['usuario_id']          = user['id']
            session['usuario_nome']        = user['nome']
            session['usuario_role']        = user['role']
            session['usuario_departamento']= user.get('nome_departamento', '')
            flash(f'Bem-vindo, {user["nome"]}!', 'success')
            return redirect(url_for('dashboard'))
        else:
            _registrar_falha(ip)
            dados   = _login_attempts[ip]
            restantes = MAX_TENTATIVAS - dados['tentativas']
            if restantes > 0:
                flash(f'Usuário ou senha inválidos. {restantes} tentativa(s) restante(s).', 'error')
            else:
                flash('Conta bloqueada por 10 minutos devido a múltiplas tentativas.', 'error')

    return render_template('login.html')

@app.route('/logout')
def logout():
    session.clear()
    flash('Sessão encerrada.', 'info')
    return redirect(url_for('login'))

# =============================================
# Dashboard — redireciona por role
# =============================================

@app.route('/')
@app.route('/dashboard')
@login_required
def dashboard():
    role = session.get('usuario_role')
    depto = session.get('usuario_departamento', '')

    if role == 'admin':
        return redirect(url_for('admin_dashboard'))
    elif role in ('gerente', 'diretor'):
        return redirect(url_for('dashboard_gerente'))
    elif role == 'pcp':
        return redirect(url_for('dashboard_pcp'))
    elif role == 'almoxarifado':
        return redirect(url_for('dashboard_almoxarifado'))
    elif role == 'almoxarifado_OLD':
        return render_template('almoxarifado/dashboard.html',
                               usuario_nome=session['usuario_nome'])
    elif role in ('operador', 'encarregado'):
        lotes = db.get_lotes_por_departamento(depto)
        stats = db.get_estatisticas_departamento(depto)
        return render_template('operador/dashboard.html',
                               usuario_nome=session['usuario_nome'],
                               usuario_departamento=depto,
                               lotes_departamento=lotes,
                               stats=stats)
    else:
        session.clear()
        flash('Role não reconhecido. Contacte o administrador.', 'error')
        return redirect(url_for('login'))

# =============================================
# Gerente
# =============================================

@app.route('/pedidos')
@login_required
@role_required('admin', 'gerente', 'diretor', 'pcp')
def pedidos_redirect():
    """Tela de Pedidos de Venda do ERP — direto da tabela pedido + empresa."""
    from datetime import date
    status_filtro = request.args.get('status', 'todos')
    busca = request.args.get('busca', '').strip()
    hoje = date.today()

    pedidos_erp = []
    resumo_erp = {
        'total_pedidos':0,'em_aberto':0,'em_producao':0,'vinculados_of':0,
        'atendidos':0,'cancelados':0,'atrasados':0,'proximos_7dias':0,
        'valor_total_faturado':0,'situacao_a':0,'situacao_p':0,'situacao_c':0,'situacao_i':0
    }

    try:
        logger.info('[/pedidos] Conectando ao PostgreSQL (ERP)...')
        pg = DatabasePostgreSQL()

        # Teste de conectividade
        pg.query_one('SELECT 1 AS ok')
        logger.info('[/pedidos] Conexao OK. Buscando resumo KPIs...')

        # Resumo de KPIs direto do ERP
        resumo_erp = pg.get_resumo_pedidos_erp()
        logger.info('[/pedidos] KPIs: total=%s em_aberto=%s em_producao=%s atrasados=%s',
                    resumo_erp.get('total_pedidos'), resumo_erp.get('em_aberto'),
                    resumo_erp.get('em_producao'), resumo_erp.get('atrasados'))

        # Pedidos filtrados do ERP
        pedidos_erp = pg.get_pedidos_erp(
            status=status_filtro,
            busca=busca if busca else None,
            limite=200
        )
        logger.info('[/pedidos] Pedidos retornados: %d (filtro=%s)', len(pedidos_erp), status_filtro)

        # Adicionar dias restantes
        for p in pedidos_erp:
            dp = p.get('data_previsao')
            if dp:
                p['dias_restantes'] = (dp - hoje).days
            else:
                p['dias_restantes'] = None

    except Exception as e:
        logger.error('[/pedidos] ERRO ao buscar dados do ERP: %s', e)
        logger.error('[/pedidos] Traceback: %s', _traceback.format_exc())
        pedidos_erp = []
        # resumo_erp ja tem valores zerados como fallback

    return render_template('pedidos.html',
                           pedidos=pedidos_erp,
                           resumo=resumo_erp,
                           status_filtro=status_filtro,
                           busca=busca,
                           agora=hoje,
                           usuario_nome=session['usuario_nome'])

@app.route('/tv')
@login_required
def tv_redirect():
    """Alias: /tv redireciona para a TV Inteligente da Diretoria."""
    return redirect(url_for('tv_diretoria'))

@app.route('/diretor/gerar-pdf')
@login_required
@role_required('admin', 'gerente', 'diretor')
def gerar_pdf_relatorio():
    """Gera um PDF com a lista de pedidos para comparação com o ERP."""
    try:
        from utils.gerador_pdf_pedidos import gerar_pdf_pedidos
        import os
        filename = f"relatorio_pedidos_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"
        # Garante que a pasta static/relatorios existe
        rel_dir = os.path.join(app.root_path, 'static', 'relatorios')
        os.makedirs(rel_dir, exist_ok=True)
        filepath = os.path.join(rel_dir, filename)
        
        count = gerar_pdf_pedidos(filepath)
        return redirect(url_for('static', filename=f'relatorios/{filename}'))
    except Exception as e:
        logger.error(f"Erro ao gerar PDF: {e}")
        return f"Erro ao gerar relatório: {e}", 500

@app.route('/tv/diretoria')
def tv_diretoria():
    """TV Inteligente da Diretoria — rotação automática com gráficos."""
    from datetime import date
    pedidos_tv = []
    kpis = {}
    hoje = date.today()

    try:
        pg = DatabasePostgreSQL()
        pedidos_tv = pg.get_pedidos_erp_para_tv(limite=50)

        # Adicionar dias restantes
        for p in pedidos_tv:
            dp = p.get('data_previsao')
            if dp:
                p['dias_restantes'] = (dp - hoje).days
            else:
                p['dias_restantes'] = None

        # KPIs
        kpis = pg.get_resumo_pedidos_erp()
    except Exception as e:
        import traceback
        print(f"Erro TV diretoria: {e}")
        traceback.print_exc()

    # NOTA: OPs do MariaDB foram removidas desta tela conforme solicitado.
    # A TV da Diretoria exibe apenas dados de pedidos do ERP (PostgreSQL).

    return render_template('tv_diretoria.html',
                           pedidos=pedidos_tv,
                           kpis=kpis,
                           agora=hoje)

@app.route('/gerente')
@login_required
@role_required('admin', 'gerente', 'diretor')
def dashboard_gerente():
    dados = db.get_dashboard_gerente()
    return render_template('gerente/dashboard.html',
                           usuario_nome=session['usuario_nome'],
                           dados=dados,
                           now=datetime.now())

# =============================================
# Kanban
# =============================================

@app.route('/kanban')
@login_required
def kanban_board():
    role = session.get('usuario_role')
    depto = session.get('usuario_departamento', '')
    departamento_filtro = None if role in ('admin', 'gerente', 'pcp', 'diretor') else depto

    # Verifica se o ERP esta acessivel
    pg_ok = False
    pg_erro = ''
    try:
        pg = DatabasePostgreSQL()
        pg.query_one("SELECT 1")
        pg_ok = True
    except Exception as e:
        pg_erro = str(e)[:120]

    cards = db.get_kanban_cards(departamento=departamento_filtro)
    stats = db.get_kanban_stats(departamento=departamento_filtro)
    concluidos_hoje = db.get_kanban_concluidos_hoje(departamento=departamento_filtro)

    return render_template('kanban/board_profissional.html',
                           cards=cards, stats=stats,
                           concluidos_hoje=concluidos_hoje,
                           usuario_role=role,
                           usuario_departamento=depto,
                           pg_ok=pg_ok, pg_erro=pg_erro)

####@app.route('/kanban/tv')
####@login_required
####@role_required('admin', 'gerente', 'pcp', 'encarregado')
####def kanban_tv():
####    depto = request.args.get('departamento')
####    cards = db.get_kanban_cards(departamento=depto)
####    return render_template('kanban/tv.html', cards=cards, departamento=depto)
@app.route('/kanban/tv')
def kanban_tv():
    depto = request.args.get('departamento')

    # Verifica se o ERP esta acessivel
    pg_ok = False
    pg_erro = ''
    try:
        pg = DatabasePostgreSQL()
        pg.query_one("SELECT 1")
        pg_ok = True
    except Exception as e:
        pg_erro = str(e)[:120]

    cards = db.get_kanban_cards(departamento=depto)
    # Resolve nome real das pecas via PostgreSQL
    for c in cards:
        cod = c.get('cod_peca') or ''
        c['nome_peca'] = _get_nome_produto(cod) if cod else ''
        c['sob_medida'] = _is_sob_medida(cod) or _is_sob_medida(c.get('lote_codigo'))
    return render_template('kanban/tv.html',
                           cards=cards,
                           departamento=depto,
                           pg_ok=pg_ok, pg_erro=pg_erro)

# =============================================
# Kanban por Setor
# =============================================

@app.route('/kanban/setores')
@login_required
@role_required('admin', 'gerente', 'diretor')
def kanban_setores():
    """Kanban visual organizado por setor/departamento."""
    departamentos = db.listar_departamentos(apenas_ativos=True)
    todos_cards = db.get_kanban_cards(departamento=None)

    # Agrupar cards por departamento
    cards_por_setor = {}
    for dept in departamentos:
        cards_por_setor[dept['codigo']] = {
            'info': dept,
            'cards': [],
            'total': 0,
            'em_producao': 0,
            'aguardando': 0,
            'pausados': 0,
            'concluidos': 0,
        }

    for card in todos_cards:
        dept_code = card.get('departamento', '')
        if dept_code in cards_por_setor:
            cards_por_setor[dept_code]['cards'].append(card)
            cards_por_setor[dept_code]['total'] += 1
            etapa = card.get('etapa', '')
            if etapa == 'em_producao':
                cards_por_setor[dept_code]['em_producao'] += 1
            elif etapa in ('aguardando', 'pendente'):
                cards_por_setor[dept_code]['aguardando'] += 1
            elif etapa == 'pausado':
                cards_por_setor[dept_code]['pausados'] += 1
            elif etapa == 'concluido':
                cards_por_setor[dept_code]['concluidos'] += 1

    # KPIs gerais
    kpis = {
        'setores_ativos': sum(1 for s in cards_por_setor.values() if s['total'] > 0),
        'total_cards': len(todos_cards),
        'em_producao': sum(1 for c in todos_cards if c.get('etapa') == 'em_producao'),
        'concluidos_hoje': db.get_kanban_concluidos_hoje(),
    }

    return render_template('kanban/setores.html',
                           cards_por_setor=cards_por_setor,
                           kpis=kpis,
                           usuario_role=session.get('usuario_role'))

# =============================================
# TV Almoxarifado
# =============================================

#@app.route('/tv/almoxarifado')
#@login_required
#@role_required('admin', 'gerente', 'almoxarifado')
#def tv_almoxarifado():
#    lotes       = db.get_lotes_importados_tv()
 #   requisicoes = db.get_requisicoes_pendentes_tv()
 #   stats       = db.get_estatisticas_gerais()
 #   return render_template('tv/almoxarifado.html',
  #                         lotes=lotes, requisicoes=requisicoes,
   #                        stats=stats,
    #                       refresh=Config.TV_REFRESH_INTERVAL)
@app.route('/tv/almoxarifado')
def tv_almoxarifado():
    lotes       = db.get_lotes_importados_tv()
    requisicoes = db.get_requisicoes_pendentes_tv()
    stats       = db.get_estatisticas_gerais()

    return render_template(
        'tv/almoxarifado.html',
        lotes=lotes,
        requisicoes=requisicoes,
        stats=stats,
        refresh=Config.TV_REFRESH_INTERVAL
    )

# =============================================
# PCP
# =============================================

# =============================================
# PCP — Importação ERP
# =============================================

@app.route('/pcp/importar')
@login_required
@role_required('admin', 'gerente', 'pcp', 'diretor')
def pcp_importar_erp():
    pg_ok   = False
    pg_erro = ''
    lotes_erp = []
    lotes_ja_importados = set()

    try:
        pg = DatabasePostgreSQL()
        # Busca lotes do ERP com produto final e maior ordem
        lotes_raw = pg.get_lotes_agrupados_abertos()
        # Para cada lote busca o produto final
        for lote in lotes_raw:
            prod = pg.get_produto_pronto_por_lote(lote['lote_codigo'])
            lote['nome_produto'] = prod.get('nome_produto') if prod else None
            # produto_final_codigo ja vem correto do ordem3, so sobrescreve se pronome foi encontrado
            if prod and prod.get('nome_produto') and prod.get('codigo_produto'):
                lote['produto_final_codigo'] = prod['codigo_produto']
            # busca a maior ordem numerica do lote
            ordens = pg.get_ordens_por_lote(lote['lote_codigo'])
            if ordens:
                lote['maior_ordem'] = max(int(o['ordem']) for o in ordens if o.get('ordem') and str(o['ordem']).isdigit())
            lote['sob_medida'] = _is_sob_medida(lote.get('produto_final_codigo')) or _is_sob_medida(lote.get('lote_codigo'))
        lotes_erp = lotes_raw
        pg_ok = True
    except Exception as e:
        pg_erro = str(e)

    # Lotes já importados no MariaDB
    ja = db.query("SELECT DISTINCT lote_codigo FROM lotes_producao WHERE lote_codigo IS NOT NULL")
    lotes_ja_importados = {r['lote_codigo'] for r in ja}

    return render_template('pcp/importar_erp.html',
                           pg_ok=pg_ok, pg_erro=pg_erro,
                           lotes_erp=lotes_erp,
                           lotes_ja_importados=lotes_ja_importados,
                           now=datetime.now(),
                           usuario_nome=session['usuario_nome'])


@app.route('/pcp/importar_erp', methods=['POST'])
@login_required
@role_required('admin', 'gerente', 'pcp', 'diretor')
def pcp_executar_importacao():
    data  = request.json or {}
    lotes = data.get('lotes', [])
    if not lotes:
        return jsonify({'status':'error','message':'Nenhum lote informado'}), 400

    importados = 0
    atualizados = 0
    erros = []

    try:
        pg = DatabasePostgreSQL()
    except Exception as e:
        return jsonify({'status':'error','message': f'Erro PostgreSQL: {e}'}), 500

    for item in lotes:
        try:
            lote_cod = str(item.get('lote_codigo',''))
            ordem_num = item.get('ordem')
            if not lote_cod:
                continue

            # Verifica se já existe
            existente = db.query_one(
                "SELECT ordem FROM lotes_producao WHERE lote_codigo=%s", (lote_cod,))
            ja_existia = existente is not None

            # Importa lote principal
            db.importar_lote_erp({
                'ordem':             int(ordem_num) if str(ordem_num).isdigit() else 0,
                'lote_codigo':       lote_cod,
                'codigo_produto':    item.get('produto',''),
                'descricao_produto': item.get('nome','') or item.get('produto',''),
                'qtde_ordem':        float(item.get('qtd', 0) or 0),
                'unidade_medida':    'PC',
                'status_erp':        'A',
                'data_previsao_erp': item.get('previsao') or None,
                'data_abertura_erp': item.get('abertura') or None,
                'planejador':        session.get('usuario_nome'),
                'observacoes':       item.get('observacoes') or '',
            })

            lote_ordem_local = int(ordem_num) if str(ordem_num).isdigit() else 0

            # Busca ordens do lote no ERP e importa OFs
            ordens_erp = pg.get_ordens_por_lote(lote_cod)
            for of in ordens_erp:
                of_num = of.get('ordem')
                if not of_num:
                    continue
                db.importar_of({
                    'lote_ordem':       lote_ordem_local,
                    'of_numero':        str(of_num),
                    'codigo_produto':   of.get('produto',''),
                    'descricao_produto': item.get('nome','') or item.get('produto',''),
                    'qtde_ordem':       float(of.get('quantidade') or 0),
                    'unidade_medida':   'PC',
                    'tipo':             'filho' if of.get('nivel_producao','') != '1' else 'pai',
                    'data_previsao':    of.get('data_previsao') or None,
                })

                # Busca processos (operações) de cada OF
                processos = pg.get_processos_ordem(str(of_num))
                for proc in processos:
                    dept_original = (proc.get('nome_departamento') or '').upper().strip()
                    if not dept_original:
                        continue
                    # Limpa parênteses e sujeiras do nome do ERP (ex: "CORTE()" → "CORTE")
                    dept_original = re.sub(r'\s*\([^)]*\)\s*$', '', dept_original).strip()
                    # Mapeia nomes do ERP (fases) para nomes do sistema local
                    dept = MAPEAMENTO_SETORES.get(dept_original, dept_original)
                    # Correcao automatica: se a operacao envolve dobra, forca DOBRA
                    desc_op = (proc.get('descricao_processo') or proc.get('operacao','')).upper()
                    if 'DOBRAR' in desc_op and dept not in ('DOBRA',):
                        dept = 'DOBRA'
                    db.importar_operacao({
                        'of_numero':          str(of_num),
                        'lote_ordem':         lote_ordem_local,
                        'sequencia':          proc.get('numero_sequencial', 0),
                        'fase':               proc.get('fase',''),
                        'descricao_operacao': proc.get('descricao_processo') or proc.get('operacao',''),
                        'departamento':       dept,
                        'codigo_barras':      None,
                    })

                # Sincroniza kanban
                try:
                    db.sincronizar_kanban_com_operacoes(lote_ordem_local)
                except Exception:
                    pass

                # Atualiza departamento_atual baseado na primeira op pendente
                try:
                    db.atualizar_departamento_atual(lote_ordem_local)
                except Exception:
                    pass

            db.add_log(session['usuario_id'], 'importar_erp',
                       f'Lote {lote_cod} importado do ERP', 'lotes_producao', lote_ordem_local)

            if ja_existia:
                atualizados += 1
            else:
                importados += 1

        except Exception as e:
            erros.append(f"{item.get('lote_codigo')}: {e}")

    return jsonify({
        'status':     'success',
        'importados':  importados,
        'atualizados': atualizados,
        'erros':       erros,
    })


@app.route('/pcp')
@login_required
@role_required('admin', 'gerente', 'pcp', 'diretor')
def dashboard_pcp():
    status_f    = request.args.get('status')
    prioridade_f= request.args.get('prioridade')
    lotes = db.get_lotes(status=status_f, prioridade=prioridade_f,
                         pagina=1, por_pagina=200)
    # Resolver nomes reais dos produtos
    for l in lotes:
        l['descricao_produto'] = _resolver_nome_lote(l)
        if not l.get('descricao_produto'):
            l['descricao_produto'] = _get_nome_produto(l.get('codigo_produto'))
        l['sob_medida'] = _is_sob_medida(l.get('codigo_produto')) or _is_sob_medida(l.get('lote_codigo'))
    stats = db.get_estatisticas_gerais()
    departamentos = db.listar_departamentos()

    # Verifica se o ERP esta acessivel e busca observacoes
    pg_ok = False
    pg_erro = ''
    try:
        pg = DatabasePostgreSQL()
        pg.query_one("SELECT 1")
        pg_ok = True
        # Busca observacoes (lottrans) do ERP para os lotes exibidos
        if lotes:
            codigos = [l.get('lote_codigo') for l in lotes if l.get('lote_codigo')]
            if codigos:
                ph = ','.join(['%s'] * len(codigos))
                obs_rows = pg.query(
                    f"SELECT lotcod, NULLIF(TRIM(lottrans),'') AS obs FROM loteprod WHERE lotcod IN ({ph})",
                    codigos
                )
                obs_map = {r['lotcod']: r['obs'] for r in obs_rows if r.get('obs')}
                for l in lotes:
                    if not l.get('observacoes') and obs_map.get(l.get('lote_codigo')):
                        l['observacoes'] = obs_map[l['lote_codigo']]
    except Exception as e:
        pg_erro = str(e)[:120]

    return render_template('pcp/dashboard.html',
                           lotes=lotes, stats=stats,
                           departamentos=departamentos,
                           usuario_nome=session['usuario_nome'],
                           pg_ok=pg_ok, pg_erro=pg_erro,
                           now=datetime.now())

# =============================================
# Almoxarifado
# =============================================

@app.route('/almoxarifado')
@login_required
@role_required('admin', 'gerente', 'almoxarifado', 'diretor')
def dashboard_almoxarifado():
    requisicoes = db.get_requisicoes(status='pendente')
    aprovadas_hoje = db.count_requisicoes_aprovadas_hoje()
    return render_template('almoxarifado/dashboard.html',
                           requisicoes=requisicoes,
                           aprovadas_hoje=aprovadas_hoje,
                           usuario_nome=session['usuario_nome'],
                           now=datetime.now())

@app.route('/almoxarifado/estoque')
@login_required
@role_required('admin', 'almoxarifado')
def estoque_interno():
    return render_template('almoxarifado/estoque.html',
                           usuario_nome=session['usuario_nome'])

# =============================================
# Operador
# =============================================

@app.route('/operador')
@login_required
@role_required('operador', 'encarregado', 'admin')
def dashboard_operador():
    depto = session.get('usuario_departamento', '')
    lotes = db.get_lotes_por_departamento(depto)
    stats = db.get_estatisticas_departamento(depto)
    return render_template('operador/dashboard.html',
                           lotes_departamento=lotes, stats=stats,
                           usuario_nome=session['usuario_nome'],
                           usuario_departamento=depto)

# =============================================
# Admin
# =============================================

@app.route('/admin')
@login_required
@role_required('admin')
def admin_dashboard():
    usuarios  = db.listar_usuarios()
    stats     = db.get_estatisticas_gerais()
    dados_ger = db.get_dashboard_gerente()
    logs      = db.get_logs(limit=8)
    return render_template('admin/dashboard.html',
                           usuarios=usuarios, stats=stats,
                           dados_ger=dados_ger, logs=logs,
                           usuario_nome=session['usuario_nome'],
                           now=datetime.now())

@app.route('/admin/usuarios/')
@app.route('/admin/usuarios')
@login_required
@role_required('admin')
def admin_usuarios():
    """Lista todos os usuários em página dedicada."""
    usuarios = db.listar_usuarios()
    departamentos = db.listar_departamentos()
    # Busca operadores do totem
    totem_users = db.query("SELECT id, nome, setor, ativo FROM serralheria_usuarios ORDER BY nome")
    return render_template('admin/usuarios.html',
                           usuarios=usuarios,
                           departamentos=departamentos,
                           roles=Config.ROLES,
                           totem_users=totem_users,
                           usuario_nome=session['usuario_nome'])

@app.route('/admin/usuarios/novo', methods=['GET', 'POST'])
@login_required
@role_required('admin')
def admin_novo_usuario():
    departamentos = db.listar_departamentos()
    if request.method == 'POST':
        dados = {
            'usuario':             request.form['usuario'],
            'nome':                request.form['nome'],
            'senha':               request.form['senha'],
            'role':                request.form['role'],
            'nome_departamento':   request.form.get('nome_departamento'),
            'departamento_codigo': request.form.get('departamento_codigo'),
        }
        try:
            db.criar_usuario(dados)
            db.add_log(session['usuario_id'], 'criar_usuario', f"Usuário {dados['usuario']} criado")
            flash('Usuário criado com sucesso!', 'success')
            return redirect(url_for('admin_dashboard'))
        except Exception as e:
            flash(f'Erro ao criar usuário: {e}', 'error')
    return render_template('admin/usuarios_form.html',
                           departamentos=departamentos, roles=Config.ROLES)

@app.route('/admin/usuarios/<int:user_id>/editar', methods=['GET', 'POST'])
@login_required
@role_required('admin')
def admin_editar_usuario(user_id):
    usuario = db.get_usuario_por_id(user_id)
    if not usuario:
        flash('Usuário não encontrado.', 'error')
        return redirect(url_for('admin_dashboard'))
    departamentos = db.listar_departamentos()
    if request.method == 'POST':
        dados = {
            'nome':                request.form['nome'],
            'role':                request.form['role'],
            'nome_departamento':   request.form.get('nome_departamento'),
            'departamento_codigo': request.form.get('departamento_codigo'),
            'ativo':               int(request.form.get('ativo', 1)),
            'senha':               request.form.get('senha') or None,
        }
        try:
            db.atualizar_usuario(user_id, dados)
            db.add_log(session['usuario_id'], 'editar_usuario', f"Usuário {user_id} atualizado")
            flash('Usuário atualizado!', 'success')
            return redirect(url_for('admin_dashboard'))
        except Exception as e:
            flash(f'Erro: {e}', 'error')
    return render_template('admin/usuarios_form.html',
                           usuario=usuario, departamentos=departamentos, roles=Config.ROLES)

@app.route('/admin/usuarios/<int:user_id>/deletar', methods=['POST'])
@login_required
@role_required('admin')
def admin_deletar_usuario(user_id):
    if user_id == session['usuario_id']:
        flash('Você não pode deletar seu próprio usuário.', 'error')
        return redirect(url_for('admin_dashboard'))
    db.deletar_usuario(user_id)
    db.add_log(session['usuario_id'], 'deletar_usuario', f"Usuário {user_id} deletado")
    flash('Usuário removido.', 'success')
    return redirect(url_for('admin_dashboard'))

# =============================================
# Operadores do Totem (serralheria_usuarios)
# =============================================

@app.route('/api/totem/usuarios', methods=['GET'])
@login_required
@role_required('admin')
def api_totem_usuarios():
    usuarios = db.query("SELECT id, nome, setor, ativo FROM serralheria_usuarios ORDER BY nome")
    return jsonify(usuarios)

@app.route('/api/totem/usuarios/<int:uid>', methods=['PUT'])
@login_required
@role_required('admin')
def api_totem_usuario_editar(uid):
    data = request.get_json()
    nome = data.get('nome', '').strip()
    setor = data.get('setor', '').strip()
    if not nome:
        return jsonify({'error': 'Nome obrigatório'}), 400
    db.execute(
        "UPDATE serralheria_usuarios SET nome=%s, setor=%s WHERE id=%s",
        (nome, setor, uid)
    )
    return jsonify({'status': 'success'})

@app.route('/api/totem/usuarios/<int:uid>/toggle', methods=['POST'])
@login_required
@role_required('admin')
def api_totem_usuario_toggle(uid):
    db.execute(
        "UPDATE serralheria_usuarios SET ativo = IF(ativo=1, 0, 1) WHERE id=%s",
        (uid,)
    )
    row = db.query_one("SELECT ativo FROM serralheria_usuarios WHERE id=%s", (uid,))
    return jsonify({'status': 'success', 'ativo': row['ativo'] if row else 0})

@app.route('/api/totem/usuarios', methods=['POST'])
@login_required
@role_required('admin')
def api_totem_usuario_criar():
    data = request.get_json()
    nome = data.get('nome', '').strip()
    setor = data.get('setor', 'Serralheria').strip()
    if not nome:
        return jsonify({'error': 'Nome obrigatório'}), 400
    db.execute(
        "INSERT INTO serralheria_usuarios (nome, setor, ativo) VALUES (%s, %s, 1)",
        (nome, setor)
    )
    return jsonify({'status': 'success'})

@app.route('/api/totem/usuarios/<int:uid>', methods=['DELETE'])
@login_required
@role_required('admin')
def api_totem_usuario_deletar(uid):
    db.execute("DELETE FROM serralheria_usuarios WHERE id=%s", (uid,))
    return jsonify({'status': 'success'})

# =============================================
# RELATORIOS (admin, gerente, pcp, diretor)
# =============================================

@app.route('/admin/relatorios')
@login_required
@role_required('admin', 'gerente', 'pcp', 'diretor')
def admin_relatorios():
    """Pagina de relatorios completa."""
    dados_ger = db.get_dashboard_gerente()
    lotes_atrasados = db.get_relatorio_lotes_atrasados()
    serralheria = db.get_relatorio_serralheria_resumo()
    producao_30d = db.get_relatorio_producao_30_dias()
    usuarios = db.listar_usuarios()
    kpis = dados_ger.get('kpis', {}) if dados_ger else {}
    return render_template('relatorios.html',
                           dados_ger=dados_ger,
                           k=kpis,
                           lotes_atrasados=lotes_atrasados,
                           serralheria=serralheria,
                           producao_30d=producao_30d,
                           usuarios=usuarios,
                           usuario_nome=session.get('usuario_nome', ''),
                           now=datetime.now(),
                           data_30d=(datetime.now() - timedelta(days=30)).strftime('%Y-%m-%d'))

@app.route('/api/relatorios/producao_periodo', methods=['GET'])
@login_required
@role_required('admin', 'gerente', 'pcp', 'diretor')
def api_relatorio_producao_periodo():
    """API: producao finalizada por periodo (AJAX)."""
    di = request.args.get('data_inicio', '')
    df = request.args.get('data_fim', '')
    if not di or not df:
        return jsonify({'error': 'Informe data_inicio e data_fim'}), 400
    try:
        kpis = db.get_relatorio_producao_periodo_kpis(di, df)
        lotes = db.get_relatorio_producao_periodo(di, df)
        return jsonify({
            'kpis': {k: int(v or 0) for k, v in kpis.items()},
            'lotes': [{k: (str(v) if isinstance(v, (datetime, timedelta)) else v) for k, v in r.items()} for r in lotes],
            'total': len(lotes)
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/relatorios/serralheria_periodo', methods=['GET'])
@login_required
@role_required('admin', 'gerente', 'pcp', 'diretor')
def api_relatorio_serralheria_periodo():
    """API: producao serralheria por periodo (AJAX)."""
    di = request.args.get('data_inicio', '')
    df = request.args.get('data_fim', '')
    if not di or not df:
        return jsonify({'error': 'Informe data_inicio e data_fim'}), 400
    try:
        rows = db.get_relatorio_serralheria_periodo(di, df)
        result = []
        for r in rows:
            result.append({k: (str(v) if isinstance(v, (datetime, timedelta)) else v) for k, v in r.items()})
        return jsonify({'dados': result, 'total': len(result)})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/relatorios/tempo_producao', methods=['GET'])
@login_required
@role_required('admin', 'gerente', 'pcp', 'diretor')
def api_relatorio_tempo_producao():
    """API: tempo medio de fabricacao por peca+setor."""
    try:
        rows = db.get_tempo_medio_producao()
        # Converte Row para dict e formata tempos
        dados = []
        for r in rows:
            d = dict(r)
            med = float(d.get('tempo_medio_min', 0) or 0)
            d['tempo_medio_fmt'] = _formatar_minutos(med)
            d['tempo_min_fmt'] = _formatar_minutos(float(d.get('tempo_min_min', 0) or 0))
            d['tempo_max_fmt'] = _formatar_minutos(float(d.get('tempo_max_min', 0) or 0))
            dados.append(d)
        # Ordena por tempo medio decrescente
        dados.sort(key=lambda x: float(x.get('tempo_medio_min', 0) or 0), reverse=True)
        return jsonify({'dados': dados, 'total': len(dados)})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

def _formatar_minutos(minutos):
    """Formata minutos para string legivel: '1h 23min' ou '45min'."""
    m = float(minutos)
    if m <= 0:
        return '—'
    h = int(m // 60)
    mi = int(round(m % 60))
    if h > 0 and mi > 0:
        return str(h) + 'h ' + str(mi) + 'min'
    if h > 0:
        return str(h) + 'h'
    return str(mi) + 'min'

# =============================================
# DIRETOR / GERENTE VIEWS
# Diretor — Relatórios, Logs, Métricas (somente leitura)
# =============================================

@app.route('/diretor/relatorios')
@login_required
@role_required('admin', 'gerente', 'diretor')
def diretor_relatorios():
    """Visão Geral da Diretoria — Pedidos de Venda do ERP + métricas locais."""
    from datetime import date, timedelta
    stats = db.get_estatisticas_gerais()
    dados_ger = db.get_dashboard_gerente()
    hoje = datetime.now().date()

    # ── ERP: pedidos de venda (substitui get_lotes_agrupados_abertos) ──
    resumo_erp = {
        'total_pedidos': 0, 'em_aberto': 0, 'em_producao': 0,
        'atrasados': 0, 'proximos_7dias': 0, 'atendidos': 0,
        'cancelados': 0, 'valor_total_faturado': 0,
        'situacao_a': 0, 'situacao_p': 0, 'situacao_c': 0, 'situacao_i': 0
    }
    pedidos_erp = []
    try:
        pg = DatabasePostgreSQL()
        resumo_erp = pg.get_resumo_pedidos_erp()
        pedidos_erp = pg.get_pedidos_erp(status='todos', limite=200)
        # Adicionar dias_restantes a cada pedido
        for p in pedidos_erp:
            dp = p.get('data_previsao')
            if dp:
                p['dias_restantes'] = (dp - hoje).days
            else:
                p['dias_restantes'] = None
    except Exception as e:
        import traceback
        print(f"Erro ERP pedidos (diretor/relatorios): {e}")
        traceback.print_exc()

    usuarios = db.listar_usuarios()
    return render_template('diretor/relatorios.html',
                           stats=stats, dados_ger=dados_ger,
                           resumo_erp=resumo_erp,
                           pedidos_erp=pedidos_erp,
                           usuarios=usuarios,
                           usuario_nome=session['usuario_nome'],
                           now=hoje)

@app.route('/diretor/logs')
@login_required
@role_required('admin', 'diretor')
def diretor_logs():
    """Logs de ações do sistema."""
    logs = db.get_logs(limit=200)
    return render_template('diretor/logs.html',
                           logs=logs,
                           usuario_nome=session['usuario_nome'])

@app.route('/diretor/acessos')
@login_required
@role_required('admin', 'diretor')
def diretor_acessos():
    """Últimos acessos dos usuários."""
    usuarios = db.listar_usuarios()
    return render_template('diretor/acessos.html',
                           usuarios=usuarios,
                           usuario_nome=session['usuario_nome'])

# =============================================
# APIs REST
# =============================================

@app.route('/operador/lote/<int:ordem>')
@login_required
@role_required('operador', 'encarregado', 'admin', 'gerente', 'pcp', 'diretor')
def operador_lote_detalhe(ordem):
    lote = db.get_lote_por_ordem(ordem)
    if not lote:
        flash('Lote não encontrado.', 'error')
        return redirect(url_for('dashboard_operador'))
    depto = session.get('usuario_departamento', '')
    return render_template('operador/lote_detalhe.html',
                           lote=lote,
                           departamento=depto,
                           usuario_nome=session.get('usuario_nome'))

@app.route('/admin/lote/<int:ordem>')
@login_required
@role_required('admin', 'gerente', 'pcp', 'diretor')
def admin_lote_detalhe(ordem):
    lote = db.get_lote_por_ordem(ordem)
    if not lote:
        flash('Lote nao encontrado.', 'error')
        return redirect(url_for('dashboard_pcp'))
    lote['sob_medida'] = _is_sob_medida(lote.get('codigo_produto')) or _is_sob_medida(lote.get('lote_codigo'))
    operacoes = db.get_operacoes_por_lote(ordem)
    ofs = db.get_ofs_por_lote(ordem)
    return render_template('admin/lote_detalhe.html',
                           lote=lote,
                           operacoes=operacoes or [],
                           ofs=ofs or [],
                           now=datetime.now(),
                           usuario_nome=session.get('usuario_nome'))

@app.route('/api/lotes')
@login_required
def api_lotes():
    role  = session.get('usuario_role')
    depto = session.get('usuario_departamento', '')
    status_filtro = request.args.get('status')  # aceita 'importado,liberado' (multi)
    depto_filtro  = None if role in ('admin', 'gerente', 'pcp', 'diretor') else depto
    # suporte a múltiplos status separados por vírgula
    if status_filtro and ',' in status_filtro:
        lotes_all = []
        for st in status_filtro.split(','):
            lotes_all += db.get_lotes(status=st.strip(), departamento=depto_filtro)
        lotes = lotes_all
    else:
        lotes = db.get_lotes(status=status_filtro, departamento=depto_filtro)
    return jsonify({'status': 'success', 'data': lotes})

@app.route('/api/requisicoes/pendentes')
def api_requisicoes_pendentes():
    reqs = db.get_requisicoes(status='pendente')
    return jsonify({'status': 'success', 'data': reqs})

@app.route('/api/lotes/<int:ordem>')
@login_required
def api_lote_detalhe(ordem):
    lote = db.get_lote_por_ordem(ordem)
    if not lote:
        return jsonify({'status': 'error', 'message': 'Lote não encontrado'}), 404
    return jsonify({'status': 'success', 'data': lote})

@app.route('/api/lotes/<int:ordem>/prioridade', methods=['POST'])
@login_required
@role_required('admin', 'gerente', 'pcp', 'diretor')
def api_alterar_prioridade_lote(ordem):
    data = request.json or {}
    prioridade = data.get('prioridade')
    if prioridade not in ('urgente', 'alta', 'media', 'baixa'):
        return jsonify({'status': 'error', 'message': 'Prioridade inválida'}), 400
    ok = db.atualizar_prioridade_lote(ordem, prioridade)
    if ok:
        db.add_log(session['usuario_id'], 'alterar_prioridade',
                   f'OP #{ordem} → {prioridade}', 'lotes', ordem)
    return jsonify({'status': 'success' if ok else 'error'})

@app.route('/api/lotes/<int:ordem>/status', methods=['POST'])
@login_required
@role_required('admin', 'gerente', 'pcp', 'diretor')
def api_alterar_status_lote(ordem):
    data   = request.json or {}
    status = data.get('status')
    validos = ('importado', 'liberado', 'em_producao', 'finalizado', 'cancelado')
    if status not in validos:
        return jsonify({'status': 'error', 'message': 'Status inválido'}), 400

    if status == 'cancelado':
        # Cancelar = volta para importado + limpa producoes em andamento
        db.execute(
            "UPDATE operacoes_producao SET status = 'pendente', "
            "usuario_inicio_id = NULL, data_inicio = NULL, usuario_fim_id = NULL, data_fim = NULL "
            "WHERE lote_ordem = %s AND status IN ('em_andamento','pausado')", (ordem,)
        )
        db.execute(
            "UPDATE serralheria_producao SET status = 'cancelado', data_fim = NOW() "
            "WHERE lote_ordem = %s AND status = 'em_producao'", (ordem,)
        )
        db.execute(
            "DELETE FROM kanban_cards WHERE lote_ordem = %s", (ordem,)
        )
        db.atualizar_status_lote(ordem, 'importado', session['usuario_id'])
    else:
        ok = db.atualizar_status_lote(ordem, status, session['usuario_id'])

    db.add_log(session['usuario_id'], 'alterar_status',
               f'OP #{ordem} → {status}', 'lotes', ordem)
    # Baixa automatica no estoque da fabrica quando OF e liberada
    if status == 'liberado':
        _baixar_estoque_por_of(ordem)
    # Atualiza departamento_atual ao mudar status
    try:
        db.atualizar_departamento_atual(ordem)
    except Exception:
        pass
    return jsonify({'status': 'success'})

# =============================================
# APIs — ALMOXARIFADO (separação de OPs)
# =============================================

def _baixar_estoque_por_of(ordem):
    """Busca materiais da OF no ERP e da baixa automatica no estoque da fabrica."""
    try:
        pg = DatabasePostgreSQL()
        materiais = pg.get_requisicoes_ordem(ordem)
        if not materiais:
            return
        for mat in materiais:
            codigo = str(mat.get('produto') or mat.get('reqproduto') or '')
            if not codigo:
                continue
            qtd = float(mat.get('quantidade') or mat.get('rqoquanti') or 0)
            if qtd <= 0:
                continue
            item = db.get_estoque_por_codigo(codigo, tipo='fabrica')
            if item and item['qtd_atual'] > 0:
                db.registrar_baixa_estoque(codigo, qtd, ordem, 'liberacao_of', tipo='fabrica')
                print(f"[ESTOQUE] Baixa fabrica: {codigo} -{qtd} (OP #{ordem})")
    except Exception as e:
        print(f"[ESTOQUE] Erro ao baixar estoque da OP #{ordem}: {e}")

# =============================================
# APIs — ESTOQUE INTERNO
# =============================================

@app.route('/api/estoque', methods=['GET'])
@login_required
@role_required('admin', 'gerente', 'almoxarifado', 'diretor')
def api_estoque_listar():
    filtro = request.args.get('filtro')
    tipo = request.args.get('tipo')
    itens = db.get_estoque_interno(status_filtro=filtro, tipo=tipo)
    kpis = db.get_estoque_kpis(tipo=tipo)
    return jsonify({'status': 'success', 'itens': itens, 'kpis': kpis})

@app.route('/api/estoque', methods=['POST'])
@login_required
@role_required('admin', 'almoxarifado')
def api_estoque_adicionar():
    dados = request.json or {}
    if not dados.get('codigo') or not dados.get('descricao'):
        return jsonify({'status': 'error', 'message': 'Código e descrição obrigatórios'}), 400
    db.adicionar_estoque(dados)
    # Registrar movimentação de entrega
    item = db.get_estoque_por_codigo(dados['codigo'])
    if item:
        sql_hist = """INSERT INTO estoque_movimentacao (item_estoque_id, tipo, quantidade, usuario_id, observacao)
                      VALUES (%s, 'reposicao', %s, %s, 'Entrega de material na fabrica')"""
        db.execute(sql_hist, [item['id'], float(dados.get('qtd_atual', 0)), session.get('usuario_id')])
    db.add_log(session.get('usuario_id'), 'adicionar_estoque',
               f'Item {dados["codigo"]} entregue na fabrica', 'estoque_interno', None)
    return jsonify({'status': 'success'})

@app.route('/api/estoque/<int:item_id>/repor', methods=['POST'])
@login_required
@role_required('admin', 'almoxarifado')
def api_estoque_repor(item_id):
    dados = request.json or {}
    nova_qtd = dados.get('qtd')
    if nova_qtd is None or float(nova_qtd) < 0:
        return jsonify({'status': 'error', 'message': 'Quantidade inválida'}), 400
    db.repor_estoque(item_id, float(nova_qtd))
    # Registra movimentação
    sql_hist = """INSERT INTO estoque_movimentacao (item_estoque_id, tipo, quantidade, usuario_id, observacao)
                  VALUES (%s, 'reposicao', %s, %s, 'Reposição manual')"""
    db.execute(sql_hist, [item_id, float(nova_qtd), session.get('usuario_id')])
    db.add_log(session.get('usuario_id'), 'repor_estoque',
               f'Item #{item_id} reposto para {nova_qtd}', 'estoque_interno', item_id)
    return jsonify({'status': 'success'})

@app.route('/api/estoque/<int:item_id>', methods=['PUT'])
@login_required
@role_required('admin', 'almoxarifado')
def api_estoque_atualizar(item_id):
    dados = request.json or {}
    db.atualizar_estoque(item_id, dados)
    return jsonify({'status': 'success'})

@app.route('/api/estoque/<int:item_id>/toggle-usuario', methods=['POST'])
@login_required
@role_required('admin', 'almoxarifado')
def api_estoque_toggle_usuario(item_id):
    """Ativa/desativa controle por usuario em um item de estoque."""
    dados = request.json or {}
    ativo = dados.get('ativo', False)
    db.toggle_controlado_por_usuario(item_id, ativo)
    return jsonify({'status': 'success'})

@app.route('/api/usuarios', methods=['GET'])
@login_required
def api_listar_usuarios():
    """Retorna lista de usuarios ativos para dropdowns."""
    usuarios = db.listar_usuarios()
    return jsonify({'status': 'success', 'usuarios': usuarios})

@app.route('/api/estoque/movimentacao', methods=['GET'])
@login_required
@role_required('admin', 'gerente', 'almoxarifado', 'diretor')
def api_estoque_movimentacao():
    movs = db.get_movimentacao_estoque(limite=100)
    return jsonify({'status': 'success', 'movimentacoes': movs})

@app.route('/api/erp/produto/<codigo>', methods=['GET'])
@login_required
@role_required('admin', 'almoxarifado', 'pcp')
def api_buscar_produto_erp(codigo):
    """Busca produto no ERP pelo codigo para auto-preencher descricao."""
    try:
        pg = DatabasePostgreSQL()
        produto = pg.buscar_produto_por_codigo(codigo)
        if produto:
            return jsonify({'status': 'success', 'produto': produto})
        return jsonify({'status': 'not_found', 'message': 'Produto nao encontrado no ERP'})
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500

@app.route('/api/almoxarifado/materiais-pendentes')
@login_required
@role_required('admin', 'gerente', 'almoxarifado')
def api_materiais_pendentes():
    """Materiais necessarios para OFs liberadas, filtrando peças fabricadas (so materiais brutos)."""
    lotes = db.get_lotes_liberados_pendentes()
    if not lotes:
        return jsonify({'status': 'success', 'ofs': []})
    ordens = [l['ordem'] for l in lotes]
    try:
        pg = DatabasePostgreSQL()
        materiais_erp = pg.get_requisicoes_multiplas_ordens(ordens)
    except Exception:
        materiais_erp = []

    # Pega todos os codigo_produto das OFs ativas para excluir peças fabricadas do BOM
    codigos_fabricados = db.get_codigos_produtos_ofs_ativas()

    mats_por_of = {}
    for m in materiais_erp:
        of_num = m.get('ordem')
        if of_num not in mats_por_of:
            mats_por_of[of_num] = []
        mats_por_of[of_num].append(m)
    todos_codigos = list(set(str(m.get('produto') or '') for m in materiais_erp if m.get('produto')))

    # Estoque: prioridade SQLite ERP (mesmo dado do TV), fallback estoque_interno
    sqlite_map = {}
    try:
        SQLITE_PATH = "/opt/painel_estoque/estoque.db"
        conn = sqlite3.connect(SQLITE_PATH)
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()
        ph = ','.join(['?'] * len(todos_codigos))
        cur.execute(
            "SELECT TRIM(codigo) as codigo, saldo_atual, descricao "
            "FROM produtos WHERE TRIM(codigo) IN (%s)" % ph,
            todos_codigos
        )
        for r in cur.fetchall():
            cod = str(r['codigo']).strip()
            sqlite_map[cod] = {
                'qtd_atual': float(r['saldo_atual'] or 0),
                'descricao': (r['descricao'] or '')[:80]
            }
        conn.close()
    except Exception as e:
        print('[ERRO] SQLite estoque (materiais-pendentes): %s' % e)

    estoque_map = {}
    for cod in todos_codigos:
        # Se tem saldo no ERP (SQLite), usa esse
        if cod in sqlite_map and sqlite_map[cod]['qtd_atual'] > 0:
            estoque_map[cod] = sqlite_map[cod]
        else:
            # Fallback: estoque_interno (MariaDB)
            item = db.get_estoque_por_codigo(cod, tipo='almoxarifado')
            if item:
                estoque_map[cod] = item
    resultado = []
    for lote in lotes:
        mats = mats_por_of.get(lote['ordem'], [])
        mats_com = []
        for m in mats:
            cod = str(m.get('produto') or '')
            # Pula peças que são fabricadas em outras OFs (ex: alça, suporte, etc.)
            if cod in codigos_fabricados:
                continue
            est = estoque_map.get(cod)
            mats_com.append({
                'codigo': cod,
                'descricao': m.get('descricao') or '',
                'unidade': m.get('unidade') or 'UN',
                'qtd_necessaria': float(m.get('quantidade') or 0),
                'tem_no_estoque': est is not None and est['qtd_atual'] > 0,
                'qtd_disponivel': float(est['qtd_atual']) if est else 0
            })
        # So inclui a OF se tiver materiais brutos
        if mats_com:
            resultado.append({
                'ordem': lote['ordem'],
                'produto': lote.get('descricao_produto') or lote.get('lote_descricao') or '',
                'quantidade': lote.get('quantidade'),
                'prioridade': lote.get('prioridade'),
                'departamento': lote.get('departamento'),
                'materiais': mats_com
            })
    return jsonify({'status': 'success', 'ofs': resultado})

@app.route('/api/estoque/<int:item_id>/separar-fabrica', methods=['POST'])
@login_required
@role_required('admin', 'almoxarifado')
def api_separar_fabrica(item_id):
    dados = request.json or {}
    qtd = float(dados.get('qtd', 0))
    operador_id = dados.get('operador_id')
    if operador_id:
        operador_id = int(operador_id)
    else:
        operador_id = None
    if qtd <= 0:
        return jsonify({'status': 'error', 'message': 'Quantidade invalida'}), 400
    ok = db.mover_estoque_para_fabrica(item_id, qtd, session.get('usuario_id'), operador_id=operador_id)
    if ok:
        db.add_log(session.get('usuario_id'), 'separar_fabrica',
                   f'Item #{item_id} separado para fabrica' + (f' (operador #{operador_id})' if operador_id else ''), 'estoque_interno', item_id)
    return jsonify({'status': 'success' if ok else 'error'})

@app.route('/api/lotes/<int:ordem>/separando', methods=['POST'])
@login_required
@role_required('admin', 'gerente', 'almoxarifado')
def api_marcar_separando(ordem):
    ok = db.marcar_separacao_lote(ordem, 'separando', session['usuario_id'])
    if ok:
        db.add_log(session['usuario_id'], 'marcar_separando',
                   f'OP #{ordem} marcada como SEPARANDO pelo almoxarifado', 'lotes', ordem)
    return jsonify({'status': 'success' if ok else 'error'})

@app.route('/api/lotes/<int:ordem>/separar', methods=['POST'])
@login_required
@role_required('admin', 'gerente', 'almoxarifado')
def api_marcar_separado(ordem):
    ok = db.marcar_separacao_lote(ordem, 'separado', session['usuario_id'])
    if ok:
        db.add_log(session['usuario_id'], 'marcar_separado',
                   f'OP #{ordem} marcada como SEPARADA pelo almoxarifado', 'lotes', ordem)
    return jsonify({'status': 'success' if ok else 'error'})

@app.route('/api/lotes/<int:ordem>/entregar', methods=['POST'])
@login_required
@role_required('admin', 'gerente', 'almoxarifado')
def api_marcar_entregue(ordem):
    ok = db.marcar_separacao_lote(ordem, 'entregue', session['usuario_id'])
    if ok:
        db.add_log(session['usuario_id'], 'marcar_entregue',
                   f'OP #{ordem} marcada como ENTREGUE ao setor', 'lotes', ordem)
    return jsonify({'status': 'success' if ok else 'error'})

@app.route('/api/lotes/<int:ordem>/separar-componentes', methods=['POST'])
@login_required
@role_required('admin', 'gerente', 'almoxarifado')
def api_separar_componentes(ordem):
    """Marca componentes específicos como separados para uma OP."""
    data = request.get_json(force=True) or {}
    codigos = data.get('codigos', [])
    if not codigos:
        return jsonify({'status': 'error', 'msg': 'Nenhum componente selecionado'})
    try:
        db.criar_tabela_separacao_componentes()
        ok = db.set_separacao_componentes(ordem, codigos, session.get('usuario_id'))
        if ok:
            db.add_log(session['usuario_id'], 'separar_componentes',
                       f'{len(codigos)} componente(s) separado(s) na OP #{ordem}', 'lotes', ordem)
            # Verifica se OP deve mudar para separando
            db.marcar_separacao_lote(ordem, 'separando', session['usuario_id'])
        return jsonify({'status': 'success' if ok else 'error'})
    except Exception as e:
        return jsonify({'status': 'error', 'msg': str(e)}), 500

@app.route('/api/lotes/<int:ordem>/finalizar-separacao', methods=['POST'])
@login_required
@role_required('admin', 'gerente', 'almoxarifado')
def api_finalizar_separacao(ordem):
    """Finaliza separacao de uma OP: marca componentes selecionados como separados.
    So muda para 'separado' se TODOS os componentes estiverem separados."""
    data = request.get_json(force=True) or {}
    codigos = data.get('codigos', [])
    try:
        db.criar_tabela_separacao_componentes()
        # Marca os componentes selecionados como separados
        if codigos:
            db.set_separacao_componentes(ordem, codigos, session.get('usuario_id'))
        # Verifica se TODOS os componentes ja estao separados
        todos = db.get_separacao_componentes(ordem)
        total = len(todos)
        separados = sum(1 for c in todos if c['status'] == 'separado')
        if total > 0 and separados >= total:
            # Todos separados -> muda para separado
            ok = db.marcar_separacao_lote(ordem, 'separado', session['usuario_id'])
            db.add_log(session['usuario_id'], 'finalizar_separacao',
                       'OP #%s finalizada como SEPARADO (todos %d componentes)' % (ordem, total), 'lotes', ordem)
        else:
            # Ainda faltam componentes -> mantem como separando
            ok = True
            db.marcar_separacao_lote(ordem, 'separando', session['usuario_id'])
            db.add_log(session['usuario_id'], 'finalizar_separacao_parcial',
                       'OP #%s: %d/%d componentes separados' % (ordem, separados, total), 'lotes', ordem)
        return jsonify({'status': 'success' if ok else 'error', 'todos_separados': total > 0 and separados >= total, 'separados': separados, 'total': total})
    except Exception as e:
        return jsonify({'status': 'error', 'msg': str(e)}), 500

@app.route('/api/lotes/<int:ordem>/separado', methods=['POST'])
@app.route('/api/lotes/<int:ordem>/entregue', methods=['POST'])
@app.route('/api/lotes/<int:ordem>/pendente', methods=['POST'])
@app.route('/api/lotes/<int:ordem>/separando', methods=['POST'])
@login_required
@role_required('admin', 'gerente', 'almoxarifado')
def api_mudar_separacao(ordem):
    """Muda o status de separacao de uma OP."""
    novo_status = request.path.split('/')[-1]
    validos = ('pendente', 'separando', 'separado', 'entregue')
    if novo_status not in validos:
        return jsonify({'status': 'error', 'msg': 'Status invalido'}), 400
    try:
        db.marcar_separacao_lote(ordem, novo_status, session.get('usuario_id'))
        db.add_log(session['usuario_id'], 'mudar_separacao',
                   'OP #%s → %s' % (ordem, novo_status), 'lotes', ordem)
        return jsonify({'status': 'success'})
    except Exception as e:
        return jsonify({'status': 'error', 'msg': str(e)}), 500

@app.route('/api/lotes/<int:ordem>/componentes-separacao')
@login_required
@role_required('admin', 'gerente', 'almoxarifado')
def api_componentes_separacao(ordem):
    """Retorna componentes de uma OP com status de separação individual."""
    try:
        db.criar_tabela_separacao_componentes()
    except Exception:
        pass
    # Busca componentes do ERP
    componentes = []
    try:
        pg = DatabasePostgreSQL()
        mats = pg.get_requisicoes_multiplas_ordens([ordem])
        try:
            codigos_fabricados = db.get_codigos_produtos_ofs_ativas()
        except Exception:
            codigos_fabricados = set()
        try:
            codigos_excluidos = db.get_codigos_excluidos_set()
        except Exception:
            codigos_excluidos = set()
        agrupados = {}
        for m in mats:
            cod = str(m.get('produto') or '')
            if cod.upper().startswith('PC-') or cod.upper().startswith('PC '):
                continue
            if cod in codigos_fabricados:
                continue
            if cod.upper().strip() in codigos_excluidos:
                continue
            if cod not in agrupados:
                agrupados[cod] = {
                    'codigo': cod,
                    'descricao': (m.get('descricao') or '')[:50],
                    'unidade': m.get('unidade') or 'UN',
                    'qtd_necessaria': 0.0
                }
            agrupados[cod]['qtd_necessaria'] += float(m.get('quantidade') or 0)
        componentes = sorted(agrupados.values(), key=lambda x: x['codigo'])
    except Exception as e:
        return jsonify({'status': 'error', 'msg': str(e)}), 500

    # Inicializa registros no banco se necessário
    if componentes:
        try:
            db.init_separacao_componentes_op(ordem, componentes)
        except Exception:
            pass

    # Busca status de separação
    sep_status = {}
    try:
        rows = db.get_separacao_componentes(ordem)
        for r in rows:
            sep_status[str(r['codigo'])] = r['status']
    except Exception:
        pass

    for c in componentes:
        c['separacao_status'] = sep_status.get(c['codigo'], 'pendente')

    return jsonify({'status': 'success', 'componentes': componentes})

@app.route('/api/requisicoes/<int:req_id>/entregar', methods=['POST'])
@login_required
@role_required('admin', 'gerente', 'almoxarifado')
def api_entregar_requisicao(req_id):
    ok = db.atualizar_status_requisicao(req_id, 'entregue', session['usuario_id'])
    if ok:
        db.add_log(session['usuario_id'], 'entregar_requisicao',
                   f'Requisição #{req_id} entregue', 'requisicoes_materiais', req_id)
    return jsonify({'status': 'success' if ok else 'error'})

@app.route('/api/requisicoes/<int:req_id>/recusar', methods=['POST'])
@login_required
@role_required('admin', 'gerente', 'almoxarifado')
def api_recusar_requisicao(req_id):
    motivo = (request.json or {}).get('motivo', 'Recusado pelo almoxarifado')
    ok = db.atualizar_status_requisicao(req_id, 'recusado', session['usuario_id'])
    if ok:
        db.add_log(session['usuario_id'], 'recusar_requisicao',
                   f'Requisição #{req_id} recusada: {motivo}', 'requisicoes_materiais', req_id)
    return jsonify({'status': 'success' if ok else 'error'})

@app.route('/api/almoxarifado/separacao')
def api_almoxarifado_separacao():
    """Endpoint para a TV e PC do almoxarifado (separacao).
    TV acessa sem login, PC acessa com login — mesma API."""
    lotes = db.get_lotes_separacao_tv()
    pendentes  = sum(1 for l in lotes if l.get('separacao_status') == 'pendente')
    separados  = sum(1 for l in lotes if l.get('separacao_status') == 'separado')
    separando  = sum(1 for l in lotes if l.get('separacao_status') == 'separando')
    urgentes   = sum(1 for l in lotes if (l.get('prioridade') or '').lower() in ('urgente','alta'))
    atrasados  = sum(1 for l in lotes if (l.get('dias_atraso') or 0) > 0)
    return jsonify({
        'status': 'success',
        'lotes': lotes,
        'stats': {
            'total': len(lotes),
            'pendentes': pendentes,
            'separando': separando,
            'separados': separados,
            'urgentes': urgentes,
            'atrasados': atrasados
        }
    })

@app.route('/api/almoxarifado/estoque')
def api_almoxarifado_estoque():
    """Estoque do almoxarifado — lê SQLite sincronizado do ERP."""
    SQLITE_PATH = "/opt/painel_estoque/estoque.db"
    stats = {'CRITICO': 0, 'BAIXO': 0, 'OK': 0}
    produtos = []
    try:
        conn = sqlite3.connect(SQLITE_PATH)
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()
        cur.execute("SELECT TRIM(codigo) as codigo, descricao, saldo_atual, estoque_minimo FROM produtos")
        rows = cur.fetchall()
        for r in rows:
            saldo = float(r['saldo_atual'] or 0)
            minimo = float(r['estoque_minimo'] or 0)
            if minimo <= 0:
                minimo = 1.0
            limite = minimo * 1.25
            if saldo <= minimo:
                status = 'CRITICO'
            elif saldo <= limite:
                status = 'BAIXO'
            else:
                status = 'OK'
            stats[status] += 1
            produtos.append({
                'codigo': r['codigo'],
                'descricao': (r['descricao'] or '')[:45],
                'saldo': int(saldo),
                'minimo': int(minimo),
                'status': status
            })
        conn.close()
    except Exception as e:
        print("[ESTOQUE TV] Erro ao ler SQLite:", e)
    # Mostra apenas CRITICO e BAIXO no almoxarifado
    produtos = [p for p in produtos if p['status'] in ('CRITICO', 'BAIXO')]
    # Ordena: CRITICO primeiro, depois BAIXO
    ordem = {'CRITICO': 0, 'BAIXO': 1}
    produtos.sort(key=lambda x: (ordem.get(x['status'], 3), x['saldo']))
    return jsonify({'status': 'success', 'stats': stats, 'produtos': produtos})

@app.route('/api/almoxarifado/separacao-materiais')
def api_separacao_materiais():
    """TV do almoxarifado: OPs liberadas com lista de componentes para separar.
    Agrupa por lote_codigo, mostra TODAS as OFs (menos entregue).
    Separando = cor normal, Separado = cor amarela piscando, Entregue = some."""
    lotes = db.get_lotes_separacao_tv()
    if not lotes:
        return jsonify({'status': 'success', 'lotes': [], 'stats': {
            'total': 0, 'pendentes': 0, 'separando': 0, 'separados': 0, 'urgentes': 0
        }})

    # Exclui pecas fabricadas em outras OFs
    try:
        codigos_fabricados = db.get_codigos_produtos_ofs_ativas()
    except Exception:
        codigos_fabricados = set()

    # Exclui materiais marcados como "não separar do almoxarifado"
    try:
        codigos_excluidos = db.get_codigos_excluidos_set()
    except Exception:
        codigos_excluidos = set()

    # Agrupa OPs por lote_codigo (preserva ordem de prioridade)
    from collections import OrderedDict
    lote_map = OrderedDict()
    for l in lotes:
        lc = l.get('lote_codigo') or ''
        if lc not in lote_map:
            lote_map[lc] = {
                'lote_codigo': lc,
                'descricao_produto': l.get('descricao_produto'),
                'qtde_ordem': l.get('qtde_ordem'),
                'prioridade': l.get('prioridade'),
                'data_previsao_erp': l.get('data_previsao_erp'),
                'departamento_atual': l.get('departamento_atual'),
                'ordens': []
            }
        lote_map[lc]['ordens'].append({
            'ordem': l['ordem'],
            'separacao_status': l.get('separacao_status', 'pendente'),
            'dias_atraso': l.get('dias_atraso', 0),
            'prioridade': l.get('prioridade', 'media'),
        })

    # Busca TODAS as OFs do lote no ERP e materiais
    pg = None
    try:
        pg = DatabasePostgreSQL()
    except Exception as e:
        print('[SEP MATS] Erro conectar ERP:', e)

    resultado = []
    stats = {'total': 0, 'pendentes': 0, 'separando': 0, 'separados': 0, 'urgentes': 0}

    for lc, info in lote_map.items():
        ordens_info = info['ordens']

        # Conta status das OFs
        ofs_pendentes = [o for o in ordens_info if o['separacao_status'] in ('pendente', 'separando')]
        ofs_separadas = [o for o in ordens_info if o['separacao_status'] == 'separado']

        # Se TODAS as OFs do lote ja foram entregues, nao mostra (ja excluido pelo SQL)
        # Se todas separadas mas nenhuma pendente, mostra apenas como informativo
        if not ofs_pendentes and not ofs_separadas:
            continue

        # Pega OFs do ERP para buscar materiais (so das OFs pendentes/separando)
        ordens_pendentes_nums = [int(o['ordem']) for o in ofs_pendentes]
        materiais_erp = []
        if pg and ordens_pendentes_nums:
            try:
                materiais_erp = pg.get_requisicoes_multiplas_ordens(ordens_pendentes_nums)
            except Exception as e:
                print('[SEP MATS] Erro materiais ERP lote %s: %s' % (lc, e))

        # Agrupa materiais repetidos somando quantidades
        agrupados = {}
        for m in materiais_erp:
            cod = str(m.get('produto') or '')
            if cod.upper().startswith('PC-') or cod.upper().startswith('PC '):
                continue
            if cod in codigos_fabricados:
                continue
            if cod.upper().strip() in codigos_excluidos:
                continue
            if cod not in agrupados:
                agrupados[cod] = {
                    'codigo': cod,
                    'descricao': (m.get('descricao') or '')[:50],
                    'unidade': m.get('unidade') or 'UN',
                    'qtd_necessaria': 0.0
                }
            agrupados[cod]['qtd_necessaria'] += float(m.get('quantidade') or 0)
        comps = sorted(agrupados.values(), key=lambda x: x['codigo'])

        # Status do lote: se tem OFs pendentes = separando/separando, se so separadas = separado
        if ofs_pendentes:
            statuses = [o['separacao_status'] for o in ofs_pendentes]
            lote_sep_status = 'separando' if 'separando' in statuses else 'pendente'
        else:
            lote_sep_status = 'separado'

        # Pior prioridade / atraso
        prio = info['prioridade']
        max_atraso = max((o.get('dias_atraso') or 0) for o in ordens_info)
        for o in ofs_pendentes:
            p = (o.get('prioridade') or 'media').lower()
            if p == 'urgente':
                prio = 'urgente'
                break
            elif p == 'alta' and prio != 'urgente':
                prio = 'alta'

        resultado.append({
            'lote_codigo': lc,
            'descricao_produto': info['descricao_produto'],
            'qtde_ordem': info['qtde_ordem'],
            'prioridade': prio,
            'data_previsao_erp': info['data_previsao_erp'],
            'departamento_atual': info['departamento_atual'],
            'separacao_status': lote_sep_status,
            'dias_atraso': max_atraso,
            'total_componentes': len(comps),
            'componentes': comps,
            'ordens_do_lote': sorted(ordens_info, key=lambda x: x['ordem']),
            'ordens_pendentes_count': len(ofs_pendentes),
            'ordens_separadas_count': len(ofs_separadas),
        })

        # Stats
        stats['total'] += 1
        if lote_sep_status == 'pendente':
            stats['pendentes'] += 1
        elif lote_sep_status == 'separando':
            stats['separando'] += 1
        else:
            stats['separados'] += 1
        if prio in ('urgente', 'alta'):
            stats['urgentes'] += 1

    return jsonify({'status': 'success', 'lotes': resultado, 'stats': stats})

@app.route('/api/almoxarifado/novas_liberacoes')
@login_required
def api_novas_liberacoes():
    """Para alerta sonoro na TV — checa novas OPs liberadas."""
    ultima = request.args.get('ultima')  # ISO datetime
    lotes = db.get_novas_liberacoes(ultima_data=ultima if ultima else None)
    return jsonify({'status': 'success', 'lotes': lotes, 'count': len(lotes)})

# ── Materiais Excluídos da Separação ──────────────────────

@app.route('/api/almoxarifado/exclusoes-separacao')
@login_required
@role_required('admin', 'gerente', 'almoxarifado')
def api_listar_exclusoes_separacao():
    """Lista materiais excluídos da separação."""
    itens = db.get_materiais_excluidos()
    return jsonify({'status': 'success', 'itens': itens})

@app.route('/api/almoxarifado/exclusoes-separacao', methods=['POST'])
@login_required
@role_required('admin', 'gerente', 'almoxarifado')
def api_adicionar_exclusao_separacao():
    """Adiciona material à lista de exclusão da separação."""
    data = request.json or {}
    codigo = data.get('codigo', '').strip()
    if not codigo:
        return jsonify({'status': 'error', 'message': 'Código obrigatório'}), 400
    descricao = data.get('descricao', '')
    motivo = data.get('motivo', 'Feito no próprio setor')
    db.add_material_excluido(codigo, descricao, motivo, session.get('usuario_id'))
    db.add_log(session['usuario_id'], 'excluir_material_separacao',
               'Material %s excluído da separação: %s' % (codigo, motivo),
               'materiais_excluidos_separacao', codigo)
    return jsonify({'status': 'success', 'message': 'Material %s excluído da separação' % codigo})

@app.route('/api/almoxarifado/exclusoes-separacao/<path:codigo>', methods=['DELETE'])
@login_required
@role_required('admin', 'gerente', 'almoxarifado')
def api_remover_exclusao_separacao(codigo):
    """Remove material da lista de exclusão."""
    db.remove_material_excluido(codigo)
    db.add_log(session['usuario_id'], 'incluir_material_separacao',
               'Material %s voltou para separação' % codigo,
               'materiais_excluidos_separacao', codigo)
    return jsonify({'status': 'success', 'message': 'Material %s voltou para separação' % codigo})

@app.route('/api/kanban/cards')
@login_required
def api_kanban_cards():
    role  = session.get('usuario_role')
    depto = session.get('usuario_departamento', '')
    departamento_filtro = None if role in ('admin', 'gerente', 'pcp', 'diretor') else depto
    cards = db.get_kanban_cards(departamento=departamento_filtro)
    # Resolve nome real das pecas via PostgreSQL
    for c in cards:
        cod = c.get('cod_peca') or ''
        c['nome_peca'] = _get_nome_produto(cod) if cod else ''
        c['sob_medida'] = _is_sob_medida(cod) or _is_sob_medida(c.get('lote_codigo'))
    # Tempo medio de fabricacao por peca+setor (para progresso por tempo)
    tempos = {}
    try:
        rows = db.get_tempo_medio_producao()
        for r in rows:
            p = str(r.get('produto', '')).strip()
            s = str(r.get('setor', '')).strip().upper()
            if p and s:
                tempos[p + '|' + s] = float(r.get('tempo_medio_min', 0) or 0)
    except Exception:
        pass
    # Verifica ERP para alerta no TV
    pg_ok = False
    try:
        pg = DatabasePostgreSQL()
        pg.query_one("SELECT 1")
        pg_ok = True
    except Exception:
        pass
    return jsonify({'status': 'success', 'cards': cards, 'tempos': tempos, 'pg_ok': pg_ok})

@app.route('/api/kanban/status')
@login_required
def api_kanban_status():
    role  = session.get('usuario_role')
    depto = session.get('usuario_departamento', '')
    departamento_filtro = None if role in ('admin', 'gerente', 'pcp', 'diretor') else depto
    stats = db.get_kanban_stats(departamento=departamento_filtro)
    concluidos_hoje = db.get_kanban_concluidos_hoje(departamento=departamento_filtro)
    em_atraso = db.get_lotes_em_atraso(departamento=departamento_filtro)
    # Verifica ERP para alerta no TV
    pg_ok = False
    try:
        pg = DatabasePostgreSQL()
        pg.query_one("SELECT 1")
        pg_ok = True
    except Exception:
        pass
    return jsonify({'status': 'success', 'stats': stats, 'concluidos_hoje': concluidos_hoje, 'em_atraso': em_atraso, 'pg_ok': pg_ok})

@app.route('/api/almoxarifado/tv')
@login_required
def api_almoxarifado_tv():
    stats = db.get_estatisticas_gerais()
    return jsonify({'status': 'success', 'stats': stats})

@app.route('/api/kanban/mover', methods=['POST'])
@login_required
def api_kanban_mover():
    data     = request.json or {}
    card_id  = data.get('card_id')
    nova_etapa = data.get('etapa')
    if not card_id or not nova_etapa:
        return jsonify({'status': 'error', 'message': 'card_id e etapa são obrigatórios'}), 400
    db.move_kanban_card(card_id, nova_etapa, session.get('usuario_id'))
    return jsonify({'status': 'success'})

@app.route('/api/operacoes/<int:operacao_id>/iniciar', methods=['POST'])
@login_required
def api_iniciar_operacao(operacao_id):
    ok = db.iniciar_operacao(operacao_id, session['usuario_id'])
    return jsonify({'status': 'success' if ok else 'error'})

@app.route('/api/operacoes/<int:operacao_id>/pausar', methods=['POST'])
@login_required
def api_pausar_operacao(operacao_id):
    motivo = (request.json or {}).get('motivo', 'Pausa')
    ok = db.pausar_operacao(operacao_id, session['usuario_id'], motivo)
    return jsonify({'status': 'success' if ok else 'error'})

@app.route('/api/operacoes/<int:operacao_id>/retomar', methods=['POST'])
@login_required
def api_retomar_operacao(operacao_id):
    ok = db.retomar_operacao(operacao_id, session['usuario_id'])
    return jsonify({'status': 'success' if ok else 'error'})

@app.route('/api/operacoes/<int:operacao_id>/finalizar', methods=['POST'])
@login_required
def api_finalizar_operacao(operacao_id):
    data = request.json or {}
    ok = db.finalizar_operacao(
        operacao_id, session['usuario_id'],
        qtde_produzida=data.get('qtde_produzida'),
        qtde_refugada=data.get('qtde_refugada', 0),
        observacoes=data.get('observacoes'),
        tipo=data.get('tipo', 'total')
    )
    return jsonify({'status': 'success' if ok else 'error'})

@app.route('/api/requisicoes', methods=['POST'])
@login_required
def api_criar_requisicao():
    data = request.json or {}
    data['usuario_id'] = session['usuario_id']
    data['departamento'] = session.get('usuario_departamento')
    req_id = db.criar_requisicao(data)
    return jsonify({'status': 'success', 'id': req_id}), 201

# =============================================
# Tratamento de erros
# =============================================

@app.errorhandler(404)
def not_found(e):
    return render_template('error.html', codigo=404, mensagem='Página não encontrada'), 404

@app.errorhandler(500)
def server_error(e):
    return render_template('error.html', codigo=500, mensagem='Erro interno do servidor'), 500

# =============================================
# Inicialização
# =============================================

if __name__ == '__main__':
    db.migrar_estoque_controlado_por_usuario()
    app.run(host='0.0.0.0', port=5002, debug=Config.DEBUG)
