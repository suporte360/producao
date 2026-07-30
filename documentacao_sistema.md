# Documentação do Sistema de Gerenciamento de Produção

## Informações do Banco de Dados
- **ERP (PostgreSQL):**
  - Host: `192.168.1.14`
  - Banco: `logica`
  - Usuário: `postgres`
  - Porta: `5432`
- **Produção Local (MariaDB):**
  - Host: `localhost`
  - Banco: `producao`
  - Usuário: `root`

## Histórico de Alterações (Log)

| Data | Alteração Realizada | Resultado |
| :--- | :--- | :--- |
| 2026-07-30 | Correção da rota `/diretor/relatorios` para usar pedidos do ERP (PostgreSQL) em vez de lotes locais. | **Sucesso** |
| 2026-07-30 | Remoção da Screen 3 (OPs MariaDB) da TV e ajuste para 3 telas focadas em pedidos. | **Sucesso** |
| 2026-07-30 | Adição de logging estruturado em `app.py` para diagnóstico de KPIs zerados. | **Sucesso** |
| 2026-07-30 | Correção de erro de GLIBC no servidor recriando o ambiente virtual (`venv`). | **Sucesso** |
| 2026-07-30 | Correção de erro de tipo no PostgreSQL (Casting SmallInt para Text para uso do TRIM). | **Sucesso** |
| 2026-07-30 | Ajuste do nome da coluna de vínculo de pedido na tabela ordem (`ordped`). | **Sucesso** |
| 2026-07-30 | Mapeamento de status para 3 dígitos (`001`, `004`) conforme padrão do ERP Lógica. | **Sucesso** |
| 2026-07-30 | Adição de destaque visual (balão roxo) para lojas 2, 3, 4 e 7 usando a coluna `pedrep`. | **Sucesso** |
| 2026-07-30 | Implementação de lógica de contagem em Python para evitar falhas de "espaços fantasmas" do banco. | **Sucesso** |
| 2026-07-30 | Ajuste de KPIs para considerar "Em OF" pedidos com campo `pedoflote` preenchido. | **Sucesso** |
| 2026-07-30 | Unificação da lógica entre TV e Relatórios para garantir números idênticos em ambas as telas. | **Sucesso** |
| 2026-07-30 | Atualização do mapeamento de status para 3 dígitos conforme solicitação (001-010). | **Sucesso** |
| 2026-07-30 | Inclusão da coluna de Loja/Depósito com destaque visual (balão roxo) para lojas 2, 3, 4 e 7. | **Sucesso** |
| 2026-07-30 | Ajuste do KPI de "Próximos 7 dias" para "Próximos 3 dias" em todo o sistema. | **Sucesso** |
| 2026-07-30 | Implementação de lógica 'blinded' para tratar ausência da coluna peddep no banco. | **Sucesso** |
| 2026-07-30 | Implementação de `DISTINCT` nos KPIs e listagem do ERP para evitar contagem duplicada de itens e garantir que o total de 180 dias reflita o número de pedidos (458) e não de itens (3804). | **Sucesso** |
| 2026-07-30 | Refinamento do KPI de Atrasados para ignorar datas de previsão inválidas (vazias ou zeradas) e excluir pedidos atendidos. | **Sucesso** |
