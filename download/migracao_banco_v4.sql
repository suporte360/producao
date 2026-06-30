-- =============================================
-- MIGRAÇÃO PARA V4.0 - Adiciona todas as colunas
-- e tabelas que o código espera
-- =============================================
-- 
-- COMO USAR:
--   mysql -u root -p nomedo_seu_banco < migracao_banco_v4.sql
--
-- Se não souber o nome do banco, veja em config/config.py
-- ou rode:  mysql -u root -p -e "SHOW DATABASES;"
-- =============================================

-- =============================================
-- 1. LOTES_PRODUCAO - Colunas faltando
-- =============================================

-- lote_codigo
ALTER TABLE lotes_producao ADD COLUMN IF NOT EXISTS `lote_codigo` varchar(50) DEFAULT NULL COMMENT 'Codigo do lote no ERP (ex: 000322)';

-- descricao_produto
ALTER TABLE lotes_producao ADD COLUMN IF NOT EXISTS `descricao_produto` varchar(200) DEFAULT NULL;

-- data_fim_producao
ALTER TABLE lotes_producao ADD COLUMN IF NOT EXISTS `data_fim_producao` datetime DEFAULT NULL;

-- unidade_medida
ALTER TABLE lotes_producao ADD COLUMN IF NOT EXISTS `unidade_medida` varchar(10) DEFAULT 'UN';

-- data_abertura_erp
ALTER TABLE lotes_producao ADD COLUMN IF NOT EXISTS `data_abertura_erp` date DEFAULT NULL;

-- planejador
ALTER TABLE lotes_producao ADD COLUMN IF NOT EXISTS `planejador` varchar(100) DEFAULT NULL;

-- observacoes
ALTER TABLE lotes_producao ADD COLUMN IF NOT EXISTS `observacoes` text DEFAULT NULL;

-- Colunas de separacao (almoxarifado)
ALTER TABLE lotes_producao ADD COLUMN IF NOT EXISTS `separacao_status` enum('pendente','separando','separado','entregue') DEFAULT 'pendente';
ALTER TABLE lotes_producao ADD COLUMN IF NOT EXISTS `data_separacao` datetime DEFAULT NULL;
ALTER TABLE lotes_producao ADD COLUMN IF NOT EXISTS `data_entrega` datetime DEFAULT NULL;
ALTER TABLE lotes_producao ADD COLUMN IF NOT EXISTS `usuario_separacao_id` int(11) DEFAULT NULL;
ALTER TABLE lotes_producao ADD COLUMN IF NOT EXISTS `usuario_entrega_id` int(11) DEFAULT NULL;

-- Garantir que a coluna ordem existe (chave primaria do lote)
-- Se a tabela foi criada sem 'ordem', precisamos adicionar
-- (se ja existe, o ALTER vai falhar silenciosamente com IF NOT EXISTS)

-- Garantir que status_erp existe
ALTER TABLE lotes_producao ADD COLUMN IF NOT EXISTS `status_erp` varchar(10) DEFAULT 'A';

-- Garantir que setor_atual_seq e total_setores existem
ALTER TABLE lotes_producao ADD COLUMN IF NOT EXISTS `setor_atual_seq` int(11) DEFAULT 1;
ALTER TABLE lotes_producao ADD COLUMN IF NOT EXISTS `total_setores` int(11) DEFAULT 0;

-- Garantir que qtde_reportada existe
ALTER TABLE lotes_producao ADD COLUMN IF NOT EXISTS `qtde_reportada` decimal(14,4) DEFAULT 0;

-- Garantir que data_ultima_sync existe
ALTER TABLE lotes_producao ADD COLUMN IF NOT EXISTS `data_ultima_sync` timestamp NOT NULL DEFAULT current_timestamp() ON UPDATE current_timestamp();

-- Garantir que data_importacao existe
ALTER TABLE lotes_producao ADD COLUMN IF NOT EXISTS `data_importacao` timestamp NOT NULL DEFAULT current_timestamp();

-- =============================================
-- 2. Atualizar ENUMs do lotes_producao
-- =============================================

