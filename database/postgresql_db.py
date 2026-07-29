"""
Classe de conexão e operações com PostgreSQL (ERP Lógica - Somente Leitura)
v4.2.2 — Reescrito com base no mapeamento real do ERP Salutem

ATENÇÃO: PostgreSQL é o banco do ERP principal (Lógica).
- SOMENTE LEITURA (SELECT)
- NUNCA fazer INSERT, UPDATE ou DELETE
- Qualquer modificação é feita no MariaDB (sistema local)
- Tabelas do ERP: pedido, empresa, loteprod, ordem, produto, fases, reqordem, passfase, respror

ESTRUTURA DO ERP (confirmada pelo cliente):
- loteprod: Tabela principal de lotes (lotcod, lotdes, lotdtini, lotdtpre, lotstatus)
- ordem: Ordens de produção (OFs) vinculadas a um lote via lotcod
- ordem3: Hierarquia PAI/FILHO — quando ordem != 0, é a OP PAI (produto final)
- fases: Setores (1=ALMOXARIFADO, 20=PINTURA, 50=MONTAGEM, 80=EMBALAGEM, etc)
- reqordem: Requisições de materiais por OP
- produto: Cadastro de produtos (coluna 'produto' = código, 'pronome' = nome)
- passfase: Apontamentos de produção por OP e fase
- respror: Roteiro de processos por OP

STATUS DO LOTE (lotstatus):
- EC = Encerrado
- EP = Em Produção
- ES = Em Separação
"""
import psycopg2
from psycopg2.extras import RealDictCursor
from contextlib import contextmanager
from config.config import Config


