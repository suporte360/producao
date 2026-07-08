/*M!999999\- enable the sandbox mode */ 
-- MariaDB dump 10.19  Distrib 10.11.14-MariaDB, for debian-linux-gnu (x86_64)
--
-- Host: localhost    Database: producao_db
-- ------------------------------------------------------
-- Server version	10.11.14-MariaDB-0+deb12u2

/*!40101 SET @OLD_CHARACTER_SET_CLIENT=@@CHARACTER_SET_CLIENT */;
/*!40101 SET @OLD_CHARACTER_SET_RESULTS=@@CHARACTER_SET_RESULTS */;
/*!40101 SET @OLD_COLLATION_CONNECTION=@@COLLATION_CONNECTION */;
/*!40101 SET NAMES utf8mb4 */;
/*!40103 SET @OLD_TIME_ZONE=@@TIME_ZONE */;
/*!40103 SET TIME_ZONE='+00:00' */;
/*!40014 SET @OLD_UNIQUE_CHECKS=@@UNIQUE_CHECKS, UNIQUE_CHECKS=0 */;
/*!40014 SET @OLD_FOREIGN_KEY_CHECKS=@@FOREIGN_KEY_CHECKS, FOREIGN_KEY_CHECKS=0 */;
/*!40101 SET @OLD_SQL_MODE=@@SQL_MODE, SQL_MODE='NO_AUTO_VALUE_ON_ZERO' */;
/*!40111 SET @OLD_SQL_NOTES=@@SQL_NOTES, SQL_NOTES=0 */;

--
-- Table structure for table `apontamentos_tempo`
--

DROP TABLE IF EXISTS `apontamentos_tempo`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8mb4 */;
CREATE TABLE `apontamentos_tempo` (
  `id` int(11) NOT NULL AUTO_INCREMENT,
  `lote_ordem` int(11) NOT NULL,
  `of_numero` int(11) DEFAULT NULL,
  `operacao_id` int(11) DEFAULT NULL,
  `departamento` varchar(100) DEFAULT NULL,
  `usuario_id` int(11) NOT NULL,
  `tipo` enum('inicio','pausa','retomada','fim') NOT NULL,
  `data_hora` datetime DEFAULT current_timestamp(),
  `motivo_pausa` varchar(200) DEFAULT NULL,
  `qtde_produzida` decimal(14,4) DEFAULT NULL,
  PRIMARY KEY (`id`),
  KEY `usuario_id` (`usuario_id`),
  KEY `lote_ordem` (`lote_ordem`),
  KEY `idx_tipo` (`tipo`),
  KEY `idx_data` (`data_hora`)
) ENGINE=InnoDB AUTO_INCREMENT=5 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `apontamentos_tempo`
--

LOCK TABLES `apontamentos_tempo` WRITE;
/*!40000 ALTER TABLE `apontamentos_tempo` DISABLE KEYS */;
INSERT INTO `apontamentos_tempo` VALUES
(1,9663,9659,30,'CORTE',4,'inicio','2026-07-01 15:23:44',NULL,NULL),
(2,9663,9659,30,'CORTE',4,'fim','2026-07-01 15:37:25',NULL,7.0000),
(3,9663,9660,31,'CORTE',4,'inicio','2026-07-01 15:37:37',NULL,NULL),
(4,9663,9660,31,'CORTE',4,'inicio','2026-07-01 15:39:21',NULL,NULL);
/*!40000 ALTER TABLE `apontamentos_tempo` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `departamentos`
--

DROP TABLE IF EXISTS `departamentos`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8mb4 */;
CREATE TABLE `departamentos` (
  `id` int(11) NOT NULL AUTO_INCREMENT,
  `codigo` varchar(20) NOT NULL,
  `nome` varchar(100) NOT NULL,
  `descricao` varchar(255) DEFAULT NULL,
  `ativo` tinyint(1) DEFAULT 1,
  `ordem_fluxo` int(11) DEFAULT 0,
  `cor_hex` varchar(7) DEFAULT '#007bff',
  `icone` varchar(50) DEFAULT 'bi-gear',
  PRIMARY KEY (`id`),
  UNIQUE KEY `codigo` (`codigo`)
) ENGINE=InnoDB AUTO_INCREMENT=9 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `departamentos`
--

