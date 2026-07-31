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
        sql = """
            SELECT DISTINCT ON (p.pedido)
                p.pedido, 
                p.peddata AS data_emissao,
                p.pedprevi AS data_previsao,
                p.pedcliente AS codigo_cliente,
                COALESCE(NULLIF(TRIM(CAST(e.empnome AS TEXT)),''), 'Não identificado') AS razao_social,
                TRIM(CAST(COALESCE(p.pedsitsit, '') AS TEXT)) AS status_codigo,
                TRIM(CAST(COALESCE(p.pedsitua, '') AS TEXT)) AS situacao_codigo,
                p.pedvlrfat AS valor_faturado,
                p.pedoflote,
                CAST(p.pedrepres AS TEXT) AS vendedor,
                CAST(p.deposito AS TEXT) AS deposito
            FROM public.pedido p
            LEFT JOIN public.empresa e ON p.pedcliente::TEXT = e.empresa::TEXT
            WHERE (
                (p.peddata >= CURRENT_DATE - INTERVAL '180 days' AND TRIM(CAST(COALESCE(p.pedsitsit, '') AS TEXT)) IN ('001', '002', '', '007'))
                OR (p.peddata >= CURRENT_DATE - INTERVAL '30 days' AND TRIM(CAST(COALESCE(p.pedsitsit, '') AS TEXT)) IN ('008', '010'))
                OR (p.peddata >= CURRENT_DATE - INTERVAL '30 days' AND TRIM(CAST(COALESCE(p.pedsitua, '') AS TEXT)) = 'C')
            )
        """
        params = []
        
        if status == 'aberto':
            sql += " AND TRIM(CAST(COALESCE(p.pedsitsit,'') AS TEXT)) IN ('001','002','')"
            sql += " AND TRIM(CAST(COALESCE(p.pedsitua,'') AS TEXT)) NOT IN ('C')"
        elif status == 'producao':
            sql += " AND (NULLIF(TRIM(CAST(p.pedoflote AS TEXT)), '') IS NOT NULL OR TRIM(CAST(COALESCE(p.pedsitsit,'') AS TEXT)) IN ('003','004','005','006'))"
            sql += " AND TRIM(CAST(COALESCE(p.pedsitua,'') AS TEXT)) NOT IN ('C')"
        elif status == 'atrasado':
            sql += " AND p.pedprevi < CURRENT_DATE"
            sql += " AND TRIM(CAST(COALESCE(p.pedsitsit,'') AS TEXT)) NOT IN ('007','008','009','010')"
            sql += " AND TRIM(CAST(COALESCE(p.pedsitua,'') AS TEXT)) NOT IN ('C')"

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

        REGRA DE NEGÓCIO (filtro por pedsitsit — status do pedido):

          Status que entram no TOTAL (somam +) e nos cards derivados:
            001 - Pedido Não Aprovado
            002 - Pedido em Aberto
            007 - Atendido Parcial
            008 - Atendido Total (somente últimos 30 dias)

          Status que NÃO somam no total (mas aparecem na lista/tabela):
            003 - Vínculo com OF Estática
            004 - Vínculo com OF em Processo
            005 - Vínculo com OF Encerrada
            006 - Vínculo com OF com Problema
            009 - Vínculo com Expedição

          Status excluídos:
            010 - Pedido Cancelado (contado separadamente, últimos 30 dias)

        Cards:
          total_pedidos   = 001 + 002 + 007 (180d) + 008 (30d)
          em_aberto       = 001 + 002 (sem OF vinculada)
          em_producao     = 003 + 004 + 005 + 006 + 007
          atrasados       = 001 + 002 + 007 com pedprevi < hoje
          proximos_3dias  = 001 + 002 + 007 com pedprevi entre hoje e hoje+3
          atendidos       = 008 (30d)
          cancelados      = 010 (30d)
        """
        sql = """
            SELECT
                -- TOTAL: 001 + 002 + 007 (180d) + 008 (30d)
                COUNT(DISTINCT CASE
                    WHEN TRIM(CAST(COALESCE(pedsitsit,'') AS TEXT)) IN ('001','002','007') THEN pedido
                    WHEN TRIM(CAST(COALESCE(pedsitsit,'') AS TEXT)) = '008'
                     AND peddata >= CURRENT_DATE - INTERVAL '30 days' THEN pedido
                END) as total,

                -- EM ABERTO: 001 + 002 (sem OF vinculada)
                COUNT(DISTINCT CASE
                    WHEN TRIM(CAST(COALESCE(pedsitsit,'') AS TEXT)) IN ('001','002')
                     AND NULLIF(TRIM(CAST(pedoflote AS TEXT)), '') IS NULL
                    THEN pedido
                END) as em_aberto,

                -- EM PRODUÇÃO (OF): 003 + 004 + 005 + 006 + 007 (não soma no total)
                COUNT(DISTINCT CASE
                    WHEN TRIM(CAST(COALESCE(pedsitsit,'') AS TEXT)) IN ('003','004','005','006','007')
                    THEN pedido
                END) as em_producao,

                -- ATRASADOS: 001 + 002 + 007 com pedprevi < hoje
                COUNT(DISTINCT CASE
                    WHEN TRIM(CAST(COALESCE(pedsitsit,'') AS TEXT)) IN ('001','002','007')
                     AND pedprevi < CURRENT_DATE
                     AND pedprevi > '2000-01-01'
                    THEN pedido
                END) as atrasados,

                -- PRÓXIMOS 3 DIAS: 001 + 002 + 007 com pedprevi entre hoje e hoje+3
                COUNT(DISTINCT CASE
                    WHEN TRIM(CAST(COALESCE(pedsitsit,'') AS TEXT)) IN ('001','002','007')
                     AND pedprevi >= CURRENT_DATE
                     AND pedprevi <= (CURRENT_DATE + INTERVAL '3 days')
                    THEN pedido
                END) as prox_3_dias,

                -- ATENDIDOS: 008 (30d)
                COUNT(DISTINCT CASE
                    WHEN TRIM(CAST(COALESCE(pedsitsit,'') AS TEXT)) = '008'
                     AND peddata >= CURRENT_DATE - INTERVAL '30 days'
                    THEN pedido
                END) as atendidos,

                -- CANCELADOS: 010 (30d)
                COUNT(DISTINCT CASE
                    WHEN TRIM(CAST(COALESCE(pedsitsit,'') AS TEXT)) = '010'
                     AND peddata >= CURRENT_DATE - INTERVAL '30 days'
                    THEN pedido
                END) as cancelados,

                -- Por situação (pedidos dos últimos 180 dias)
                COUNT(DISTINCT CASE WHEN TRIM(CAST(COALESCE(pedsitua,'') AS TEXT)) = 'A' THEN pedido END) as situacao_a,
                COUNT(DISTINCT CASE WHEN TRIM(CAST(COALESCE(pedsitua,'') AS TEXT)) = 'P' THEN pedido END) as situacao_p,
                COUNT(DISTINCT CASE WHEN TRIM(CAST(COALESCE(pedsitua,'') AS TEXT)) = 'C' THEN pedido END) as situacao_c,
                COUNT(DISTINCT CASE WHEN TRIM(CAST(COALESCE(pedsitua,'') AS TEXT)) = 'I' THEN pedido END) as situacao_i
            FROM public.pedido
            WHERE peddata >= CURRENT_DATE - INTERVAL '180 days'
        """
        res = self.query_one(sql)
        if not res:
            return {'total_pedidos':0, 'em_aberto':0, 'em_producao':0, 'atrasados':0,
                    'proximos_3dias':0, 'atendidos':0, 'cancelados':0,
                    'situacao_a':0, 'situacao_p':0, 'situacao_c':0, 'situacao_i':0}

        return {
            'total_pedidos': int(res.get('total') or 0),
            'em_aberto': int(res.get('em_aberto') or 0),
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
                TRIM(CAST(COALESCE(p.pedsitsit, '') AS TEXT)) AS status_codigo,
                TRIM(CAST(COALESCE(p.pedsitua, '') AS TEXT)) AS situacao_codigo,
                p.pedvlrfat AS valor_faturado,
                p.pedoflote,
                CAST(p.pedrepres AS TEXT) AS vendedor,
                CAST(p.deposito AS TEXT) AS deposito
            FROM public.pedido p
            LEFT JOIN public.empresa e ON p.pedcliente::TEXT = e.empresa::TEXT
            WHERE p.peddata >= CURRENT_DATE - INTERVAL '180 days'
              AND (TRIM(CAST(COALESCE(p.pedsitua, '') AS TEXT)) IN ('A', 'P', ''))
              AND TRIM(CAST(COALESCE(p.pedsitsit, '') AS TEXT)) NOT IN ('007', '008', '009', '010')
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
