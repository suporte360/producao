"""
Módulo de Rotas para Sistema de Apontamentos de Tempo (Toyota/Lean)
Integra-se ao app.py principal
"""

from flask import Blueprint, request, jsonify, session
from datetime import datetime
from functools import wraps

# Criar blueprint para rotas de apontamentos
apontamentos_bp = Blueprint('apontamentos', __name__, url_prefix='/api/apontamentos')


def login_required_api(f):
    """Decorator para verificar autenticação em rotas API"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'usuario_id' not in session:
            return jsonify({'status': 'error', 'message': 'Não autenticado'}), 401
        return f(*args, **kwargs)
    return decorated_function


def role_required_api(*roles):
    """Decorator para verificar role em rotas API"""
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if 'usuario_role' not in session or session['usuario_role'] not in roles:
                return jsonify({'status': 'error', 'message': 'Permissão negada'}), 403
            return f(*args, **kwargs)
        return decorated_function
    return decorator


# ========== ROTAS DE APONTAMENTOS DE TEMPO ==========

@apontamentos_bp.route('/tempo/iniciar', methods=['POST'])
@login_required_api
def iniciar_apontamento_tempo():
    """
    Inicia o apontamento de tempo para um lote/departamento
    Esperado: { "ordem": 9618, "departamento": "SERRALHERIA" }
    """
    from database.mysql_db import DatabaseMySQL
    
    try:
        data = request.get_json()
        ordem = data.get('ordem')
        departamento = data.get('departamento')
        usuario_id = session.get('usuario_id')
        
        if not all([ordem, departamento, usuario_id]):
            return jsonify({'status': 'error', 'message': 'Dados incompletos'}), 400
        
        db = DatabaseMySQL()
        
        # Registrar apontamento de início
        result = db.registrar_apontamento_tempo(
            ordem=ordem,
            departamento=departamento,
            usuario_id=usuario_id,
            tipo='inicio'
        )
        
        if result:
            return jsonify({
                'status': 'success',
                'message': 'Apontamento de início registrado',
                'data': {
                    'ordem': ordem,
                    'departamento': departamento,
                    'tipo': 'inicio',
                    'data_hora': datetime.now().isoformat()
                }
            }), 200
        else:
            return jsonify({'status': 'error', 'message': 'Falha ao registrar'}), 500
            
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500


@apontamentos_bp.route('/tempo/pausar', methods=['POST'])
@login_required_api
def pausar_apontamento_tempo():
    """
    Pausa o apontamento de tempo (banheiro, almoço, etc.)
    Esperado: { "ordem": 9618, "departamento": "SERRALHERIA", "motivo": "almoço" }
    """
    from database.mysql_db import DatabaseMySQL
    
    try:
        data = request.get_json()
        ordem = data.get('ordem')
        departamento = data.get('departamento')
        motivo = data.get('motivo', 'Pausa')
        usuario_id = session.get('usuario_id')
        
        if not all([ordem, departamento, usuario_id]):
            return jsonify({'status': 'error', 'message': 'Dados incompletos'}), 400
        
        db = DatabaseMySQL()
        
        # Registrar apontamento de pausa
        result = db.registrar_apontamento_tempo(
            ordem=ordem,
            departamento=departamento,
            usuario_id=usuario_id,
            tipo='pausa',
            motivo_pausa=motivo
        )
        
        if result:
            return jsonify({
                'status': 'success',
                'message': 'Pausa registrada',
                'data': {
                    'ordem': ordem,
                    'departamento': departamento,
                    'tipo': 'pausa',
                    'motivo': motivo,
                    'data_hora': datetime.now().isoformat()
                }
            }), 200
        else:
            return jsonify({'status': 'error', 'message': 'Falha ao registrar'}), 500
            
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500


@apontamentos_bp.route('/tempo/retomar', methods=['POST'])
@login_required_api
def retomar_apontamento_tempo():
    """
    Retoma o apontamento de tempo após pausa
    Esperado: { "ordem": 9618, "departamento": "SERRALHERIA" }
    """
    from database.mysql_db import DatabaseMySQL
    
    try:
        data = request.get_json()
        ordem = data.get('ordem')
        departamento = data.get('departamento')
        usuario_id = session.get('usuario_id')
        
        if not all([ordem, departamento, usuario_id]):
            return jsonify({'status': 'error', 'message': 'Dados incompletos'}), 400
        
        db = DatabaseMySQL()
        
        # Registrar apontamento de retomada
        result = db.registrar_apontamento_tempo(
            ordem=ordem,
            departamento=departamento,
            usuario_id=usuario_id,
            tipo='retomada'
        )
        
        if result:
            return jsonify({
                'status': 'success',
                'message': 'Produção retomada',
                'data': {
                    'ordem': ordem,
                    'departamento': departamento,
                    'tipo': 'retomada',
                    'data_hora': datetime.now().isoformat()
                }
            }), 200
        else:
            return jsonify({'status': 'error', 'message': 'Falha ao registrar'}), 500
            
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500


@apontamentos_bp.route('/tempo/finalizar', methods=['POST'])
@login_required_api
def finalizar_apontamento_tempo():
    """
    Finaliza o apontamento de tempo e calcula tempo total gasto
    Esperado: { "ordem": 9618, "departamento": "SERRALHERIA", "quantidade": 140 }
    """
    from database.mysql_db import DatabaseMySQL
    
    try:
        data = request.get_json()
        ordem = data.get('ordem')
        departamento = data.get('departamento')
        quantidade = data.get('quantidade')
        usuario_id = session.get('usuario_id')
        
        if not all([ordem, departamento, usuario_id]):
            return jsonify({'status': 'error', 'message': 'Dados incompletos'}), 400
        
        db = DatabaseMySQL()
        
        # Registrar apontamento de fim
        result = db.registrar_apontamento_tempo(
            ordem=ordem,
            departamento=departamento,
            usuario_id=usuario_id,
            tipo='fim'
        )
        
        if result:
            # Calcular tempo total gasto
            tempo_total = db.calcular_tempo_total_gasto(ordem, departamento)
            
            # Calcular previsão de término
            previsao = db.calcular_previsao_termino(ordem, departamento)
            
            return jsonify({
                'status': 'success',
                'message': 'Produção finalizada',
                'data': {
                    'ordem': ordem,
                    'departamento': departamento,
                    'tipo': 'fim',
                    'data_hora': datetime.now().isoformat(),
                    'tempo_total_minutos': tempo_total,
                    'tempo_total_horas': round(tempo_total / 60, 2),
                    'previsao_termino': previsao
                }
            }), 200
        else:
            return jsonify({'status': 'error', 'message': 'Falha ao registrar'}), 500
            
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500


@apontamentos_bp.route('/tempo/historico/<int:ordem>', methods=['GET'])
@login_required_api
def obter_historico_apontamentos(ordem):
    """
    Retorna o histórico de apontamentos de tempo de um lote
    """
    from database.mysql_db import DatabaseMySQL
    
    try:
        departamento = request.args.get('departamento')
        db = DatabaseMySQL()
        
        apontamentos = db.get_apontamentos_tempo(ordem, departamento)
        
        return jsonify({
            'status': 'success',
            'data': apontamentos
        }), 200
        
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500


@apontamentos_bp.route('/tempo/previsao/<int:ordem>', methods=['GET'])
@login_required_api
def obter_previsao_termino(ordem):
    """
    Retorna a previsão de término para um lote
    """
    from database.mysql_db import DatabaseMySQL
    
    try:
        departamento = request.args.get('departamento')
        horas_trabalho = int(request.args.get('horas_trabalho', 8))
        
        db = DatabaseMySQL()
        previsao = db.calcular_previsao_termino(ordem, departamento, horas_trabalho)
        
        if previsao:
            return jsonify({
                'status': 'success',
                'data': {
                    'tempo_medio_minutos': round(previsao['tempo_medio_minutos'], 2),
                    'tempo_restante_minutos': round(previsao['tempo_restante_minutos'], 2),
                    'tempo_restante_horas': round(previsao['tempo_restante_horas'], 2),
                    'data_previsao_termino': previsao['data_previsao_termino'].isoformat()
                }
            }), 200
        else:
            return jsonify({'status': 'error', 'message': 'Não há dados suficientes para calcular previsão'}), 400
        
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500


# ========== ROTAS DE REQUISIÇÕES (ALMOXARIFADO) ==========

@apontamentos_bp.route('/requisicoes/pendentes', methods=['GET'])
@login_required_api
@role_required_api('almoxarifado', 'admin', 'gerente')
def obter_requisicoes_pendentes():
    """
    Retorna requisições pendentes de entrega
    Filtro opcional: ?departamento=SERRALHERIA
    """
    from database.mysql_db import DatabaseMySQL
    
    try:
        departamento = request.args.get('departamento')
        db = DatabaseMySQL()
        
        requisicoes = db.get_requisicoes_pendentes(departamento)
        
        return jsonify({
            'status': 'success',
            'total': len(requisicoes),
            'data': requisicoes
        }), 200
        
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500


@apontamentos_bp.route('/requisicoes/<int:requisicao_id>/entregar', methods=['POST'])
@login_required_api
@role_required_api('almoxarifado', 'admin')
def entregar_requisicao(requisicao_id):
    """
    Marca uma requisição como entregue
    Esperado: { "observacao": "Entregue conforme solicitado" }
    """
    from database.mysql_db import DatabaseMySQL
    
    try:
        data = request.get_json()
        usuario_id = session.get('usuario_id')
        
        db = DatabaseMySQL()
        
        # Atualizar status para 'entregue'
        result = db.atualizar_status_requisicao(requisicao_id, 'entregue', usuario_id)
        
        if result:
            # Registrar log
            requisicao = db.get_requisicao_info(requisicao_id)
            db.registrar_atividade(
                usuario=session.get('usuario_nome'),
                acao='entregar_requisicao',
                tabela='requisicoes',
                registro_id=requisicao_id,
                descricao=f"Requisição {requisicao['req_codigo']} entregue"
            )
            
            return jsonify({
                'status': 'success',
                'message': 'Requisição marcada como entregue'
            }), 200
        else:
            return jsonify({'status': 'error', 'message': 'Falha ao atualizar'}), 500
            
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500


@apontamentos_bp.route('/requisicoes/<int:requisicao_id>/recusar', methods=['POST'])
@login_required_api
@role_required_api('almoxarifado', 'admin')
def recusar_requisicao(requisicao_id):
    """
    Marca uma requisição como recusada
    Esperado: { "observacao": "Material com defeito" }
    """
    from database.mysql_db import DatabaseMySQL
    
    try:
        data = request.get_json()
        usuario_id = session.get('usuario_id')
        
        db = DatabaseMySQL()
        
        # Atualizar status para 'recusada'
        result = db.atualizar_status_requisicao(requisicao_id, 'recusada', usuario_id)
        
        if result:
            # Registrar log
            requisicao = db.get_requisicao_info(requisicao_id)
            db.registrar_atividade(
                usuario=session.get('usuario_nome'),
                acao='recusar_requisicao',
                tabela='requisicoes',
                registro_id=requisicao_id,
                descricao=f"Requisição {requisicao['req_codigo']} recusada"
            )
            
            return jsonify({
                'status': 'success',
                'message': 'Requisição marcada como recusada'
            }), 200
        else:
            return jsonify({'status': 'error', 'message': 'Falha ao atualizar'}), 500
            
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500


# ========== ROTAS DE PRIORIDADES (PCP) ==========

@apontamentos_bp.route('/prioridades/<int:ordem>', methods=['PUT'])
@login_required_api
@role_required_api('pcp', 'admin', 'gerente')
def atualizar_prioridade(ordem):
    """
    Atualiza a prioridade de um lote
    Esperado: { "prioridade": "alta" }
    """
    from database.mysql_db import DatabaseMySQL
    
    try:
        data = request.get_json()
        prioridade = data.get('prioridade')
        
        if prioridade not in ['alta', 'media', 'baixa']:
            return jsonify({'status': 'error', 'message': 'Prioridade inválida'}), 400
        
        db = DatabaseMySQL()
        result = db.atualizar_prioridade_lote(ordem, prioridade)
        
        if result:
            db.registrar_atividade(
                usuario=session.get('usuario_nome'),
                acao='atualizar_prioridade',
                tabela='lotes_producao',
                registro_id=ordem,
                descricao=f"Prioridade alterada para {prioridade}"
            )
            
            return jsonify({
                'status': 'success',
                'message': f'Prioridade atualizada para {prioridade}'
            }), 200
        else:
            return jsonify({'status': 'error', 'message': 'Falha ao atualizar'}), 500
            
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500


@apontamentos_bp.route('/lotes/ordenados', methods=['GET'])
@login_required_api
def obter_lotes_ordenados():
    """
    Retorna lotes ordenados por prioridade e data
    Filtro opcional: ?departamento=SERRALHERIA
    """
    from database.mysql_db import DatabaseMySQL
    
    try:
        departamento = request.args.get('departamento')
        db = DatabaseMySQL()
        
        lotes = db.get_lotes_ordenados_prioridade(departamento)
        
        return jsonify({
            'status': 'success',
            'total': len(lotes),
            'data': lotes
        }), 200
        
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500


# ========== ROTAS DE ESTATÍSTICAS ==========

@apontamentos_bp.route('/estatisticas/operador/<departamento>', methods=['GET'])
@login_required_api
def obter_estatisticas_operador(departamento):
    """
    Retorna estatísticas do operador/departamento
    """
    from database.mysql_db import DatabaseMySQL
    
    try:
        db = DatabaseMySQL()
        stats = db.get_estatisticas_operador(departamento)
        
        return jsonify({
            'status': 'success',
            'data': stats
        }), 200
        
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500


@apontamentos_bp.route('/estatisticas/gerais', methods=['GET'])
@login_required_api
@role_required_api('admin', 'gerente', 'pcp')
def obter_estatisticas_gerais():
    """
    Retorna estatísticas gerais do sistema
    """
    from database.mysql_db import DatabaseMySQL
    
    try:
        db = DatabaseMySQL()
        stats = db.get_estatisticas_gerais()
        
        return jsonify({
            'status': 'success',
            'data': stats
        }), 200
        
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500
