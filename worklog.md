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
---
Task ID: 1
Agent: main
Task: Corrigir totems que nao mostravam lotes para fazer (so mostravam lotes produzindo)

Work Log:
- Investigou o codigo do totem_setor.py e serralheria_tomem.py
- Identificou causa raiz: o cache `_lotes_ativos` so era carregado na inicializacao do servidor
- Novos lotes liberados pelo PCP apos o totem iniciar nunca apareciam
- Adicionou `import threading` em todos os 4 arquivos
- Criou funcao `_background_refresh_loop()` com intervalo de 30 segundos
- Iniciou thread daemon no bloco `if __name__ == '__main__'`
- Arquivos modificados: totem_setor.py, serralheria_tomem.py (raiz + producao/)
- Commits feitos no submodule e repo pai

Stage Summary:
- Todos os totems (5003, 5004, 5005, 5006) agora auto-refresh a cada 30s
- Lotes liberados pelo PCP aparecem automaticamente nos totems sem reiniciar
---
Task ID: 3
Agent: Manus AI
Task: Corrigir discrepância de KPIs do ERP (Total, Abertos, Atrasados)

Work Log:
- Identificada causa raiz: a tabela `public.pedido` no PostgreSQL do ERP contém múltiplos registros por pedido (provavelmente itens ou histórico), fazendo com que `COUNT(*)` retornasse o número de itens (3804) em vez de pedidos (458).
- Database/postgresql_db.py:
    - `get_resumo_pedidos_erp`: Total e Aberto agora somam apenas status 01, 02 e 07. Atendidos (08) e Cancelados (10/C) limitados aos últimos 30 dias.
    - `get_pedidos_erp`: Ajustada a cláusula WHERE principal para incluir apenas os status desejados dentro de seus respectivos períodos (180 dias para abertos, 30 dias para finalizados/cancelados).
    - `DISTINCT` mantido para evitar contagem duplicada por itens.
    - Filtro de data de previsão: Adicionado `pedprevi > '2000-01-01'` para evitar contagem de datas inválidas como atrasos.
- Documentacao_sistema.md: Atualizado com o histórico das correções.

Stage Summary:
- Arquivos modificados: database/postgresql_db.py, documentacao_sistema.md, worklog.md
- Resultado esperado: Total de pedidos ~458, Pedidos em Aberto ~137, Atrasados significativamente reduzidos.
---
