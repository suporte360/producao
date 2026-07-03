"""
Sistema de Gerenciamento de Produção - SALUTEM
Arquivo de Configuração v4.1
"""
import os
from datetime import timedelta
from dotenv import load_dotenv

load_dotenv()

class Config:
    # =============================================
    # Segurança — NUNCA coloque valores reais aqui
    # Use variáveis de ambiente (.env)
    # =============================================
    SECRET_KEY = os.environ.get('SECRET_KEY')
    if not SECRET_KEY:
        raise RuntimeError("SECRET_KEY não definida. Configure o arquivo .env")

    # =============================================
    # PostgreSQL (ERP Logica - Somente Leitura)
    # =============================================
    PG_HOST     = os.environ.get('PG_HOST',     '192.168.1.17')
    PG_PORT     = os.environ.get('PG_PORT',     '5432')
    PG_DATABASE = os.environ.get('PG_DATABASE', 'salutem')
    PG_USERNAME = os.environ.get('PG_USERNAME', 'postgres')
    PG_PASSWORD = os.environ.get('PG_PASSWORD', '')

    # =============================================
    # MariaDB/MySQL (Sistema Local - Leitura/Escrita)
    # =============================================
    MYSQL_HOST     = os.environ.get('MYSQL_HOST',     'localhost')
    MYSQL_PORT     = int(os.environ.get('MYSQL_PORT', 3306))
    MYSQL_DATABASE = os.environ.get('MYSQL_DATABASE', 'producao_db')
    MYSQL_USERNAME = os.environ.get('MYSQL_USERNAME', 'producao')
    MYSQL_PASSWORD = os.environ.get('MYSQL_PASSWORD', '')

    # =============================================
    # Ambiente — DEBUG desligado por padrão
    # =============================================
    DEBUG   = os.environ.get('DEBUG', 'False').lower() == 'true'
    TESTING = False

    # =============================================
    # Sistema
    # =============================================
    SISTEMA_NOME  = 'Sistema de Produção SALUTEM'
    SISTEMA_VERSAO = '4.2.0'
    EMPRESA_NOME  = 'SALUTEM COMERCIO DE MOVEIS HOSPITALARES LTDA'
    TIMEZONE      = 'America/Sao_Paulo'

    # Sessão
    SESSION_TIMEOUT          = 28800  # 8 horas
    PERMANENT_SESSION_LIFETIME = timedelta(seconds=SESSION_TIMEOUT)
    SESSION_COOKIE_SECURE    = os.environ.get('FLASK_ENV') == 'production'
    SESSION_COOKIE_HTTPONLY  = True
    SESSION_COOKIE_SAMESITE  = 'Lax'

    # Paginação e logs
    REGISTROS_POR_PAGINA = 25
    LOG_ATIVIDADES       = True

    # Atualização automática das TVs (segundos)
    TV_REFRESH_INTERVAL = 30

    # Setores do fluxo de produção (na ordem do processo)
    SETORES_PRODUCAO = [
        'ALMOXARIFADO',
        'CORTE',
        'SOLDA',
        'ACABAMENTO',
        'MONTAGEM',
        'EMBALAGEM',
    ]

    # Roles disponíveis
    ROLES = {
        'admin':        'Administrador',
        'gerente':      'Gerente',
        'pcp':          'PCP',
        'encarregado':  'Encarregado',
        'almoxarifado': 'Almoxarifado',
        'operador':     'Operador',
    }
