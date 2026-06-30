---
Task ID: 2
Agent: main
Task: Implementar controle de estoque com dois tipos (almoxarifado/fabrica) + materiais das OFs no dashboard

Work Log:
- Adicionada coluna `tipo` (VARCHAR 20, default 'fabrica') na tabela estoque_interno via auto-migration no app.py
- postgresql_db.py: adicionada funcao get_requisicoes_multiplas_ordens() para buscar materiais de varias OFs em uma query
- mysql_db.py: atualizadas get_estoque_interno, get_estoque_kpis, adicionar_estoque, get_estoque_por_codigo, baixar_estoque_por_codigo, registrar_baixa_estoque com suporte a tipo
- mysql_db.py: adicionadas mover_estoque_para_fabrica() e get_lotes_liberados_pendentes()
- app.py: adicionado API /api/almoxarifado/materiais-pendentes (cruza OFs liberadas com estoque almoxarifado)
- app.py: adicionado API /api/estoque/<id>/separar-fabrica (move do almoxarifado para fabrica)
- app.py: _baixar_estoque_por_of agora so da baixa no tipo='fabrica'
- dashboard.html: adicionada secao "Materiais p/ Separar" mostrando materiais de cada OF com status de estoque
- estoque.html: reescrito com abas "Estoque Almoxarifado" e "Na Fabrica", modais separados

Stage Summary:
- 6 arquivos modificados: app.py, database/mysql_db.py, database/postgresql_db.py, templates/almoxarifado/estoque.html, templates/almoxarifado/dashboard.html, worklog.md
- Fluxo: cadastrar material no almoxarifado com codigo ERP → ver materiais das OFs no dashboard → separar p/ fabrica → consumo automatico
- Migration automatica: ao iniciar o Flask, se a coluna tipo nao existir, cria com DEFAULT 'fabrica' (registros existentes ficam como fabrica)