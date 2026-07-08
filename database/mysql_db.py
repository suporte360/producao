"""
Sistema de Produção SALUTEM - Camada de Banco de Dados MySQL/MariaDB
Versão 4.0 - Controle Total de Linha de Fabricação
"""
import pymysql
from pymysql.cursors import DictCursor
from contextlib import contextmanager
from datetime import datetime
from config.config import Config
from werkzeug.security import check_password_hash, generate_password_hash


class DatabaseMySQL:
    _initialized = False
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(DatabaseMySQL, cls).__new__(cls)
        return cls._instance

    def __init__(self):
        if self._initialized:
            return
        self._initialized = True
        self.config = {
            'host': Config.MYSQL_HOST,
            'port': Config.MYSQL_PORT,
            'user': Config.MYSQL_USERNAME,
            'password': Config.MYSQL_PASSWORD,
            'database': Config.MYSQL_DATABASE,
            'charset': 'utf8mb4',
            'cursorclass': DictCursor,
            'autocommit': False,
            'connect_timeout': 10,
        }

    @contextmanager
    def get_connection(self):
        connection = pymysql.connect(**self.config)
        try:
            yield connection
            connection.commit()
        except Exception as e:
            connection.rollback()
            raise e
        finally:
            connection.close()

    def query(self, sql, params=None):
        with self.get_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute(sql, params or ())
                return cursor.fetchall()

    def query_one(self, sql, params=None):
        with self.get_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute(sql, params or ())
                return cursor.fetchone()

    def execute(self, sql, params=None):
        with self.get_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute(sql, params or ())
                return cursor.lastrowid or cursor.rowcount

    # =============================================
    # AUTENTICAÇÃO E USUÁRIOS
    # =============================================

    def verificar_usuario(self, usuario, senha):
        sql = "SELECT * FROM usuarios WHERE usuario = %s AND ativo = 1"
        user = self.query_one(sql, (usuario,))
        if user:
            if user['senha'].startswith('scrypt:') or user['senha'].startswith('pbkdf2:'):
                if check_password_hash(user['senha'], senha):
                    self.execute("UPDATE usuarios SET ultimo_acesso = NOW() WHERE id = %s", (user['id'],))
                    return user
            elif user['senha'] == senha:
                self.execute("UPDATE usuarios SET ultimo_acesso = NOW() WHERE id = %s", (user['id'],))
                return user
        return None

    def listar_usuarios(self):
        return self.query("""
            SELECT u.id, u.usuario, u.nome, u.role, u.nome_departamento,
                   u.departamento_codigo, u.ativo, u.data_criacao, u.ultimo_acesso
            FROM usuarios u
            ORDER BY u.nome
        """)

    def get_usuario_por_id(self, user_id):
        return self.query_one("""
            SELECT id, usuario, nome, role, nome_departamento, departamento_codigo, ativo
            FROM usuarios WHERE id = %s
        """, (user_id,))

    def criar_usuario(self, dados):
        sql = """
            INSERT INTO usuarios (usuario, nome, senha, role, nome_departamento, departamento_codigo, ativo)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
        """
        senha_hash = generate_password_hash(dados['senha'])
        return self.execute(sql, [
            dados['usuario'], dados['nome'], senha_hash,
            dados['role'], dados.get('nome_departamento'), dados.get('departamento_codigo'), 1
        ])

    def atualizar_usuario(self, user_id, dados):
        sql = "UPDATE usuarios SET nome = %s, role = %s, nome_departamento = %s, departamento_codigo = %s, ativo = %s"
        params = [dados['nome'], dados['role'], dados.get('nome_departamento'), dados.get('departamento_codigo'), dados['ativo']]
        if dados.get('senha'):
            sql += ", senha = %s"
            params.append(generate_password_hash(dados['senha']))
        sql += " WHERE id = %s"
        params.append(user_id)
        return self.execute(sql, params)

    def deletar_usuario(self, user_id):
        return self.execute("DELETE FROM usuarios WHERE id = %s", (user_id,))

    # =============================================
    # DEPARTAMENTOS
    # =============================================

    def listar_departamentos(self, apenas_ativos=True):
        sql = "SELECT * FROM departamentos"
        if apenas_ativos:
            sql += " WHERE ativo = 1"
        sql += " ORDER BY ordem_fluxo, nome"
        return self.query(sql)

    def get_departamento(self, codigo):
        return self.query_one("SELECT * FROM departamentos WHERE codigo = %s", (codigo,))

    # =============================================
    # LOTES DE PRODUÇÃO
    # =============================================

    def get_lotes(self, status=None, departamento=None, prioridade=None, pagina=1, por_pagina=30):
        offset = (pagina - 1) * por_pagina
        sql = """
            SELECT l.*, 
                   (SELECT COUNT(*) FROM operacoes_producao op WHERE op.lote_ordem = l.ordem) AS total_operacoes,
                   (SELECT COUNT(*) FROM operacoes_producao op WHERE op.lote_ordem = l.ordem AND op.status = 'concluido') AS operacoes_concluidas
            FROM lotes_producao l
            WHERE 1=1
        """
        params = []
        if status:
            if isinstance(status, list):
                placeholders = ','.join(['%s'] * len(status))
                sql += f" AND l.status IN ({placeholders})"
                params.extend(status)
            else:
                sql += " AND l.status = %s"
                params.append(status)
        if departamento:
            sql += " AND l.departamento_atual = %s"
            params.append(departamento)
        if prioridade:
            sql += " AND l.prioridade = %s"
            params.append(prioridade)
        sql += """
            ORDER BY
                FIELD(l.prioridade, 'urgente', 'alta', 'media', 'baixa'),
                l.data_previsao_erp ASC
            LIMIT %s OFFSET %s
        """
        params.extend([por_pagina, offset])
        return self.query(sql, params)

    def get_lote_por_ordem(self, ordem):
        return self.query_one("""
            SELECT l.*,
                   (SELECT COUNT(*) FROM operacoes_producao op WHERE op.lote_ordem = l.ordem) AS total_operacoes,
                   (SELECT COUNT(*) FROM operacoes_producao op WHERE op.lote_ordem = l.ordem AND op.status = 'concluido') AS operacoes_concluidas,
                   (SELECT COUNT(*) FROM ordens_fabricacao of2 WHERE of2.lote_ordem = l.ordem) AS total_ofs
            FROM lotes_producao l
            WHERE l.ordem = %s
        """, (ordem,))

    def get_lotes_por_departamento(self, departamento, status=None):
        """
        Retorna 1 linha por OP/LOTE para o departamento, com a próxima operação pendente.
        Evita duplicação: pega só a operação mais antiga pendente/em_andamento do setor.
        """
        sql = """
            SELECT l.*,
                   op.id            AS op_id,
                   op.status        AS op_status,
                   op.data_inicio   AS data_inicio,
                   op.descricao_operacao,
                   op.qtde_produzida,
                   op.sequencia,
                   op.of_numero,
                   (SELECT COUNT(*) FROM operacoes_producao op2
                    WHERE op2.lote_ordem = l.ordem AND op2.departamento = %s
                      AND op2.status != 'concluido') AS ops_pendentes
            FROM lotes_producao l
            INNER JOIN operacoes_producao op ON op.lote_ordem = l.ordem
            WHERE op.departamento = %s
              AND op.status IN ('pendente', 'em_andamento', 'pausado')
              AND l.status NOT IN ('cancelado', 'finalizado')
              AND op.id = (
                  SELECT MIN(op3.id)
                  FROM operacoes_producao op3
                  WHERE op3.lote_ordem = l.ordem
                    AND op3.departamento = %s
                    AND op3.status IN ('pendente', 'em_andamento', 'pausado')
              )
        """
        params = [departamento, departamento, departamento]
        if status:
            sql += " AND l.status = %s"
            params.append(status)
        sql += " ORDER BY FIELD(l.prioridade, 'urgente', 'alta', 'media', 'baixa'), l.data_previsao_erp ASC"
        return self.query(sql, params)

    def importar_lote_erp(self, dados):
        """Importa ou atualiza um lote vindo do ERP"""
        sql = """
            INSERT INTO lotes_producao 
                (ordem, lote_codigo, codigo_produto, descricao_produto, qtde_ordem,
                 unidade_medida, status_erp, data_previsao_erp, data_abertura_erp, planejador, status, observacoes)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, 'importado', %s)
            ON DUPLICATE KEY UPDATE
                descricao_produto = VALUES(descricao_produto),
                qtde_ordem = VALUES(qtde_ordem),
                data_previsao_erp = VALUES(data_previsao_erp),
                status_erp = VALUES(status_erp),
                data_ultima_sync = NOW(),
                observacoes = COALESCE(NULLIF(VALUES(observacoes),''), observacoes)
        """
        return self.execute(sql, [
            dados['ordem'], dados.get('lote_codigo'), dados.get('codigo_produto'),
            dados.get('descricao_produto'), dados.get('qtde_ordem', 0),
            dados.get('unidade_medida', 'UN'), dados.get('status_erp', 'A'),
            dados.get('data_previsao_erp'), dados.get('data_abertura_erp'),
            dados.get('planejador'),
            dados.get('observacoes')
        ])

    def atualizar_status_lote(self, ordem, novo_status, usuario_id=None):
        sql = "UPDATE lotes_producao SET status = %s"
        params = [novo_status]
        if novo_status == 'em_producao':
            sql += ", data_inicio_producao = COALESCE(data_inicio_producao, NOW())"
        elif novo_status == 'finalizado':
            sql += ", data_fim_producao = NOW()"
        elif novo_status == 'liberado':
            # Ao liberar, zera o status de separação para o almoxarifado pegar
            sql += ", separacao_status = 'pendente', data_separacao = NULL, data_entrega = NULL"
        sql += " WHERE ordem = %s"
        params.append(ordem)
        return self.execute(sql, params)

    def atualizar_prioridade_lote(self, ordem, prioridade):
        return self.execute("UPDATE lotes_producao SET prioridade = %s WHERE ordem = %s", (prioridade, ordem))

    def atualizar_departamento_atual(self, lote_ordem):
        """Calcula e atualiza o departamento_atual, setor_atual_seq e total_setores
        de um lote baseado na primeira operacao pendente (nao concluida)."""
        # Busca OFs do lote
        ofs = self.query(
            "SELECT of_numero FROM ordens_fabricacao WHERE lote_ordem = %s",
            (lote_ordem,)
        )
        if not ofs:
            return

        of_nums = [o['of_numero'] for o in ofs]
        if not of_nums:
            return

        ph = ','.join(['%s'] * len(of_nums))

        # Total de departamentos unicos (setores) do lote
        total = self.query_one(
            "SELECT COUNT(DISTINCT departamento) as t FROM operacoes_producao "
            "WHERE of_numero IN (" + ph + ") AND departamento IS NOT NULL AND departamento != ''",
            tuple(of_nums)
        )
        total_setores = int(total['t'] or 0) if total else 0

        # Primeira operacao pendente (nao concluida) ordenada por sequencia
        primeira = self.query_one(
            "SELECT departamento, sequencia FROM operacoes_producao "
            "WHERE of_numero IN (" + ph + ") "
            "AND status != 'concluido' "
            "ORDER BY sequencia ASC LIMIT 1",
            tuple(of_nums)
        )

        dept = primeira['departamento'] if primeira else None
        seq = int(primeira['sequencia']) if primeira else 0

        self.execute(
            "UPDATE lotes_producao "
            "SET departamento_atual = %s, setor_atual_seq = %s, total_setores = %s "
            "WHERE ordem = %s",
            (dept, seq, total_setores, lote_ordem)
        )

    # =============================================
    # ORDENS DE FABRICAÇÃO (OFs)
    # =============================================

    def get_ofs_por_lote(self, lote_ordem):
        return self.query("""
            SELECT of2.*, 
                   (SELECT COUNT(*) FROM operacoes_producao op WHERE op.of_numero = of2.of_numero) AS total_ops,
                   (SELECT COUNT(*) FROM operacoes_producao op WHERE op.of_numero = of2.of_numero AND op.status = 'concluido') AS ops_concluidas
            FROM ordens_fabricacao of2
            WHERE of2.lote_ordem = %s
            ORDER BY of2.tipo DESC, of2.of_numero
        """, (lote_ordem,))

    def importar_of(self, dados):
        sql = """
            INSERT INTO ordens_fabricacao
                (lote_ordem, of_numero, codigo_produto, descricao_produto, qtde_ordem, unidade_medida, tipo, data_previsao)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            ON DUPLICATE KEY UPDATE
                descricao_produto = VALUES(descricao_produto),
                qtde_ordem = VALUES(qtde_ordem)
        """
        return self.execute(sql, [
            dados['lote_ordem'], dados['of_numero'], dados.get('codigo_produto'),
            dados.get('descricao_produto'), dados.get('qtde_ordem', 0),
            dados.get('unidade_medida', 'PC'), dados.get('tipo', 'filho'),
            dados.get('data_previsao')
        ])

    # =============================================
    # OPERAÇÕES DE PRODUÇÃO
    # =============================================

    def get_operacoes_por_lote(self, lote_ordem, departamento=None):
        sql = """
            SELECT op.*, u_ini.nome AS usuario_inicio_nome, u_fim.nome AS usuario_fim_nome,
                   of2.codigo_produto, of2.descricao_produto AS produto_of
            FROM operacoes_producao op
            LEFT JOIN ordens_fabricacao of2 ON op.of_numero = of2.of_numero
            LEFT JOIN usuarios u_ini ON op.usuario_inicio_id = u_ini.id
            LEFT JOIN usuarios u_fim ON op.usuario_fim_id = u_fim.id
            WHERE op.lote_ordem = %s
        """
        params = [lote_ordem]
        if departamento:
            sql += " AND op.departamento = %s"
            params.append(departamento)
        sql += " ORDER BY op.of_numero, op.sequencia"
        return self.query(sql, params)

    def get_operacoes_por_departamento(self, departamento, status=None):
        sql = """
            SELECT op.*, l.descricao_produto, l.prioridade, l.data_previsao_erp, l.lote_codigo,
                   of2.codigo_produto AS cod_produto_of,
                   u.nome AS operador_nome
            FROM operacoes_producao op
            INNER JOIN lotes_producao l ON op.lote_ordem = l.ordem
            LEFT JOIN ordens_fabricacao of2 ON op.of_numero = of2.of_numero
            LEFT JOIN usuarios u ON op.usuario_inicio_id = u.id
            WHERE op.departamento = %s
              AND l.status NOT IN ('cancelado', 'finalizado')
        """
        params = [departamento]
        if status:
            if isinstance(status, list):
                placeholders = ','.join(['%s'] * len(status))
                sql += f" AND op.status IN ({placeholders})"
                params.extend(status)
            else:
                sql += " AND op.status = %s"
                params.append(status)
        sql += " ORDER BY FIELD(l.prioridade, 'urgente', 'alta', 'media', 'baixa'), l.data_previsao_erp ASC, op.sequencia"
        return self.query(sql, params)

    def importar_operacao(self, dados):
        sql = """
            INSERT INTO operacoes_producao
                (of_numero, lote_ordem, sequencia, fase, descricao_operacao, departamento, codigo_barras)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
            ON DUPLICATE KEY UPDATE
                descricao_operacao = VALUES(descricao_operacao),
                departamento = VALUES(departamento)
        """
        return self.execute(sql, [
            dados['of_numero'], dados['lote_ordem'], dados['sequencia'],
            dados.get('fase'), dados['descricao_operacao'],
            dados.get('departamento'), dados.get('codigo_barras')
        ])

    def iniciar_operacao(self, operacao_id, usuario_id):
        op = self.query_one("SELECT * FROM operacoes_producao WHERE id = %s", (operacao_id,))
        if not op:
            return False
        self.execute("""
            UPDATE operacoes_producao 
            SET status = 'em_andamento', data_inicio = NOW(), usuario_inicio_id = %s
            WHERE id = %s AND status IN ('pendente', 'pausado')
        """, (usuario_id, operacao_id))
        self.atualizar_status_lote(op['lote_ordem'], 'em_producao', usuario_id)
        self.registrar_apontamento_tempo(op['lote_ordem'], op['of_numero'], operacao_id, op['departamento'], usuario_id, 'inicio')
        # Sincroniza kanban: card vai para 'em_producao'
        self._sincronizar_kanban_operacao(operacao_id, 'em_producao', usuario_id)
        return True

    def pausar_operacao(self, operacao_id, usuario_id, motivo='Pausa'):
        op = self.query_one("SELECT * FROM operacoes_producao WHERE id = %s", (operacao_id,))
        if not op:
            return False
        self.execute("""
            UPDATE operacoes_producao SET status = 'pausado' WHERE id = %s AND status = 'em_andamento'
        """, (operacao_id,))
        self.registrar_apontamento_tempo(op['lote_ordem'], op['of_numero'], operacao_id, op['departamento'], usuario_id, 'pausa', motivo)
        # Sincroniza kanban: card vai para 'pausado'
        self._sincronizar_kanban_operacao(operacao_id, 'pausado', usuario_id)
        return True

    def retomar_operacao(self, operacao_id, usuario_id):
        op = self.query_one("SELECT * FROM operacoes_producao WHERE id = %s", (operacao_id,))
        if not op:
            return False
        self.execute("""
            UPDATE operacoes_producao SET status = 'em_andamento' WHERE id = %s AND status = 'pausado'
        """, (operacao_id,))
        self.registrar_apontamento_tempo(op['lote_ordem'], op['of_numero'], operacao_id, op['departamento'], usuario_id, 'retomada')
        # Sincroniza kanban: card volta para 'em_producao'
        self._sincronizar_kanban_operacao(operacao_id, 'em_producao', usuario_id)
        return True

    def _sincronizar_kanban_operacao(self, operacao_id, etapa, operador_id=None):
        """Atualiza o card do kanban correspondente à operação.
        Se o card não existir, cria automaticamente."""
        try:
            # Busca a operação e o lote
            op = self.query_one("""
                SELECT op.*, l.prioridade
                FROM operacoes_producao op
                LEFT JOIN lotes_producao l ON op.lote_ordem = l.ordem
                WHERE op.id = %s
            """, (operacao_id,))
            if not op:
                return

            # Verifica se já existe card para esta operação
            existente = self.query_one(
                "SELECT id FROM kanban_cards WHERE operacao_id = %s",
                (operacao_id,)
            )

            if existente:
                # Atualiza card existente
                self.execute("""
                    UPDATE kanban_cards
                    SET etapa = %s,
                        operador_id = COALESCE(%s, operador_id),
                        atualizado_em = NOW()
                    WHERE operacao_id = %s
                """, (etapa, operador_id, operacao_id))
            else:
                # Cria card novo (para operações importadas antes do fix)
                self.execute("""
                    INSERT INTO kanban_cards
                        (lote_ordem, of_numero, operacao_id, etapa, departamento, prioridade, operador_id)
                    VALUES (%s, %s, %s, %s, %s, %s, %s)
                """, (
                    op['lote_ordem'],
                    op.get('of_numero'),
                    operacao_id,
                    etapa,
                    op.get('departamento'),
                    op.get('prioridade') or 'media',
                    operador_id
                ))
        except Exception as e:
            print(f"Erro ao sincronizar kanban: {e}")

    def finalizar_operacao(self, operacao_id, usuario_id, qtde_produzida=None, qtde_refugada=0, observacoes=None, tipo='total'):
        """
        tipo='total'   → marca como concluido e fecha o lote se todas as ops concluídas
        tipo='parcial' → registra a quantidade produzida até agora e reinicia a operação
                         (status volta para 'pendente' com qtde_produzida acumulada)
                         Assim o próximo setor já pode ver as peças disponíveis.
        """
        op = self.query_one("SELECT * FROM operacoes_producao WHERE id = %s", (operacao_id,))
        if not op:
            return False

        if tipo == 'parcial':
            # Acumula a quantidade e volta para pendente (disponível para próximo setor)
            self.execute("""
                UPDATE operacoes_producao
                SET status = 'pendente',
                    data_inicio = NULL,
                    qtde_produzida = COALESCE(qtde_produzida, 0) + COALESCE(%s, 0),
                    qtde_refugada  = COALESCE(qtde_refugada, 0)  + COALESCE(%s, 0),
                    observacoes    = COALESCE(%s, observacoes)
                WHERE id = %s
            """, (qtde_produzida, qtde_refugada, observacoes, operacao_id))
            # Atualiza status do lote para 'importado' (disponível) se estava em_producao
            self.execute("""
                UPDATE lotes_producao SET status = 'importado'
                WHERE ordem = %s AND status = 'em_producao'
            """, (op['lote_ordem'],))
            self.registrar_apontamento_tempo(op['lote_ordem'], op.get('of_numero'), operacao_id, op['departamento'], usuario_id, 'parcial', qtde_produzida=qtde_produzida)
            # Sincroniza kanban: card volta para 'aguardando' (próximo setor pega)
            self._sincronizar_kanban_operacao(operacao_id, 'aguardando')
        else:
            self.execute("""
                UPDATE operacoes_producao
                SET status = 'concluido', data_fim = NOW(), usuario_fim_id = %s,
                    qtde_produzida = COALESCE(%s, qtde_produzida),
                    qtde_refugada = COALESCE(%s, 0),
                    observacoes = COALESCE(%s, observacoes)
                WHERE id = %s
            """, (usuario_id, qtde_produzida, qtde_refugada, observacoes, operacao_id))
            self.registrar_apontamento_tempo(op['lote_ordem'], op.get('of_numero'), operacao_id, op['departamento'], usuario_id, 'fim', qtde_produzida=qtde_produzida)
            # Sincroniza kanban: card vai para 'concluido'
            self._sincronizar_kanban_operacao(operacao_id, 'concluido', usuario_id)
            # Verifica se todas as operações do lote foram concluídas
            self._verificar_conclusao_lote(op['lote_ordem'])
        return True

    def _verificar_conclusao_lote(self, lote_ordem):
        total = self.query_one("SELECT COUNT(*) as t FROM operacoes_producao WHERE lote_ordem = %s", (lote_ordem,))['t']
        concluidas = self.query_one("SELECT COUNT(*) as t FROM operacoes_producao WHERE lote_ordem = %s AND status = 'concluido'", (lote_ordem,))['t']
        if total > 0 and total == concluidas:
            self.execute("UPDATE lotes_producao SET status = 'finalizado', data_fim_producao = NOW() WHERE ordem = %s", (lote_ordem,))
        # Sempre recalcula departamento_atual ao finalizar uma operacao
        try:
            self.atualizar_departamento_atual(lote_ordem)
        except Exception:
            pass

    # =============================================
    # APONTAMENTOS DE TEMPO
    # =============================================

    def registrar_apontamento_tempo(self, lote_ordem, of_numero, operacao_id, departamento, usuario_id, tipo, motivo_pausa=None, qtde_produzida=None):
        sql = """
            INSERT INTO apontamentos_tempo (lote_ordem, of_numero, operacao_id, departamento, usuario_id, tipo, motivo_pausa, qtde_produzida, data_hora)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, NOW())
        """
        return self.execute(sql, [lote_ordem, of_numero, operacao_id, departamento, usuario_id, tipo, motivo_pausa, qtde_produzida])

    def calcular_tempo_operacao(self, operacao_id):
        """Calcula o tempo total gasto em uma operação em minutos"""
        sql = """
            SELECT 
                SUM(CASE WHEN tipo IN ('inicio', 'retomada') THEN UNIX_TIMESTAMP(data_hora) * -1
                         WHEN tipo IN ('pausa', 'fim') THEN UNIX_TIMESTAMP(data_hora)
                    END) / 60 AS minutos
            FROM apontamentos_tempo
            WHERE operacao_id = %s
        """
        result = self.query_one(sql, (operacao_id,))
        return max(0, int(result['minutos'] or 0))

    def get_apontamentos_operacao(self, operacao_id):
        return self.query("""
            SELECT at.*, u.nome AS usuario_nome
            FROM apontamentos_tempo at
            LEFT JOIN usuarios u ON at.usuario_id = u.id
            WHERE at.operacao_id = %s
            ORDER BY at.data_hora ASC
        """, (operacao_id,))

    # =============================================
    # REQUISIÇÕES DE MATERIAIS (ALMOXARIFADO)
    # =============================================

    def get_requisicoes(self, status=None, departamento=None):
        sql = """
            SELECT r.*, l.descricao_produto, l.prioridade AS prioridade_lote,
                   u_sol.nome AS solicitante_nome, u_at.nome AS atendente_nome
            FROM requisicoes_materiais r
            LEFT JOIN lotes_producao l ON r.lote_ordem = l.ordem
            LEFT JOIN usuarios u_sol ON r.usuario_solicitante_id = u_sol.id
            LEFT JOIN usuarios u_at ON r.usuario_atendimento_id = u_at.id
            WHERE 1=1
        """
        params = []
        if status:
            sql += " AND r.status = %s"
            params.append(status)
        if departamento:
            sql += " AND r.departamento_solicitante = %s"
            params.append(departamento)
        sql += " ORDER BY FIELD(l.prioridade, 'urgente', 'alta', 'media', 'baixa'), r.data_solicitacao DESC"
        return self.query(sql, params)

    def criar_requisicao(self, dados):
        sql = """
            INSERT INTO requisicoes_materiais
                (lote_ordem, of_numero, material_codigo, material_descricao, quantidade,
                 unidade_medida, departamento_solicitante, usuario_solicitante_id)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
        """
        return self.execute(sql, [
            dados['lote_ordem'], dados.get('of_numero'), dados.get('material_codigo'),
            dados['material_descricao'], dados['quantidade'],
            dados.get('unidade_medida', 'UN'), dados.get('departamento'),
            dados.get('usuario_id')
        ])

    def atualizar_status_requisicao(self, req_id, novo_status, usuario_id=None):
        sql = "UPDATE requisicoes_materiais SET status = %s"
        params = [novo_status]
        if novo_status in ('aprovado', 'entregue', 'recusado'):
            sql += ", usuario_atendimento_id = %s, data_atendimento = NOW()"
            params.append(usuario_id)
        sql += " WHERE id = %s"
        params.append(req_id)
        return self.execute(sql, params)

    def get_requisicao_por_id(self, req_id):
        return self.query_one("""
            SELECT r.*, l.descricao_produto, l.prioridade AS prioridade_lote
            FROM requisicoes_materiais r
            LEFT JOIN lotes_producao l ON r.lote_ordem = l.ordem
            WHERE r.id = %s
        """, (req_id,))

    # =============================================
    # KANBAN
    # =============================================

    def get_kanban_cards(self, departamento=None, etapa=None):
        sql = """
            SELECT k.*, l.lote_codigo, l.descricao_produto, l.qtde_ordem,
                   l.data_previsao_erp, l.prioridade AS prioridade_lote,
                   op.descricao_operacao, op.sequencia, op.status AS status_operacao,
                   op.qtde_produzida, op.data_inicio,
                   of2.codigo_produto AS cod_peca,
                   u.nome AS operador_nome,
                   (SELECT CASE WHEN COUNT(*) = 0 THEN 0
                       ELSE ROUND(SUM(CASE WHEN status = 'concluido' THEN 1 ELSE 0 END) * 100.0 / COUNT(*), 0)
                       END
                    FROM operacoes_producao WHERE lote_ordem = k.lote_ordem
                   ) AS progresso
            FROM kanban_cards k
            LEFT JOIN lotes_producao l ON k.lote_ordem = l.ordem
            LEFT JOIN operacoes_producao op ON k.operacao_id = op.id
            LEFT JOIN ordens_fabricacao of2 ON k.of_numero = of2.of_numero
            LEFT JOIN usuarios u ON k.operador_id = u.id
            WHERE 1=1
        """
        params = []
        if departamento:
            sql += " AND k.departamento = %s"
            params.append(departamento)
        if etapa:
            sql += " AND k.etapa = %s"
            params.append(etapa)
        sql += """
            ORDER BY
                FIELD(k.prioridade, 'urgente', 'alta', 'media', 'baixa'),
                k.criado_em ASC
        """
        return self.query(sql, params)

    def get_kanban_stats(self, departamento=None):
        sql = """
            SELECT k.etapa, COUNT(*) as total,
                   SUM(CASE WHEN k.prioridade = 'urgente' THEN 1 ELSE 0 END) as urgentes,
                   SUM(CASE WHEN k.prioridade = 'alta' THEN 1 ELSE 0 END) as altas
            FROM kanban_cards k
            WHERE k.etapa != 'concluido'
        """
        params = []
        if departamento:
            sql += " AND k.departamento = %s"
            params.append(departamento)
        sql += " GROUP BY k.etapa"
        return self.query(sql, params)

    def get_kanban_concluidos_hoje(self, departamento=None):
        sql = """
            SELECT COUNT(*) as total FROM kanban_cards
            WHERE etapa = 'concluido' AND DATE(atualizado_em) = CURDATE()
        """
        params = []
        if departamento:
            sql += " AND departamento = %s"
            params.append(departamento)
        result = self.query_one(sql, params)
        return result['total'] if result else 0

    def move_kanban_card(self, card_id, nova_etapa, operador_id=None):
        return self.execute("""
            UPDATE kanban_cards
            SET etapa = %s, operador_id = COALESCE(%s, operador_id), atualizado_em = NOW()
            WHERE id = %s
        """, (nova_etapa, operador_id, card_id))

    def add_kanban_card(self, lote_ordem, etapa='aguardando', operador_id=None, prioridade='media', departamento=None, of_numero=None, operacao_id=None):
        return self.execute("""
            INSERT INTO kanban_cards (lote_ordem, of_numero, operacao_id, etapa, departamento, prioridade, operador_id)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
        """, (lote_ordem, of_numero, operacao_id, etapa, departamento, prioridade, operador_id))

    def sincronizar_kanban_com_operacoes(self, lote_ordem):
        """Cria/atualiza cards do Kanban baseado nas operações do lote"""
        operacoes = self.get_operacoes_por_lote(lote_ordem)
        lote = self.get_lote_por_ordem(lote_ordem)
        if not lote:
            return
        for op in operacoes:
            existente = self.query_one("SELECT id FROM kanban_cards WHERE operacao_id = %s", (op['id'],))
            if not existente:
                etapa = 'aguardando'
                if op['status'] == 'em_andamento':
                    etapa = 'em_producao'
                elif op['status'] == 'concluido':
                    etapa = 'concluido'
                elif op['status'] == 'pausado':
                    etapa = 'pausado'
                self.add_kanban_card(
                    lote_ordem=lote_ordem,
                    etapa=etapa,
                    prioridade=lote['prioridade'],
                    departamento=op['departamento'],
                    of_numero=op['of_numero'],
                    operacao_id=op['id']
                )

    # =============================================
    # ESTATÍSTICAS E DASHBOARD
    # =============================================

    def get_estatisticas_gerais(self):
        """Retorna estatísticas gerais do sistema em apenas 2 queries (antes eram 8)."""
        try:
            lotes = self.query_one("""
                SELECT
                    COUNT(*)                                                              AS total_lotes,
                    SUM(status = 'importado')                                             AS importados,
                    SUM(status = 'em_producao')                                           AS em_producao,
                    SUM(status = 'finalizado' AND DATE(data_fim_producao) = CURDATE())    AS finalizados_hoje
                FROM lotes_producao
            """)
            ops = self.query_one("""
                SELECT
                    COUNT(*)                                                              AS total_operacoes,
                    SUM(status = 'em_andamento')                                          AS ops_em_andamento,
                    SUM(status = 'concluido' AND DATE(data_fim) = CURDATE())              AS ops_concluidas_hoje,
                    (SELECT COUNT(*) FROM requisicoes_materiais WHERE status = 'pendente') AS requisicoes_pendentes
                FROM operacoes_producao
            """)
            return {
                'total_lotes':          int(lotes['total_lotes']       or 0),
                'importados':           int(lotes['importados']         or 0),
                'em_producao':          int(lotes['em_producao']        or 0),
                'finalizados_hoje':     int(lotes['finalizados_hoje']   or 0),
                'total_operacoes':      int(ops['total_operacoes']      or 0),
                'ops_em_andamento':     int(ops['ops_em_andamento']     or 0),
                'ops_concluidas_hoje':  int(ops['ops_concluidas_hoje']  or 0),
                'requisicoes_pendentes':int(ops['requisicoes_pendentes']or 0),
            }
        except Exception as e:
            print(f"Erro get_estatisticas_gerais: {e}")
            return {'total_lotes': 0, 'importados': 0, 'em_producao': 0, 'finalizados_hoje': 0,
                    'total_operacoes': 0, 'ops_em_andamento': 0, 'ops_concluidas_hoje': 0, 'requisicoes_pendentes': 0}

    def get_estatisticas_departamento(self, departamento):
        """Retorna estatísticas de um departamento em 1 query (antes eram 4)."""
        try:
            r = self.query_one("""
                SELECT
                    SUM(status = 'pendente')                                                                      AS pendentes,
                    SUM(status = 'em_andamento')                                                                  AS em_andamento,
                    SUM(status = 'concluido' AND DATE(data_fim) = CURDATE())                                      AS concluidas_hoje,
                    SUM(status = 'concluido' AND MONTH(data_fim) = MONTH(CURDATE())
                                             AND YEAR(data_fim)  = YEAR(CURDATE()))                               AS concluidas_mes
                FROM operacoes_producao
                WHERE departamento = %s
            """, (departamento,))
            return {
                'pendentes':       int(r['pendentes']       or 0),
                'em_andamento':    int(r['em_andamento']    or 0),
                'concluidas_hoje': int(r['concluidas_hoje'] or 0),
                'concluidas_mes':  int(r['concluidas_mes']  or 0),
            }
        except Exception as e:
            print(f"Erro get_estatisticas_departamento: {e}")
            return {'pendentes': 0, 'em_andamento': 0, 'concluidas_hoje': 0, 'concluidas_mes': 0}

    def get_lotes_importados_tv(self):
        return self.query("""
            SELECT l.ordem, l.lote_codigo, l.descricao_produto, l.qtde_ordem,
                   l.prioridade, l.data_previsao_erp, l.departamento_atual, l.status,
                   l.separacao_status, l.data_separacao, l.data_entrega
            FROM lotes_producao l
            WHERE l.status IN ('importado', 'liberado')
            ORDER BY FIELD(l.prioridade, 'urgente', 'alta', 'media', 'baixa'), l.data_previsao_erp ASC
        """)

    def marcar_separacao_lote(self, ordem, novo_status, usuario_id=None):
        """
        Atualiza o status de separação pelo almoxarifado.
        novo_status: 'separando' | 'separado' | 'entregue' | 'pendente'
        """
        sql = "UPDATE lotes_producao SET separacao_status = %s"
        params = [novo_status]
        if novo_status == 'separado':
            sql += ", data_separacao = COALESCE(data_separacao, NOW()), usuario_separacao_id = %s"
            params.append(usuario_id)
        elif novo_status == 'entregue':
            sql += ", data_entrega = COALESCE(data_entrega, NOW()), usuario_entrega_id = %s"
            params.append(usuario_id)
        elif novo_status == 'separando':
            sql += ", usuario_separacao_id = %s"
            params.append(usuario_id)
        sql += " WHERE ordem = %s"
        params.append(ordem)
        return self.execute(sql, params)

    def get_lotes_separacao_tv(self):
        """Retorna lotes com info de separação para a TV do almoxarifado."""
        return self.query("""
            SELECT l.ordem, l.lote_codigo, l.descricao_produto, l.qtde_ordem,
                   l.prioridade, l.data_previsao_erp, l.departamento_atual,
                   l.status, l.separacao_status, l.data_separacao, l.data_entrega,
                   l.data_importacao,
                   (SELECT COUNT(*) FROM operacoes_producao op WHERE op.lote_ordem = l.ordem) AS total_operacoes,
                   (SELECT COUNT(*) FROM operacoes_producao op WHERE op.lote_ordem = l.ordem AND op.status = 'concluido') AS operacoes_concluidas,
                   DATEDIFF(CURDATE(), l.data_previsao_erp) AS dias_atraso
            FROM lotes_producao l
            WHERE l.status IN ('liberado', 'em_producao')
              AND l.separacao_status IN ('pendente', 'separando', 'separado')
            ORDER BY FIELD(l.separacao_status, 'pendente', 'separando', 'separado'),
                     FIELD(l.prioridade, 'urgente', 'alta', 'media', 'baixa'),
                     l.data_previsao_erp ASC
        """)

    def get_novas_liberacoes(self, ultima_data=None):
        """Retorna lotes liberados após uma data (para alerta sonoro na TV)."""
        sql = """
            SELECT ordem, lote_codigo, descricao_produto, qtde_ordem,
                   prioridade, data_previsao_erp, separacao_status
            FROM lotes_producao
            WHERE status = 'liberado' AND separacao_status = 'pendente'
        """
        params = []
        if ultima_data:
            sql += " AND data_ultima_sync > %s"
            params.append(ultima_data)
        sql += " ORDER BY data_ultima_sync DESC LIMIT 5"
        return self.query(sql, params)

    def get_requisicoes_pendentes_tv(self):
        return self.query("""
            SELECT r.id, r.lote_ordem, r.material_descricao AS material, r.quantidade,
                   r.departamento_solicitante AS solicitado_por, r.data_solicitacao, r.status,
                   l.descricao_produto, l.prioridade, l.data_previsao_erp
            FROM requisicoes_materiais r
            LEFT JOIN lotes_producao l ON r.lote_ordem = l.ordem
            WHERE r.status = 'pendente'
            ORDER BY FIELD(l.prioridade, 'urgente', 'alta', 'media', 'baixa'), r.data_solicitacao DESC
        """)

    def count_requisicoes_aprovadas_hoje(self):
        result = self.query_one("""
            SELECT COUNT(*) as t FROM requisicoes_materiais
            WHERE status IN ('aprovado', 'entregue') AND DATE(data_atendimento) = CURDATE()
        """)
        return result['t'] if result else 0

    # =============================================
    # LOGS
    # =============================================

    def add_log(self, usuario_id, acao, descricao=None, tabela=None, registro_id=None):
        try:
            usuario = self.query_one("SELECT nome FROM usuarios WHERE id = %s", (usuario_id,))
            nome = usuario['nome'] if usuario else 'Sistema'
            self.execute("""
                INSERT INTO log_atividades (usuario_id, usuario_nome, acao, tabela, registro_id, descricao)
                VALUES (%s, %s, %s, %s, %s, %s)
            """, [usuario_id, nome, acao, tabela, registro_id, descricao])
        except:
            pass

    def get_logs(self, limit=100, usuario_id=None):
        sql = "SELECT * FROM log_atividades"
        params = []
        if usuario_id:
            sql += " WHERE usuario_id = %s"
            params.append(usuario_id)
        sql += " ORDER BY data_hora DESC LIMIT %s"
        params.append(limit)
        return self.query(sql, params)

    # =============================================
    # DASHBOARD GERENTE — Visão consolidada
    # =============================================

    def get_dashboard_gerente(self):
        """Retorna todos os dados do dashboard gerencial em poucas queries."""
        try:
            # 1. KPIs principais
            kpis = self.query_one("""
                SELECT
                    COUNT(*) AS total_lotes,
                    SUM(status = 'importado')     AS aguardando_liberacao,
                    SUM(status = 'liberado')      AS aguardando_inicio,
                    SUM(status = 'em_producao')   AS em_producao,
                    SUM(status = 'pausado')       AS pausados,
                    SUM(status = 'finalizado' AND DATE(data_fim_producao) = CURDATE()) AS concluidos_hoje,
                    SUM(status = 'finalizado' AND MONTH(data_fim_producao) = MONTH(CURDATE())
                                                AND YEAR(data_fim_producao)  = YEAR(CURDATE())) AS concluidos_mes,
                    SUM(prioridade = 'urgente' AND status NOT IN ('finalizado','cancelado')) AS urgentes,
                    SUM(prioridade = 'alta'     AND status NOT IN ('finalizado','cancelado')) AS altas,
                    SUM(data_previsao_erp IS NOT NULL
                        AND data_previsao_erp < CURDATE()
                        AND status NOT IN ('finalizado','cancelado')) AS atrasados
                FROM lotes_producao
            """)

            # 2. Produção por setor (quantidade de operações por status)
            por_setor = self.query("""
                SELECT
                    d.codigo AS departamento,
                    d.nome   AS nome_departamento,
                    d.cor_hex,
                    d.ordem_fluxo,
                    COUNT(op.id) AS total_ops,
                    SUM(op.status = 'pendente')     AS pendentes,
                    SUM(op.status = 'em_andamento') AS em_andamento,
                    SUM(op.status = 'pausado')      AS pausados,
                    SUM(op.status = 'concluido' AND DATE(op.data_fim) = CURDATE()) AS concluidas_hoje
                FROM departamentos d
                LEFT JOIN operacoes_producao op ON op.departamento = d.codigo
                WHERE d.ativo = 1 AND d.ordem_fluxo > 0
                GROUP BY d.codigo, d.nome, d.cor_hex, d.ordem_fluxo
                ORDER BY d.ordem_fluxo
            """)

            # 3. Produção dos últimos 7 dias (finalizados por dia)
            por_dia = self.query("""
                SELECT
                    DATE(data_fim_producao) AS dia,
                    COUNT(*) AS total,
                    SUM(qtde_ordem) AS pecas
                FROM lotes_producao
                WHERE status = 'finalizado'
                  AND data_fim_producao >= DATE_SUB(CURDATE(), INTERVAL 6 DAY)
                GROUP BY DATE(data_fim_producao)
                ORDER BY dia
            """)

            # 4. Próximas OPs a iniciar (liberadas + aguardando, com prioridade)
            proximas = self.query("""
                SELECT ordem, lote_codigo, descricao_produto, qtde_ordem,
                       prioridade, data_previsao_erp, status
                FROM lotes_producao
                WHERE status IN ('liberado', 'importado')
                ORDER BY FIELD(prioridade, 'urgente','alta','media','baixa'),
                         data_previsao_erp ASC
                LIMIT 8
            """)

            # 5. Em produção agora
            em_producao = self.query("""
                SELECT ordem, lote_codigo, descricao_produto, qtde_ordem,
                       prioridade, data_inicio_producao, departamento_atual
                FROM lotes_producao
                WHERE status = 'em_producao'
                ORDER BY data_inicio_producao ASC
                LIMIT 8
            """)

            # 6. TOP atrasados (alertas)
            atrasados = self.query("""
                SELECT ordem, lote_codigo, descricao_produto, qtde_ordem,
                       prioridade, data_previsao_erp, status, departamento_atual
                FROM lotes_producao
                WHERE data_previsao_erp IS NOT NULL
                  AND data_previsao_erp < CURDATE()
                  AND status NOT IN ('finalizado','cancelado')
                ORDER BY FIELD(prioridade, 'urgente','alta','media','baixa'),
                         data_previsao_erp ASC
                LIMIT 10
            """)

            return {
                'kpis': {
                    'total_lotes':          int(kpis['total_lotes']          or 0),
                    'aguardando_liberacao': int(kpis['aguardando_liberacao'] or 0),
                    'aguardando_inicio':    int(kpis['aguardando_inicio']    or 0),
                    'em_producao':          int(kpis['em_producao']          or 0),
                    'pausados':             int(kpis['pausados']             or 0),
                    'concluidos_hoje':      int(kpis['concluidos_hoje']      or 0),
                    'concluidos_mes':       int(kpis['concluidos_mes']       or 0),
                    'urgentes':             int(kpis['urgentes']             or 0),
                    'altas':                int(kpis['altas']                or 0),
                    'atrasados':            int(kpis['atrasados']            or 0),
                },
                'por_setor':      por_setor,
                'por_dia':        por_dia,
                'proximas_ops':   proximas,
                'em_producao':    em_producao,
                'atrasados':      atrasados,
            }
        except Exception as e:
            print(f"Erro get_dashboard_gerente: {e}")
            return {
                'kpis': {'total_lotes':0,'aguardando_liberacao':0,'aguardando_inicio':0,'em_producao':0,
                         'pausados':0,'concluidos_hoje':0,'concluidos_mes':0,'urgentes':0,'altas':0,'atrasados':0},
                'por_setor': [], 'por_dia': [], 'proximas_ops': [], 'em_producao': [], 'atrasados': []
            }

    # =============================================
    # ESTOQUE INTERNO (ALMOXARIFADO)
    # =============================================

    def get_estoque_interno(self, status_filtro=None, tipo=None):
        """Retorna itens do estoque. status_filtro: 'baixo'|'normal'|None  tipo: 'almoxarifado'|'fabrica'|None"""
        sql = "SELECT * FROM estoque_interno WHERE 1=1"
        params = []
        if tipo:
            sql += " AND tipo = %s"
            params.append(tipo)
        if status_filtro == 'baixo':
            sql += " AND (qtd_atual <= 0 OR (qtd_inicial > 0 AND qtd_atual <= qtd_inicial * 0.2))"
        elif status_filtro == 'normal':
            sql += " AND qtd_atual > 0 AND (qtd_inicial = 0 OR qtd_atual > qtd_inicial * 0.2)"
        sql += " ORDER BY (qtd_atual <= 0 OR (qtd_inicial > 0 AND qtd_atual <= qtd_inicial * 0.2)) DESC, descricao ASC"
        return self.query(sql, params)

    def get_estoque_kpis(self, tipo=None):
        """KPIs do estoque. Filtra por tipo se informado."""
        sql = """
            SELECT
                COUNT(*) AS total_itens,
                SUM(CASE WHEN qtd_atual <= 0 THEN 1 ELSE 0 END) AS sem_estoque,
                SUM(CASE WHEN qtd_atual > 0 AND qtd_inicial > 0 AND qtd_atual <= qtd_inicial * 0.2 THEN 1 ELSE 0 END) AS estoque_baixo,
                SUM(CASE WHEN qtd_atual > 0 AND (qtd_inicial = 0 OR qtd_atual > qtd_inicial * 0.2) THEN 1 ELSE 0 END) AS estoque_ok
            FROM estoque_interno
        """
        if tipo:
            sql += " WHERE tipo = %s"
            return self.query_one(sql, (tipo,))
        return self.query_one(sql)

    def adicionar_estoque(self, dados):
        """Adiciona item ao estoque. Se existe o codigo+tipo, acumula. tipo: 'almoxarifado'|'fabrica'"""
        qtd = dados.get('qtd_atual', 0)
        tipo = dados.get('tipo', 'almoxarifado')
        sql = """
            INSERT INTO estoque_interno (codigo, descricao, unidade, qtd_atual, qtd_minima, qtd_inicial, tipo)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
            ON DUPLICATE KEY UPDATE
                descricao = VALUES(descricao),
                unidade = VALUES(unidade),
                qtd_inicial = qtd_inicial + VALUES(qtd_inicial),
                qtd_atual = qtd_atual + VALUES(qtd_atual)
        """
        return self.execute(sql, [
            dados['codigo'], dados['descricao'], dados.get('unidade', 'UN'),
            qtd, dados.get('qtd_minima', 0),
            dados.get('qtd_inicial', qtd), tipo
        ])

    def repor_estoque(self, item_id, nova_qtd_total):
        """Reposiciona o estoque: define nova qtd_atual e atualiza qtd_inicial como referência."""
        sql = """
            UPDATE estoque_interno
            SET qtd_atual = %s,
                qtd_inicial = %s,
                updated_at = NOW()
            WHERE id = %s
        """
        return self.execute(sql, [nova_qtd_total, nova_qtd_total, item_id])

    def baixar_estoque_por_codigo(self, codigo, quantidade, tipo=None):
        """Dá baixa no estoque pelo código. Se tipo, filtra por tipo."""
        if tipo:
            sql = "UPDATE estoque_interno SET qtd_atual = GREATEST(qtd_atual - %s, 0), updated_at = NOW() WHERE codigo = %s AND tipo = %s"
            return self.execute(sql, [quantidade, codigo, tipo])
        sql = "UPDATE estoque_interno SET qtd_atual = GREATEST(qtd_atual - %s, 0), updated_at = NOW() WHERE codigo = %s"
        return self.execute(sql, [quantidade, codigo])

    def registrar_baixa_estoque(self, codigo, quantidade, ordem, motivo='liberacao_of', tipo='fabrica'):
        """Dá baixa e registra no histórico de movimentação."""
        self.baixar_estoque_por_codigo(codigo, quantidade, tipo=tipo)
        where = "WHERE codigo = %s"
        params_hist = [quantidade, ordem, motivo, codigo]
        if tipo:
            where += " AND tipo = %s"
            params_hist.append(tipo)
        sql_hist = f"""
            INSERT INTO estoque_movimentacao (item_estoque_id, tipo, quantidade, ordem_relacionada, usuario_id, observacao)
            SELECT id, 'baixa', %s, %s, NULL, %s
            FROM estoque_interno {where}
        """
        self.execute(sql_hist, params_hist)

    def get_estoque_por_codigo(self, codigo, tipo=None):
        """Busca item de estoque pelo código e opcionalmente por tipo."""
        if tipo:
            return self.query_one("SELECT * FROM estoque_interno WHERE codigo = %s AND tipo = %s", (codigo, tipo))
        return self.query_one("SELECT * FROM estoque_interno WHERE codigo = %s", (codigo,))

    def atualizar_estoque(self, item_id, dados):
        """Atualiza dados de um item do estoque."""
        campos = []
        params = []
        for campo in ('descricao', 'unidade', 'qtd_minima'):
            if campo in dados:
                campos.append(f"{campo} = %s")
                params.append(dados[campo])
        if not campos:
            return False
        params.append(item_id)
        sql = f"UPDATE estoque_interno SET {', '.join(campos)}, updated_at = NOW() WHERE id = %s"
        return self.execute(sql, params)

    def get_movimentacao_estoque(self, limite=50):
        """Retorna historico de movimentacoes do estoque."""
        sql = """
            SELECT m.*, e.codigo, e.descricao AS material_descricao, e.unidade, e.tipo AS estoque_tipo,
                   u.nome AS usuario_nome
            FROM estoque_movimentacao m
            LEFT JOIN estoque_interno e ON m.item_estoque_id = e.id
            LEFT JOIN usuarios u ON m.usuario_id = u.id
            ORDER BY m.created_at DESC
            LIMIT %s
        """
        return self.query(sql, (limite,))

    def mover_estoque_para_fabrica(self, item_id, quantidade, usuario_id=None):
        """Move quantidade do almoxarifado para a fabrica."""
        item = self.query_one("SELECT * FROM estoque_interno WHERE id = %s AND tipo = 'almoxarifado'", (item_id,))
        if not item or quantidade <= 0:
            return False
        qtd_mover = min(quantidade, item['qtd_atual'])
        # Deduz do almoxarifado
        self.execute(
            "UPDATE estoque_interno SET qtd_atual = GREATEST(qtd_atual - %s, 0), updated_at = NOW() WHERE id = %s",
            [qtd_mover, item_id]
        )
        # Adiciona na fabrica
        self.execute("""
            INSERT INTO estoque_interno (codigo, descricao, unidade, qtd_atual, qtd_minima, qtd_inicial, tipo)
            VALUES (%s, %s, %s, %s, 0, %s, 'fabrica')
            ON DUPLICATE KEY UPDATE
                qtd_atual = qtd_atual + VALUES(qtd_atual),
                qtd_inicial = qtd_inicial + VALUES(qtd_inicial)
        """, [item['codigo'], item['descricao'], item['unidade'], qtd_mover, qtd_mover])
        # Registra movimentacao
        fab = self.query_one("SELECT id FROM estoque_interno WHERE codigo = %s AND tipo = 'fabrica'", (item['codigo'],))
        if fab:
            self.execute("""INSERT INTO estoque_movimentacao (item_estoque_id, tipo, quantidade, usuario_id, observacao)
                            VALUES (%s, 'transferencia', %s, %s, 'Separado do almoxarifado p/ fabrica')""",
                         [fab['id'], qtd_mover, usuario_id])
        return True

    def get_lotes_liberados_pendentes(self):
        """OFs liberadas aguardando separacao."""
        return self.query("""
            SELECT ordem, lote_descricao, descricao_produto, qtde_ordem AS quantidade,
                   prioridade, departamento_atual AS departamento, data_previsao_erp AS data_previsao
            FROM lotes
            WHERE status = 'liberado'
            AND separacao_status IN ('pendente', 'separando')
            ORDER BY
                CASE prioridade WHEN 'urgente' THEN 1 WHEN 'alta' THEN 2 WHEN 'media' THEN 3 ELSE 4 END,
                data_previsao_erp ASC
        """)

    def get_codigos_produtos_ofs_ativas(self):
        """Retorna todos os codigo_produto das OFs ativas (para filtrar peças fabricadas do BOM)."""
        rows = self.query("""
            SELECT DISTINCT codigo_produto
            FROM lotes_producao
            WHERE codigo_produto IS NOT NULL AND codigo_produto != ''
        """)
        return set(str(r['codigo_produto']) for r in rows)

