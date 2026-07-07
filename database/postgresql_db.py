"""
Classe de conexão e operações com PostgreSQL (ERP Lógica - Somente Leitura)
v4.2.2 — Reescrito com base no mapeamento real do ERP Salutem

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
        with self.get_connection() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cursor:
                cursor.execute(sql, params or ())
                results = cursor.fetchall()
                return [{k: (v.replace('\\','') if isinstance(v,str) else v) for k,v in dict(row).items()} for row in results]

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