LOCK TABLES `departamentos` WRITE;
/*!40000 ALTER TABLE `departamentos` DISABLE KEYS */;
INSERT INTO `departamentos` VALUES
(1,'ALMOXARIFADO','Almoxarifado','Separacao e controle de materiais',1,1,'#17a2b8','bi-box-seam'),
(2,'CORTE','Corte / Conformacao','Corte, prensa, dobra e curvamento',1,2,'#fd7e14','bi-scissors'),
(3,'SOLDA','Solda','Soldagem e tratamento de solda',1,3,'#dc3545','bi-fire'),
(4,'ACABAMENTO','Acabamento / Polimento','Polimento, lixamento e acabamento superficial',1,4,'#6f42c1','bi-stars'),
(5,'MONTAGEM','Montagem','Montagem do produto final',1,5,'#0d6efd','bi-tools'),
(6,'EMBALAGEM','Embalagem / Expedicao','Embalagem e liberacao para expedicao',1,6,'#198754','bi-truck'),
(7,'PCP','PCP','Planejamento e Controle da Producao',1,0,'#6c757d','bi-clipboard-data'),
(8,'ADMINISTRACAO','Administracao','Administracao geral do sistema',1,0,'#343a40','bi-gear-fill');
/*!40000 ALTER TABLE `departamentos` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `estoque_interno`
--

DROP TABLE IF EXISTS `estoque_interno`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8mb4 */;
CREATE TABLE `estoque_interno` (
  `id` int(11) NOT NULL AUTO_INCREMENT,
  `codigo` varchar(100) NOT NULL,
  `descricao` varchar(300) DEFAULT NULL,
  `unidade` varchar(20) DEFAULT 'UN',
  `qtd_atual` decimal(14,4) DEFAULT 0.0000,
  `qtd_minima` decimal(14,4) DEFAULT 0.0000,
  `qtd_inicial` decimal(14,4) DEFAULT 0.0000,
  `tipo` varchar(20) NOT NULL DEFAULT 'almoxarifado',
  `created_at` datetime DEFAULT current_timestamp(),
  `updated_at` datetime DEFAULT current_timestamp() ON UPDATE current_timestamp(),
  PRIMARY KEY (`id`),
  UNIQUE KEY `uk_codigo_tipo` (`codigo`,`tipo`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `estoque_interno`
--

LOCK TABLES `estoque_interno` WRITE;
/*!40000 ALTER TABLE `estoque_interno` DISABLE KEYS */;
/*!40000 ALTER TABLE `estoque_interno` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `kanban_cards`
--

DROP TABLE IF EXISTS `kanban_cards`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8mb4 */;
CREATE TABLE `kanban_cards` (
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
) ENGINE=InnoDB AUTO_INCREMENT=94 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `kanban_cards`
--

LOCK TABLES `kanban_cards` WRITE;
/*!40000 ALTER TABLE `kanban_cards` DISABLE KEYS */;
INSERT INTO `kanban_cards` VALUES
(1,10016,10012,1,'aguardando','CORTE','media',NULL,'2026-07-07 15:30:34','2026-07-07 15:30:34'),
(2,10016,10012,2,'aguardando','CORTE','media',NULL,'2026-07-07 15:30:34','2026-07-07 15:30:34'),
(3,10016,10013,3,'aguardando','CORTE','media',NULL,'2026-07-07 15:30:34','2026-07-07 15:30:34'),
(4,10016,10014,4,'aguardando','CORTE','media',NULL,'2026-07-07 15:30:34','2026-07-07 15:30:34'),
(5,10016,10015,5,'aguardando','CORTE','media',NULL,'2026-07-07 15:30:34','2026-07-07 15:30:34'),
(6,10016,10015,6,'aguardando','CORTE','media',NULL,'2026-07-07 15:30:34','2026-07-07 15:30:34'),
(7,10009,10002,7,'aguardando','CORTE','media',NULL,'2026-07-07 15:30:35','2026-07-07 15:30:35'),
(8,10009,10002,8,'aguardando','FUNILARIA','media',NULL,'2026-07-07 15:30:35','2026-07-07 15:30:35'),
(9,10009,10003,9,'aguardando','CORTE','media',NULL,'2026-07-07 15:30:35','2026-07-07 15:30:35'),
(10,10009,10003,10,'aguardando','FUNILARIA','media',NULL,'2026-07-07 15:30:35','2026-07-07 15:30:35'),
(11,10009,10004,11,'aguardando','CORTE','media',NULL,'2026-07-07 15:30:35','2026-07-07 15:30:35'),
(12,10009,10004,12,'aguardando','FUNILARIA','media',NULL,'2026-07-07 15:30:35','2026-07-07 15:30:35'),
(13,10009,10005,13,'aguardando','CORTE','media',NULL,'2026-07-07 15:30:35','2026-07-07 15:30:35'),
(14,10009,10006,14,'aguardando','CORTE','media',NULL,'2026-07-07 15:30:35','2026-07-07 15:30:35'),
(15,10009,10007,15,'aguardando','CORTE','media',NULL,'2026-07-07 15:30:35','2026-07-07 15:30:35'),
(16,10009,10008,16,'aguardando','CORTE','media',NULL,'2026-07-07 15:30:35','2026-07-07 15:30:35'),
(17,10009,10009,17,'aguardando','CORTE','media',NULL,'2026-07-07 15:30:35','2026-07-07 15:30:35'),
(18,10009,10009,18,'aguardando','PINTURA','media',NULL,'2026-07-07 15:30:35','2026-07-07 15:30:35'),
(19,10009,10009,19,'aguardando','MONTAGEM','media',NULL,'2026-07-07 15:30:35','2026-07-07 15:30:35'),
(20,10009,10009,20,'aguardando','MONTAGEM','media',NULL,'2026-07-07 15:30:35','2026-07-07 15:30:35'),
(21,10001,9993,21,'aguardando','CORTE','media',NULL,'2026-07-07 15:30:35','2026-07-07 15:30:35'),
(22,10001,9993,22,'aguardando','FUNILARIA','media',NULL,'2026-07-07 15:30:35','2026-07-07 15:30:35'),
(23,10001,9994,23,'aguardando','CORTE','media',NULL,'2026-07-07 15:30:35','2026-07-07 15:30:35'),
(24,10001,9995,24,'aguardando','CORTE','media',NULL,'2026-07-07 15:30:36','2026-07-07 15:30:36'),
(25,10001,9996,25,'aguardando','CORTE','media',NULL,'2026-07-07 15:30:36','2026-07-07 15:30:36'),
(26,10001,9996,26,'aguardando','FUNILARIA','media',NULL,'2026-07-07 15:30:36','2026-07-07 15:30:36'),
(27,10001,9997,27,'aguardando','CORTE','media',NULL,'2026-07-07 15:30:36','2026-07-07 15:30:36'),
(28,10001,9998,28,'aguardando','CORTE','media',NULL,'2026-07-07 15:30:36','2026-07-07 15:30:36'),
(29,10001,9999,29,'aguardando','CORTE','media',NULL,'2026-07-07 15:30:36','2026-07-07 15:30:36'),
(30,10001,10000,30,'aguardando','CORTE','media',NULL,'2026-07-07 15:30:36','2026-07-07 15:30:36'),
(31,10001,10000,31,'aguardando','PINTURA','media',NULL,'2026-07-07 15:30:36','2026-07-07 15:30:36'),
(32,10001,10000,32,'aguardando','MONTAGEM','media',NULL,'2026-07-07 15:30:36','2026-07-07 15:30:36'),
(33,10001,10000,33,'aguardando','MONTAGEM','media',NULL,'2026-07-07 15:30:36','2026-07-07 15:30:36'),
(34,10001,10001,34,'aguardando','CORTE','media',NULL,'2026-07-07 15:30:36','2026-07-07 15:30:36'),
(35,10001,10001,35,'aguardando','FUNILARIA','media',NULL,'2026-07-07 15:30:36','2026-07-07 15:30:36'),
(36,10038,10028,36,'aguardando','SERRALHERIA','media',NULL,'2026-07-08 12:01:37','2026-07-08 12:01:37'),
(37,10038,10028,37,'aguardando','SERRALHERIA','media',NULL,'2026-07-08 12:01:37','2026-07-08 12:01:37'),
(38,10038,10029,38,'aguardando','SERRALHERIA','media',NULL,'2026-07-08 12:01:37','2026-07-08 12:01:37'),
(39,10038,10029,39,'aguardando','FUNILARIA','media',NULL,'2026-07-08 12:01:37','2026-07-08 12:01:37'),
(40,10038,10030,40,'aguardando','SERRALHERIA','media',NULL,'2026-07-08 12:01:38','2026-07-08 12:01:38'),
(41,10038,10030,41,'aguardando','SERRALHERIA','media',NULL,'2026-07-08 12:01:38','2026-07-08 12:01:38'),
(42,10038,10031,42,'aguardando','SERRALHERIA','media',NULL,'2026-07-08 12:01:38','2026-07-08 12:01:38'),
(43,10038,10032,43,'aguardando','SERRALHERIA','media',NULL,'2026-07-08 12:01:38','2026-07-08 12:01:38'),
(44,10038,10032,44,'aguardando','FUNILARIA','media',NULL,'2026-07-08 12:01:38','2026-07-08 12:01:38'),
(45,10038,10033,45,'aguardando','SERRALHERIA','media',NULL,'2026-07-08 12:01:38','2026-07-08 12:01:38'),
(46,10038,10034,46,'aguardando','SERRALHERIA','media',NULL,'2026-07-08 12:01:38','2026-07-08 12:01:38'),
(47,10038,10035,47,'aguardando','SERRALHERIA','media',NULL,'2026-07-08 12:01:38','2026-07-08 12:01:38'),
(48,10038,10036,48,'aguardando','SERRALHERIA','media',NULL,'2026-07-08 12:01:38','2026-07-08 12:01:38'),
(49,10038,10036,49,'aguardando','TAPECARIA','media',NULL,'2026-07-08 12:01:38','2026-07-08 12:01:38'),
(50,10038,10036,50,'aguardando','TAPECARIA','media',NULL,'2026-07-08 12:01:38','2026-07-08 12:01:38'),
(51,10038,10037,51,'aguardando','SERRALHERIA','media',NULL,'2026-07-08 12:01:38','2026-07-08 12:01:38'),
(52,10038,10037,52,'aguardando','TAPECARIA','media',NULL,'2026-07-08 12:01:38','2026-07-08 12:01:38'),
(53,10038,10037,53,'aguardando','TAPECARIA','media',NULL,'2026-07-08 12:01:38','2026-07-08 12:01:38'),
(54,10038,10038,54,'aguardando','SERRALHERIA','media',NULL,'2026-07-08 12:01:38','2026-07-08 12:01:38'),
(55,10038,10038,55,'aguardando','PINTURA','media',NULL,'2026-07-08 12:01:38','2026-07-08 12:01:38'),
(56,10038,10038,56,'aguardando','MONTAGEM','media',NULL,'2026-07-08 12:01:38','2026-07-08 12:01:38'),
(57,10038,10038,57,'aguardando','MONTAGEM','media',NULL,'2026-07-08 12:01:38','2026-07-08 12:01:38'),
(58,10027,10017,58,'aguardando','SERRALHERIA','media',NULL,'2026-07-08 12:01:38','2026-07-08 12:01:38'),
(59,10027,10017,59,'aguardando','SERRALHERIA','media',NULL,'2026-07-08 12:01:38','2026-07-08 12:01:38'),
(60,10027,10018,60,'aguardando','SERRALHERIA','media',NULL,'2026-07-08 12:01:38','2026-07-08 12:01:38'),
(61,10027,10018,61,'aguardando','FUNILARIA','media',NULL,'2026-07-08 12:01:38','2026-07-08 12:01:38'),
(62,10027,10019,62,'aguardando','SERRALHERIA','media',NULL,'2026-07-08 12:01:38','2026-07-08 12:01:38'),
(63,10027,10019,63,'aguardando','SERRALHERIA','media',NULL,'2026-07-08 12:01:38','2026-07-08 12:01:38'),
(64,10027,10020,64,'aguardando','SERRALHERIA','media',NULL,'2026-07-08 12:01:38','2026-07-08 12:01:38'),
(65,10027,10021,65,'aguardando','SERRALHERIA','media',NULL,'2026-07-08 12:01:38','2026-07-08 12:01:38'),
(66,10027,10021,66,'aguardando','FUNILARIA','media',NULL,'2026-07-08 12:01:38','2026-07-08 12:01:38'),
(67,10027,10022,67,'aguardando','SERRALHERIA','media',NULL,'2026-07-08 12:01:38','2026-07-08 12:01:38'),
(68,10027,10023,68,'aguardando','SERRALHERIA','media',NULL,'2026-07-08 12:01:38','2026-07-08 12:01:38'),
(69,10027,10024,69,'aguardando','SERRALHERIA','media',NULL,'2026-07-08 12:01:38','2026-07-08 12:01:38'),
(70,10027,10025,70,'aguardando','SERRALHERIA','media',NULL,'2026-07-08 12:01:39','2026-07-08 12:01:39'),
(71,10027,10025,71,'aguardando','TAPECARIA','media',NULL,'2026-07-08 12:01:39','2026-07-08 12:01:39'),
(72,10027,10025,72,'aguardando','TAPECARIA','media',NULL,'2026-07-08 12:01:39','2026-07-08 12:01:39'),
(73,10027,10026,73,'aguardando','SERRALHERIA','media',NULL,'2026-07-08 12:01:39','2026-07-08 12:01:39'),
(74,10027,10026,74,'aguardando','TAPECARIA','media',NULL,'2026-07-08 12:01:39','2026-07-08 12:01:39'),
(75,10027,10026,75,'aguardando','TAPECARIA','media',NULL,'2026-07-08 12:01:39','2026-07-08 12:01:39'),
(76,10027,10027,76,'aguardando','SERRALHERIA','media',NULL,'2026-07-08 12:01:39','2026-07-08 12:01:39'),
(77,10027,10027,77,'aguardando','PINTURA','media',NULL,'2026-07-08 12:01:39','2026-07-08 12:01:39'),
(78,10027,10027,78,'aguardando','MONTAGEM','media',NULL,'2026-07-08 12:01:39','2026-07-08 12:01:39'),
(79,10027,10027,79,'aguardando','MONTAGEM','media',NULL,'2026-07-08 12:01:39','2026-07-08 12:01:39'),
(80,9992,9987,80,'aguardando','SERRALHERIA','media',NULL,'2026-07-08 12:01:39','2026-07-08 12:01:39'),
(81,9992,9987,81,'aguardando','FUNILARIA','media',NULL,'2026-07-08 12:01:39','2026-07-08 12:01:39'),
(82,9992,9988,82,'aguardando','SERRALHERIA','media',NULL,'2026-07-08 12:01:39','2026-07-08 12:01:39'),
(83,9992,9988,83,'aguardando','SERRALHERIA','media',NULL,'2026-07-08 12:01:39','2026-07-08 12:01:39'),
(84,9992,9989,84,'aguardando','SERRALHERIA','media',NULL,'2026-07-08 12:01:39','2026-07-08 12:01:39'),
(85,9992,9989,85,'aguardando','SERRALHERIA','media',NULL,'2026-07-08 12:01:39','2026-07-08 12:01:39'),
(86,9992,9990,86,'aguardando','SERRALHERIA','media',NULL,'2026-07-08 12:01:39','2026-07-08 12:01:39'),
(87,9992,9991,87,'aguardando','SERRALHERIA','media',NULL,'2026-07-08 12:01:39','2026-07-08 12:01:39'),
(88,9992,9992,88,'aguardando','SERRALHERIA','media',NULL,'2026-07-08 12:01:39','2026-07-08 12:01:39'),
(89,9992,9992,89,'aguardando','SERRALHERIA','media',NULL,'2026-07-08 12:01:39','2026-07-08 12:01:39'),
(90,9992,9992,90,'aguardando','ACABAMENTO','media',NULL,'2026-07-08 12:01:39','2026-07-08 12:01:39'),
(91,9992,9992,91,'aguardando','ACABAMENTO','media',NULL,'2026-07-08 12:01:39','2026-07-08 12:01:39'),
(92,9992,9992,92,'aguardando','MONTAGEM','media',NULL,'2026-07-08 12:01:39','2026-07-08 12:01:39'),
(93,9992,9992,93,'aguardando','EMBALAGEM','media',NULL,'2026-07-08 12:01:39','2026-07-08 12:01:39');
/*!40000 ALTER TABLE `kanban_cards` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `log_atividades`
--

DROP TABLE IF EXISTS `log_atividades`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8mb4 */;
CREATE TABLE `log_atividades` (
  `id` int(11) NOT NULL AUTO_INCREMENT,
  `data_hora` timestamp NOT NULL DEFAULT current_timestamp(),
  `usuario_id` int(11) DEFAULT NULL,
  `usuario_nome` varchar(100) DEFAULT NULL,
  `acao` varchar(100) NOT NULL,
  `tabela` varchar(50) DEFAULT NULL,
  `registro_id` int(11) DEFAULT NULL,
  `descricao` text DEFAULT NULL,
  `ip_address` varchar(50) DEFAULT NULL,
  PRIMARY KEY (`id`),
  KEY `idx_data` (`data_hora`),
  KEY `idx_usuario` (`usuario_id`)
) ENGINE=InnoDB AUTO_INCREMENT=30 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `log_atividades`
--

LOCK TABLES `log_atividades` WRITE;
/*!40000 ALTER TABLE `log_atividades` DISABLE KEYS */;
INSERT INTO `log_atividades` VALUES
(1,'2026-07-01 18:08:08',1,'Administrador','importar_erp','lotes_producao',9682,'Lote 000332 importado do ERP',NULL),
(2,'2026-07-01 18:12:34',1,'Administrador','importar_erp','lotes_producao',9674,'Lote 000331 importado do ERP',NULL),
(3,'2026-07-01 18:12:34',1,'Administrador','importar_erp','lotes_producao',9663,'Lote 000330 importado do ERP',NULL),
(4,'2026-07-01 18:12:35',1,'Administrador','importar_erp','lotes_producao',9490,'Lote 000290 importado do ERP',NULL),
(5,'2026-07-01 18:22:21',1,'Administrador','alterar_prioridade','lotes',9663,'OP #9663 → urgente',NULL),
(6,'2026-07-01 18:22:27',1,'Administrador','alterar_status','lotes',9663,'OP #9663 → liberado',NULL),
(7,'2026-07-01 18:52:15',1,'Administrador','marcar_separado','lotes',9490,'OP #9490 marcada como SEPARADA pelo almoxarifado',NULL),
(8,'2026-07-06 20:04:08',1,'Administrador','importar_erp','lotes_producao',9727,'Lote 000336 importado do ERP',NULL),
(9,'2026-07-07 11:37:04',1,'Administrador','importar_erp','lotes_producao',9738,'Lote 000337 importado do ERP',NULL),
(10,'2026-07-07 11:37:05',1,'Administrador','importar_erp','lotes_producao',9717,'Lote 000335 importado do ERP',NULL),
(11,'2026-07-07 11:37:05',1,'Administrador','importar_erp','lotes_producao',9706,'Lote 000334 importado do ERP',NULL),
(12,'2026-07-07 11:37:52',1,'Administrador','alterar_prioridade','lotes',9738,'OP #9738 → baixa',NULL),
(13,'2026-07-07 11:37:55',1,'Administrador','alterar_prioridade','lotes',9717,'OP #9717 → urgente',NULL),
(14,'2026-07-07 11:38:00',1,'Administrador','alterar_prioridade','lotes',9706,'OP #9706 → alta',NULL),
(15,'2026-07-07 11:43:13',1,'Administrador','alterar_status','lotes',9738,'OP #9738 → liberado',NULL),
(16,'2026-07-07 11:43:17',1,'Administrador','alterar_status','lotes',9706,'OP #9706 → liberado',NULL),
(17,'2026-07-07 18:30:34',1,'Administrador','importar_erp','lotes_producao',10016,'Lote 000362 importado do ERP',NULL),
(18,'2026-07-07 18:30:35',1,'Administrador','importar_erp','lotes_producao',10009,'Lote 000361 importado do ERP',NULL),
(19,'2026-07-07 18:30:36',1,'Administrador','importar_erp','lotes_producao',10001,'Lote 000360 importado do ERP',NULL),
(20,'2026-07-07 18:30:52',1,'Administrador','alterar_prioridade','lotes',10001,'OP #10001 → alta',NULL),
(21,'2026-07-07 18:30:54',1,'Administrador','alterar_prioridade','lotes',10009,'OP #10009 → baixa',NULL),
(22,'2026-07-07 18:30:56',1,'Administrador','alterar_prioridade','lotes',10016,'OP #10016 → urgente',NULL),
(23,'2026-07-07 18:51:45',1,'Administrador','alterar_status','lotes',10001,'OP #10001 → liberado',NULL),
(24,'2026-07-07 18:51:49',1,'Administrador','alterar_status','lotes',10016,'OP #10016 → liberado',NULL),
(25,'2026-07-07 18:51:52',1,'Administrador','alterar_status','lotes',10009,'OP #10009 → liberado',NULL),
(26,'2026-07-08 12:06:54',1,'Administrador','alterar_status','lotes',10016,'OP #10016 → cancelado',NULL),
(27,'2026-07-08 15:01:38',1,'Administrador','importar_erp','lotes_producao',10038,'Lote 000364 importado do ERP',NULL),
(28,'2026-07-08 15:01:39',1,'Administrador','importar_erp','lotes_producao',10027,'Lote 000363 importado do ERP',NULL),
(29,'2026-07-08 15:01:39',1,'Administrador','importar_erp','lotes_producao',9992,'Lote 000359 importado do ERP',NULL);
/*!40000 ALTER TABLE `log_atividades` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `lotes_producao`
--

DROP TABLE IF EXISTS `lotes_producao`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8mb4 */;
CREATE TABLE `lotes_producao` (
  `id` int(11) NOT NULL AUTO_INCREMENT,
  `lote_codigo` varchar(50) DEFAULT NULL,
  `ordem` int(11) NOT NULL COMMENT 'Numero da OF principal',
  `codigo_produto` varchar(50) DEFAULT NULL,
  `descricao_produto` varchar(200) DEFAULT NULL,
  `qtde_ordem` decimal(14,4) DEFAULT 0.0000,
  `qtde_reportada` decimal(14,4) DEFAULT 0.0000,
  `unidade_medida` varchar(10) DEFAULT 'UN',
  `status_erp` varchar(10) DEFAULT 'A',
  `status` enum('importado','liberado','em_producao','pausado','finalizado','cancelado') DEFAULT 'importado',
  `prioridade` enum('urgente','alta','media','baixa') DEFAULT 'media',
  `data_previsao_erp` date DEFAULT NULL,
  `data_abertura_erp` date DEFAULT NULL,
  `data_importacao` timestamp NOT NULL DEFAULT current_timestamp(),
  `data_ultima_sync` timestamp NOT NULL DEFAULT current_timestamp() ON UPDATE current_timestamp(),
  `data_inicio_producao` datetime DEFAULT NULL,
  `data_fim_producao` datetime DEFAULT NULL,
  `departamento_atual` varchar(50) DEFAULT NULL,
  `setor_atual_seq` int(11) DEFAULT 1,
  `total_setores` int(11) DEFAULT 0,
  `planejador` varchar(100) DEFAULT NULL,
  `observacoes` text DEFAULT NULL,
  `separacao_status` enum('pendente','separando','separado','entregue') DEFAULT 'pendente',
  `data_separacao` datetime DEFAULT NULL,
  `data_entrega` datetime DEFAULT NULL,
  `usuario_separacao_id` int(11) DEFAULT NULL,
  `usuario_entrega_id` int(11) DEFAULT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `ordem` (`ordem`),
  KEY `idx_status` (`status`),
  KEY `idx_prioridade` (`prioridade`),
  KEY `idx_departamento` (`departamento_atual`)
) ENGINE=InnoDB AUTO_INCREMENT=7 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `lotes_producao`
--

LOCK TABLES `lotes_producao` WRITE;
/*!40000 ALTER TABLE `lotes_producao` DISABLE KEYS */;
INSERT INTO `lotes_producao` VALUES
(1,'000362',10016,'S-0060          ','BANCO GIR PINT EPOXI ASS EST C/ PONTEIRAS         ',100.0000,0.0000,'PC','A','cancelado','urgente','2026-08-07','2026-07-07','2026-07-07 18:30:34','2026-07-08 12:06:54',NULL,NULL,'CORTE',22806,1,'Administrador',NULL,'pendente',NULL,NULL,NULL,NULL),
(2,'000361',10009,'S-0020          ','ARMARIO VITRINE COM 02 PORTAS                     ',100.0000,0.0000,'PC','A','liberado','baixa','2026-07-27','2026-07-07','2026-07-07 18:30:34','2026-07-07 18:51:52',NULL,NULL,'CORTE',22792,4,'Administrador',NULL,'pendente',NULL,NULL,NULL,NULL),
(3,'000360',10001,'S-0010          ','ARMARIO VITRINE COM 01 PORTA                      ',10.0000,0.0000,'PC','A','liberado','alta','2026-07-17','2026-07-07','2026-07-07 18:30:35','2026-07-07 18:51:45',NULL,NULL,'CORTE',22777,4,'Administrador',NULL,'pendente',NULL,NULL,NULL,NULL),
(4,'000364',10038,'S-0440-X        ','MESA P EX. CLI. P/ 150 KG ESPECIAL                ',2.0000,0.0000,'PC','A','importado','media','2026-08-20','2026-07-08','2026-07-08 15:01:37','2026-07-08 15:01:38',NULL,NULL,'SERRALHERIA',22834,5,'Administrador',NULL,'pendente',NULL,NULL,NULL,NULL),
(5,'000363',10027,'S-0440          ','MESA P EX. CLI. P/ 150 KG                         ',100.0000,0.0000,'PC','A','importado','media','2026-07-30','2026-07-08','2026-07-08 15:01:38','2026-07-08 15:01:39',NULL,NULL,'SERRALHERIA',22812,5,'Administrador',NULL,'pendente',NULL,NULL,NULL,NULL),
(6,'000359',9992,'S-0300          ','CARRO PARA CURATIVO SIMPLES EM ACO INOX           ',10.0000,0.0000,'PC','A','importado','media','2026-07-07','2026-07-07','2026-07-08 15:01:39','2026-07-08 15:01:39',NULL,NULL,'SERRALHERIA',22763,5,'Administrador',NULL,'pendente',NULL,NULL,NULL,NULL);
/*!40000 ALTER TABLE `lotes_producao` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `materiais_of`
--

DROP TABLE IF EXISTS `materiais_of`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8mb4 */;
CREATE TABLE `materiais_of` (
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
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `materiais_of`
--

LOCK TABLES `materiais_of` WRITE;
/*!40000 ALTER TABLE `materiais_of` DISABLE KEYS */;
/*!40000 ALTER TABLE `materiais_of` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `operacoes_producao`
--

DROP TABLE IF EXISTS `operacoes_producao`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8mb4 */;
CREATE TABLE `operacoes_producao` (
  `id` int(11) NOT NULL AUTO_INCREMENT,
  `of_numero` int(11) NOT NULL,
  `lote_ordem` int(11) NOT NULL,
  `sequencia` int(11) NOT NULL,
  `fase` varchar(10) DEFAULT NULL,
  `descricao_operacao` varchar(200) NOT NULL,
  `departamento` varchar(50) DEFAULT NULL,
  `codigo_barras` varchar(50) DEFAULT NULL,
  `status` enum('pendente','em_andamento','pausado','concluido','cancelado') DEFAULT 'pendente',
  `data_inicio` datetime DEFAULT NULL,
  `data_fim` datetime DEFAULT NULL,
  `usuario_inicio_id` int(11) DEFAULT NULL,
  `usuario_fim_id` int(11) DEFAULT NULL,
  `tempo_gasto_minutos` int(11) DEFAULT 0,
  `qtde_produzida` decimal(14,4) DEFAULT 0.0000,
  `qtde_refugada` decimal(14,4) DEFAULT 0.0000,
  `observacoes` text DEFAULT NULL,
  PRIMARY KEY (`id`),
  KEY `of_numero` (`of_numero`),
  KEY `lote_ordem` (`lote_ordem`),
  KEY `idx_departamento` (`departamento`),
  KEY `idx_status` (`status`)
) ENGINE=InnoDB AUTO_INCREMENT=94 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `operacoes_producao`
--

LOCK TABLES `operacoes_producao` WRITE;
/*!40000 ALTER TABLE `operacoes_producao` DISABLE KEYS */;
INSERT INTO `operacoes_producao` VALUES
(1,10012,10016,22806,'10','CORTAR                                                      ','CORTE',NULL,'pendente',NULL,NULL,NULL,NULL,0,0.0000,0.0000,NULL),
(2,10012,10016,22807,'10','CURVAR                                                      ','CORTE',NULL,'pendente',NULL,NULL,NULL,NULL,0,0.0000,0.0000,NULL),
(3,10013,10016,22808,'10','CORTAR                                                      ','CORTE',NULL,'pendente',NULL,NULL,NULL,NULL,0,0.0000,0.0000,NULL),
(4,10014,10016,22809,'10','CORTAR                                                      ','CORTE',NULL,'pendente',NULL,NULL,NULL,NULL,0,0.0000,0.0000,NULL),
(5,10015,10016,22810,'10','CORTAR                                                      ','CORTE',NULL,'pendente',NULL,NULL,NULL,NULL,0,0.0000,0.0000,NULL),
(6,10015,10016,22811,'10','CURVAR                                                      ','CORTE',NULL,'pendente',NULL,NULL,NULL,NULL,0,0.0000,0.0000,NULL),
(7,10002,10009,22792,'10','CORTAR                                                      ','CORTE',NULL,'pendente',NULL,NULL,NULL,NULL,0,0.0000,0.0000,NULL),
(8,10002,10009,22793,'15','DOBRAR                                                      ','FUNILARIA',NULL,'pendente',NULL,NULL,NULL,NULL,0,0.0000,0.0000,NULL),
(9,10003,10009,22794,'10','CORTAR                                                      ','CORTE',NULL,'pendente',NULL,NULL,NULL,NULL,0,0.0000,0.0000,NULL),
(10,10003,10009,22795,'15','DOBRAR                                                      ','FUNILARIA',NULL,'pendente',NULL,NULL,NULL,NULL,0,0.0000,0.0000,NULL),
(11,10004,10009,22796,'10','CORTAR                                                      ','CORTE',NULL,'pendente',NULL,NULL,NULL,NULL,0,0.0000,0.0000,NULL),
(12,10004,10009,22797,'15','DOBRAR                                                      ','FUNILARIA',NULL,'pendente',NULL,NULL,NULL,NULL,0,0.0000,0.0000,NULL),
(13,10005,10009,22798,'10','CORTAR                                                      ','CORTE',NULL,'pendente',NULL,NULL,NULL,NULL,0,0.0000,0.0000,NULL),
(14,10006,10009,22799,'10','CORTAR                                                      ','CORTE',NULL,'pendente',NULL,NULL,NULL,NULL,0,0.0000,0.0000,NULL),
(15,10007,10009,22800,'10','CORTAR                                                      ','CORTE',NULL,'pendente',NULL,NULL,NULL,NULL,0,0.0000,0.0000,NULL),
(16,10008,10009,22801,'10','PRENSA (CORTAR)                                             ','CORTE',NULL,'pendente',NULL,NULL,NULL,NULL,0,0.0000,0.0000,NULL),
(17,10009,10009,22802,'10','SOLDAR                                                      ','CORTE',NULL,'pendente',NULL,NULL,NULL,NULL,0,0.0000,0.0000,NULL),
(18,10009,10009,22803,'20','PINTAR                                                      ','PINTURA',NULL,'pendente',NULL,NULL,NULL,NULL,0,0.0000,0.0000,NULL),
(19,10009,10009,22804,'50','MONTAR                                                      ','MONTAGEM',NULL,'pendente',NULL,NULL,NULL,NULL,0,0.0000,0.0000,NULL),
(20,10009,10009,22805,'50','EMBALAGEM                                                   ','MONTAGEM',NULL,'pendente',NULL,NULL,NULL,NULL,0,0.0000,0.0000,NULL),
(21,9993,10001,22777,'10','CORTAR                                                      ','CORTE',NULL,'pendente',NULL,NULL,NULL,NULL,0,0.0000,0.0000,NULL),
(22,9993,10001,22778,'15','DOBRAR                                                      ','FUNILARIA',NULL,'pendente',NULL,NULL,NULL,NULL,0,0.0000,0.0000,NULL),
(23,9994,10001,22779,'10','CORTAR                                                      ','CORTE',NULL,'pendente',NULL,NULL,NULL,NULL,0,0.0000,0.0000,NULL),
(24,9995,10001,22780,'10','CORTAR                                                      ','CORTE',NULL,'pendente',NULL,NULL,NULL,NULL,0,0.0000,0.0000,NULL),
(25,9996,10001,22781,'10','CORTAR                                                      ','CORTE',NULL,'pendente',NULL,NULL,NULL,NULL,0,0.0000,0.0000,NULL),
(26,9996,10001,22782,'15','DOBRAR                                                      ','FUNILARIA',NULL,'pendente',NULL,NULL,NULL,NULL,0,0.0000,0.0000,NULL),
(27,9997,10001,22783,'10','CORTAR                                                      ','CORTE',NULL,'pendente',NULL,NULL,NULL,NULL,0,0.0000,0.0000,NULL),
(28,9998,10001,22784,'10','CORTAR                                                      ','CORTE',NULL,'pendente',NULL,NULL,NULL,NULL,0,0.0000,0.0000,NULL),
(29,9999,10001,22785,'10','PRENSA (CORTAR)                                             ','CORTE',NULL,'pendente',NULL,NULL,NULL,NULL,0,0.0000,0.0000,NULL),
(30,10000,10001,22786,'10','SOLDAR                                                      ','CORTE',NULL,'pendente',NULL,NULL,NULL,NULL,0,0.0000,0.0000,NULL),
(31,10000,10001,22787,'20','PINTAR                                                      ','PINTURA',NULL,'pendente',NULL,NULL,NULL,NULL,0,0.0000,0.0000,NULL),
(32,10000,10001,22788,'50','MONTAR                                                      ','MONTAGEM',NULL,'pendente',NULL,NULL,NULL,NULL,0,0.0000,0.0000,NULL),
(33,10000,10001,22789,'50','EMBALAGEM                                                   ','MONTAGEM',NULL,'pendente',NULL,NULL,NULL,NULL,0,0.0000,0.0000,NULL),
(34,10001,10001,22790,'10','CORTAR                                                      ','CORTE',NULL,'pendente',NULL,NULL,NULL,NULL,0,0.0000,0.0000,NULL),
(35,10001,10001,22791,'15','DOBRAR                                                      ','FUNILARIA',NULL,'pendente',NULL,NULL,NULL,NULL,0,0.0000,0.0000,NULL),
(36,10028,10038,22834,'10','PRENSA (CORTAR)                                             ','SERRALHERIA',NULL,'pendente',NULL,NULL,NULL,NULL,0,0.0000,0.0000,NULL),
(37,10028,10038,22835,'10','CURVAR                                                      ','SERRALHERIA',NULL,'pendente',NULL,NULL,NULL,NULL,0,0.0000,0.0000,NULL),
(38,10029,10038,22836,'10','CORTAR                                                      ','SERRALHERIA',NULL,'pendente',NULL,NULL,NULL,NULL,0,0.0000,0.0000,NULL),
(39,10029,10038,22837,'15','CURVAR                                                      ','FUNILARIA',NULL,'pendente',NULL,NULL,NULL,NULL,0,0.0000,0.0000,NULL),
(40,10030,10038,22838,'10','CORTAR                                                      ','SERRALHERIA',NULL,'pendente',NULL,NULL,NULL,NULL,0,0.0000,0.0000,NULL),
(41,10030,10038,22839,'10','CURVAR                                                      ','SERRALHERIA',NULL,'pendente',NULL,NULL,NULL,NULL,0,0.0000,0.0000,NULL),
(42,10031,10038,22840,'10','CORTAR                                                      ','SERRALHERIA',NULL,'pendente',NULL,NULL,NULL,NULL,0,0.0000,0.0000,NULL),
(43,10032,10038,22841,'10','CORTAR                                                      ','SERRALHERIA',NULL,'pendente',NULL,NULL,NULL,NULL,0,0.0000,0.0000,NULL),
(44,10032,10038,22842,'15','DOBRAR                                                      ','FUNILARIA',NULL,'pendente',NULL,NULL,NULL,NULL,0,0.0000,0.0000,NULL),
(45,10033,10038,22843,'10','CORTAR                                                      ','SERRALHERIA',NULL,'pendente',NULL,NULL,NULL,NULL,0,0.0000,0.0000,NULL),
(46,10034,10038,22844,'10','CORTAR                                                      ','SERRALHERIA',NULL,'pendente',NULL,NULL,NULL,NULL,0,0.0000,0.0000,NULL),
(47,10035,10038,22845,'10','CORTAR                                                      ','SERRALHERIA',NULL,'pendente',NULL,NULL,NULL,NULL,0,0.0000,0.0000,NULL),
(48,10036,10038,22846,'10','CORTAR                                                      ','SERRALHERIA',NULL,'pendente',NULL,NULL,NULL,NULL,0,0.0000,0.0000,NULL),
(49,10036,10038,22847,'40','COLAR                                                       ','TAPECARIA',NULL,'pendente',NULL,NULL,NULL,NULL,0,0.0000,0.0000,NULL),
(50,10036,10038,22848,'40','GRAMPEAR                                                    ','TAPECARIA',NULL,'pendente',NULL,NULL,NULL,NULL,0,0.0000,0.0000,NULL),
(51,10037,10038,22849,'10','CORTAR                                                      ','SERRALHERIA',NULL,'pendente',NULL,NULL,NULL,NULL,0,0.0000,0.0000,NULL),
(52,10037,10038,22850,'40','COLAR                                                       ','TAPECARIA',NULL,'pendente',NULL,NULL,NULL,NULL,0,0.0000,0.0000,NULL),
(53,10037,10038,22851,'40','GRAMPEAR                                                    ','TAPECARIA',NULL,'pendente',NULL,NULL,NULL,NULL,0,0.0000,0.0000,NULL),
(54,10038,10038,22852,'10','SOLDAR                                                      ','SERRALHERIA',NULL,'pendente',NULL,NULL,NULL,NULL,0,0.0000,0.0000,NULL),
(55,10038,10038,22853,'20','PINTAR                                                      ','PINTURA',NULL,'pendente',NULL,NULL,NULL,NULL,0,0.0000,0.0000,NULL),
(56,10038,10038,22854,'50','MONTAR                                                      ','MONTAGEM',NULL,'pendente',NULL,NULL,NULL,NULL,0,0.0000,0.0000,NULL),
(57,10038,10038,22855,'50','EMBALAGEM                                                   ','MONTAGEM',NULL,'pendente',NULL,NULL,NULL,NULL,0,0.0000,0.0000,NULL),
(58,10017,10027,22812,'10','PRENSA (CORTAR)                                             ','SERRALHERIA',NULL,'pendente',NULL,NULL,NULL,NULL,0,0.0000,0.0000,NULL),
(59,10017,10027,22813,'10','CURVAR                                                      ','SERRALHERIA',NULL,'pendente',NULL,NULL,NULL,NULL,0,0.0000,0.0000,NULL),
(60,10018,10027,22814,'10','CORTAR                                                      ','SERRALHERIA',NULL,'pendente',NULL,NULL,NULL,NULL,0,0.0000,0.0000,NULL),
(61,10018,10027,22815,'15','CURVAR                                                      ','FUNILARIA',NULL,'pendente',NULL,NULL,NULL,NULL,0,0.0000,0.0000,NULL),
(62,10019,10027,22816,'10','CORTAR                                                      ','SERRALHERIA',NULL,'pendente',NULL,NULL,NULL,NULL,0,0.0000,0.0000,NULL),
(63,10019,10027,22817,'10','CURVAR                                                      ','SERRALHERIA',NULL,'pendente',NULL,NULL,NULL,NULL,0,0.0000,0.0000,NULL),
(64,10020,10027,22818,'10','CORTAR                                                      ','SERRALHERIA',NULL,'pendente',NULL,NULL,NULL,NULL,0,0.0000,0.0000,NULL),
(65,10021,10027,22819,'10','CORTAR                                                      ','SERRALHERIA',NULL,'pendente',NULL,NULL,NULL,NULL,0,0.0000,0.0000,NULL),
(66,10021,10027,22820,'15','DOBRAR                                                      ','FUNILARIA',NULL,'pendente',NULL,NULL,NULL,NULL,0,0.0000,0.0000,NULL),
(67,10022,10027,22821,'10','CORTAR                                                      ','SERRALHERIA',NULL,'pendente',NULL,NULL,NULL,NULL,0,0.0000,0.0000,NULL),
(68,10023,10027,22822,'10','CORTAR                                                      ','SERRALHERIA',NULL,'pendente',NULL,NULL,NULL,NULL,0,0.0000,0.0000,NULL),
(69,10024,10027,22823,'10','CORTAR                                                      ','SERRALHERIA',NULL,'pendente',NULL,NULL,NULL,NULL,0,0.0000,0.0000,NULL),
(70,10025,10027,22824,'10','CORTAR                                                      ','SERRALHERIA',NULL,'pendente',NULL,NULL,NULL,NULL,0,0.0000,0.0000,NULL),
(71,10025,10027,22825,'40','COLAR                                                       ','TAPECARIA',NULL,'pendente',NULL,NULL,NULL,NULL,0,0.0000,0.0000,NULL),
(72,10025,10027,22826,'40','GRAMPEAR                                                    ','TAPECARIA',NULL,'pendente',NULL,NULL,NULL,NULL,0,0.0000,0.0000,NULL),
(73,10026,10027,22827,'10','CORTAR                                                      ','SERRALHERIA',NULL,'pendente',NULL,NULL,NULL,NULL,0,0.0000,0.0000,NULL),
(74,10026,10027,22828,'40','COLAR                                                       ','TAPECARIA',NULL,'pendente',NULL,NULL,NULL,NULL,0,0.0000,0.0000,NULL),
(75,10026,10027,22829,'40','GRAMPEAR                                                    ','TAPECARIA',NULL,'pendente',NULL,NULL,NULL,NULL,0,0.0000,0.0000,NULL),
(76,10027,10027,22830,'10','SOLDAR                                                      ','SERRALHERIA',NULL,'pendente',NULL,NULL,NULL,NULL,0,0.0000,0.0000,NULL),
(77,10027,10027,22831,'20','PINTAR                                                      ','PINTURA',NULL,'pendente',NULL,NULL,NULL,NULL,0,0.0000,0.0000,NULL),
(78,10027,10027,22832,'50','MONTAR                                                      ','MONTAGEM',NULL,'pendente',NULL,NULL,NULL,NULL,0,0.0000,0.0000,NULL),
(79,10027,10027,22833,'50','EMBALAGEM                                                   ','MONTAGEM',NULL,'pendente',NULL,NULL,NULL,NULL,0,0.0000,0.0000,NULL),
(80,9987,9992,22763,'10','CORTAR                                                      ','SERRALHERIA',NULL,'pendente',NULL,NULL,NULL,NULL,0,0.0000,0.0000,NULL),
(81,9987,9992,22764,'15','DOBRAR                                                      ','FUNILARIA',NULL,'pendente',NULL,NULL,NULL,NULL,0,0.0000,0.0000,NULL),
(82,9988,9992,22765,'10','CORTAR                                                      ','SERRALHERIA',NULL,'pendente',NULL,NULL,NULL,NULL,0,0.0000,0.0000,NULL),
(83,9988,9992,22766,'10','CURVAR                                                      ','SERRALHERIA',NULL,'pendente',NULL,NULL,NULL,NULL,0,0.0000,0.0000,NULL),
(84,9989,9992,22767,'10','CORTAR                                                      ','SERRALHERIA',NULL,'pendente',NULL,NULL,NULL,NULL,0,0.0000,0.0000,NULL),
(85,9989,9992,22768,'10','CURVAR                                                      ','SERRALHERIA',NULL,'pendente',NULL,NULL,NULL,NULL,0,0.0000,0.0000,NULL),
(86,9990,9992,22769,'10','CORTAR                                                      ','SERRALHERIA',NULL,'pendente',NULL,NULL,NULL,NULL,0,0.0000,0.0000,NULL),
(87,9991,9992,22770,'10','CORTAR                                                      ','SERRALHERIA',NULL,'pendente',NULL,NULL,NULL,NULL,0,0.0000,0.0000,NULL),
(88,9992,9992,22771,'10','SOLDAR                                                      ','SERRALHERIA',NULL,'pendente',NULL,NULL,NULL,NULL,0,0.0000,0.0000,NULL),
(89,9992,9992,22772,'10','TRATAMENTO DE SOLDA                                         ','SERRALHERIA',NULL,'pendente',NULL,NULL,NULL,NULL,0,0.0000,0.0000,NULL),
(90,9992,9992,22773,'30','LIMPEZA                                                     ','ACABAMENTO',NULL,'pendente',NULL,NULL,NULL,NULL,0,0.0000,0.0000,NULL),
(91,9992,9992,22774,'30','POLIMENTO                                                   ','ACABAMENTO',NULL,'pendente',NULL,NULL,NULL,NULL,0,0.0000,0.0000,NULL),
(92,9992,9992,22775,'50','MONTAR                                                      ','MONTAGEM',NULL,'pendente',NULL,NULL,NULL,NULL,0,0.0000,0.0000,NULL),
(93,9992,9992,22776,'80','EMBALAGEM                                                   ','EMBALAGEM',NULL,'pendente',NULL,NULL,NULL,NULL,0,0.0000,0.0000,NULL);
/*!40000 ALTER TABLE `operacoes_producao` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `ordens_fabricacao`
--

DROP TABLE IF EXISTS `ordens_fabricacao`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8mb4 */;
CREATE TABLE `ordens_fabricacao` (
  `id` int(11) NOT NULL AUTO_INCREMENT,
  `lote_ordem` int(11) NOT NULL,
  `of_numero` int(11) NOT NULL,
  `codigo_produto` varchar(50) DEFAULT NULL,
  `descricao_produto` varchar(200) DEFAULT NULL,
  `qtde_ordem` decimal(14,4) DEFAULT 0.0000,
  `unidade_medida` varchar(10) DEFAULT 'PC',
  `tipo` enum('pai','filho') DEFAULT 'filho',
  `status` enum('pendente','em_producao','pausado','concluido','cancelado') DEFAULT 'pendente',
  `data_previsao` date DEFAULT NULL,
  `data_inicio` datetime DEFAULT NULL,
  `data_fim` datetime DEFAULT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `of_numero` (`of_numero`),
  KEY `lote_ordem` (`lote_ordem`)
) ENGINE=InnoDB AUTO_INCREMENT=53 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `ordens_fabricacao`
--

LOCK TABLES `ordens_fabricacao` WRITE;
/*!40000 ALTER TABLE `ordens_fabricacao` DISABLE KEYS */;
INSERT INTO `ordens_fabricacao` VALUES
(1,10016,10010,'CJ-0174         ','BANCO GIR PINT EPOXI ASS EST C/ PONTEIRAS         ',100.0000,'PC','filho','pendente','2026-08-07',NULL,NULL),
(2,10016,10011,'CJ-0175         ','BANCO GIR PINT EPOXI ASS EST C/ PONTEIRAS         ',100.0000,'PC','filho','pendente','2026-08-07',NULL,NULL),
(3,10016,10012,'PP-0320         ','BANCO GIR PINT EPOXI ASS EST C/ PONTEIRAS         ',400.0000,'PC','filho','pendente','2026-08-07',NULL,NULL),
(4,10016,10013,'PP-0321         ','BANCO GIR PINT EPOXI ASS EST C/ PONTEIRAS         ',100.0000,'PC','filho','pendente','2026-08-07',NULL,NULL),
(5,10016,10014,'PP-0322         ','BANCO GIR PINT EPOXI ASS EST C/ PONTEIRAS         ',100.0000,'PC','filho','pendente','2026-08-07',NULL,NULL),
(6,10016,10015,'PP-0323         ','BANCO GIR PINT EPOXI ASS EST C/ PONTEIRAS         ',100.0000,'PC','filho','pendente','2026-08-07',NULL,NULL),
(7,10016,10016,'S-0060          ','BANCO GIR PINT EPOXI ASS EST C/ PONTEIRAS         ',100.0000,'PC','filho','pendente','2026-08-07',NULL,NULL),
(8,10009,10002,'PC-2710         ','ARMARIO VITRINE COM 02 PORTAS                     ',100.0000,'PC','filho','pendente','2026-07-27',NULL,NULL),
(9,10009,10003,'PC-2711         ','ARMARIO VITRINE COM 02 PORTAS                     ',100.0000,'PC','filho','pendente','2026-07-27',NULL,NULL),
(10,10009,10004,'PC-2712         ','ARMARIO VITRINE COM 02 PORTAS                     ',100.0000,'PC','filho','pendente','2026-07-27',NULL,NULL),
(11,10009,10005,'PC-2713         ','ARMARIO VITRINE COM 02 PORTAS                     ',100.0000,'PC','filho','pendente','2026-07-27',NULL,NULL),
(12,10009,10006,'PC-2714         ','ARMARIO VITRINE COM 02 PORTAS                     ',400.0000,'PC','filho','pendente','2026-07-27',NULL,NULL),
(13,10009,10007,'PC-2717         ','ARMARIO VITRINE COM 02 PORTAS                     ',400.0000,'PC','filho','pendente','2026-07-27',NULL,NULL),
(14,10009,10008,'PC-2718         ','ARMARIO VITRINE COM 02 PORTAS                     ',100.0000,'PC','filho','pendente','2026-07-27',NULL,NULL),
(15,10009,10009,'S-0020          ','ARMARIO VITRINE COM 02 PORTAS                     ',100.0000,'PC','filho','pendente','2026-07-27',NULL,NULL),
(16,10001,9993,'PP-0021         ','ARMARIO VITRINE COM 01 PORTA                      ',10.0000,'PC','filho','pendente','2026-07-17',NULL,NULL),
(17,10001,9994,'PP-0022         ','ARMARIO VITRINE COM 01 PORTA                      ',10.0000,'PC','filho','pendente','2026-07-17',NULL,NULL),
(18,10001,9995,'PP-0023         ','ARMARIO VITRINE COM 01 PORTA                      ',40.0000,'PC','filho','pendente','2026-07-17',NULL,NULL),
(19,10001,9996,'PP-0329         ','ARMARIO VITRINE COM 01 PORTA                      ',10.0000,'PC','filho','pendente','2026-07-17',NULL,NULL),
(20,10001,9997,'PP-0330         ','ARMARIO VITRINE COM 01 PORTA                      ',10.0000,'PC','filho','pendente','2026-07-17',NULL,NULL),
(21,10001,9998,'PP-0331         ','ARMARIO VITRINE COM 01 PORTA                      ',10.0000,'PC','filho','pendente','2026-07-17',NULL,NULL),
(22,10001,9999,'PP-0332         ','ARMARIO VITRINE COM 01 PORTA                      ',10.0000,'PC','filho','pendente','2026-07-17',NULL,NULL),
(23,10001,10000,'S-0010          ','ARMARIO VITRINE COM 01 PORTA                      ',10.0000,'PC','filho','pendente','2026-07-17',NULL,NULL),
(24,10001,10001,'S-0010-PC0001   ','ARMARIO VITRINE COM 01 PORTA                      ',10.0000,'PC','filho','pendente','2026-07-17',NULL,NULL),
(25,10038,10028,'PC-0001         ','MESA P EX. CLI. P/ 150 KG ESPECIAL                ',2.0000,'PC','filho','pendente','2026-08-20',NULL,NULL),
(26,10038,10029,'PC-0004         ','MESA P EX. CLI. P/ 150 KG ESPECIAL                ',4.0000,'PC','filho','pendente','2026-08-20',NULL,NULL),
(27,10038,10030,'PC-0005         ','MESA P EX. CLI. P/ 150 KG ESPECIAL                ',2.0000,'PC','filho','pendente','2026-08-20',NULL,NULL),
(28,10038,10031,'PC-0006         ','MESA P EX. CLI. P/ 150 KG ESPECIAL                ',4.0000,'PC','filho','pendente','2026-08-20',NULL,NULL),
(29,10038,10032,'PC-0008         ','MESA P EX. CLI. P/ 150 KG ESPECIAL                ',2.0000,'PC','filho','pendente','2026-08-20',NULL,NULL),
(30,10038,10033,'PC-0009         ','MESA P EX. CLI. P/ 150 KG ESPECIAL                ',2.0000,'PC','filho','pendente','2026-08-20',NULL,NULL),
(31,10038,10034,'PC-0010         ','MESA P EX. CLI. P/ 150 KG ESPECIAL                ',2.0000,'PC','filho','pendente','2026-08-20',NULL,NULL),
(32,10038,10035,'PC-0011         ','MESA P EX. CLI. P/ 150 KG ESPECIAL                ',2.0000,'PC','filho','pendente','2026-08-20',NULL,NULL),
(33,10038,10036,'PC-0659         ','MESA P EX. CLI. P/ 150 KG ESPECIAL                ',2.0000,'PC','filho','pendente','2026-08-20',NULL,NULL),
(34,10038,10037,'PC-0662         ','MESA P EX. CLI. P/ 150 KG ESPECIAL                ',2.0000,'PC','filho','pendente','2026-08-20',NULL,NULL),
(35,10038,10038,'S-0440-X        ','MESA P EX. CLI. P/ 150 KG ESPECIAL                ',2.0000,'PC','filho','pendente','2026-08-20',NULL,NULL),
(36,10027,10017,'PC-0001         ','MESA P EX. CLI. P/ 150 KG                         ',100.0000,'PC','filho','pendente','2026-07-30',NULL,NULL),
(37,10027,10018,'PC-0004         ','MESA P EX. CLI. P/ 150 KG                         ',200.0000,'PC','filho','pendente','2026-07-30',NULL,NULL),
(38,10027,10019,'PC-0005         ','MESA P EX. CLI. P/ 150 KG                         ',100.0000,'PC','filho','pendente','2026-07-30',NULL,NULL),
(39,10027,10020,'PC-0006         ','MESA P EX. CLI. P/ 150 KG                         ',200.0000,'PC','filho','pendente','2026-07-30',NULL,NULL),
(40,10027,10021,'PC-0008         ','MESA P EX. CLI. P/ 150 KG                         ',100.0000,'PC','filho','pendente','2026-07-30',NULL,NULL),
(41,10027,10022,'PC-0009         ','MESA P EX. CLI. P/ 150 KG                         ',100.0000,'PC','filho','pendente','2026-07-30',NULL,NULL),
(42,10027,10023,'PC-0010         ','MESA P EX. CLI. P/ 150 KG                         ',100.0000,'PC','filho','pendente','2026-07-30',NULL,NULL),
(43,10027,10024,'PC-0011         ','MESA P EX. CLI. P/ 150 KG                         ',100.0000,'PC','filho','pendente','2026-07-30',NULL,NULL),
(44,10027,10025,'PC-0659         ','MESA P EX. CLI. P/ 150 KG                         ',100.0000,'PC','filho','pendente','2026-07-30',NULL,NULL),
(45,10027,10026,'PC-0662         ','MESA P EX. CLI. P/ 150 KG                         ',100.0000,'PC','filho','pendente','2026-07-30',NULL,NULL),
(46,10027,10027,'S-0440          ','MESA P EX. CLI. P/ 150 KG                         ',100.0000,'PC','filho','pendente','2026-07-30',NULL,NULL),
(47,9992,9987,'PC-1033         ','CARRO PARA CURATIVO SIMPLES EM ACO INOX           ',20.0000,'PC','filho','pendente','2026-07-07',NULL,NULL),
(48,9992,9988,'PC-1034         ','CARRO PARA CURATIVO SIMPLES EM ACO INOX           ',20.0000,'PC','filho','pendente','2026-07-07',NULL,NULL),
(49,9992,9989,'PC-1035         ','CARRO PARA CURATIVO SIMPLES EM ACO INOX           ',20.0000,'PC','filho','pendente','2026-07-07',NULL,NULL),
(50,9992,9990,'PC-1036         ','CARRO PARA CURATIVO SIMPLES EM ACO INOX           ',20.0000,'PC','filho','pendente','2026-07-07',NULL,NULL),
(51,9992,9991,'PC-1037         ','CARRO PARA CURATIVO SIMPLES EM ACO INOX           ',20.0000,'PC','filho','pendente','2026-07-07',NULL,NULL),
(52,9992,9992,'S-0300          ','CARRO PARA CURATIVO SIMPLES EM ACO INOX           ',10.0000,'PC','filho','pendente','2026-07-07',NULL,NULL);
/*!40000 ALTER TABLE `ordens_fabricacao` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `requisicoes_materiais`
--

DROP TABLE IF EXISTS `requisicoes_materiais`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8mb4 */;
CREATE TABLE `requisicoes_materiais` (
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
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `requisicoes_materiais`
--

LOCK TABLES `requisicoes_materiais` WRITE;
/*!40000 ALTER TABLE `requisicoes_materiais` DISABLE KEYS */;
/*!40000 ALTER TABLE `requisicoes_materiais` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `serralheria_producao`
--

DROP TABLE IF EXISTS `serralheria_producao`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8mb4 */;
CREATE TABLE `serralheria_producao` (
  `id` int(11) NOT NULL AUTO_INCREMENT,
  `ordem_id` int(11) DEFAULT NULL,
  `lote` varchar(20) DEFAULT NULL,
  `produto` varchar(100) DEFAULT NULL,
  `usuario_id` int(11) DEFAULT NULL,
  `usuario_nome` varchar(50) DEFAULT NULL,
  `status` varchar(20) DEFAULT 'em_producao',
  `data_inicio` datetime DEFAULT NULL,
  `data_fim` datetime DEFAULT NULL,
  `setor` varchar(50) DEFAULT '',
  `of_numero` int(11) DEFAULT NULL,
  PRIMARY KEY (`id`)
) ENGINE=InnoDB AUTO_INCREMENT=5 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `serralheria_producao`
--

LOCK TABLES `serralheria_producao` WRITE;
/*!40000 ALTER TABLE `serralheria_producao` DISABLE KEYS */;
INSERT INTO `serralheria_producao` VALUES
(1,10002,'000361','PC-2710',217,'serra1','em_producao','2026-07-08 13:18:06',NULL,'CORTE',10002),
(2,10003,'000361','PC-2711',217,'serra1','finalizado','2026-07-08 13:18:06','2026-07-08 13:27:11','CORTE',10003),
(3,10005,'000361','PC-2713',217,'serra1','em_producao','2026-07-08 13:18:06',NULL,'CORTE',10005),
(4,10009,'000361','S-0020',217,'serra1','finalizado','2026-07-08 13:18:06','2026-07-08 13:27:11','CORTE',10009);
/*!40000 ALTER TABLE `serralheria_producao` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `serralheria_usuarios`
--

DROP TABLE IF EXISTS `serralheria_usuarios`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8mb4 */;
CREATE TABLE `serralheria_usuarios` (
  `id` int(11) NOT NULL AUTO_INCREMENT,
  `nome` varchar(50) NOT NULL,
  `setor` varchar(50) DEFAULT 'Serralheria',
  `ativo` tinyint(4) DEFAULT 1,
  PRIMARY KEY (`id`)
) ENGINE=InnoDB AUTO_INCREMENT=229 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `serralheria_usuarios`
--

LOCK TABLES `serralheria_usuarios` WRITE;
/*!40000 ALTER TABLE `serralheria_usuarios` DISABLE KEYS */;
INSERT INTO `serralheria_usuarios` VALUES
(219,'Gabriel','CORTE',1),
(220,'Erivaldo','SERRALHERIA',1),
(221,'Junior','CORTE',1),
(222,'Reverson','CORTE',1),
(223,'José','CORTE',1),
(224,'Juninho','CORTE',1),
(225,'Francisco','SOLDA',1),
(226,'Leonardo','SOLDA',1),
(227,'José Barbosa','DOBRA',1),
(228,'Jhonatas','DOBRA',1);
/*!40000 ALTER TABLE `serralheria_usuarios` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `usuarios`
--

DROP TABLE IF EXISTS `usuarios`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8mb4 */;
CREATE TABLE `usuarios` (
  `id` int(11) NOT NULL AUTO_INCREMENT,
  `usuario` varchar(50) NOT NULL,
  `nome` varchar(100) NOT NULL,
  `senha` varchar(255) NOT NULL,
  `role` enum('admin','gerente','diretor','pcp','almoxarifado','encarregado','operador') NOT NULL DEFAULT 'operador',
  `nome_departamento` varchar(100) DEFAULT NULL,
  `departamento_codigo` varchar(20) DEFAULT NULL,
  `ativo` tinyint(1) DEFAULT 1,
  `data_criacao` timestamp NOT NULL DEFAULT current_timestamp(),
  `ultimo_acesso` datetime DEFAULT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `usuario` (`usuario`)
) ENGINE=InnoDB AUTO_INCREMENT=8 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `usuarios`
--

LOCK TABLES `usuarios` WRITE;
/*!40000 ALTER TABLE `usuarios` DISABLE KEYS */;
INSERT INTO `usuarios` VALUES
(1,'admin','Administrador','scrypt:32768:8:1$MwSXGfo6Q2NHSzKe$d9037fc1fdec10830d1fce3e797b47671880459b78a418dc71d1d5b2378eb8c85f9e6bb9294fa8afcb4ca6c41f2aaab478e26cfdc1df61386e137a64934d6582','admin','Administracao','ADMINISTRACAO',1,'2026-07-01 17:37:28','2026-07-03 16:26:59'),
(2,'gerente','Gerente','scrypt:32768:8:1$QcumbazuijIc40hF$804d909033479c6fa27446fee6938ddac9bba669acd19b9b30f52fff7485da7f237d73dfa1eb90150f5bf906186018509fc1e67de0176f6924d99cf850286b3e','gerente','Geral','GER',1,'2026-07-02 11:14:31',NULL),
(3,'diretor','Diretor','scrypt:32768:8:1$xU3BuV8O91joMYjG$fb71b9d87c3a749a5893f017666972723a61737bd96f5d752a91657b13b4f6be447dd8c5cb75e99503dc2fe51e2232bc13cec618e99c7fe4a7d501aa1a0956f4','diretor','Diretoria','DIR',1,'2026-07-02 11:14:31',NULL),
(4,'pcp','PCP','scrypt:32768:8:1$e3ntKUZBhJa3pH1i$7a2441384f157a680f68aed785eaf5f3d82b48d4b96b75965d0454e8a85cd37b3fa83d89e650259ee9d66aa019cafa0d9088481363b250ead8dd7656662c5cd2','pcp','PCP','PCP',1,'2026-07-02 11:14:31',NULL),
(5,'almoxarifado','Almoxarife','scrypt:32768:8:1$amim9FpURPsmjx6x$cf0739b62546548546334ae5b01301a0309ad5fc599bf664bc33b9ce9793f8c49df6764386bc60be48de8a06640bdbf999441aba4ab38979c234e4e5029cd9a8','almoxarifado','Almoxarifado','ALM',1,'2026-07-02 11:14:32',NULL),
(6,'encarregado','Encarregado','scrypt:32768:8:1$GGRDvylH8AAraf3L$432c92f065570005c3f5fa0a9dcd1859a8a1cf7fc7e4d960d4efd9df326bcd3b983bb86555b27fbe0578ee84f1a8a11beed30d5baafbdf57e95b639c7caaf26f','encarregado','Producao','ENC',1,'2026-07-02 11:14:32',NULL),
(7,'operador','Operador','scrypt:32768:8:1$U0gSx2ASHvAnnOLj$f165e8fbee77ab2fd4ae1d71dba71251e3ca85ce29c90e115afc23ad545b5ebbd76f3858beef412ee4a6d076b8131ce64bf53abbc99a7278974d63595a5d0e2a','operador','Producao','OPE',1,'2026-07-02 11:14:32',NULL);
/*!40000 ALTER TABLE `usuarios` ENABLE KEYS */;
UNLOCK TABLES;
/*!40103 SET TIME_ZONE=@OLD_TIME_ZONE */;

/*!40101 SET SQL_MODE=@OLD_SQL_MODE */;
/*!40014 SET FOREIGN_KEY_CHECKS=@OLD_FOREIGN_KEY_CHECKS */;
/*!40014 SET UNIQUE_CHECKS=@OLD_UNIQUE_CHECKS */;
/*!40101 SET CHARACTER_SET_CLIENT=@OLD_CHARACTER_SET_CLIENT */;
/*!40101 SET CHARACTER_SET_RESULTS=@OLD_CHARACTER_SET_RESULTS */;
/*!40101 SET COLLATION_CONNECTION=@OLD_COLLATION_CONNECTION */;
/*!40111 SET SQL_NOTES=@OLD_SQL_NOTES */;

-- Dump completed on 2026-07-08 16:16:59