class DatabasePostgreSQL:
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(DatabasePostgreSQL, cls).__new__(cls)
        return cls._instance

    def __init__(self):
        self.config = {
            'host': Config.PG_HOST,
            'port': Config.PG_PORT,
            'user': Config.PG_USERNAME,
            'password': Config.PG_PASSWORD,
            'database': Config.PG_DATABASE
        }

    @contextmanager
    def get_connection(self):
        connection = psycopg2.connect(**self.config)
        try:
            yield connection
        except Exception as e:
            raise e
        finally:
            connection.close()

    def query(self, sql, params=None):
        try:
            with self.get_connection() as conn:
                with conn.cursor(cursor_factory=RealDictCursor) as cursor:
                    cursor.execute(sql, params or ())
                    results = cursor.fetchall()
                    return [{k: (v.replace('\\','') if isinstance(v,str) else v) for k,v in dict(row).items()} for row in results]
        except Exception as e:
            # Se der erro de coluna, tenta uma versão simplificada sem o vínculo de ordem
            if 'UndefinedColumn' in str(e) and 'ordem_producao' in sql:
                import re
                # Remove a subquery de ordem_producao
                sql_limpo = re.sub(r'\(SELECT o\.ordem::integer.*?\) AS ordem_producao,?', '', sql, flags=re.DOTALL)
                # Tenta novamente sem a subquery problematica
                with self.get_connection() as conn:
                    with conn.cursor(cursor_factory=RealDictCursor) as cursor:
                        cursor.execute(sql_limpo, params or ())
                        results = cursor.fetchall()
                        return [{k: (v.replace('\\','') if isinstance(v,str) else v) for k,v in dict(row).items()} for row in results]
            raise e

    def query_one(self, sql, params=None):
        with self.get_connection() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cursor:
                cursor.execute(sql, params or ())
                result = cursor.fetchone()
                return dict(result) if result else None

    # =============================================
    # LOTES — Tabela principal: loteprod
    # =============================================

    def get_lotes_agrupados_abertos(self):
        """
        Retorna lotes abertos do ERP (tabela loteprod) com:
        - Código, descrição, datas
        - OP PAI (produto final) identificada via tabela ordem3
        - Total de OFs e quantidade total (da tabela ordem)
        - Nome do produto final (da tabela produto)

        Considera "abertos" os lotes com lotstatus IN ('EP', 'ES') ou NULL.
        """
        sql = """
            SELECT
                lp.lotcod AS lote_codigo,
                lp.lotdes AS lote_descricao,
                lp.lotdtini AS data_abertura,
                lp.lotdtpre AS data_previsao,
                lp.lotstatus AS status_erp,
                NULLIF(TRIM(lp.lottrans),'') AS lote_observacao,

                -- OP PAI (produto final): pega da ordem onde ordnivprod = '1'
                (SELECT o.ordproduto
                 FROM public.ordem o
                 WHERE o.lotcod = lp.lotcod AND o.ordnivprod = '1'
                 LIMIT 1) AS produto_final_codigo,

                -- Total de OFs do lote
                (SELECT COUNT(DISTINCT o.ordem)
                 FROM public.ordem o
                 WHERE o.lotcod = lp.lotcod) AS total_ofs,

                -- Quantidade do produto final (OP PAI, nivel_producao = '1')
                (SELECT COALESCE(o.ordquanti, 0)
                 FROM public.ordem o
                 WHERE o.lotcod = lp.lotcod
                   AND o.ordnivprod = '1'
                 LIMIT 1) AS quantidade_pai,

                -- Quantidade total de pecas (soma de TODAS as OFs)
                (SELECT COALESCE(SUM(o.ordquanti), 0)
                 FROM public.ordem o
                 WHERE o.lotcod = lp.lotcod) AS quantidade_total,

                -- Maior numero de OP (para usar como "ordem" no sistema local)
                (SELECT MAX(o.ordem)
                 FROM public.ordem o
                 WHERE o.lotcod = lp.lotcod) AS maior_ordem

            FROM
                public.loteprod lp
            WHERE
                lp.lotcod IS NOT NULL
                AND lp.lotcod <> ''
                AND (lp.lotstatus IS NULL OR lp.lotstatus IN ('EP', 'ES', ''))
            ORDER BY
                lp.lotcod DESC
        """
        return self.query(sql)

    def get_produto_pronto_por_lote(self, lote_codigo):
        """Retorna o produto PAI (final) do lote.
        Usa ordem.ordnivprod = '1' para identificar o produto final."""
        sql = """
            SELECT 
                o.ordproduto AS codigo_produto,
                p.pronome AS nome_produto,
                o.ordquanti::float AS quantidade
            FROM public.ordem o
            LEFT JOIN public.produto p ON TRIM(o.ordproduto) = TRIM(p.produto)
            WHERE o.lotcod = %s AND o.ordnivprod = '1'
            LIMIT 1
        """
        try:
            result = self.query_one(sql, (lote_codigo,))
            if result and result.get('codigo_produto'):
                return result
        except Exception:
            pass
        # Fallback: pega qualquer ordem do lote
        return self._fallback_produto_lote(lote_codigo)

    
    def _fallback_produto_lote(self, lote_codigo):
        """Fallback: pega a OP PAI (nivel 1) do lote, senao a primeira."""
        sql = """
            SELECT
                o.ordproduto AS codigo_produto,
                p.pronome AS nome_produto,
                o.ordquanti AS quantidade
            FROM
                public.ordem o
            LEFT JOIN
                public.produto p ON o.ordproduto::TEXT = p.produto::TEXT
            WHERE
                o.lotcod = %s
            ORDER BY
                CASE WHEN o.ordnivprod = '1' THEN 0 ELSE 1 END,
                o.ordem DESC
            LIMIT 1
        """
        return self.query_one(sql, (lote_codigo,))

    # =============================================
    # ORDENS (OFs) — Tabela: ordem
    # =============================================

    def get_ordens_por_lote(self, lote_codigo):
        """Retorna todas as OFs de um lote específico."""
        sql = """
            SELECT
                ordem,
                tipoord AS tipo_ordem,
                ordquanti AS quantidade,
                orddtaber AS data_abertura,
                orddtprev AS data_previsao,
                ordproduto AS produto,
                lotcod AS lote_codigo,
                ordnivprod AS nivel_producao
            FROM
                public.ordem
            WHERE
                lotcod = %s
            ORDER BY
                ordem
        """
        return self.query(sql, (lote_codigo,))

    def get_lotes_abertos(self):
        """Retorna todas as OFs (para compatibilidade)."""
        sql = """
            SELECT
                ordem,
                tipoord AS tipo_ordem,
                ordquanti AS quantidade,
                orddtaber AS data_abertura,
                orddtprev AS data_previsao,
                ordproduto AS produto,
                lotcod AS lote_codigo
            FROM
                public.ordem
            ORDER BY
                ordem DESC
        """
        return self.query(sql)

    # =============================================
    # PROCESSOS / ROTEIRO — Tabela: respror
    # =============================================

    def get_processos_ordem(self, ordem):
        """
        Retorna o roteiro de processos de uma OP.
        JOIN com fases para pegar o nome do setor (fasnome).
        """
        sql = """
            SELECT
                rprnumero AS numero_sequencial,
                rprordem AS ordem,
                rprqtde AS quantidade,
                rprproce AS processo,
                rproper AS operacao,
                rproped AS descricao_processo,
                rprfase AS fase,
                f.fasnome AS nome_departamento,
                rprmaq AS codigo_maquina,
                rprmaqno AS nome_maquina,
                COALESCE(CAST(f.fase AS INTEGER), 999) AS ordem_departamento
            FROM
                public.respror rpr
            INNER JOIN
                public.fases f ON rpr.rprfase::TEXT = f.fase::TEXT
            WHERE
                rpr.rprordem::TEXT = %s::TEXT
            ORDER BY
                rpr.rprproce
        """
        try:
            return self.query(sql, (ordem,))
        except Exception:
            # Fallback: sem JOIN com fases
            sql_fb = """
                SELECT
                    rprnumero AS numero_sequencial,
                    rprordem AS ordem,
                    rprqtde AS quantidade,
                    rprproce AS processo,
                    rproper AS operacao,
                    rproped AS descricao_processo,
                    rprfase AS fase,
                    NULL AS nome_departamento,
                    rprmaq AS codigo_maquina,
                    rprmaqno AS nome_maquina,
                    COALESCE(CAST(rprfase AS INTEGER), 999) AS ordem_departamento
                FROM
                    public.respror rpr
                WHERE
                    rpr.rprordem::TEXT = %s::TEXT
                ORDER BY
                    rpr.rprproce
            """
            return self.query(sql_fb, (ordem,))

    # =============================================
    # REQUISIÇÕES — Tabela: reqordem
    # =============================================

    def get_requisicoes_ordem(self, ordem):
        """
        Retorna todas as requisições de materiais de uma OP.
        JOIN com produto para pegar nome (pronome) e unidade (unimedida).
        """
        sql = """
            SELECT
                reqnumero AS req_numero,
                reqord AS req_codigo,
                reqproduto AS produto,
                rqoquanti AS quantidade,
                reqlote AS lote,
                reqfase AS fase,
                p.pronome AS descricao,
                p.unimedida AS unidade_medida
            FROM
                public.reqordem
            LEFT JOIN
                public.produto p ON reqproduto::TEXT = p.produto::TEXT
            WHERE
                reqord::integer = %s
        """
        try:
            return self.query(sql, (ordem,))
        except Exception:
            # Fallback sem JOIN
            sql_fb = """
                SELECT
                    reqnumero AS req_numero,
                    reqord AS req_codigo,
                    reqproduto AS produto,
                    rqoquanti AS quantidade,
                    reqlote AS lote,
                    reqfase AS fase,
                    NULL AS descricao,
                    NULL AS unidade_medida
                FROM
                    public.reqordem
                WHERE
                    reqord::integer = %s
            """
            return self.query(sql_fb, (ordem,))

    # =============================================
    # RESUMO DO LOTE — Visão consolidada
    # =============================================

    def get_resumo_lote_erp(self, lote_codigo):
        """Retorna um resumo detalhado de um lote específico do ERP."""

        # 1. Informações do lote (tabela loteprod)
        sql_lote = """
            SELECT
                lp.lotcod AS lote_codigo,
                lp.lotdes AS lote_descricao,
                lp.lotdtini AS data_abertura,
                lp.lotdtpre AS data_previsao,
                lp.lotstatus AS status_erp,
                (SELECT COUNT(ordem) FROM public.ordem WHERE lotcod = lp.lotcod) AS total_ofs,
                (SELECT COALESCE(SUM(ordquanti), 0) FROM public.ordem WHERE lotcod = lp.lotcod) AS quantidade_total,
                (SELECT STRING_AGG(DISTINCT ordproduto::text, ', ')
                 FROM public.ordem WHERE lotcod = lp.lotcod) AS produtos_lista
            FROM
                public.loteprod lp
            WHERE
                lp.lotcod = %s
        """
        lote_info = self.query_one(sql_lote, (lote_codigo,))

        if not lote_info:
            return None

        # 2. Setores envolvidos (via respror + fases)
        sql_setores = """
            SELECT
                STRING_AGG(DISTINCT f.fasnome::text, ' -> ') AS setores_envolvidos
            FROM
                public.ordem o
            INNER JOIN
                public.respror rpr ON o.ordem::TEXT = rpr.rprordem::TEXT
            INNER JOIN
                public.fases f ON rpr.rprfase::TEXT = f.fase::TEXT
            WHERE
                o.lotcod = %s
        """
        setores_info = self.query_one(sql_setores, (lote_codigo,))

        lote_info['setores_envolvidos'] = setores_info['setores_envolvidos'] if setores_info else 'N/A'

        return lote_info

    # =============================================
    # DATAS DE PEDIDO (mantido para compatibilidade)
    # =============================================

    def get_datas_pedido(self, ordens):
        """Busca peddata e pedprevi da tabela pedido por lista de ordens"""
        if not ordens:
            return {}

        placeholders = ",".join(["%s"] * len(ordens))
        sql = f"""
            SELECT pedido, peddata, pedprevi
            FROM pedido
            WHERE pedido IN ({placeholders})
        """
        results = self.query(sql, ordens)
        return {r["pedido"]: {"peddata": r["peddata"], "pedprevi": r["pedprevi"]} for r in results}

    # =============================================
    # BUSCA DE PRODUTO POR CÓDIGO
    # =============================================

    def buscar_produto_por_codigo(self, codigo):
        """Busca produto no ERP pelo código. Retorna dict ou None."""
        sql = """
            SELECT produto AS codigo, pronome AS descricao, unimedida AS unidade
            FROM public.produto
            WHERE produto::TEXT = %s
            LIMIT 1
        """
        return self.query_one(sql, (str(codigo).strip(),))

    def buscar_produtos_por_nome(self, termo):
        """Busca produtos no ERP pelo nome (like). Retorna lista."""
        sql = """
            SELECT produto AS codigo, pronome AS descricao, unimedida AS unidade
            FROM public.produto
            WHERE pronome ILIKE %s
            ORDER BY pronome
            LIMIT 20
        """
        return self.query(sql, (f'%{termo}%',))

    # ═══════════════════════════════════════════════════════
    # PEDIDOS DE VENDA — Tabela: pedido + empresa
    # ═══════════════════════════════════════════════════════

    STATUS_MAP = {
        '001': 'Pedido Não Aprovado',
        '002': 'Pedido em Aberto',
        '003': 'Vínculo com OF Estática',
        '004': 'Vínculo com OF em Processo',
        '005': 'Vínculo com OF Encerrada',
        '006': 'Vínculo com OF Com Problema',
        '007': 'Atendido Parcial',
        '008': 'Atendido Total',
        '009': 'Vínculo com Expedição',
        '010': 'Pedido Cancelado',
        '': 'Aberto'
    }

    SIT_MAP = {
        'A': 'Aprovado',
        'P': 'Pendente',
        'C': 'Cancelado',
        'I': 'Incompleto',
    }

    def get_pedidos_erp(self, status=None, busca=None, limite=100):
        """
        Retorna pedidos de venda do ERP com cliente, razão social, status, etc.
        status: 'todos', 'aberto', 'atrasado', 'producao', 'atendido', 'cancelado'
        busca: texto para filtrar por número pedido, cliente ou razão social
        """
        sql = """
            SELECT
                p.pedido,
                p.peddata AS data_emissao,
                p.tipoped AS tipo,
                p.pedprevi AS data_previsao,
                p.peddtdigit AS data_digitacao,
                p.pedhrdigit AS hora_digitacao,
                p.pedusu AS usuario_digitou,
                p.deposito,
                p.pedcliente AS codigo_cliente,
                COALESCE(NULLIF(TRIM(e.empnome),''), 'Não identificado') AS razao_social,
                e.empdemptip AS tipo_cliente,
                p.pedordcmp AS ordem_compra,
                p.pedcondica AS condicao_pagamento,
                p.pedtransp AS codigo_transportadora,
                p.pedoperaca AS operacao,
                NULLIF(TRIM(p.pedrepres), '') AS codigo_representante,
                '-' AS nome_representante,
                TRIM(p.pedsitua) AS situacao_codigo,
                TRIM(p.pedsitsit) AS status_codigo,
                COALESCE(NULLIF(TRIM(p.pedordcomp),''), '') AS numero_carga,
                COALESCE(NULLIF(TRIM(p.pedrep),''), '') AS pedido_representante,
                p.pedvlrfat AS valor_faturado,
                p.pedobserva AS observacao,
                p.pedaprova AS aprovado,
                p.peddtrepla AS data_reprogramacao,
                p.peddtaalt AS data_alteracao,
                p.pedusualt AS usuario_alterou,
                CAST(p.pedrepres AS TEXT) AS vendedor,
                -- Buscar OP vinculada via ordem (vínculo via lotcod ou ordped)
                (SELECT o.ordem::integer FROM public.ordem o
                 WHERE o.ordped = p.pedido 
                    OR (NULLIF(TRIM(CAST(p.pedoflote AS TEXT)), '') IS NOT NULL 
                        AND (o.lotcod = TRIM(CAST(p.pedoflote AS TEXT)) OR o.lotcod = REPLACE(TRIM(CAST(p.pedoflote AS TEXT)), 'LOTE ', '')))
                 LIMIT 1) AS ordem_producao
            FROM public.pedido p
            LEFT JOIN public.empresa e ON p.pedcliente::TEXT = e.empresa::TEXT
            WHERE 1=1
        """
        params = []

        # Filtro por status
        if status == 'aberto':
            sql += " AND (TRIM(COALESCE(p.pedsitsit,'')) IN ('01','02','') )"
            sql += " AND TRIM(COALESCE(p.pedsitua,'')) != 'C'"
        elif status == 'producao':
            sql += " AND TRIM(COALESCE(p.pedsitsit,'')) IN ('03','04','06')"
            sql += " AND TRIM(COALESCE(p.pedsitua,'')) != 'C'"
        elif status == 'atendido':
            sql += " AND TRIM(COALESCE(p.pedsitsit,'')) IN ('05','07','08','09')"
        elif status == 'cancelado':
            sql += " AND (TRIM(COALESCE(p.pedsitsit,'')) = '10' OR TRIM(COALESCE(p.pedsitua,'')) = 'C')"
        elif status == 'atrasado':
            sql += " AND p.pedprevi IS NOT NULL"
            sql += " AND p.pedprevi < CURRENT_DATE"
            sql += " AND (TRIM(COALESCE(p.pedsitsit,'')) IN ('01','02','03','04',''))"
            sql += " AND TRIM(COALESCE(p.pedsitua,'')) != 'C'"

        # Busca por texto
        if busca:
            busca_like = f'%{busca}%'
            sql += " AND (CAST(p.pedido AS TEXT) LIKE %s OR NULLIF(TRIM(e.empnome),'') ILIKE %s OR CAST(p.pedcliente AS TEXT) LIKE %s)"
            params.extend([busca_like, busca_like, busca_like])

        # Somente pedidos recentes (últimos 2 anos) e que não são cancelados a menos que solicitado
        if status != 'cancelado':
            sql += " AND p.peddata >= CURRENT_DATE - INTERVAL '2 years'"

        sql += " ORDER BY p.pedido DESC LIMIT %s"
        params.append(limite)

        resultados = self.query(sql, tuple(params))

        # Aplicar mapa de status
        for r in resultados:
            r['status_descricao'] = self.STATUS_MAP.get(r.get('status_codigo') or '', 'Desconhecido')
            r['situacao_descricao'] = self.SIT_MAP.get(r.get('situacao_codigo') or '', 'Desconhecido')

        return resultados

    def get_resumo_pedidos_erp(self):
        """Retorna resumo rápido de pedidos para KPIs.
        NOTA: Colunas do ERP têm valores com espaços (CHAR fixo).
        Usamos TRIM para comparar corretamente.
        Pedidos sem status (vazio após TRIM) são considerados 'Em Aberto'.
        """
        try:
            resultados = self.query("""
                SELECT
                    COUNT(*) AS total_pedidos,
                    SUM(CASE WHEN TRIM(CAST(COALESCE(pedsitsit,'') AS TEXT)) IN ('001','002','') AND TRIM(CAST(COALESCE(pedsitua,'') AS TEXT)) != 'C' THEN 1 ELSE 0 END) AS em_aberto,
                    SUM(CASE WHEN TRIM(CAST(COALESCE(pedsitsit,'') AS TEXT)) IN ('003','004') AND TRIM(CAST(COALESCE(pedsitua,'') AS TEXT)) != 'C' THEN 1 ELSE 0 END) AS em_producao,
                    SUM(CASE WHEN TRIM(CAST(COALESCE(pedsitsit,'') AS TEXT)) = '005' AND TRIM(CAST(COALESCE(pedsitua,'') AS TEXT)) != 'C' THEN 1 ELSE 0 END) AS vinculados_of,
                    SUM(CASE WHEN TRIM(CAST(COALESCE(pedsitsit,'') AS TEXT)) IN ('007','008','009') THEN 1 ELSE 0 END) AS atendidos,
                    SUM(CASE WHEN TRIM(CAST(COALESCE(pedsitsit,'') AS TEXT)) = '010' OR TRIM(CAST(COALESCE(pedsitua,'') AS TEXT)) = 'C' THEN 1 ELSE 0 END) AS cancelados,
                    SUM(CASE WHEN pedprevi IS NOT NULL AND pedprevi < CURRENT_DATE AND TRIM(CAST(COALESCE(pedsitsit,'') AS TEXT)) IN ('001','002','003','004','') AND TRIM(CAST(COALESCE(pedsitua,'') AS TEXT)) != 'C' THEN 1 ELSE 0 END) AS atrasados,
                    -- Próximos 3 dias úteis (considerando intervalo de 5 dias corridos para cobrir final de semana)
                    SUM(CASE WHEN pedprevi IS NOT NULL AND pedprevi >= CURRENT_DATE AND pedprevi <= (CURRENT_DATE + INTERVAL '5 days') 
                        AND EXTRACT(DOW FROM pedprevi) NOT IN (0, 6)
                        AND TRIM(CAST(COALESCE(pedsitsit,'') AS TEXT)) IN ('001','002','003','004','') 
                        AND TRIM(CAST(COALESCE(pedsitua,'') AS TEXT)) != 'C' THEN 1 ELSE 0 END) AS proximos_3dias,
                    SUM(CASE WHEN pedprevi IS NOT NULL AND TRIM(CAST(COALESCE(pedsitsit,'') AS TEXT)) IN ('003','004') THEN 1 ELSE 0 END) AS em_of_vinculo,
                    SUM(CASE WHEN TRIM(CAST(COALESCE(pedsitua,'') AS TEXT)) IN ('A', '') THEN 1 ELSE 0 END) AS situacao_a,
                    SUM(CASE WHEN TRIM(CAST(COALESCE(pedsitua,'') AS TEXT)) = 'P' THEN 1 ELSE 0 END) AS situacao_p,
                    SUM(CASE WHEN TRIM(CAST(COALESCE(pedsitua,'') AS TEXT)) = 'C' THEN 1 ELSE 0 END) AS situacao_c,
                    SUM(CASE WHEN TRIM(CAST(COALESCE(pedsitua,'') AS TEXT)) = 'I' THEN 1 ELSE 0 END) AS situacao_i,
                    SUM(COALESCE(pedvlrfat, 0)) AS valor_total_faturado
                FROM public.pedido
                WHERE peddata >= CURRENT_DATE - INTERVAL '1 year'
                  AND peddata IS NOT NULL
            """)
            r = resultados[0] if resultados else {}
            return {
                'total_pedidos': int(r.get('total_pedidos', 0) or 0),
                'em_aberto': int(r.get('em_aberto', 0) or 0),
                'em_producao': int(r.get('em_producao', 0) or 0),
                'vinculados_of': int(r.get('vinculados_of', 0) or 0),
                'atendidos': int(r.get('atendidos', 0) or 0),
                'cancelados': int(r.get('cancelados', 0) or 0),
                'atrasados': int(r.get('atrasados', 0) or 0),
                'proximos_7dias': int(r.get('proximos_7dias', 0) or 0),
                'valor_total_faturado': float(r.get('valor_total_faturado', 0) or 0),
                'situacao_a': int(r.get('situacao_a', 0) or 0),
                'situacao_p': int(r.get('situacao_p', 0) or 0),
                'situacao_c': int(r.get('situacao_c', 0) or 0),
                'situacao_i': int(r.get('situacao_i', 0) or 0),
            }
        except Exception as e:
            print(f"Erro get_resumo_pedidos_erp: {e}")
            import traceback; traceback.print_exc()
            return {
                'total_pedidos':0,'em_aberto':0,'em_producao':0,'vinculados_of':0,
                'atendidos':0,'cancelados':0,'atrasados':0,'proximos_7dias':0,'valor_total_faturado':0,
                'situacao_a':0,'situacao_p':0,'situacao_c':0,'situacao_i':0
            }

    def get_pedidos_erp_para_tv(self, limite=50):
        """
        Retorna pedidos relevantes para a TV da diretoria.
        Filtra pedidos ativos (não cancelados) dos últimos 180 dias.
        Prioriza: Atrasados -> Em Produção -> Próximos Vencimentos.
        """
        sql = """
            SELECT
                p.pedido,
                p.peddata AS data_emissao,
                p.pedprevi AS data_previsao,
                COALESCE(NULLIF(TRIM(CAST(e.empnome AS TEXT)),''), 'Não identificado') AS razao_social,
                TRIM(CAST(COALESCE(p.pedsitsit, '') AS TEXT)) AS status_codigo,
                TRIM(CAST(COALESCE(p.pedsitua, '') AS TEXT)) AS situacao_codigo,
                p.pedvlrfat AS valor_faturado,
                p.pedoflote,
                CAST(p.pedrepres AS TEXT) AS vendedor,
                CAST(p.peddep AS TEXT) AS deposito,
                -- Buscar OP vinculada (vínculo via lotcod ou ordped)
                (SELECT o.ordem::integer FROM public.ordem o
                 WHERE o.ordped = p.pedido 
                    OR (NULLIF(TRIM(CAST(p.pedoflote AS TEXT)), '') IS NOT NULL 
                        AND (o.lotcod = TRIM(CAST(p.pedoflote AS TEXT)) OR o.lotcod = REPLACE(TRIM(CAST(p.pedoflote AS TEXT)), 'LOTE ', '')))
                 LIMIT 1) AS ordem_producao
            FROM public.pedido p
            LEFT JOIN public.empresa e ON p.pedcliente::TEXT = e.empresa::TEXT
            WHERE p.peddata >= CURRENT_DATE - INTERVAL '120 days'
              AND p.peddata IS NOT NULL
              -- Apenas Aprovados (A), Parciais (P) ou Sem Situação (vazio)
              AND (TRIM(CAST(COALESCE(p.pedsitua, '') AS TEXT)) IN ('A', 'P', ''))
              -- Remove Cancelados (010) e Atendidos Totais (007,008,009) para focar no que falta
              AND TRIM(CAST(COALESCE(p.pedsitsit, '') AS TEXT)) NOT IN ('007', '008', '009', '010')
            ORDER BY
                -- 1. Atrasados (em aberto ou em produção)
                CASE WHEN p.pedprevi < CURRENT_DATE THEN 0 ELSE 1 END,
                -- 2. Em produção (status 003, 004)
                CASE WHEN TRIM(CAST(COALESCE(p.pedsitsit, '') AS TEXT)) IN ('003','004') THEN 0 ELSE 1 END,
                -- 3. Data de previsão mais próxima
                p.pedprevi ASC,
                p.pedido DESC
            LIMIT %s
        """
        resultados = self.query(sql, (limite,))

        for r in resultados:
            r['status_descricao'] = self.STATUS_MAP.get(r.get('status_codigo') or '', 'Desconhecido')

        return resultados

    def get_requisicoes_multiplas_ordens(self, ordens):
        """Busca materiais de varias OFs de uma vez (otimizado para dashboard)."""
        if not ordens:
            return []
        placeholders = ','.join(['%s'] * len(ordens))
        sql = f"""
            SELECT
                r.reqord::integer AS ordem,
                r.reqproduto AS produto,
                r.rqoquanti AS quantidade,
                p.pronome AS descricao,
                p.unimedida AS unidade
            FROM public.reqordem r
            LEFT JOIN public.produto p ON r.reqproduto::TEXT = p.produto::TEXT
            WHERE r.reqord::integer IN ({placeholders})
            ORDER BY r.reqord, r.reqproduto
        """
        try:
            return self.query(sql, tuple(ordens))
        except Exception:
            sql_fb = f"""
                SELECT
                    r.reqord::integer AS ordem,
                    r.reqproduto AS produto,
                    r.rqoquanti AS quantidade,
                    NULL AS descricao,
                    NULL AS unidade
                FROM public.reqordem r
                WHERE r.reqord::integer IN ({placeholders})
                ORDER BY r.reqord
            """
            return self.query(sql_fb, tuple(ordens))
