"""Cria usuario PCP para gerenciar, importar, classificar e liberar producao."""
import sys
sys.path.insert(0, '/home/suporte/producao_muito/producao')
from database.mysql_db import DatabaseMySQL
from werkzeug.security import generate_password_hash

db = DatabaseMySQL()

pcp_user = {
    'usuario': 'pcp',
    'nome': 'PCP',
    'senha': '123',
    'role': 'pcp',
    'nome_departamento': 'PCP',
    'departamento_codigo': 'PCP',
}

try:
    db.criar_usuario(pcp_user)
    print(f"[OK] Usuario 'pcp' criado com sucesso!")
    print(f"     Login: pcp")
    print(f"     Senha: 123")
    print(f"     Role:  pcp (importar, classificar, liberar OFs)")
except Exception as e:
    print(f"[ERRO] {e}")