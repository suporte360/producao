---
Task ID: 1
Agent: main
Task: Ajustar controle de material na fábrica — lógica de alerta por % restante, acumular entregas, registrar movimentação

Work Log:
- Corrigido `mysql_db.py`: `adicionar_estoque()` agora acumula `qtd_inicial` (ON DUPLICATE KEY UPDATE `qtd_inicial = qtd_inicial + VALUES(qtd_inicial)`)
- Alterado `get_estoque_interno()` e `get_estoque_kpis()`: filtro "baixo" agora usa <= 20% do entregue em vez de `qtd_minima`
- Corrigido `app.py`: `api_estoque_adicionar()` agora registra movimentação em `estoque_movimentacao` ao entregar material
- Atualizado `estoque.html`: lógica do badge "SEPARAR" usa `qtd <= qtdIni * 0.2`, removida referência a `qtd_minima` e `setor`
- Atualizado `dashboard.html`: `carregarResumoEstoque()` remove filtro client-side redundante (backend já filtra), adicionado % no resumo

Stage Summary:
- 4 arquivos modificados: database/mysql_db.py, app.py, templates/almoxarifado/estoque.html, templates/almoxarifado/dashboard.html
- Fluxo: Entregar Material → acumula total entregue → OF liberada abate → quando restou <=20% aparece "PRECISA SEPARAR"
- Threshold de 20% é padrão provisório, usuário pediu para definir depois