-- Alterar prioridade para incluir 'urgente'
ALTER TABLE lotes_producao MODIFY COLUMN `prioridade` enum('urgente','alta','media','baixa') DEFAULT 'media';

-- Alterar status para incluir 'liberado'
ALTER TABLE lotes_producao MODIFY COLUMN `status` enum('importado','liberado','em_producao','pausado','finalizado','cancelado') DEFAULT 'importado';

-- =============================================
-- 3. Tabela ORDEM FABRICACAO (OFs)
-- =============================================

CREATE TABLE IF NOT EXISTS `ordens_fabricacao` (
  `id` int(11) NOT NULL AUTO_INCREMENT,
  `lote_ordem` int(11) NOT NULL COMMENT 'FK para lotes_producao.ordem',
  `of_numero` int(11) NOT NULL COMMENT 'Numero da OF no ERP',
  `codigo_produto` varchar(50) DEFAULT NULL,
  `descricao_produto` varchar(200) DEFAULT NULL,
  `qtde_ordem` decimal(14,4) DEFAULT 0,
  `unidade_medida` varchar(10) DEFAULT 'PC',
  `tipo` enum('pai','filho') DEFAULT 'filho',
  `status` enum('pendente','em_producao','pausado','concluido','cancelado') DEFAULT 'pendente',
  `data_previsao` date DEFAULT NULL,
  `data_inicio` datetime DEFAULT NULL,
  `data_fim` datetime DEFAULT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `of_numero` (`of_numero`),
  KEY `lote_ordem` (`lote_ordem`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- =============================================
-- 4. Tabela OPERACOES_PRODUCAO (Roteiro)
-- =============================================

CREATE TABLE IF NOT EXISTS `operacoes_producao` (
  `id` int(11) NOT NULL AUTO_INCREMENT,
  `of_numero` int(11) NOT NULL COMMENT 'FK para ordens_fabricacao.of_numero',
  `lote_ordem` int(11) NOT NULL,
  `sequencia` int(11) NOT NULL COMMENT 'Sequencia da operacao (010, 020, 030...)',
  `fase` varchar(10) DEFAULT NULL COMMENT 'Codigo da fase no ERP',
  `descricao_operacao` varchar(200) NOT NULL,
  `departamento` varchar(50) DEFAULT NULL COMMENT 'Setor responsavel',
  `codigo_barras` varchar(50) DEFAULT NULL COMMENT 'Codigo de barras da operacao',
  `status` enum('pendente','em_andamento','pausado','concluido','cancelado') DEFAULT 'pendente',
  `data_inicio` datetime DEFAULT NULL,
  `data_fim` datetime DEFAULT NULL,
  `usuario_inicio_id` int(11) DEFAULT NULL,
  `usuario_fim_id` int(11) DEFAULT NULL,
  `tempo_gasto_minutos` int(11) DEFAULT 0,
  `qtde_produzida` decimal(14,4) DEFAULT 0,
  `qtde_refugada` decimal(14,4) DEFAULT 0,
  `observacoes` text DEFAULT NULL,
  PRIMARY KEY (`id`),
  KEY `of_numero` (`of_numero`),
  KEY `lote_ordem` (`lote_ordem`),
  KEY `idx_departamento` (`departamento`),
  KEY `idx_status` (`status`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- =============================================
-- 5. Tabela MATERIAIS_OF
-- =============================================

CREATE TABLE IF NOT EXISTS `materiais_of` (
  `id` int(11) NOT NULL AUTO_INCREMENT,
  `of_numero` int(11) NOT NULL,
  `lote_ordem` int(11) NOT NULL,
  `codigo_material` varchar(50) DEFAULT NULL,
  `descricao_material` varchar(255) NOT NULL,
  `quantidade` decimal(14,4) NOT NULL,
  `unidade_medida` varchar(10) DEFAULT 'UN',
  `tipo` enum('componente','filho','embalagem') DEFAULT 'componente',
  `status_requisicao` enum('pendente','solicitado','entregue','recusado') DEFAULT 'pendente',
  `data_entrega` datetime DEFAULT NULL,
  PRIMARY KEY (`id`),
  KEY `of_numero` (`of_numero`),
  KEY `lote_ordem` (`lote_ordem`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- =============================================
-- 6. Tabela KANBAN_CARDS
-- =============================================

CREATE TABLE IF NOT EXISTS `kanban_cards` (
  `id` int(11) NOT NULL AUTO_INCREMENT,
  `lote_ordem` int(11) NOT NULL,
  `of_numero` int(11) DEFAULT NULL,
  `operacao_id` int(11) DEFAULT NULL,
  `etapa` varchar(50) NOT NULL DEFAULT 'aguardando',
  `departamento` varchar(50) DEFAULT NULL,
  `prioridade` enum('urgente','alta','media','baixa') DEFAULT 'media',
  `operador_id` int(11) DEFAULT NULL,
  `criado_em` datetime DEFAULT current_timestamp(),
  `atualizado_em` datetime DEFAULT current_timestamp() ON UPDATE current_timestamp(),
  PRIMARY KEY (`id`),
  KEY `lote_ordem` (`lote_ordem`),
  KEY `idx_etapa` (`etapa`),
  KEY `idx_departamento` (`departamento`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- =============================================
-- 7. Tabela REQUISICOES_MATERIAIS (versao v4.0)
-- =============================================

-- Verifica se a tabela ja existe com a estrutura antiga
-- Se existe mas esta errada, renomeia e cria nova
CREATE TABLE IF NOT EXISTS `requisicoes_materiais_v4` (
  `id` int(11) NOT NULL AUTO_INCREMENT,
  `lote_ordem` int(11) NOT NULL,
  `of_numero` int(11) DEFAULT NULL,
  `material_codigo` varchar(50) DEFAULT NULL,
  `material_descricao` varchar(255) NOT NULL,
  `quantidade` decimal(14,4) NOT NULL,
  `unidade_medida` varchar(10) DEFAULT 'UN',
  `departamento_solicitante` varchar(50) DEFAULT NULL,
  `usuario_solicitante_id` int(11) DEFAULT NULL,
  `data_solicitacao` datetime DEFAULT current_timestamp(),
  `status` enum('pendente','aprovado','entregue','recusado') DEFAULT 'pendente',
  `usuario_atendimento_id` int(11) DEFAULT NULL,
  `data_atendimento` datetime DEFAULT NULL,
  `observacao` text DEFAULT NULL,
  PRIMARY KEY (`id`),
  KEY `lote_ordem` (`lote_ordem`),
  KEY `idx_status` (`status`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- Se a tabela requisicoes_materiais nao tem a coluna lote_ordem int, 
-- provavelmente e a versao antiga. Vamos tentar adicionar colunas
ALTER TABLE requisicoes_materiais ADD COLUMN IF NOT EXISTS `lote_ordem` int(11) DEFAULT NULL;
ALTER TABLE requisicoes_materiais ADD COLUMN IF NOT EXISTS `of_numero` int(11) DEFAULT NULL;
ALTER TABLE requisicoes_materiais ADD COLUMN IF NOT EXISTS `material_codigo` varchar(50) DEFAULT NULL;
ALTER TABLE requisicoes_materiais ADD COLUMN IF NOT EXISTS `material_descricao` varchar(255) DEFAULT NULL;
ALTER TABLE requisicoes_materiais ADD COLUMN IF NOT EXISTS `unidade_medida` varchar(10) DEFAULT 'UN';
ALTER TABLE requisicoes_materiais ADD COLUMN IF NOT EXISTS `departamento_solicitante` varchar(50) DEFAULT NULL;
ALTER TABLE requisicoes_materiais ADD COLUMN IF NOT EXISTS `usuario_solicitante_id` int(11) DEFAULT NULL;
ALTER TABLE requisicoes_materiais ADD COLUMN IF NOT EXISTS `data_solicitacao` datetime DEFAULT NULL;
ALTER TABLE requisicoes_materiais ADD COLUMN IF NOT EXISTS `usuario_atendimento_id` int(11) DEFAULT NULL;
ALTER TABLE requisicoes_materiais ADD COLUMN IF NOT EXISTS `data_atendimento` datetime DEFAULT NULL;
ALTER TABLE requisicoes_materiais ADD COLUMN IF NOT EXISTS `observacao` text DEFAULT NULL;

-- Atualizar status enum da requisicoes_materiais
ALTER TABLE requisicoes_materiais MODIFY COLUMN `status` enum('pendente','aprovado','entregue','recusado') DEFAULT 'pendente';

-- =============================================
-- 8. Tabela APONTAMENTOS_TEMPO (versao v4.0)
-- =============================================

ALTER TABLE apontamentos_tempo ADD COLUMN IF NOT EXISTS `of_numero` int(11) DEFAULT NULL;
ALTER TABLE apontamentos_tempo ADD COLUMN IF NOT EXISTS `operacao_id` int(11) DEFAULT NULL;
ALTER TABLE apontamentos_tempo ADD COLUMN IF NOT EXISTS `qtde_produzida` decimal(14,4) DEFAULT NULL;

-- =============================================
-- 9. Tabela DEPARTAMENTOS - colunas faltando
-- =============================================

ALTER TABLE departamentos ADD COLUMN IF NOT EXISTS `descricao` varchar(255) DEFAULT NULL;
ALTER TABLE departamentos ADD COLUMN IF NOT EXISTS `ordem_fluxo` int(11) DEFAULT 0;
ALTER TABLE departamentos ADD COLUMN IF NOT EXISTS `cor_hex` varchar(7) DEFAULT '#007bff';
ALTER TABLE departamentos ADD COLUMN IF NOT EXISTS `icone` varchar(50) DEFAULT 'bi-gear';

-- =============================================
-- 10. Tabela USUARIOS - colunas faltando
-- =============================================

ALTER TABLE usuarios ADD COLUMN IF NOT EXISTS `departamento_codigo` varchar(20) DEFAULT NULL;
ALTER TABLE usuarios ADD COLUMN IF NOT EXISTS `ultimo_acesso` datetime DEFAULT NULL;

-- Atualizar role enum para incluir 'encarregado'
ALTER TABLE usuarios MODIFY COLUMN `role` enum('admin','gerente','pcp','encarregado','almoxarifado','operador') NOT NULL DEFAULT 'operador';

-- =============================================
-- 11. LOG_ATIVIDADES - colunas faltando
-- =============================================

ALTER TABLE log_atividades ADD COLUMN IF NOT EXISTS `usuario_id` int(11) DEFAULT NULL;
ALTER TABLE log_atividades ADD COLUMN IF NOT EXISTS `usuario_nome` varchar(100) DEFAULT NULL;

-- =============================================
-- 12. Garantir que a coluna 'ordem' existe como chave
-- =============================================
-- Se a tabela lotes_producao nao tem a coluna 'ordem', nada funciona.
-- Vamos verificar e adicionar se necessario.

-- =============================================
-- 13. DADOS INICIAIS - Departamentos
-- =============================================

INSERT IGNORE INTO `departamentos` (`codigo`, `nome`, `descricao`, `ordem_fluxo`, `cor_hex`, `icone`) VALUES
('ALMOXARIFADO', 'Almoxarifado', 'Separacao e controle de materiais', 1, '#17a2b8', 'bi-box-seam'),
('CORTE', 'Corte / Conformacao', 'Corte, prensa, dobra e curvamento', 2, '#fd7e14', 'bi-scissors'),
('SOLDA', 'Solda', 'Soldagem e tratamento de solda', 3, '#dc3545', 'bi-fire'),
('ACABAMENTO', 'Acabamento / Polimento', 'Polimento, lixamento e acabamento superficial', 4, '#6f42c1', 'bi-stars'),
('MONTAGEM', 'Montagem', 'Montagem do produto final', 5, '#0d6efd', 'bi-tools'),
('EMBALAGEM', 'Embalagem / Expedicao', 'Embalagem e liberacao para expedicao', 6, '#198754', 'bi-truck'),
('PCP', 'PCP', 'Planejamento e Controle da Producao', 0, '#6c757d', 'bi-clipboard-data'),
('ADMINISTRACAO', 'Administracao', 'Administracao geral do sistema', 0, '#343a40', 'bi-gear-fill');

-- =============================================
-- 14. VIEWS
-- =============================================

CREATE OR REPLACE VIEW `vw_stats_departamento` AS
SELECT
  d.codigo,
  d.nome,
  d.cor_hex,
  d.ordem_fluxo,
  COUNT(DISTINCT CASE WHEN op.status = 'pendente' THEN op.id END) AS pendentes,
  COUNT(DISTINCT CASE WHEN op.status = 'em_andamento' THEN op.id END) AS em_andamento,
  COUNT(DISTINCT CASE WHEN op.status = 'concluido' AND DATE(op.data_fim) = CURDATE() THEN op.id END) AS concluidos_hoje,
  COUNT(DISTINCT CASE WHEN op.status = 'concluido' THEN op.id END) AS total_concluidos
FROM departamentos d
LEFT JOIN operacoes_producao op ON op.departamento = d.codigo
WHERE d.ativo = 1
GROUP BY d.id, d.codigo, d.nome, d.cor_hex, d.ordem_fluxo;

CREATE OR REPLACE VIEW `vw_kanban_completo` AS
SELECT
  k.id,
  k.lote_ordem,
  k.of_numero,
  k.operacao_id,
  k.etapa,
  k.departamento,
  k.prioridade,
  k.criado_em,
  k.atualizado_em,
  l.lote_codigo,
  l.descricao_produto,
  l.qtde_ordem,
  l.data_previsao_erp,
  l.status AS status_lote,
  op.descricao_operacao,
  op.sequencia,
  op.status AS status_operacao,
  op.qtde_produzida,
  u.nome AS operador_nome
FROM kanban_cards k
LEFT JOIN lotes_producao l ON k.lote_ordem = l.ordem
LEFT JOIN operacoes_producao op ON k.operacao_id = op.id
LEFT JOIN usuarios u ON k.operador_id = u.id;

-- =============================================
-- 15. INDICES ADICIONAIS
-- =============================================

CREATE INDEX IF NOT EXISTS idx_op_depto_status ON operacoes_producao (departamento, status);
CREATE INDEX IF NOT EXISTS idx_op_status_fim ON operacoes_producao (status, data_fim);
CREATE INDEX IF NOT EXISTS idx_op_lote_depto ON operacoes_producao (lote_ordem, departamento);
CREATE INDEX IF NOT EXISTS idx_lote_status_prev ON lotes_producao (status, data_previsao_erp);
CREATE INDEX IF NOT EXISTS idx_lote_fim ON lotes_producao (status, data_fim_producao);
CREATE INDEX IF NOT EXISTS idx_apt_op_tipo ON apontamentos_tempo (operacao_id, tipo, data_hora);
CREATE INDEX IF NOT EXISTS idx_req_status_data ON requisicoes_materiais (status, data_solicitacao);
CREATE INDEX IF NOT EXISTS idx_kanban_depto_etapa ON kanban_cards (departamento, etapa);
CREATE INDEX IF NOT EXISTS idx_kanban_etapa_atualizado ON kanban_cards (etapa, atualizado_em);
CREATE INDEX IF NOT EXISTS idx_log_usuario_data ON log_atividades (usuario_id, data_hora);

-- =============================================
-- 16. Garantir que admin existe com senha padrao
-- =============================================
-- Senha padrao: admin123 (scrypt hash)
INSERT IGNORE INTO `usuarios` (`usuario`, `nome`, `senha`, `role`, `nome_departamento`, `departamento_codigo`, `ativo`) VALUES
('admin', 'Administrador', 'scrypt:32768:8:1$MwSXGfo6Q2NHSzKe$d9037fc1fdec10830d1fce3e797b47671880459b78a418dc71d1d5b2378eb8c85f9e6bb9294fa8afcb4ca6c41f2aaab478e26cfdc1df61386e137a64934d6582', 'admin', 'Administracao', 'ADMINISTRACAO', 1);

-- =============================================
-- FIM DA MIGRACAO
-- =============================================