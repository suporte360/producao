import psycopg2
from psycopg2.extras import RealDictCursor
from contextlib import contextmanager
from config.config import Config

class DatabasePostgreSQL:
    def __init__(self):
        # Utiliza as configurações centralizadas do config.py
        self.config = {
            'host': Config.PG_HOST,
            'database': Config.PG_DATABASE,
            'user': Config.PG_USERNAME,
            'password': Config.PG_PASSWORD,
            'port': int(Config.PG_PORT),
            'connect_timeout': 5
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
            # Tratamento resiliente para colunas ausentes ou erros de query
            if 'UndefinedColumn' in str(e):
                import re
                sql_fix = sql
                # Fallback para subquery de ordem_producao se falhar
                if 'ordem_producao' in str(e) or 'o.ordped' in str(e):
                    sql_fix = re.sub(r'\(SELECT o\.ordem::integer.*?\) AS ordem_producao,?', 'NULL AS ordem_producao,', sql_fix, flags=re.DOTALL)

                try:
                    with self.get_connection() as conn:
                        with conn.cursor(cursor_factory=RealDictCursor) as cursor:
                            cursor.execute(sql_fix, params or ())
                            results = cursor.fetchall()
                            return [{k: (v.replace('\\','') if isinstance(v,str) else v) for k,v in dict(row).items()} for row in results]
                except Exception:
                    raise e
            raise e

    def query_one(self, sql, params=None):
        res = self.query(sql, params)
        return res[0] if res else None

    STATUS_MAP = {
        '01': 'Pedido Não Aprovado',
        '02': 'Pedido em Aberto',
        '03': 'Vínculo OF Estática',
        '04': 'Vínculo OF em Processo',
        '05': 'Vínculo OF Encerrada',
        '06': 'Vínculo OF Problema',
        '07': 'Atendido Parcial',
        '08': 'Atendido Total',
        '09': 'Vínculo Expedição',
        '10': 'Pedido Cancelado',
        # Compatibilidade com pedsitsit (3 dígitos)
        '001': 'Pedido Não Aprovado',
        '002': 'Pedido em Aberto',
        '003': 'Vínculo OF Estática',
        '004': 'Vínculo OF em Processo',
        '005': 'Vínculo OF Encerrada',
        '006': 'Vínculo OF Problema',
        '007': 'Atendido Parcial',
        '008': 'Atendido Total',
        '009': 'Vínculo Expedição',
        '010': 'Pedido Cancelado',
        '': 'Aberto'
    }

    SIT_MAP = {
        'A': 'Aprovado',
        'P': 'Parcial',
        'C': 'Cancelado',
        'I': 'Incompleto',
        ' ': 'Em Aberto'
    }

    def get_pedidos_erp(self, status=None, busca=None, limite=100):
        """Lista de pedidos do ERP usando status da tabela pestatus (não pedsitsit)."""
        sql = """
            SELECT DISTINCT ON (p.pedido)
                p.pedido, 
                p.peddata AS data_emissao,
                p.pedprevi AS data_previsao,
                p.pedcliente AS codigo_cliente,
                COALESCE(NULLIF(TRIM(CAST(e.empnome AS TEXT)),''), 'Não identificado') AS razao_social,
                TRIM(CAST(COALESCE(ps.pesstatus, '') AS TEXT)) AS status_codigo,
                TRIM(CAST(COALESCE(p.pedsitua, '') AS TEXT)) AS situacao_codigo,
                p.pedvlrfat AS valor_faturado,
                p.pedoflote,
                CAST(p.pedrepres AS TEXT) AS vendedor,
                CAST(p.deposito AS TEXT) AS deposito
            FROM public.pedido p
            LEFT JOIN public.empresa e ON p.pedcliente::TEXT = e.empresa::TEXT
            LEFT JOIN public.pestatus ps ON p.pedido::TEXT = ps.pespedido::TEXT
            WHERE (
                (p.peddata >= CURRENT_DATE - INTERVAL '180 days' AND TRIM(CAST(COALESCE(ps.pesstatus, '') AS TEXT)) IN ('01', '02', '07'))
                OR (p.peddata >= CURRENT_DATE - INTERVAL '30 days' AND TRIM(CAST(COALESCE(ps.pesstatus, '') AS TEXT)) IN ('08', '10'))
            )
        """
        params = []
        
        if status == 'aberto':
            sql += " AND TRIM(CAST(COALESCE(ps.pesstatus,'') AS TEXT)) = '02'"
        elif status == 'parcial':
            sql += " AND TRIM(CAST(COALESCE(ps.pesstatus,'') AS TEXT)) = '07'"
        elif status == 'producao':
            sql += " AND TRIM(CAST(COALESCE(ps.pesstatus,'') AS TEXT)) IN ('03','04','05','06','07')"
        elif status == 'atrasado':
            sql += " AND p.pedprevi < CURRENT_DATE"
            sql += " AND TRIM(CAST(COALESCE(ps.pesstatus,'') AS TEXT)) IN ('01','02','07')"
        elif status == 'atendido':
            sql += " AND TRIM(CAST(COALESCE(ps.pesstatus,'') AS TEXT)) = '08'"
            sql += " AND p.peddata >= CURRENT_DATE - INTERVAL '30 days'"
        elif status == 'cancelado':
            sql += " AND TRIM(CAST(COALESCE(ps.pesstatus,'') AS TEXT)) = '10'"
            sql += " AND p.peddata >= CURRENT_DATE - INTERVAL '30 days'"

        if busca:
            busca_like = f'%{busca}%'
            sql += " AND (CAST(p.pedido AS TEXT) LIKE %s OR e.empnome ILIKE %s)"
            params.extend([busca_like, busca_like])

        sql += " ORDER BY p.pedido DESC LIMIT %s"
        params.append(limite)
        
        resultados = self.query(sql, tuple(params))
        for r in resultados:
            r['status_descricao'] = self.STATUS_MAP.get(r.get('status_codigo'), 'Desconhecido')
            r['situacao_descricao'] = self.SIT_MAP.get(r.get('situacao_codigo'), 'Desconhecido')
        return resultados

    def get_resumo_pedidos_erp(self):
        """Resumo de KPIs de pedidos do ERP (180 dias).

        USA A TABELA pestatus (pesstatus) — não a coluna pedsitsit da tabela pedido.
        A coluna pedsitsit fica desatualizada no ERP; pestatus é a fonte correta.

        REGRA DE NEGÓCIO (filtro por pesstatus — status do pedido):

          "PDF 1" - Em Aberto (entra no total E no card Em Aberto):
            02 - Pedido em Aberto
          "PDF 2" - Atendido Parcial (entra no total E tem card próprio):
            07 - Atendido Parcial
          "PDF 3" - Atendido Total (NÃO soma em nada, só conta no card Atendidos):
            08 - Atendido Total (somente últimos 30 dias)
          "PDF 4" - Pedido Cancelado (NÃO soma em nada, só conta no card Cancelados):
            10 - Pedido Cancelado (somente últimos 30 dias)
          Outros status (01, 03, 04, 05, 06, 09) não são listados nos PDFs.

        Cards:
          total_pedidos   = 01 + 02 + 07 (180d)
          em_aberto       = 02
          parcial         = 07
          em_producao     = 03 + 04 + 05 + 06 + 07 (não soma no total)
          atrasados       = 01 + 02 + 07 com pedprevi < hoje
          proximos_3dias  = 01 + 02 + 07 com pedprevi entre hoje e hoje+3
          atendidos       = 08 (30d) — não soma em nenhum outro card
          cancelados      = 10 (30d)
        """
        sql = """
            SELECT
                -- TOTAL: 01 + 02 + 07 (180d)
                -- 08 NÃO soma no total, só conta no card Atendidos
                COUNT(DISTINCT CASE
                    WHEN TRIM(CAST(COALESCE(ps.pesstatus,'') AS TEXT)) IN ('01','02','07') THEN p.pedido
                END) as total,

                -- EM ABERTO: 02 ("primeiro PDF")
                COUNT(DISTINCT CASE
                    WHEN TRIM(CAST(COALESCE(ps.pesstatus,'') AS TEXT)) = '02'
                    THEN p.pedido
                END) as em_aberto,

                -- PARCIAL: 07 ("segundo PDF")
                COUNT(DISTINCT CASE
                    WHEN TRIM(CAST(COALESCE(ps.pesstatus,'') AS TEXT)) = '07'
                    THEN p.pedido
                END) as parcial,

                -- EM PRODUÇÃO (OF): 03 + 04 + 05 + 06 + 07 (não soma no total)
                COUNT(DISTINCT CASE
                    WHEN TRIM(CAST(COALESCE(ps.pesstatus,'') AS TEXT)) IN ('03','04','05','06','07')
                    THEN p.pedido
                END) as em_producao,

                -- ATRASADOS: 01 + 02 + 07 com pedprevi < hoje
                COUNT(DISTINCT CASE
                    WHEN TRIM(CAST(COALESCE(ps.pesstatus,'') AS TEXT)) IN ('01','02','07')
                     AND p.pedprevi < CURRENT_DATE
                     AND p.pedprevi > '2000-01-01'
                    THEN p.pedido
                END) as atrasados,

                -- PRÓXIMOS 3 DIAS: 01 + 02 + 07 com pedprevi entre hoje e hoje+3
                COUNT(DISTINCT CASE
                    WHEN TRIM(CAST(COALESCE(ps.pesstatus,'') AS TEXT)) IN ('01','02','07')
                     AND p.pedprevi >= CURRENT_DATE
                     AND p.pedprevi <= (CURRENT_DATE + INTERVAL '3 days')
                    THEN p.pedido
                END) as prox_3_dias,

                -- ATENDIDOS: 08 (30d) — "terceiro PDF", não soma em nenhum outro card
                COUNT(DISTINCT CASE
                    WHEN TRIM(CAST(COALESCE(ps.pesstatus,'') AS TEXT)) = '08'
                     AND p.peddata >= CURRENT_DATE - INTERVAL '30 days'
                    THEN p.pedido
                END) as atendidos,

                -- CANCELADOS: 10 (30d) — "quarto PDF"
                COUNT(DISTINCT CASE
                    WHEN TRIM(CAST(COALESCE(ps.pesstatus,'') AS TEXT)) = '10'
                     AND p.peddata >= CURRENT_DATE - INTERVAL '30 days'
                    THEN p.pedido
                END) as cancelados,

                -- Por situação (pedsitua — situação de aprovação)
                COUNT(DISTINCT CASE WHEN TRIM(CAST(COALESCE(p.pedsitua,'') AS TEXT)) = 'A' THEN p.pedido END) as situacao_a,
                COUNT(DISTINCT CASE WHEN TRIM(CAST(COALESCE(p.pedsitua,'') AS TEXT)) = 'P' THEN p.pedido END) as situacao_p,
                COUNT(DISTINCT CASE WHEN TRIM(CAST(COALESCE(p.pedsitua,'') AS TEXT)) = 'C' THEN p.pedido END) as situacao_c,
                COUNT(DISTINCT CASE WHEN TRIM(CAST(COALESCE(p.pedsitua,'') AS TEXT)) = 'I' THEN p.pedido END) as situacao_i
            FROM public.pedido p
            LEFT JOIN public.pestatus ps ON p.pedido::TEXT = ps.pespedido::TEXT
            WHERE p.peddata >= CURRENT_DATE - INTERVAL '180 days'
        """
        res = self.query_one(sql)
        if not res:
            return {'total_pedidos':0, 'em_aberto':0, 'parcial':0, 'em_producao':0,
                    'atrasados':0, 'proximos_3dias':0, 'atendidos':0, 'cancelados':0,
                    'situacao_a':0, 'situacao_p':0, 'situacao_c':0, 'situacao_i':0}

        return {
            'total_pedidos': int(res.get('total') or 0),
            'em_aberto': int(res.get('em_aberto') or 0),
            'parcial': int(res.get('parcial') or 0),
            'em_producao': int(res.get('em_producao') or 0),
            'atrasados': int(res.get('atrasados') or 0),
            'proximos_3dias': int(res.get('prox_3_dias') or 0),
            'atendidos': int(res.get('atendidos') or 0),
            'cancelados': int(res.get('cancelados') or 0),
            'situacao_a': int(res.get('situacao_a') or 0),
            'situacao_p': int(res.get('situacao_p') or 0),
            'situacao_c': int(res.get('situacao_c') or 0),
            'situacao_i': int(res.get('situacao_i') or 0)
        }

    def get_pedidos_erp_para_tv(self, limite=50):
        sql = """
            SELECT DISTINCT ON (p.pedido)
                p.pedido, 
                p.peddata AS data_emissao,
                p.pedprevi AS data_previsao,
                COALESCE(NULLIF(TRIM(CAST(e.empnome AS TEXT)),''), 'Não identificado') AS razao_social,
                TRIM(CAST(COALESCE(ps.pesstatus, '') AS TEXT)) AS status_codigo,
                TRIM(CAST(COALESCE(p.pedsitua, '') AS TEXT)) AS situacao_codigo,
                p.pedvlrfat AS valor_faturado,
                p.pedoflote,
                CAST(p.pedrepres AS TEXT) AS vendedor,
                CAST(p.deposito AS TEXT) AS deposito
            FROM public.pedido p
            LEFT JOIN public.empresa e ON p.pedcliente::TEXT = e.empresa::TEXT
            LEFT JOIN public.pestatus ps ON p.pedido::TEXT = ps.pespedido::TEXT
            WHERE p.peddata >= CURRENT_DATE - INTERVAL '180 days'
              AND TRIM(CAST(COALESCE(ps.pesstatus, '') AS TEXT)) IN ('01', '02', '07')
            ORDER BY 
                p.pedido,
                CASE WHEN p.pedprevi < CURRENT_DATE THEN 0 ELSE 1 END,
                p.pedprevi ASC
            LIMIT %s
        """
        resultados = self.query(sql, (limite,))
        for r in resultados:
            r['status_descricao'] = self.STATUS_MAP.get(r.get('status_codigo'), 'Desconhecido')
        return resultados
