-- MySQL dump 10.13  Distrib 26.10.0, for Win64 (x86_64)
--
-- Host: localhost    Database: fitmeal
-- ------------------------------------------------------
-- Server version	26.10.0

/*!40101 SET @OLD_CHARACTER_SET_CLIENT=@@CHARACTER_SET_CLIENT */;
/*!40101 SET @OLD_CHARACTER_SET_RESULTS=@@CHARACTER_SET_RESULTS */;
/*!40101 SET @OLD_COLLATION_CONNECTION=@@COLLATION_CONNECTION */;
/*!50503 SET NAMES utf8mb4 */;
/*!40103 SET @OLD_TIME_ZONE=@@TIME_ZONE */;
/*!40103 SET TIME_ZONE='+00:00' */;
/*!40014 SET @OLD_UNIQUE_CHECKS=@@UNIQUE_CHECKS, UNIQUE_CHECKS=0 */;
/*!40014 SET @OLD_FOREIGN_KEY_CHECKS=@@FOREIGN_KEY_CHECKS, FOREIGN_KEY_CHECKS=0 */;
/*!40101 SET @OLD_SQL_MODE=@@SQL_MODE, SQL_MODE='NO_AUTO_VALUE_ON_ZERO' */;
/*!40111 SET @OLD_SQL_NOTES=@@SQL_NOTES, SQL_NOTES=0 */;

--
-- Table structure for table `account_emailaddress`
--

DROP TABLE IF EXISTS `account_emailaddress`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `account_emailaddress` (
  `id` int NOT NULL AUTO_INCREMENT,
  `email` varchar(254) COLLATE utf8mb4_unicode_ci NOT NULL,
  `verified` tinyint(1) NOT NULL,
  `primary` tinyint(1) NOT NULL,
  `user_id` bigint NOT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `account_emailaddress_user_id_email_987c8728_uniq` (`user_id`,`email`),
  KEY `account_emailaddress_email_03be32b2` (`email`),
  CONSTRAINT `account_emailaddress_user_id_2c513194_fk_accounts_user_id` FOREIGN KEY (`user_id`) REFERENCES `accounts_user` (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `account_emailaddress`
--

LOCK TABLES `account_emailaddress` WRITE;
/*!40000 ALTER TABLE `account_emailaddress` DISABLE KEYS */;
/*!40000 ALTER TABLE `account_emailaddress` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `account_emailconfirmation`
--

DROP TABLE IF EXISTS `account_emailconfirmation`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `account_emailconfirmation` (
  `id` int NOT NULL AUTO_INCREMENT,
  `created` datetime(6) NOT NULL,
  `sent` datetime(6) DEFAULT NULL,
  `key` varchar(64) COLLATE utf8mb4_unicode_ci NOT NULL,
  `email_address_id` int NOT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `key` (`key`),
  KEY `account_emailconfirm_email_address_id_5b7f8c58_fk_account_e` (`email_address_id`),
  CONSTRAINT `account_emailconfirm_email_address_id_5b7f8c58_fk_account_e` FOREIGN KEY (`email_address_id`) REFERENCES `account_emailaddress` (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `account_emailconfirmation`
--

LOCK TABLES `account_emailconfirmation` WRITE;
/*!40000 ALTER TABLE `account_emailconfirmation` DISABLE KEYS */;
/*!40000 ALTER TABLE `account_emailconfirmation` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `accounts_customeraddress`
--

DROP TABLE IF EXISTS `accounts_customeraddress`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `accounts_customeraddress` (
  `id` bigint NOT NULL AUTO_INCREMENT,
  `label` varchar(50) COLLATE utf8mb4_unicode_ci NOT NULL,
  `address` varchar(250) COLLATE utf8mb4_unicode_ci NOT NULL,
  `district` varchar(100) COLLATE utf8mb4_unicode_ci NOT NULL,
  `city` varchar(100) COLLATE utf8mb4_unicode_ci NOT NULL,
  `is_default` tinyint(1) NOT NULL,
  `created_at` datetime(6) NOT NULL,
  `user_id` bigint NOT NULL,
  PRIMARY KEY (`id`),
  KEY `accounts_customeraddress_user_id_09d750f6_fk_accounts_user_id` (`user_id`),
  CONSTRAINT `accounts_customeraddress_user_id_09d750f6_fk_accounts_user_id` FOREIGN KEY (`user_id`) REFERENCES `accounts_user` (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `accounts_customeraddress`
--

LOCK TABLES `accounts_customeraddress` WRITE;
/*!40000 ALTER TABLE `accounts_customeraddress` DISABLE KEYS */;
/*!40000 ALTER TABLE `accounts_customeraddress` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `accounts_loginevent`
--

DROP TABLE IF EXISTS `accounts_loginevent`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `accounts_loginevent` (
  `id` bigint NOT NULL AUTO_INCREMENT,
  `login_identifier` varchar(254) COLLATE utf8mb4_unicode_ci NOT NULL,
  `ip_address` varchar(45) COLLATE utf8mb4_unicode_ci NOT NULL,
  `user_agent` varchar(255) COLLATE utf8mb4_unicode_ci NOT NULL,
  `outcome` varchar(10) COLLATE utf8mb4_unicode_ci NOT NULL,
  `details` varchar(120) COLLATE utf8mb4_unicode_ci NOT NULL,
  `created_at` datetime(6) NOT NULL,
  `user_id` bigint DEFAULT NULL,
  PRIMARY KEY (`id`),
  KEY `accounts_loginevent_user_id_0b0fdf50_fk_accounts_user_id` (`user_id`),
  KEY `accounts_loginevent_created_at_1da55333` (`created_at`),
  CONSTRAINT `accounts_loginevent_user_id_0b0fdf50_fk_accounts_user_id` FOREIGN KEY (`user_id`) REFERENCES `accounts_user` (`id`)
) ENGINE=InnoDB AUTO_INCREMENT=39 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `accounts_loginevent`
--

LOCK TABLES `accounts_loginevent` WRITE;
/*!40000 ALTER TABLE `accounts_loginevent` DISABLE KEYS */;
INSERT INTO `accounts_loginevent` VALUES (20,'toeicplus82@gmail.com','127.0.0.1','Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/157.0.0.0 Safari/537.36','success','Đăng nhập thành công','2026-11-17 11:45:04.779064',7),(21,'tansang123@gmail.com','127.0.0.1','Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/157.0.0.0 Safari/537.36','success','Đăng nhập thành công','2026-11-17 11:46:45.575350',8),(22,'toeicplus82@gmail.com','127.0.0.1','Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/157.0.0.0 Safari/537.36','success','Đăng nhập thành công','2026-11-17 14:00:30.706686',7),(23,'gptpluschung123@gmail.com','127.0.0.1','Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/157.0.0.0 Safari/537.36','success','Đăng nhập thành công','2026-11-17 16:57:34.064905',5),(24,'toeicplus82@gmail.com','127.0.0.1','Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/157.0.0.0 Safari/537.36','success','Đăng nhập thành công','2026-11-17 16:58:36.014647',7),(25,'psang531@gmail.com','127.0.0.1','Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/157.0.0.0 Safari/537.36','success','Đăng nhập thành công','2026-11-17 17:12:14.951773',1),(26,'customer-983119cf86b242689cc6fe1068f80855','127.0.0.1','Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/157.0.0.0 Safari/537.36','failure','Sai mật khẩu hoặc tài khoản','2026-11-18 01:39:41.089164',NULL),(27,'customer-983119cf86b242689cc6fe1068f80855','127.0.0.1','Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/157.0.0.0 Safari/537.36','failure','Sai mật khẩu hoặc tài khoản','2026-11-18 01:40:11.727148',NULL),(28,'customer-983119cf86b242689cc6fe1068f80855','127.0.0.1','Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/157.0.0.0 Safari/537.36','failure','Sai mật khẩu hoặc tài khoản','2026-11-18 01:40:48.245952',NULL),(29,'customer-983119cf86b242689cc6fe1068f80855','127.0.0.1','Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/157.0.0.0 Safari/537.36','failure','Sai mật khẩu hoặc tài khoản','2026-11-18 01:41:01.093752',NULL),(30,'toeicplus82@gmail.com','127.0.0.1','Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/157.0.0.0 Safari/537.36','success','Đăng nhập thành công','2026-11-18 01:41:31.506006',7),(31,'customer-983119cf86b242689cc6fe1068f80855','127.0.0.1','Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/157.0.0.0 Safari/537.36','failure','Sai mật khẩu hoặc tài khoản','2026-11-18 01:42:14.029789',NULL),(32,'customer-983119cf86b242689cc6fe1068f80855','127.0.0.1','Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/157.0.0.0 Safari/537.36','failure','Sai mật khẩu hoặc tài khoản','2026-11-18 01:43:06.963018',NULL),(33,'tansang1234@gmail.com','127.0.0.1','Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/157.0.0.0 Safari/537.36','success','Đăng nhập thành công','2026-11-18 01:44:10.817030',9),(34,'tansang1234@gmail.com','127.0.0.1','Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/157.0.0.0 Safari/537.36','success','Đăng nhập thành công','2026-11-18 01:47:00.453375',9),(35,'toeicplus82@gmail.com','127.0.0.1','Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/157.0.0.0 Safari/537.36','success','Đăng nhập thành công','2026-11-18 09:25:57.209879',7),(36,'employee-13f395387d2c41c8a755dfb7294dfb92','127.0.0.1','Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/157.0.0.0 Safari/537.36','failure','Sai mật khẩu hoặc tài khoản','2026-11-18 17:34:18.387649',NULL),(37,'employee-13f395387d2c41c8a755dfb7294dfb92','127.0.0.1','Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/157.0.0.0 Safari/537.36','failure','Sai mật khẩu hoặc tài khoản','2026-11-18 17:34:31.956906',NULL),(38,'gptpluschung123@gmail.com','127.0.0.1','Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/157.0.0.0 Safari/537.36','success','Đăng nhập thành công','2026-11-18 17:35:17.724779',5);
/*!40000 ALTER TABLE `accounts_loginevent` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `accounts_loginthrottle`
--

DROP TABLE IF EXISTS `accounts_loginthrottle`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `accounts_loginthrottle` (
  `id` bigint NOT NULL AUTO_INCREMENT,
  `ip_address` varchar(45) COLLATE utf8mb4_unicode_ci NOT NULL,
  `failure_count` smallint unsigned NOT NULL,
  `window_started_at` datetime(6) NOT NULL,
  `blocked_until` datetime(6) DEFAULT NULL,
  `updated_at` datetime(6) NOT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `ip_address` (`ip_address`),
  CONSTRAINT `accounts_loginthrottle_chk_1` CHECK ((`failure_count` >= 0))
) ENGINE=InnoDB AUTO_INCREMENT=5 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `accounts_loginthrottle`
--

LOCK TABLES `accounts_loginthrottle` WRITE;
/*!40000 ALTER TABLE `accounts_loginthrottle` DISABLE KEYS */;
/*!40000 ALTER TABLE `accounts_loginthrottle` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `accounts_orderreview`
--

DROP TABLE IF EXISTS `accounts_orderreview`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `accounts_orderreview` (
  `id` bigint NOT NULL AUTO_INCREMENT,
  `rating` smallint unsigned NOT NULL,
  `comment` longtext COLLATE utf8mb4_unicode_ci NOT NULL,
  `created_at` datetime(6) NOT NULL,
  `updated_at` datetime(6) NOT NULL,
  `order_id` bigint NOT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `order_id` (`order_id`),
  CONSTRAINT `accounts_orderreview_order_id_26105c86_fk_orders_order_id` FOREIGN KEY (`order_id`) REFERENCES `orders_order` (`id`),
  CONSTRAINT `accounts_orderreview_chk_1` CHECK ((`rating` >= 0))
) ENGINE=InnoDB AUTO_INCREMENT=3 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `accounts_orderreview`
--

LOCK TABLES `accounts_orderreview` WRITE;
/*!40000 ALTER TABLE `accounts_orderreview` DISABLE KEYS */;
/*!40000 ALTER TABLE `accounts_orderreview` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `accounts_pendingemailchange`
--

DROP TABLE IF EXISTS `accounts_pendingemailchange`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `accounts_pendingemailchange` (
  `id` bigint NOT NULL AUTO_INCREMENT,
  `email` varchar(254) COLLATE utf8mb4_unicode_ci NOT NULL,
  `token` char(32) COLLATE utf8mb4_unicode_ci NOT NULL,
  `created_at` datetime(6) NOT NULL,
  `expires_at` datetime(6) NOT NULL,
  `user_id` bigint NOT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `token` (`token`),
  UNIQUE KEY `user_id` (`user_id`),
  CONSTRAINT `accounts_pendingemailchange_user_id_dc2cd48e_fk_accounts_user_id` FOREIGN KEY (`user_id`) REFERENCES `accounts_user` (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `accounts_pendingemailchange`
--

LOCK TABLES `accounts_pendingemailchange` WRITE;
/*!40000 ALTER TABLE `accounts_pendingemailchange` DISABLE KEYS */;
/*!40000 ALTER TABLE `accounts_pendingemailchange` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `accounts_pointstransaction`
--

DROP TABLE IF EXISTS `accounts_pointstransaction`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `accounts_pointstransaction` (
  `id` bigint NOT NULL AUTO_INCREMENT,
  `kind` varchar(12) COLLATE utf8mb4_unicode_ci NOT NULL,
  `points` int NOT NULL,
  `description` varchar(200) COLLATE utf8mb4_unicode_ci NOT NULL,
  `created_at` datetime(6) NOT NULL,
  `order_id` bigint DEFAULT NULL,
  `user_id` bigint NOT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `accounts_unique_order_points_kind` (`order_id`,`kind`),
  KEY `accounts_pointstransaction_user_id_0b869d9c_fk_accounts_user_id` (`user_id`),
  CONSTRAINT `accounts_pointstransaction_order_id_c46628f0_fk_orders_order_id` FOREIGN KEY (`order_id`) REFERENCES `orders_order` (`id`),
  CONSTRAINT `accounts_pointstransaction_user_id_0b869d9c_fk_accounts_user_id` FOREIGN KEY (`user_id`) REFERENCES `accounts_user` (`id`)
) ENGINE=InnoDB AUTO_INCREMENT=19 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `accounts_pointstransaction`
--

LOCK TABLES `accounts_pointstransaction` WRITE;
/*!40000 ALTER TABLE `accounts_pointstransaction` DISABLE KEYS */;
INSERT INTO `accounts_pointstransaction` VALUES (1,'earned',20,'Tích điểm đơn FM-2026-860E24F1','2026-11-15 16:58:12.055568',NULL,6),(2,'earned',80,'Tích điểm đơn FM-2026-2CDA509F','2026-11-15 17:16:50.038779',NULL,6),(3,'earned',340,'Tích điểm đơn FM-2026-38DDB2B0','2026-11-15 17:19:27.886101',NULL,6),(4,'earned',20,'Tích điểm đơn FM-2026-4EF2528E','2026-11-15 17:57:58.858902',NULL,6),(5,'earned',200,'Tích điểm đơn FM-2026-DD12A8DE','2026-11-16 05:19:44.339638',NULL,6),(6,'earned',120,'Tích điểm đơn FM-2026-38D28837','2026-11-16 07:53:47.180226',NULL,6),(7,'earned',20,'Tích điểm đơn FM-2026-7C08E2AE','2026-11-16 08:00:10.185891',NULL,6),(8,'earned',10,'Tích điểm đơn FM-2026-E9C313D9','2026-11-16 08:05:01.680771',NULL,6),(9,'earned',20,'Tích điểm đơn FM-2026-847BE6F7','2026-11-16 08:05:40.561463',NULL,6),(10,'earned',20,'Tích điểm đơn FM-2026-3724CF3D','2026-11-16 08:28:35.545682',NULL,6),(11,'earned',200,'Tích điểm đơn FM-2026-18F0145D','2026-11-16 15:02:57.295227',NULL,6),(12,'earned',2800,'Tích điểm đơn FM-2026-3CF65AD2','2026-11-16 15:08:18.593092',NULL,6),(13,'earned',200,'Tích điểm đơn FM-2026-D2F4C286','2026-11-16 16:51:31.295014',NULL,6),(14,'earned',10,'Tích điểm đơn FM-2026-3CD22D5E','2026-11-16 17:04:23.195853',NULL,6),(15,'earned',1800,'Tích điểm đơn FM-2026-FF9992D6','2026-11-16 17:09:09.471172',NULL,6),(16,'earned',10,'Tích điểm đơn FM-2026-279EEBC4','2026-11-17 09:35:02.712018',NULL,6),(17,'earned',70,'Tích điểm đơn FM-2026-27117A39','2026-11-17 16:59:19.847275',59,8),(18,'earned',40,'Tích điểm đơn FM-2026-B2F7741A','2026-11-18 09:26:26.797199',64,9);
/*!40000 ALTER TABLE `accounts_pointstransaction` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `accounts_securitypolicy`
--

DROP TABLE IF EXISTS `accounts_securitypolicy`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `accounts_securitypolicy` (
  `id` bigint NOT NULL AUTO_INCREMENT,
  `require_admin_2fa` tinyint(1) NOT NULL,
  `require_manager_2fa` tinyint(1) NOT NULL,
  `updated_at` datetime(6) NOT NULL,
  `updated_by_id` bigint DEFAULT NULL,
  PRIMARY KEY (`id`),
  KEY `accounts_securitypol_updated_by_id_fa6320a3_fk_accounts_` (`updated_by_id`),
  CONSTRAINT `accounts_securitypol_updated_by_id_fa6320a3_fk_accounts_` FOREIGN KEY (`updated_by_id`) REFERENCES `accounts_user` (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `accounts_securitypolicy`
--

LOCK TABLES `accounts_securitypolicy` WRITE;
/*!40000 ALTER TABLE `accounts_securitypolicy` DISABLE KEYS */;
/*!40000 ALTER TABLE `accounts_securitypolicy` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `accounts_user`
--

DROP TABLE IF EXISTS `accounts_user`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `accounts_user` (
  `id` bigint NOT NULL AUTO_INCREMENT,
  `password` varchar(128) COLLATE utf8mb4_unicode_ci NOT NULL,
  `last_login` datetime(6) DEFAULT NULL,
  `is_superuser` tinyint(1) NOT NULL,
  `username` varchar(150) COLLATE utf8mb4_unicode_ci NOT NULL,
  `first_name` varchar(150) COLLATE utf8mb4_unicode_ci NOT NULL,
  `last_name` varchar(150) COLLATE utf8mb4_unicode_ci NOT NULL,
  `email` varchar(254) COLLATE utf8mb4_unicode_ci NOT NULL,
  `is_staff` tinyint(1) NOT NULL,
  `is_active` tinyint(1) NOT NULL,
  `date_joined` datetime(6) NOT NULL,
  `phone` varchar(15) COLLATE utf8mb4_unicode_ci NOT NULL,
  `address` varchar(250) COLLATE utf8mb4_unicode_ci NOT NULL,
  `avatar` varchar(100) COLLATE utf8mb4_unicode_ci NOT NULL,
  `birth_date` date DEFAULT NULL,
  `gender` varchar(12) COLLATE utf8mb4_unicode_ci NOT NULL,
  `phone_verified` tinyint(1) NOT NULL,
  `must_change_password` tinyint(1) NOT NULL,
  `cccd` varchar(12) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `staff_role` varchar(12) COLLATE utf8mb4_unicode_ci NOT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `username` (`username`),
  UNIQUE KEY `cccd` (`cccd`)
) ENGINE=InnoDB AUTO_INCREMENT=10 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `accounts_user`
--

LOCK TABLES `accounts_user` WRITE;
/*!40000 ALTER TABLE `accounts_user` DISABLE KEYS */;
INSERT INTO `accounts_user` VALUES (1,'pbkdf2_sha256$1000000$tCTIBfOGSbjy9WA1QH59Jg$YWkETE328SWk7KXwHbYvK5qzAdnMRhr3wYIy+YAixIc=','2026-11-17 17:12:14.942491',1,'sangazad','','','psang531@gmail.com',1,1,'2026-11-15 12:02:18.301426','','','',NULL,'unspecified',0,0,NULL,'admin'),(5,'pbkdf2_sha256$1000000$3qQEuAn6NQrKIjhXJNpm2T$euOOr1hW4ljYg3p1Y7i9GW7OLRnTIZWb6wrfpuxDncQ=','2026-11-18 17:35:17.716438',0,'employee-13f395387d2c41c8a755dfb7294dfb92','Lưu','Nguyễn Hồng Phúc','gptpluschung123@gmail.com',1,1,'2026-11-15 15:58:26.563487','0345633123','','',NULL,'unspecified',0,0,'051205011337','sales'),(7,'pbkdf2_sha256$1000000$VnJ6hU234G03aGV1kkOnZG$bucLbTwNMPpclw7enyHoEetQOoHhS494+cjv/6Aau+c=','2026-11-18 09:25:57.201285',0,'employee-21ba36ee516942f6b10dec0512e7eaf7','Lê','Chí Thắng','toeicplus82@gmail.com',1,1,'2026-11-15 16:52:41.866514','0357038179','','',NULL,'unspecified',0,0,NULL,'manager'),(8,'pbkdf2_sha256$1000000$d1hMs1WGe8Mch3wdToFbZP$aXN1ycBmIxEghGjD4+mqooeZQmsgu8dAeAq/Zs/1EC4=','2026-11-17 11:46:45.570405',0,'customer-983119cf86b242689cc6fe1068f80855','PHUNG','Sang','tansang13@gmail.com',0,1,'2026-11-17 11:46:45.326297','0908388667','','',NULL,'unspecified',0,0,NULL,''),(9,'pbkdf2_sha256$1000000$09LHGuSIIgkGjjrhTRHa3i$mBlgXNuOL3o1o5PQ9byXpu4ldphkm0qByEUkEjJei6Q=','2026-11-18 01:47:00.449554',0,'customer-3c89c1ec23314095bfa7a816646967fa','PHUNG','Sang','tansang1234@gmail.com',0,1,'2026-11-18 01:44:10.550691','0357038177','','',NULL,'unspecified',0,0,NULL,'');
/*!40000 ALTER TABLE `accounts_user` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `accounts_user_groups`
--

DROP TABLE IF EXISTS `accounts_user_groups`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `accounts_user_groups` (
  `id` bigint NOT NULL AUTO_INCREMENT,
  `user_id` bigint NOT NULL,
  `group_id` int NOT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `accounts_user_groups_user_id_group_id_59c0b32f_uniq` (`user_id`,`group_id`),
  KEY `accounts_user_groups_group_id_bd11a704_fk_auth_group_id` (`group_id`),
  CONSTRAINT `accounts_user_groups_group_id_bd11a704_fk_auth_group_id` FOREIGN KEY (`group_id`) REFERENCES `auth_group` (`id`),
  CONSTRAINT `accounts_user_groups_user_id_52b62117_fk_accounts_user_id` FOREIGN KEY (`user_id`) REFERENCES `accounts_user` (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `accounts_user_groups`
--

LOCK TABLES `accounts_user_groups` WRITE;
/*!40000 ALTER TABLE `accounts_user_groups` DISABLE KEYS */;
/*!40000 ALTER TABLE `accounts_user_groups` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `accounts_user_user_permissions`
--

DROP TABLE IF EXISTS `accounts_user_user_permissions`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `accounts_user_user_permissions` (
  `id` bigint NOT NULL AUTO_INCREMENT,
  `user_id` bigint NOT NULL,
  `permission_id` int NOT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `accounts_user_user_permi_user_id_permission_id_2ab516c2_uniq` (`user_id`,`permission_id`),
  KEY `accounts_user_user_p_permission_id_113bb443_fk_auth_perm` (`permission_id`),
  CONSTRAINT `accounts_user_user_p_permission_id_113bb443_fk_auth_perm` FOREIGN KEY (`permission_id`) REFERENCES `auth_permission` (`id`),
  CONSTRAINT `accounts_user_user_p_user_id_e4f0a161_fk_accounts_` FOREIGN KEY (`user_id`) REFERENCES `accounts_user` (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `accounts_user_user_permissions`
--

LOCK TABLES `accounts_user_user_permissions` WRITE;
/*!40000 ALTER TABLE `accounts_user_user_permissions` DISABLE KEYS */;
/*!40000 ALTER TABLE `accounts_user_user_permissions` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `auth_group`
--

DROP TABLE IF EXISTS `auth_group`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `auth_group` (
  `id` int NOT NULL AUTO_INCREMENT,
  `name` varchar(150) COLLATE utf8mb4_unicode_ci NOT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `name` (`name`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `auth_group`
--

LOCK TABLES `auth_group` WRITE;
/*!40000 ALTER TABLE `auth_group` DISABLE KEYS */;
/*!40000 ALTER TABLE `auth_group` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `auth_group_permissions`
--

DROP TABLE IF EXISTS `auth_group_permissions`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `auth_group_permissions` (
  `id` bigint NOT NULL AUTO_INCREMENT,
  `group_id` int NOT NULL,
  `permission_id` int NOT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `auth_group_permissions_group_id_permission_id_0cd325b0_uniq` (`group_id`,`permission_id`),
  KEY `auth_group_permissio_permission_id_84c5c92e_fk_auth_perm` (`permission_id`),
  CONSTRAINT `auth_group_permissio_permission_id_84c5c92e_fk_auth_perm` FOREIGN KEY (`permission_id`) REFERENCES `auth_permission` (`id`),
  CONSTRAINT `auth_group_permissions_group_id_b120cbf9_fk_auth_group_id` FOREIGN KEY (`group_id`) REFERENCES `auth_group` (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `auth_group_permissions`
--

LOCK TABLES `auth_group_permissions` WRITE;
/*!40000 ALTER TABLE `auth_group_permissions` DISABLE KEYS */;
/*!40000 ALTER TABLE `auth_group_permissions` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `auth_permission`
--

DROP TABLE IF EXISTS `auth_permission`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `auth_permission` (
  `id` int NOT NULL AUTO_INCREMENT,
  `name` varchar(255) COLLATE utf8mb4_unicode_ci NOT NULL,
  `content_type_id` int NOT NULL,
  `codename` varchar(100) COLLATE utf8mb4_unicode_ci NOT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `auth_permission_content_type_id_codename_01ab375a_uniq` (`content_type_id`,`codename`),
  CONSTRAINT `auth_permission_content_type_id_2f476e4b_fk_django_co` FOREIGN KEY (`content_type_id`) REFERENCES `django_content_type` (`id`)
) ENGINE=InnoDB AUTO_INCREMENT=117 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `auth_permission`
--

LOCK TABLES `auth_permission` WRITE;
/*!40000 ALTER TABLE `auth_permission` DISABLE KEYS */;
INSERT INTO `auth_permission` VALUES (1,'Can add log entry',1,'add_logentry'),(2,'Can change log entry',1,'change_logentry'),(3,'Can delete log entry',1,'delete_logentry'),(4,'Can view log entry',1,'view_logentry'),(5,'Can add permission',2,'add_permission'),(6,'Can change permission',2,'change_permission'),(7,'Can delete permission',2,'delete_permission'),(8,'Can view permission',2,'view_permission'),(9,'Can add group',3,'add_group'),(10,'Can change group',3,'change_group'),(11,'Can delete group',3,'delete_group'),(12,'Can view group',3,'view_group'),(13,'Can add content type',4,'add_contenttype'),(14,'Can change content type',4,'change_contenttype'),(15,'Can delete content type',4,'delete_contenttype'),(16,'Can view content type',4,'view_contenttype'),(17,'Can add session',5,'add_session'),(18,'Can change session',5,'change_session'),(19,'Can delete session',5,'delete_session'),(20,'Can view session',5,'view_session'),(21,'Can add email address',6,'add_emailaddress'),(22,'Can change email address',6,'change_emailaddress'),(23,'Can delete email address',6,'delete_emailaddress'),(24,'Can view email address',6,'view_emailaddress'),(25,'Can add email confirmation',7,'add_emailconfirmation'),(26,'Can change email confirmation',7,'change_emailconfirmation'),(27,'Can delete email confirmation',7,'delete_emailconfirmation'),(28,'Can view email confirmation',7,'view_emailconfirmation'),(29,'Can add social application',8,'add_socialapp'),(30,'Can change social application',8,'change_socialapp'),(31,'Can delete social application',8,'delete_socialapp'),(32,'Can view social application',8,'view_socialapp'),(33,'Can add social account',9,'add_socialaccount'),(34,'Can change social account',9,'change_socialaccount'),(35,'Can delete social account',9,'delete_socialaccount'),(36,'Can view social account',9,'view_socialaccount'),(37,'Can add social application token',10,'add_socialtoken'),(38,'Can change social application token',10,'change_socialtoken'),(39,'Can delete social application token',10,'delete_socialtoken'),(40,'Can view social application token',10,'view_socialtoken'),(41,'Can add Người dùng',11,'add_user'),(42,'Can change Người dùng',11,'change_user'),(43,'Can delete Người dùng',11,'delete_user'),(44,'Can view Người dùng',11,'view_user'),(45,'Can add Địa chỉ khách hàng',12,'add_customeraddress'),(46,'Can change Địa chỉ khách hàng',12,'change_customeraddress'),(47,'Can delete Địa chỉ khách hàng',12,'delete_customeraddress'),(48,'Can view Địa chỉ khách hàng',12,'view_customeraddress'),(49,'Can add Giao dịch điểm',13,'add_pointstransaction'),(50,'Can change Giao dịch điểm',13,'change_pointstransaction'),(51,'Can delete Giao dịch điểm',13,'delete_pointstransaction'),(52,'Can view Giao dịch điểm',13,'view_pointstransaction'),(53,'Can add Đánh giá đơn hàng',14,'add_orderreview'),(54,'Can change Đánh giá đơn hàng',14,'change_orderreview'),(55,'Can delete Đánh giá đơn hàng',14,'delete_orderreview'),(56,'Can view Đánh giá đơn hàng',14,'view_orderreview'),(57,'Can add Yêu cầu đổi email',15,'add_pendingemailchange'),(58,'Can change Yêu cầu đổi email',15,'change_pendingemailchange'),(59,'Can delete Yêu cầu đổi email',15,'delete_pendingemailchange'),(60,'Can view Yêu cầu đổi email',15,'view_pendingemailchange'),(61,'Can add Sản phẩm',16,'add_product'),(62,'Can change Sản phẩm',16,'change_product'),(63,'Can delete Sản phẩm',16,'delete_product'),(64,'Can view Sản phẩm',16,'view_product'),(65,'Can add Đơn hàng',17,'add_order'),(66,'Can change Đơn hàng',17,'change_order'),(67,'Can delete Đơn hàng',17,'delete_order'),(68,'Can view Đơn hàng',17,'view_order'),(69,'Can add Món trong đơn',18,'add_orderitem'),(70,'Can change Món trong đơn',18,'change_orderitem'),(71,'Can delete Món trong đơn',18,'delete_orderitem'),(72,'Can view Món trong đơn',18,'view_orderitem'),(73,'Can add Nhật ký sản phẩm',19,'add_productactivity'),(74,'Can change Nhật ký sản phẩm',19,'change_productactivity'),(75,'Can delete Nhật ký sản phẩm',19,'delete_productactivity'),(76,'Can view Nhật ký sản phẩm',19,'view_productactivity'),(77,'Can add Yêu cầu hủy đơn',20,'add_ordercancellationrequest'),(78,'Can change Yêu cầu hủy đơn',20,'change_ordercancellationrequest'),(79,'Can delete Yêu cầu hủy đơn',20,'delete_ordercancellationrequest'),(80,'Can view Yêu cầu hủy đơn',20,'view_ordercancellationrequest'),(81,'Can add Khiếu nại giao hàng',21,'add_deliveryissue'),(82,'Can change Khiếu nại giao hàng',21,'change_deliveryissue'),(83,'Can delete Khiếu nại giao hàng',21,'delete_deliveryissue'),(84,'Can view Khiếu nại giao hàng',21,'view_deliveryissue'),(85,'Can add authenticator',22,'add_authenticator'),(86,'Can change authenticator',22,'change_authenticator'),(87,'Can delete authenticator',22,'delete_authenticator'),(88,'Can view authenticator',22,'view_authenticator'),(89,'Can add Giới hạn đăng nhập theo IP',23,'add_loginthrottle'),(90,'Can change Giới hạn đăng nhập theo IP',23,'change_loginthrottle'),(91,'Can delete Giới hạn đăng nhập theo IP',23,'delete_loginthrottle'),(92,'Can view Giới hạn đăng nhập theo IP',23,'view_loginthrottle'),(93,'Can add Sự kiện đăng nhập',24,'add_loginevent'),(94,'Can change Sự kiện đăng nhập',24,'change_loginevent'),(95,'Can delete Sự kiện đăng nhập',24,'delete_loginevent'),(96,'Can view Sự kiện đăng nhập',24,'view_loginevent'),(97,'Can add Chính sách bảo mật',25,'add_securitypolicy'),(98,'Can change Chính sách bảo mật',25,'change_securitypolicy'),(99,'Can delete Chính sách bảo mật',25,'delete_securitypolicy'),(100,'Can view Chính sách bảo mật',25,'view_securitypolicy'),(101,'Can add Giao dịch thanh toán',26,'add_paymenttransaction'),(102,'Can change Giao dịch thanh toán',26,'change_paymenttransaction'),(103,'Can delete Giao dịch thanh toán',26,'delete_paymenttransaction'),(104,'Can view Giao dịch thanh toán',26,'view_paymenttransaction'),(105,'Can add Yêu cầu bổ sung tồn kho',27,'add_inventoryrestockrequest'),(106,'Can change Yêu cầu bổ sung tồn kho',27,'change_inventoryrestockrequest'),(107,'Can delete Yêu cầu bổ sung tồn kho',27,'delete_inventoryrestockrequest'),(108,'Can view Yêu cầu bổ sung tồn kho',27,'view_inventoryrestockrequest'),(109,'Can add Yêu cầu khiếu nại / đổi trả',28,'add_ordercarerequest'),(110,'Can change Yêu cầu khiếu nại / đổi trả',28,'change_ordercarerequest'),(111,'Can delete Yêu cầu khiếu nại / đổi trả',28,'delete_ordercarerequest'),(112,'Can view Yêu cầu khiếu nại / đổi trả',28,'view_ordercarerequest'),(113,'Can add Nhật ký truy cập dữ liệu đơn hàng',29,'add_orderpiiaccesslog'),(114,'Can change Nhật ký truy cập dữ liệu đơn hàng',29,'change_orderpiiaccesslog'),(115,'Can delete Nhật ký truy cập dữ liệu đơn hàng',29,'delete_orderpiiaccesslog'),(116,'Can view Nhật ký truy cập dữ liệu đơn hàng',29,'view_orderpiiaccesslog');
/*!40000 ALTER TABLE `auth_permission` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `django_admin_log`
--

DROP TABLE IF EXISTS `django_admin_log`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `django_admin_log` (
  `id` int NOT NULL AUTO_INCREMENT,
  `action_time` datetime(6) NOT NULL,
  `object_id` longtext COLLATE utf8mb4_unicode_ci,
  `object_repr` varchar(200) COLLATE utf8mb4_unicode_ci NOT NULL,
  `action_flag` smallint unsigned NOT NULL,
  `change_message` longtext COLLATE utf8mb4_unicode_ci NOT NULL,
  `content_type_id` int DEFAULT NULL,
  `user_id` bigint NOT NULL,
  PRIMARY KEY (`id`),
  KEY `django_admin_log_content_type_id_c4bce8eb_fk_django_co` (`content_type_id`),
  KEY `django_admin_log_user_id_c564eba6_fk_accounts_user_id` (`user_id`),
  CONSTRAINT `django_admin_log_content_type_id_c4bce8eb_fk_django_co` FOREIGN KEY (`content_type_id`) REFERENCES `django_content_type` (`id`),
  CONSTRAINT `django_admin_log_user_id_c564eba6_fk_accounts_user_id` FOREIGN KEY (`user_id`) REFERENCES `accounts_user` (`id`),
  CONSTRAINT `django_admin_log_chk_1` CHECK ((`action_flag` >= 0))
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `django_admin_log`
--

LOCK TABLES `django_admin_log` WRITE;
/*!40000 ALTER TABLE `django_admin_log` DISABLE KEYS */;
/*!40000 ALTER TABLE `django_admin_log` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `django_content_type`
--

DROP TABLE IF EXISTS `django_content_type`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `django_content_type` (
  `id` int NOT NULL AUTO_INCREMENT,
  `app_label` varchar(100) COLLATE utf8mb4_unicode_ci NOT NULL,
  `model` varchar(100) COLLATE utf8mb4_unicode_ci NOT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `django_content_type_app_label_model_76bd3d3b_uniq` (`app_label`,`model`)
) ENGINE=InnoDB AUTO_INCREMENT=30 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `django_content_type`
--

LOCK TABLES `django_content_type` WRITE;
/*!40000 ALTER TABLE `django_content_type` DISABLE KEYS */;
INSERT INTO `django_content_type` VALUES (6,'account','emailaddress'),(7,'account','emailconfirmation'),(12,'accounts','customeraddress'),(24,'accounts','loginevent'),(23,'accounts','loginthrottle'),(14,'accounts','orderreview'),(15,'accounts','pendingemailchange'),(13,'accounts','pointstransaction'),(25,'accounts','securitypolicy'),(11,'accounts','user'),(1,'admin','logentry'),(3,'auth','group'),(2,'auth','permission'),(4,'contenttypes','contenttype'),(22,'mfa','authenticator'),(21,'orders','deliveryissue'),(17,'orders','order'),(20,'orders','ordercancellationrequest'),(28,'orders','ordercarerequest'),(18,'orders','orderitem'),(29,'orders','orderpiiaccesslog'),(26,'payments','paymenttransaction'),(27,'products','inventoryrestockrequest'),(16,'products','product'),(19,'products','productactivity'),(5,'sessions','session'),(9,'socialaccount','socialaccount'),(8,'socialaccount','socialapp'),(10,'socialaccount','socialtoken');
/*!40000 ALTER TABLE `django_content_type` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `django_migrations`
--

DROP TABLE IF EXISTS `django_migrations`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `django_migrations` (
  `id` bigint NOT NULL AUTO_INCREMENT,
  `app` varchar(255) COLLATE utf8mb4_unicode_ci NOT NULL,
  `name` varchar(255) COLLATE utf8mb4_unicode_ci NOT NULL,
  `applied` datetime(6) NOT NULL,
  PRIMARY KEY (`id`)
) ENGINE=InnoDB AUTO_INCREMENT=69 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `django_migrations`
--

LOCK TABLES `django_migrations` WRITE;
/*!40000 ALTER TABLE `django_migrations` DISABLE KEYS */;
INSERT INTO `django_migrations` VALUES (1,'contenttypes','0001_initial','2026-11-14 04:15:17.257566'),(2,'contenttypes','0002_remove_content_type_name','2026-11-14 04:15:17.382942'),(3,'auth','0001_initial','2026-11-14 04:15:17.652453'),(4,'auth','0002_alter_permission_name_max_length','2026-11-14 04:15:17.724111'),(5,'auth','0003_alter_user_email_max_length','2026-11-14 04:15:17.728739'),(6,'auth','0004_alter_user_username_opts','2026-11-14 04:15:17.734000'),(7,'auth','0005_alter_user_last_login_null','2026-11-14 04:15:17.739553'),(8,'auth','0006_require_contenttypes_0002','2026-11-14 04:15:17.741963'),(9,'auth','0007_alter_validators_add_error_messages','2026-11-14 04:15:17.746808'),(10,'auth','0008_alter_user_username_max_length','2026-11-14 04:15:17.753538'),(11,'auth','0009_alter_user_last_name_max_length','2026-11-14 04:15:17.759207'),(12,'auth','0010_alter_group_name_max_length','2026-11-14 04:15:17.772473'),(13,'auth','0011_update_proxy_permissions','2026-11-14 04:15:17.777990'),(14,'auth','0012_alter_user_first_name_max_length','2026-11-14 04:15:17.782964'),(15,'accounts','0001_initial','2026-11-14 04:15:18.103120'),(16,'admin','0001_initial','2026-11-14 04:15:18.228885'),(17,'admin','0002_logentry_remove_auto_add','2026-11-14 04:15:18.234749'),(18,'admin','0003_logentry_add_action_flag_choices','2026-11-14 04:15:18.240517'),(19,'products','0001_initial','2026-11-14 04:15:18.295320'),(20,'orders','0001_initial','2026-11-14 04:15:18.548963'),(21,'orders','0002_alter_order_subtotal_alter_order_total','2026-11-14 04:15:18.688653'),(22,'sessions','0001_initial','2026-11-14 04:15:18.715678'),(23,'accounts','0002_user_address','2026-11-14 04:42:02.275707'),(24,'account','0001_initial','2026-11-14 07:24:35.497260'),(25,'account','0002_email_max_length','2026-11-14 07:24:35.519126'),(26,'account','0003_alter_emailaddress_create_unique_verified_email','2026-11-14 07:24:35.569296'),(27,'account','0004_alter_emailaddress_drop_unique_email','2026-11-14 07:24:35.623012'),(28,'account','0005_emailaddress_idx_upper_email','2026-11-14 07:24:35.662694'),(29,'account','0006_emailaddress_lower','2026-11-14 07:24:35.687998'),(30,'account','0007_emailaddress_idx_email','2026-11-14 07:24:35.747236'),(31,'account','0008_emailaddress_unique_primary_email_fixup','2026-11-14 07:24:35.770323'),(32,'account','0009_emailaddress_unique_primary_email','2026-11-14 07:24:35.780622'),(33,'socialaccount','0001_initial','2026-11-14 07:24:36.095695'),(34,'socialaccount','0002_token_max_lengths','2026-11-14 07:24:36.135515'),(35,'socialaccount','0003_extra_data_default_dict','2026-11-14 07:24:36.144599'),(36,'socialaccount','0004_app_provider_id_settings','2026-11-14 07:24:36.364949'),(37,'socialaccount','0005_socialtoken_nullable_app','2026-11-14 07:24:36.501864'),(38,'socialaccount','0006_alter_socialaccount_extra_data','2026-11-14 07:24:36.572780'),(39,'accounts','0003_user_avatar_user_birth_date_user_gender_and_more','2026-11-15 05:48:06.454692'),(40,'accounts','0004_orderreview','2026-11-15 08:09:50.651708'),(41,'accounts','0005_user_must_change_password','2026-11-15 11:43:16.724876'),(42,'accounts','0006_user_cccd','2026-11-15 11:51:58.647511'),(43,'accounts','0007_user_staff_role','2026-11-15 15:46:07.053454'),(44,'products','0002_product_low_stock_threshold_product_stock_quantity_and_more','2026-11-15 17:35:42.880320'),(45,'orders','0003_order_cancellation_reason_order_cancelled_at_and_more','2026-11-15 18:33:51.085808'),(46,'orders','0004_orderitem_product_category_and_more','2026-11-16 04:31:10.080146'),(47,'products','0003_product_expiry_date_product_shipping_weight_grams_and_more','2026-11-16 04:31:10.222536'),(48,'orders','0005_order_customer_pii_encrypted','2026-11-16 05:00:47.971949'),(49,'orders','0006_deliveryissue_order_delivery_confirmation_deadline_and_more','2026-11-16 05:39:26.801530'),(50,'orders','0007_encrypt_cancelled_order_pii','2026-11-16 08:40:29.665423'),(51,'accounts','0008_loginthrottle_loginevent','2026-11-16 10:13:31.633503'),(52,'accounts','0009_securitypolicy','2026-11-16 10:13:31.727181'),(53,'mfa','0001_initial','2026-11-16 10:13:31.834542'),(54,'mfa','0002_authenticator_timestamps','2026-11-16 10:13:31.961881'),(55,'mfa','0003_authenticator_type_uniq','2026-11-16 10:13:32.110169'),(56,'orders','0008_alter_order_delivery_slot_alter_order_payment_method','2026-11-16 10:13:32.141290'),(57,'payments','0001_initial','2026-11-16 10:13:32.264062'),(58,'orders','0009_orderitem_inventory_deducted','2026-11-16 15:19:54.040273'),(59,'orders','0010_order_cancellation_reason_category_and_more','2026-11-16 16:46:47.252082'),(60,'products','0004_dry_goods_only_inventory','2026-11-16 17:16:18.658173'),(61,'products','0005_inventoryrestockrequest','2026-11-16 17:33:52.126634'),(62,'products','0006_alter_inventoryrestockrequest_status','2026-11-17 04:48:03.116471'),(63,'orders','0011_alter_order_payment_method','2026-11-17 05:28:44.336494'),(64,'orders','0012_alter_order_payment_method','2026-11-17 05:28:44.353993'),(65,'payments','0002_paymenttransaction_bank_transfer_code_and_more','2026-11-17 05:28:44.515956'),(66,'orders','0013_alter_deliveryissue_resolution_outcome','2026-11-17 11:08:22.119981'),(67,'orders','0014_deliveryissue_source','2026-11-17 11:08:22.197013'),(68,'orders','0015_order_customer_pii_purged_at_ordercarerequest_and_more','2026-11-17 14:00:14.829187');
/*!40000 ALTER TABLE `django_migrations` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `django_session`
--

DROP TABLE IF EXISTS `django_session`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `django_session` (
  `session_key` varchar(40) COLLATE utf8mb4_unicode_ci NOT NULL,
  `session_data` longtext COLLATE utf8mb4_unicode_ci NOT NULL,
  `expire_date` datetime(6) NOT NULL,
  PRIMARY KEY (`session_key`),
  KEY `django_session_expire_date_a5c62663` (`expire_date`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `django_session`
--

LOCK TABLES `django_session` WRITE;
/*!40000 ALTER TABLE `django_session` DISABLE KEYS */;
INSERT INTO `django_session` VALUES ('04kddvcvpra4agh3bdrh3njtfel0pl7u','.eJxVjstOwzAQRX_F8opKkWsndl5dAQuQStlQqUtrbE8a05BEsQstiH9HgQrBdu65c88H1XCMrT4GnLR3tKaCJn9vBuwB-zlwz9DvB2aHPk7esBlhlzSwzeCwu7mw_x60EFpa06yxuZO8qmxVKqlKQONSl5UcpOPGyQq4kWlpIBcGGuGMzYwCAGVkirlAmtCA9jj5eNZ-1ODchCHMvmnBOONs9v4lvpdhj32kNd0M777rYKkYJ1c737vhLZDHLRGc8RXZ-T6XK3LK5YJcj2OHOzRrH5cqK1iWk6v1_XbzkJDOH5DcoT0MC3LbTsMLLoX6WebkCRqY_KUye0RoGt1BiBps9K8-nmktikqWMq1KwfKCF0olVAcMwQ-9xtPop5kpOf_8ArYVgAE:1xSyeL:X6q4bu6IbEZ-3bR5oBD0Xppzj8MDh1wb3LUO5xukgZ0','2026-11-16 15:59:41.706512'),('0wqys0ikuir77x0r8hplmei1ie7t59a4','.eJxVjEsOgjAUAO_SNWn6hZale8_QvNdXpErA0GI0xrsbEha6nZnMmwXY6hi2ktaQifVMsuaXIcRbmndBV5gvC4_LXNeMfE_4YQs_L5Sm09H-DUYoI-uZHmJLRngfvbPGOkhIirQTYEggGQ8CjXIIrUQYJGHUaAHAolGplWmfllRKXuaQnve8vlgvnRANKxWGIUxQaoBY8yPXXXXeOGVU1_JOaaH05wud0Ey5:1xStme:bUvEO-f2eDNpuuWp7uTqoAkA8Pm9z-3owBMewHS809g','2026-11-16 10:47:56.757168'),('4q10ioeyyb1boac3p7dm9183wz70a5rc','.eJxVjsFOwzAQRH_F8qmVItdJnNRJT8ABpFIuVOrRWtubxjTEUexCC-LfUaCq4LrzZud9UgXH2KpjwFE5S2ua0uTvTYM5YD8F9gX6vWfG93F0mk0Iu6SBbbzF7vbC_nvQQmhpTfPGlFbwqjKVLEQhAbXNbC45CMu1FRVwLTKpoUw1NKnVJtcFABRaZFimSBMa0BxHF8_KDQqsHTGEyTdbMs44m7yvxM8y7LGPtKYb_-G6DhYF42S2c73174E8bUnKGV-RnetLsSKnUszJzTB0uEO9dnFR5EuWl2S2fthuHhPSuQOSezQHPyd37ehfcZEWv8ucPEMDo7tUJo8ITaM6CFGBie7NxTOt02UlpJBlljPOK5knVAUMwfle4Wlw44RIzr--ATi_f8Y:1xT07L:FtpD4Nq6fG-GrPdsrgDoTeKZf-Ihs827GdYjP58l8Rk','2026-11-16 17:33:43.067052'),('4xyisdaqi54kyaopflo0anwssje4xjl7','.eJxVjrtOwzAYhV_F8kSlyP1T3-J0AgaQSlmo1NFybKcxDXEUu9CCeHdU6FDWc75z-cLaHHKnD8lPOjhcY46La60xdu-Hs-FezbCLxMYhT6EhZ4Rc3ETW0fn-7sL-K-hM6nCNqbDMWtsqQW1VSa-gkkYwAO64pK7hTrWioRV1jjmg3LbUqwXQErhUVgIucPL2MIV80mHUxrnJp4RrXC4kAQKkvCZ-l83ODxnXeB0_Q9-bOSeAbrZhcPEjoecNKoHAEm3DINgSHQWbodtx7P3WN6uQ55xKQgW6WT1u1k8F6sPeowdv93GG7rspvvl5yf-WAb2Y1kzhEjn_yKZtdW9S1sbm8B7yCdelVEyVjFVAKsWEWBRYJ59SiIP2xzFMZ6YC-P4BQ4J-gg:1xTHFY:J_FN4fbLfMgNS3Ng_90bDOTAihawysio1ilct_xl88M','2026-11-17 11:51:20.910993'),('5mxa2tw489r18klwk0hxfy4a11ib55oj','.eJxVjEEKwjAQAP-yZwlb06Rpj959Q9hNtjYqiTQtKOLfpdCDXmeGeYOndZn8WmX2KcIAFg6_jCncJG8iXilfigolL3NitSVqt1WdS5T7aW__BhPVCQYIRmLXWNP25OKxM64zlluU2B4RjdWOQhxH1GgcaWlsE7jXrIltjzw6s02r1JpK9vJ8pPkFA36-bwU-sg:1xSrFv:DxeNqlgtkG7Jno8Q_Y8YbCuFmWlG0tTjCzCX1OaqfV0','2026-11-30 07:35:59.291606'),('5qdo1a6mb5qiitdynp95284pxuhdtzgd','.eJxVjk1PwyAcxr8K4eSShsGAUrqTetBkzotLdiQU_l1xtTSF6abxu5vpDvP6PL_n5Qsbe8idOSSYTPC4xhIX11pj3R6Gs-Ff7bCLxMUhT6EhZ4Rc3ETW0UN_d2H_FXQ2dbjGvHTCOdfqkruqUqBppWwpKJVeKu4b6XVbNrzi3gtPuXQtB72gnFGptFMUFziBO0whn0wYjfV-gpRwjdlCEUooYdfE77LdwZBxjdfxM_S9nUtC0c02DD5-JPS8QYwSukTbMJRiiY6lmKHbcexhC80q5LnkivAS3aweN-unAvVhD-gB3D7O0H03xTeYM_m3TNGLbe0ULpHzj2zb1vQ2ZWNdDu8hn3DNlBaVXEgmCdNaCFFgkyClEAcDxzFMZ6ai9PsHQwR-fg:1xT187:rr77MpwzHmhqydoTlW_KPfmwIUuX7k1jbk9GsigcM8c','2026-11-16 18:38:35.231564'),('6813ibpr3eln1lm9ykrcv3bf5y28jzbf','.eJxVjMsKwjAQAP8lZwmr27x69O43hGQ3tVFJStOCIv67FHrQ68wwb-HDuox-bWn2mUUvlDj8shjonsom-BbKtUqqZZlzlFsid9vkpXJ6nPf2bzCGNopeoKaOiAankaw1yYE1QXcAipVBjordoCNaZO4YUNGAyZ0Aj6CMIwPbtKXWci0-Pac8v0QPny99SD6U:1xSdLf:3d1Dmr1D3h5ckxWtFZMk57MRvqhu5G8Y3ZIohCtnqpk','2026-11-29 16:44:59.976693'),('6btscihzvo7m0poxezvdiml3vwvuyaey','.eJxVjMsKwjAQAP8lZwnbbp49evcbQrqb2Ki00kRRxH-Xgge9zgzzEiHe2hRuNa2hsBiEFrtfNkY6p3kTfIrzcZG0zG0to9wS-bVVHhZOl_23_RtMsU5iEGhIEVH2Bsk5mzw4G40C0Kwt8qjZZzOiQ2bFgJoyJt8DdqCtJwvbtKZayzKH9LiW9SmGzgHsRG0x53CJtYVIrdxL25T1yvUKlZF9D77T7w8pCUs7:1xStnm:sytoRqagy5I8d9_85OMreVAoLLk8hlfMz580hSlu4RA','2026-11-16 10:49:06.231970'),('6pnqpj7uw43d52ic94d9f0msp5gtevgb','.eJxVjEFuwyAUBe_COkJAjAEvu88Z0OPzqWkjOzK4ahTl7pGlLNrtzGgeImLvc9wbb7FmMQknTn9ZAn3zcoj8heVzlbQufatJHol82yYva-brx7v9N5jRZjEJo4MZ2I6WKVlyIAU4eLIZ58Q-Fy46ICSnoEgHlHNRNhO0S0aPDse0cWt1XSL_3up2F5P2Sp1E6yglXtF6BPX6U_uhXBi8GYz3chi1M-PzBcN8TQA:1xStmq:8cQUfP3xvVYmWtSpXlfW2P6PG1VR99F2KlAEZlfqkZo','2026-11-16 10:48:08.466189'),('759bkj5zai0otudk9tmpkjil6lk48afv','.eJxVjr1OwzAUhV_F8kSlyLWdxG7SCRhAKmWhUkfrxr5pTEMcxS60IN4dFTqU9Zzv_HxRA4fUmUPEyXhHa6ppdq01YPc4nA33CsMuMBuGNPmGnRF2cSNbB4f93YX9V9BB7GhNpahkgaUq0Tal1WA5gIaFLR3kDS5ci62ooGo0B25FBW3e8tJZELqRQmmgGY1oD5NPJ-NHA85NGCOtqZCaccaZuCZ-l2GHQ6I1XYdP3_cwLxknN1s_uPARyfOGCM74kmz9oIolOapiRm7HscctNiuf5mWuWa7Izepxs37KSO_3SB7Q7sOM3HdTeMO5KP-WOXmBFiZ_iZx_JGhb00NMBmzy7z6daC10VVRCSSGZVlJKlVETMUYfBoPH0U9nZsH59w8A1IAs:1xTHhU:63ytdoZXhkSN_GJ3TEc_q2zhR5Xb4pK4ZEJchACdz-Y','2026-11-17 12:20:12.795359'),('77zg49c2m75ihqo5gyyknr3wfbo3mw3n','.eJxVjr1OwzAUhV_F8kSlyL2p4zhOJ2AAqZSFSh0tx75pTEMcxS60IN4dFTqU9Zzv_HxRbQ6p04eIk_aO1lTQ7FprjN3jcDbcqxl2gdkwpMk37IywixvZOjjs7y7sv4LOxI7WlJe2sNa2quS2qiQqqKQpCwDhhOSuEU61ZcMr7lzhgAvbclQL4DkIqawEmtGI9jD5dNJ-1Ma5CWOkNc0XkgEDll8Tv8tmh0OiNV2HT9_3Zi4YkJutH1z4iOR5Q3JgsCRbP5TFkhzLYkZux7HHLTYrn-aCS8ZLcrN63KyfMtL7PZIHtPswI_fdFN5wnou_ZSAvpjWTv0TOP5JpW92bmLSxyb_7dKJ1LlVRFQshJYNcKiUzqiPG6MOg8Tj66cxUAN8_Q_x-hw:1xSyXp:UU96OPJ68finHLCK-L12MLofC0GyWPAWLhfd6IdAeVM','2026-11-16 15:52:57.049241'),('95jt4q4kjpqgxwgrgxaegdz5500oa88h','.eJxVj7FOwzAYhF_F8tRKkWsndpykEzCAVMpCpY6RY_9uTIMd2aloQbw7CnQo6913d7ov3KrT1LenBLF1Bje4xtmt1il9BD8b5k35QyA6-Cm6jswIubqJbIOB4f7K_ivoVepxg_OurkSRcyEVrRgt8tp0SlNZ1kxIy6XhlNnaVrrSllKZM8XA1FYYY3LLOMcZTqBP0U2X1o2tMiZCSrjBLJeEEkrYLfG7rA7gJ9zgbfh0w6BWglC02DtvwkdCLzvEKKFrtHe-5Gt0LvkS3Y3jAHvoNm5aiUKSokSLzdNu-5yhwR0BPYI-hiV66GN4hxUTf8sUvSqrortG5vsJUnLBt3AeXbzghn7_APD1cb8:1xTUlI:pSeZSKHWupMMyfaMxFjZGZNlLVKTUhsyGn4bl0m_wmM','2026-12-02 01:47:00.457183'),('bp4ovoemvvwls0bfjq6ma37y2iw36zya','.eJxVjk1PwjAcxr9K0xMkS_mPtms3TupBE8SLJBybru1YZa7LWhQ0fncz5QDX5_k9L99Y6WNq1TG6UXmLK8xxdq3V2hxcPxn2Tff7QEzo0-hrMiHk4kayCdZ19xf2pqDVscUVpoVhxpimLKiRUrgSpNAFA-CWC2prbsumqKmk1jILlJuGunIJNAcuSiMAZzg6cxx9Ois_KG3t6GLEFc6XggABkl8Tf8t67_qEK7wJX77r9IITQLOd7234jOhli3IgsEI73xdshU4Fm6O7YejcztVrnxacCkILNFs_bTfPGer8waFHZw5hjh7aMby7Rc7_lwG96kaP_hKZfiTdNKrTMSltkv_w6YyrXJRMlgyAEcl5zmWGVXQx-tArdxr8ODES4OcXQwp-fg:1xTBvI:2-eFIyHRbm1Jr2CPI1bkDvM5us2_5M1dnPH-Ckz6lzs','2026-11-17 06:10:04.970820'),('e5by1i7uwamnusm0wnp9en6eibaq9qkn','.eJxNjctugzAURH_FuqtEQsYGGwNZpV20Uko3jcQSGT-CC8UIg_pS_71KmwXbOWdmvqGR69I1azBz4zSUUEC0zVqpejNegX6V48Vj5cdldi2-KvhGA668NsPdzY22A50MHZSQtEXO04RxIUlOSZoUupWKiKygXFgmNCPUFjZXubKEiIRKanRhudY6sZQxiCAYtc5u-Wzc1EitZxMClEATgQkmmG6Nv2d5MeMCJVT-yw2DjDkmaFe7Ufv3gJ7PiBJMDqh2Y8YO6CNje3ScpsHUpj25JeapwGmGdqfHc_UUocH1Bj0Y1fs9uu9m_2Ziyv-fCXqRVs7uVoGfX1RKaoI:1xTUiY:ITc9YLEnL1-AFVguCGq9MBpwQxDvE4LtJWb9RM4Oeik','2026-12-02 01:44:10.824163'),('feclf1q5b2m2k9fxlkpsdbh8fxbd9ovk','.eJxVjjtPwzAUhf-K5YlKkWvn5TidgAGkUhYqdbRu7JvGNMRR7EIL4r-jQIeynvOdxxfVcIydPgactLO0ppIm11oD5oDDbNhXGPaeGT_EyTVsRtjFDWzjLfZ3F_ZfQQehozVNhUpzLMoCTVMYCYYDSKhMYSFrsLIttkKBaiQHboSCNmt5YQ0I2aSilEATGtAcJxfP2o0arJ0wBFpTkUrGGWfimvhdhj0OkdZ04z9d38OyYJzc7Nxg_Ucgz1siOOMrsnNDma_IqcwX5HYce9xhs3ZxWWSSZSW5WT9uN08J6d0ByQOag1-Q-27yb7gUxd8yJy_QwuQukflHhLbVPYSowUT37uKZ1kKqXHGpqowpxStVJVQHDMH5QeNpdNPMVJx__wAErYBN:1xTFYm:-mXmL_Lmf4JkUQhi5R1KjP6IoS6GJbsUwDIqeOSAVTE','2026-11-17 10:03:04.008413'),('fx708omwlh5fbt53ur0fksoyhj9logwt','.eJxNjjtvgzAUhf-K5SmRkGPANo9MaYdWStOlkRjRxb4OLhQjDOpL_e9VWoas53zn8U1rWOa2XgJOtTO0pDmNbrUGdIfD1TCvMFw8036YJ9ewK8JWN7CTN9jfrWx0W9BCaGlJCysVGKut4SLV2uZSGJSFyrDRCRY6FkboNOcCG2tNDJhgUagMVCIF5PL6KqBeJjd_1m6swZgJQ6AljZOMccZZfEv8LcMFh5mW9OS_XN_DTjJONpUbjH8P5PlMYs74nlRuUGJPPpTYksM49lhhc3TzTqYZSxXZHB_Pp6eI9K5D8oC681ty307-DXex_F_m5AUsTG6N0J9fyLxsHg:1xTHe9:eyN2cvpbjISvcBhhOeyrKzGPZt5sFZGEq7F_fQUlMrU','2026-12-01 11:46:45.580034'),('hfqaltjycaxvgyik9vr7t5rctxfm9kve','.eJxVjk1PwjAcxr9K0xMkS_mPru06TupBE8SLJBybru1YZa7LWhQ0fncz5QDX5_k9L99Y6WNq1TG6UXmLK8xwdq3V2hxcPxn2Tff7QEzo0-hrMiHk4kayCdZ19xf2pqDVscUVptwUxphGcmrKUjgJpdC8AGCWCWprZmXDa1pSawsLlJmGOrkEmgMT0gjAGY7OHEefzsoPSls7uhhxhfOlIECA5NfE37Leuz7hCm_Cl-86vWAE0Gznexs-I3rZohwIrNDO97xYoRMv5uhuGDq3c_XapwWjglCOZuun7eY5Q50_OPTozCHM0UM7hne3yNn_MqBX3ejRXyLTj6SbRnU6JqVN8h8-nXGVC1lIKBnlhC0Fl3mGVXQx-tArdxr8ODElwM8vQ4t-gg:1xTFhg:tpAjhU3ZwCwrKM6fYlY3fbLnGqOrI6pplaAh8cqsf5A','2026-11-17 10:12:16.560326'),('o105wbct51vhdcdjlz6sv59pwevr55jc','.eJxVjstOwzAQRX_F8opKkWsntvPoCliAVMqGSl1a40ca0xBHsQstiH9HgQrBdu65c88HVnBMnTpGNylvcYMZzv7eNJiDG-bAPsOwD8SEIU1ekxkhlzSSTbCuv7mw_x50EDvc4KI10nJa16auBBcVOG1zW1QUuKXa8hqo5nmlQTINLbPaFFoAgNA8d5I5nOHozHHy6az8qMDaycU4--YloYSS2fuX-F6GvRsSbvAmvPu-h6UgFF3t_GDDW0SPW8QooSu084PkK3SSfIGux7F3O6fXPi1FUZJCoqv1_XbzkKHeHxy6c-YQFui2m8KLWzLxs0zRE7Qw-Utl9kjQtqqHmBSY5F99OuOGlTWvCyFlRVhZ5EWVYRVdjD4Myp1GP81MRennF7YFgAA:1xTMlI:7qy2mURhIA9Nd8WVDomYcT7MvXtQ_5rFp7VUSLhOI50','2026-11-17 17:44:28.213299'),('ohs7byr7ivcwbs4fhjwpejc879wipgrf','.eJxVjr1OwzAUhV_F8kSlyLWTOK7TCRhAKmWhUkfrxr5pTEMcxS60IN4dFTqU9Zzv_HxRA4fUmUPEyXhHa6podq01YPc4nA33CsMuMBuGNPmGnRF2cSNbB4f93YX9V9BB7GhNc6HzEmUl0TbSKrAcQMHCSgdFgwvXYis06EZx4FZoaIuWS2dBqCYXlQKa0Yj2MPl0Mn404NyEMdKailwxzjgT18TvMuxwSLSm6_Dp-x7mknFys_WDCx-RPG-I4IwvydYPVbkkx6qckdtx7HGLzcqnuSwUKypys3rcrJ8y0vs9kge0-zAj990U3nAu5N8yJy_QwuQvkfOPBG1reojJgE3-3acTrYXSpdZSVpwJXZYyz6iJGKMPg8Hj6Kczs-D8-wcCl4A5:1xTcLI:R1y-bH0Uj-tuQdVCQ9uWsMMLOmQQbjhowyyHHpz-DNc','2026-11-18 10:22:40.235957'),('qe8x3y8qqm7i94f6tizrcxriu0zb5mf1','.eJxVjr1OwzAUhV_F8kSlyLWTOI7TCRhAKmWhUkfrxr5pTEMSxS60IN4dBTqU9Zzv_HxRA8fYmmPAyXhHK6pocq3VYA_Yz4Z7hX4_MDv0cfI1mxF2cQPbDA67uwv7r6CF0NKKpkKnOcpCoq2lVWA5gILSSgdZjaVrsBEadK04cCs0NFnDpbMgVJ2KQgFNaEB7nHw8Gz8acG7CEGhFRaoYZ5yJa-J3GfbYR1rRzfDpuw6WknFys_O9Gz4Ced4SwRlfkZ3vi3xFTkW-ILfj2OEO67WPS5kplhXkZv243TwlpPMHJA9oD8OC3LfT8IZLIf-WOXmBBiZ_icw_IjSN6SBEAzb6dx_PtBJK52WqhdQslzpLVUJNwBD80Bs8jX6amZLz7x8C_4A-:1xSv3P:NqUvkd2r9jYNgQp266M8zy45oNdniJnHAEMPx90Td6o','2026-11-16 12:09:19.468980'),('qpo397ut8anekqsyk99l36u5flxaljvj','.eJxVjr1OwzAUhV_F8kSlyLWTOE7SCRhAKmWhUkfrxr5pTEMcxS60IN4dBTqU9Zzv_HxRDcfY6WPASTtLa6pocq01YA44zIZ9hWHvmfFDnFzDZoRd3MA23mJ_d2H_FXQQOlrTVFRpjrKQaBppFBgOoKA00kLWYGlbbEUFVaM4cCMqaLOWS2tAqCYVhQKa0IDmOLl41m7UYO2EIdCailQxzjgT18TvMuxxiLSmG__p-h6WknFys3OD9R-BPG-J4IyvyM4NRb4ipyJfkNtx7HGHzdrFpcwUywpys37cbp4S0rsDkgc0B78g993k33Ap5N8yJy_QwuQukflHhLbVPYSowUT37uKZ1kJVeZXKlJeszFRaqITqgCE4P2g8jW6amZLz7x8CSIA5:1xTK2a:Qu2rgqfOSsXOaNspUpBlb1vy-mi9xSFhFlYEORmL2tU','2026-11-17 14:50:08.867655'),('qpvtq3wdnsvdm8xj9wawe3x37h9c1pu6','.eJxVjEEOwiAQAP-yZ0OglVJ69O4byLIsFjVgoE00xr-bJj3odWYyb3C4LrNbG1eXAkxg4PDLPNKN8ybCFfOlCCp5qcmLLRG7beJcAt9Pe_s3mLHNMEGnbHdkPWgmr8kgSUSDI-mAvecxRI7KovVGoiRlMfZR6kCojO_UYHCbNm4tlez4-Uj1BZP8fAHNUUBN:1xSdU3:3aEWKi3HFvUCLFPW97c-3UkRR3POHvYSDU4z0SAnnnQ','2026-11-29 16:53:39.104537'),('r1czdw6otjk5ygqn640x30u5igx4bj33','.eJxVjk1PwyAcxr8K4eSShv0phZbupB40mfPikh0JBbriamkK003jdzfVHeb1eX7PyxdW-pg6dYxuUt7iGnOcXWuNNgc3zIZ91cM-EBOGNPmGzAi5uJFsgnX93YX9V9Dp2OEaM2EKY0wrBTNVVToJValFAcAtL5ltuJWtaFjFrC0sMG5a5mQOjAIvpSkBZzg6c5x8Ois_Km3t5GLENaZ5SYAAodfE77LeuyHhGm_Cp-97veQE0M3ODzZ8RPS8RRQIrNDOD6JYoZMoFuh2HHu3c83apyVnJWEC3awft5unDPX-4NCDM4ewQPfdFN7ckvK_ZUAvutWTv0TmH0m3rep1TEqb5N99OuOalpJDzpjIiawolTLDKroYfRiUO41-mpkK4PsHQlt-ew:1xTjZi:ump9olnFWn8wnajRUAB80JQOsza4Etj_nobaE6LAsLo','2026-11-18 18:06:02.992890'),('r507nd4snwg15lywwy9b87cep72xdv0a','.eJxVjk9PwjAYxr9K0xMkS3lH13UbJ_WgCeJFEo5N175jlbkua1HQ-N3NlANcn-f3_PmmSh9jq44BR-UsraigybVWa3PAfjLsm-73nhnfx9HVbELYxQ1s4y129xf2pqDVoaUV5bnJjDFNmXNTFBJLKKTOMwBhheS2FrZs8poX3NrMAhem4VgugacgZGkk0IQGNMfRxbNyg9LWjhgCrWi6lAwYsPSa-FvWe-wjrejGf7mu0wvBgMx2rrf-M5CXLUmBwYrsXJ9nK3LKszm5G4YOd1ivXVwILhnPyWz9tN08J6RzBySPaA5-Th7a0b_jIhX_y0BedaNHd4lMP6JuGtXpEJU20X24eKZVKsusEMuyEIwLAYInVAUMwfle4Wlw48QUAD-_Q2B-fw:1xT1Fh:DL0DsKIk98btrUsDKAJNIGqxIu-8czhxnqHXWIXuuiE','2026-11-16 18:46:25.379626'),('rg1wniytgonr8amvetztz3wa8ivzz7rg','.eJxVjrtOwzAYhV_F8kSlyP1dx5ekEzCAVMpCpY6WYzuNaYij2IUWxLujQoeynvOdyxfW5pA7fUh-0sHhGnNcXGuNsXs_nA33aoZdJDYOeQoNOSPk4iayjs73dxf2X0FnUodrzIQtrbVtJZhVSvoKlDSiBOCOS-Ya7qpWNEwx50oHjNuW-WoBjAKXlZWAC5y8PUwhn3QYtXFu8inhGtOFJECA0Gvid9ns_JBxjdfxM_S9mXMC6GYbBhc_EnreIAoElmgbBlEu0VGUM3Q7jr3f-mYV8pwzSZhAN6vHzfqpQH3Ye_Tg7T7O0H03xTc_p_xvGdCLac0ULpHzj2zaVvcmZW1sDu8hn3BNZVUqRgVVRCgOwAqsk08pxEH74ximM6MAvn8AQjd-dg:1xSvh4:mHbvkjFq4tAB3iFWjo21pNROg4mNHpozrAcXLBqcpn8','2026-11-16 12:50:18.706379'),('sckgwifbv06uz2u47qejp4g7y1xwq8ut','.eJxVjr1OwzAUhV_F8kSlyLWTOE7SCRhAKmWhUkfrxr5pTEMcxS60IN4dBTqU9Zzv_HxRDcfY6WPASTtLa6pocq01YA44zIZ9hWHvmfFDnFzDZoRd3MA23mJ_d2H_FXQQOlrTVFRpjrKQaBppFBgOoKA00kLWYGlbbEUFVaM4cCMqaLOWS2tAqCYVhQKa0IDmOLl41m7UYO2EIdCailQxzjgT18TvMuxxiLSmG__p-h6WknFys3OD9R-BPG-J4IyvyM4NRb4ipyJfkNtx7HGHzdrFpcwUywpys37cbp4S0rsDkgc0B78g993k33Ap5N8yJy_QwuQukflHhLbVPYSowUT37uKZ1kJVeSnTShRMSlWVIqE6YAjODxpPo5tmpuT8-wcDMIBA:1xT1Ea:chdBVwdP62mQNCiyploRQQo-AwGTfe_7EJ5afiQnIAc','2026-11-16 18:45:16.591922'),('sfswrygj2juhntfr4ral3exla5z2raou','.eJxVjEEOwiAQAP-yZ0OglVJ69O4byLIsFjVgoE00xr-bJj3odWYyb3C4LrNbG1eXAkxg4PDLPNKN8ybCFfOlCCp5qcmLLRG7beJcAt9Pe_s3mLHNMEGnbHdkPWgmr8kgSUSDI-mAvecxRI7KovVGoiRlMfZR6kCojO_UYHCbNm4tlez4-Uj1BZP8fAHNUUBN:1xSeEV:KoFhARwnHEELZnGGaoWepfFsJjMgjXpP_sUSTyez2Us','2026-11-29 17:41:39.974093'),('um84sd0xn1mz82b8jkbjzxwxl0cuupkm','.eJxVjjtPwzAUhf-K5YlKkWvn5TidgAGkUhYqdbRu7JvGNMRR7EIL4r-jQIeynvOdxxfVcIydPgactLO0ppIm11oD5oDDbNhXGPaeGT_EyTVsRtjFDWzjLfZ3F_ZfQQehozVNhUpzLMoCTVMYCYYDSKhMYSFrsLIttkKBaiQHboSCNmt5YQ0I2aSilEATGtAcJxfP2o0arJ0wBFpTkUrGGWfimvhdhj0OkdZ04z9d38OyYJzc7Nxg_Ucgz1siOOMrsnNDma_IqcwX5HYce9xhs3ZxWWSSZSW5WT9uN08J6d0ByQOag1-Q-27yb7gUxd8yJy_QwuQukflHhLbVPYSowUT37uKZ1kKqvMpTpQRTMq2yKqE6YAjODxpPo5tmpuL8-wcDrIBE:1xSyeV:h75EMy2q15ywzoiSntejZ1ZCZAX2ufZFVh9z4L2qIhc','2026-11-16 15:59:51.991177'),('upaktd3dzfk5pd6ess4lpar6jlhd4fcs','.eJxVjstOwzAQRX_F8opKkWsnjuOkK2ABUikbKnVpjR9pTEMcxS60IP4dBSoE27nnzj0fWMExdeoY3aS8xQ1mOPt702AObpgD-wzDPhAThjR5TWaEXNJINsG6_ubC_nvQQexwg4vWCMtpXZtalryU4LTNbSEpcEu15TVQzXOpQTANLbPaFLoEgFLz3AnmcIajM8fJp7PyowJrJxfj7JtXhBJKZu9f4nsZ9m5IuMGb8O77HpYloehq5wcb3iJ63CJGCV2hnR8EX6GT4At0PY692zm99mlZFhUpBLpa3283Dxnq_cGhO2cOYYFuuym8uCUrf5YpeoIWJn-pzB4J2lb1EJMCk_yrT2fcsKrmMpeCMcKoFEWVYRVdjD4Myp1GP82MpPTzC7S0f_Y:1xSuuZ:A5lqNk3LrmAJoDsIHqGA6gfvoCA_2bjS1_aSV9lqcNw','2026-11-16 12:00:11.155862'),('wmx53hpkp023grt8wsoe5bedb598tyde','.eJxVjr1OwzAUhV_F8kSlyLWTOE7SCRhAKmWhUkfrxr5pTEMcxS60IN4dBTqU9Zzv_HxRDcfY6WPASTtLa6pocq01YA44zIZ9hWHvmfFDnFzDZoRd3MA23mJ_d2H_FXQQOlrTVFRpjrKQaBppFBgOoKA00kLWYGlbbEUFVaM4cCMqaLOWS2tAqCYVhQKa0IDmOLl41m7UYO2EIdCailQxzjgT18TvMuxxiLSmG__p-h6WknFys3OD9R-BPG-J4IyvyM4NRb4ipyJfkNtx7HGHzdrFpcwUywpys37cbp4S0rsDkgc0B78g993k33Ap5N8yJy_QwuQukflHhLbVPYSowUT37uKZ1kJVeZVJVZasLItMFQnVAUNwftB4Gt00MyXn3z8Er4BM:1xTMnE:a7it-aGyka4b5GZtkZabZeS9d7QMK_3JIwrvzcY6TAk','2026-11-17 17:46:28.928306');
/*!40000 ALTER TABLE `django_session` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `mfa_authenticator`
--

DROP TABLE IF EXISTS `mfa_authenticator`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `mfa_authenticator` (
  `id` bigint NOT NULL AUTO_INCREMENT,
  `type` varchar(20) COLLATE utf8mb4_unicode_ci NOT NULL,
  `data` json NOT NULL,
  `user_id` bigint NOT NULL,
  `created_at` datetime(6) NOT NULL,
  `last_used_at` datetime(6) DEFAULT NULL,
  PRIMARY KEY (`id`),
  KEY `mfa_authenticator_user_id_0c3a50c0` (`user_id`),
  CONSTRAINT `mfa_authenticator_user_id_0c3a50c0_fk_accounts_user_id` FOREIGN KEY (`user_id`) REFERENCES `accounts_user` (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `mfa_authenticator`
--

LOCK TABLES `mfa_authenticator` WRITE;
/*!40000 ALTER TABLE `mfa_authenticator` DISABLE KEYS */;
/*!40000 ALTER TABLE `mfa_authenticator` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `orders_deliveryissue`
--

DROP TABLE IF EXISTS `orders_deliveryissue`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `orders_deliveryissue` (
  `id` bigint NOT NULL AUTO_INCREMENT,
  `status` varchar(10) COLLATE utf8mb4_unicode_ci NOT NULL,
  `details` longtext COLLATE utf8mb4_unicode_ci NOT NULL,
  `reported_at` datetime(6) NOT NULL,
  `resolution` longtext COLLATE utf8mb4_unicode_ci NOT NULL,
  `resolution_outcome` varchar(12) COLLATE utf8mb4_unicode_ci NOT NULL,
  `resolved_at` datetime(6) DEFAULT NULL,
  `order_id` bigint NOT NULL,
  `reported_by_id` bigint DEFAULT NULL,
  `resolved_by_id` bigint DEFAULT NULL,
  `source` varchar(16) COLLATE utf8mb4_unicode_ci NOT NULL,
  PRIMARY KEY (`id`),
  KEY `orders_deliveryissue_order_id_21d62804_fk_orders_order_id` (`order_id`),
  KEY `orders_deliveryissue_reported_by_id_a8f23d58_fk_accounts_user_id` (`reported_by_id`),
  KEY `orders_deliveryissue_resolved_by_id_499663a4_fk_accounts_user_id` (`resolved_by_id`),
  KEY `orders_deli_status_0defd8_idx` (`status`,`reported_at`),
  CONSTRAINT `orders_deliveryissue_order_id_21d62804_fk_orders_order_id` FOREIGN KEY (`order_id`) REFERENCES `orders_order` (`id`),
  CONSTRAINT `orders_deliveryissue_reported_by_id_a8f23d58_fk_accounts_user_id` FOREIGN KEY (`reported_by_id`) REFERENCES `accounts_user` (`id`),
  CONSTRAINT `orders_deliveryissue_resolved_by_id_499663a4_fk_accounts_user_id` FOREIGN KEY (`resolved_by_id`) REFERENCES `accounts_user` (`id`)
) ENGINE=InnoDB AUTO_INCREMENT=2 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `orders_deliveryissue`
--

LOCK TABLES `orders_deliveryissue` WRITE;
/*!40000 ALTER TABLE `orders_deliveryissue` DISABLE KEYS */;
/*!40000 ALTER TABLE `orders_deliveryissue` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `orders_order`
--

DROP TABLE IF EXISTS `orders_order`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `orders_order` (
  `id` bigint NOT NULL AUTO_INCREMENT,
  `order_number` varchar(20) COLLATE utf8mb4_unicode_ci NOT NULL,
  `tracking_token` char(32) COLLATE utf8mb4_unicode_ci NOT NULL,
  `customer_name` varchar(120) COLLATE utf8mb4_unicode_ci NOT NULL,
  `customer_email` varchar(254) COLLATE utf8mb4_unicode_ci NOT NULL,
  `customer_phone` varchar(20) COLLATE utf8mb4_unicode_ci NOT NULL,
  `address` varchar(250) COLLATE utf8mb4_unicode_ci NOT NULL,
  `district` varchar(100) COLLATE utf8mb4_unicode_ci NOT NULL,
  `city` varchar(100) COLLATE utf8mb4_unicode_ci NOT NULL,
  `delivery_date` date NOT NULL,
  `delivery_slot` varchar(20) COLLATE utf8mb4_unicode_ci NOT NULL,
  `note` longtext COLLATE utf8mb4_unicode_ci NOT NULL,
  `payment_method` varchar(16) COLLATE utf8mb4_unicode_ci NOT NULL,
  `status` varchar(24) COLLATE utf8mb4_unicode_ci NOT NULL,
  `subtotal` decimal(14,2) NOT NULL,
  `shipping_fee` decimal(12,2) NOT NULL,
  `total` decimal(14,2) NOT NULL,
  `created_at` datetime(6) NOT NULL,
  `updated_at` datetime(6) NOT NULL,
  `customer_id` bigint DEFAULT NULL,
  `cancellation_reason` longtext COLLATE utf8mb4_unicode_ci NOT NULL,
  `cancelled_at` datetime(6) DEFAULT NULL,
  `cancelled_by_id` bigint DEFAULT NULL,
  `refund_status` varchar(20) COLLATE utf8mb4_unicode_ci NOT NULL,
  `customer_pii_encrypted` longtext COLLATE utf8mb4_unicode_ci NOT NULL,
  `delivery_confirmation_deadline` datetime(6) DEFAULT NULL,
  `delivery_confirmation_method` varchar(12) COLLATE utf8mb4_unicode_ci NOT NULL,
  `delivery_confirmed_at` datetime(6) DEFAULT NULL,
  `cancellation_reason_category` varchar(20) COLLATE utf8mb4_unicode_ci NOT NULL,
  `delivery_region` varchar(8) COLLATE utf8mb4_unicode_ci NOT NULL,
  `customer_pii_purged_at` datetime(6) DEFAULT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `order_number` (`order_number`),
  UNIQUE KEY `tracking_token` (`tracking_token`),
  KEY `orders_orde_status_25e057_idx` (`status`,`created_at`),
  KEY `orders_orde_custome_242823_idx` (`customer_id`,`created_at`),
  KEY `orders_order_cancelled_by_id_b6528c6d_fk_accounts_user_id` (`cancelled_by_id`),
  KEY `orders_due_conf_idx` (`status`,`delivery_confirmation_deadline`),
  CONSTRAINT `orders_order_cancelled_by_id_b6528c6d_fk_accounts_user_id` FOREIGN KEY (`cancelled_by_id`) REFERENCES `accounts_user` (`id`),
  CONSTRAINT `orders_order_customer_id_0b76f6a4_fk_accounts_user_id` FOREIGN KEY (`customer_id`) REFERENCES `accounts_user` (`id`)
) ENGINE=InnoDB AUTO_INCREMENT=66 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `orders_order`
--

LOCK TABLES `orders_order` WRITE;
/*!40000 ALTER TABLE `orders_order` DISABLE KEYS */;
INSERT INTO `orders_order` VALUES (59,'FM-2026-27117A39','18b0f3af54624b69945952281137ba7b','','','','','thủ đức','Hồ Chí Minh','2026-11-18','08:00–10:00','','cod','delivered',700000.00,0.00,700000.00,'2026-11-17 16:58:14.555205','2026-11-17 16:59:19.843090',8,'',NULL,NULL,'not_required','gAAAAABq_IfnFViyRJpskX9f-N5L50a8SwKHDVbJ3anaJ7BAuBMzdx3uEO7bQlECHtdy4WAVZcf2NG8aSR1jlEgC6IHFXacwfJ67dO3A8h2qd9kBXB0hZE7DCTBRSavJCybULa9xy9KWkUVXwwU-yVJiZvVT9G3s29RT2x_qrJJNTgo0TCrmaV4e3A3dgT21bGwiE7mkFZec0d2KNDuDHckbaWIahFfWe8cSJP1DX0R7wCr7P50EgxP3PZ1T5HELB1PaRfdKupAQB7KF0PyM5x0GPftcRcktyyEoXNLWvJElhY2AvsjXpVU_ezHpuSOl7_MkqdMT6icF70rJppRavMCrWK2YkP_RU-UuCYP48W_I_PJ-xq8165FNVcoa0geAVrmNxAyAc_LmeOyYUOfzeD8hcF7LSiKaaD7xxsp3KqK4cHkJwDAczME=',NULL,'customer','2026-11-17 16:59:19.815532','','hcm',NULL),(64,'FM-2026-B2F7741A','6f0e2e9e5cca44e69fc6d0a9a0935a09','','','','','thủ đức','tp hcm','2026-11-19','08:00–10:00','','cod','delivered',400000.00,0.00,400000.00,'2026-11-18 09:24:42.824744','2026-11-18 09:26:26.793916',9,'',NULL,NULL,'not_required','gAAAAABq_W9CH7lK6T3LE8kC8qWQMFO7vKdA1JOjNhsCI19xmP3Bvp7-4j2-1ofsdMIiIae84aayuEmVuLyyII3gBaun_5i7jJ1Kq5P9WpZHNtv-MO5zGIfU7VPnx7AQWG7hyUkVHinO4BCRr8F7VKU0dO2bGiqodLB6u2PGjy6dA3DPaq5iXuRnSFfCoN-N5TQHs5Ydv19ugnX_dk1E9Q6WYKdbETfY4lZ1_l_EhV9UfC-HnUqMTsHZDmuA0swqWr5jcA7UGgEMqCwYh0d5rY8WCSLXLhUyhnGTq8FQNjP5dPigbHlvDxLqMHP0-EQF9iZIunOAxVs_RGYoG4FVqmbbKu2QHCZYuhmsxjYbfw-4dLF8qmIOsPrpHYNqUaDrbcSjdmVQpbQr4ByvJN4E437_WkwyUPH2LAsrgSrHqbmoh7SIgFDTUA4=',NULL,'customer','2026-11-18 09:26:26.772299','','hcm',NULL);
/*!40000 ALTER TABLE `orders_order` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `orders_ordercancellationrequest`
--

DROP TABLE IF EXISTS `orders_ordercancellationrequest`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `orders_ordercancellationrequest` (
  `id` bigint NOT NULL AUTO_INCREMENT,
  `source` varchar(12) COLLATE utf8mb4_unicode_ci NOT NULL,
  `status` varchar(20) COLLATE utf8mb4_unicode_ci NOT NULL,
  `reason` longtext COLLATE utf8mb4_unicode_ci NOT NULL,
  `contact_outcome` varchar(20) COLLATE utf8mb4_unicode_ci NOT NULL,
  `contact_attempts` smallint unsigned NOT NULL,
  `contact_notes` longtext COLLATE utf8mb4_unicode_ci NOT NULL,
  `manager_resolution_reason` longtext COLLATE utf8mb4_unicode_ci NOT NULL,
  `requested_at` datetime(6) NOT NULL,
  `updated_at` datetime(6) NOT NULL,
  `resolved_at` datetime(6) DEFAULT NULL,
  `contacted_by_id` bigint DEFAULT NULL,
  `order_id` bigint NOT NULL,
  `requested_by_id` bigint DEFAULT NULL,
  `resolved_by_id` bigint DEFAULT NULL,
  PRIMARY KEY (`id`),
  KEY `orders_ordercancella_contacted_by_id_4410edc0_fk_accounts_` (`contacted_by_id`),
  KEY `orders_ordercancella_order_id_de08b4da_fk_orders_or` (`order_id`),
  KEY `orders_ordercancella_requested_by_id_e3e79e47_fk_accounts_` (`requested_by_id`),
  KEY `orders_ordercancella_resolved_by_id_76ab109d_fk_accounts_` (`resolved_by_id`),
  KEY `orders_orde_status_545be5_idx` (`status`,`requested_at`),
  CONSTRAINT `orders_ordercancella_contacted_by_id_4410edc0_fk_accounts_` FOREIGN KEY (`contacted_by_id`) REFERENCES `accounts_user` (`id`),
  CONSTRAINT `orders_ordercancella_order_id_de08b4da_fk_orders_or` FOREIGN KEY (`order_id`) REFERENCES `orders_order` (`id`),
  CONSTRAINT `orders_ordercancella_requested_by_id_e3e79e47_fk_accounts_` FOREIGN KEY (`requested_by_id`) REFERENCES `accounts_user` (`id`),
  CONSTRAINT `orders_ordercancella_resolved_by_id_76ab109d_fk_accounts_` FOREIGN KEY (`resolved_by_id`) REFERENCES `accounts_user` (`id`),
  CONSTRAINT `orders_ordercancellationrequest_chk_1` CHECK ((`contact_attempts` >= 0))
) ENGINE=InnoDB AUTO_INCREMENT=10 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `orders_ordercancellationrequest`
--

LOCK TABLES `orders_ordercancellationrequest` WRITE;
/*!40000 ALTER TABLE `orders_ordercancellationrequest` DISABLE KEYS */;
/*!40000 ALTER TABLE `orders_ordercancellationrequest` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `orders_ordercarerequest`
--

DROP TABLE IF EXISTS `orders_ordercarerequest`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `orders_ordercarerequest` (
  `id` bigint NOT NULL AUTO_INCREMENT,
  `request_type` varchar(12) COLLATE utf8mb4_unicode_ci NOT NULL,
  `status` varchar(10) COLLATE utf8mb4_unicode_ci NOT NULL,
  `details` longtext COLLATE utf8mb4_unicode_ci NOT NULL,
  `requested_at` datetime(6) NOT NULL,
  `resolution_note` longtext COLLATE utf8mb4_unicode_ci NOT NULL,
  `resolved_at` datetime(6) DEFAULT NULL,
  `order_id` bigint NOT NULL,
  `requested_by_id` bigint DEFAULT NULL,
  `resolved_by_id` bigint DEFAULT NULL,
  PRIMARY KEY (`id`),
  KEY `orders_ordercarerequest_order_id_83545732_fk_orders_order_id` (`order_id`),
  KEY `orders_ordercarerequ_requested_by_id_d1f0c1c0_fk_accounts_` (`requested_by_id`),
  KEY `orders_ordercarerequ_resolved_by_id_49da5ba0_fk_accounts_` (`resolved_by_id`),
  KEY `orders_orde_status_9e2a45_idx` (`status`,`requested_at`),
  CONSTRAINT `orders_ordercarerequ_requested_by_id_d1f0c1c0_fk_accounts_` FOREIGN KEY (`requested_by_id`) REFERENCES `accounts_user` (`id`),
  CONSTRAINT `orders_ordercarerequ_resolved_by_id_49da5ba0_fk_accounts_` FOREIGN KEY (`resolved_by_id`) REFERENCES `accounts_user` (`id`),
  CONSTRAINT `orders_ordercarerequest_order_id_83545732_fk_orders_order_id` FOREIGN KEY (`order_id`) REFERENCES `orders_order` (`id`)
) ENGINE=InnoDB AUTO_INCREMENT=2 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `orders_ordercarerequest`
--

LOCK TABLES `orders_ordercarerequest` WRITE;
/*!40000 ALTER TABLE `orders_ordercarerequest` DISABLE KEYS */;
INSERT INTO `orders_ordercarerequest` VALUES (1,'return','rejected','thiếu món','2026-11-17 16:59:44.344109','khách hàng không cung cấp đủ thông tin','2026-11-17 17:09:10.832358',59,8,7);
/*!40000 ALTER TABLE `orders_ordercarerequest` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `orders_orderitem`
--

DROP TABLE IF EXISTS `orders_orderitem`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `orders_orderitem` (
  `id` bigint NOT NULL AUTO_INCREMENT,
  `product_sku` varchar(32) COLLATE utf8mb4_unicode_ci NOT NULL,
  `product_name` varchar(120) COLLATE utf8mb4_unicode_ci NOT NULL,
  `unit_price` decimal(10,2) NOT NULL,
  `quantity` smallint unsigned NOT NULL,
  `line_total` decimal(12,2) NOT NULL,
  `order_id` bigint NOT NULL,
  `product_id` bigint DEFAULT NULL,
  `product_category` varchar(16) COLLATE utf8mb4_unicode_ci NOT NULL,
  `shipping_weight_grams` int unsigned NOT NULL,
  `inventory_deducted` tinyint(1) NOT NULL,
  PRIMARY KEY (`id`),
  KEY `orders_orderitem_order_id_fe61a34d_fk_orders_order_id` (`order_id`),
  KEY `orders_orderitem_product_id_afe4254a_fk_products_product_id` (`product_id`),
  CONSTRAINT `orders_orderitem_order_id_fe61a34d_fk_orders_order_id` FOREIGN KEY (`order_id`) REFERENCES `orders_order` (`id`),
  CONSTRAINT `orders_orderitem_product_id_afe4254a_fk_products_product_id` FOREIGN KEY (`product_id`) REFERENCES `products_product` (`id`),
  CONSTRAINT `orders_orderitem_chk_1` CHECK ((`quantity` >= 0)),
  CONSTRAINT `orders_orderitem_chk_2` CHECK ((`shipping_weight_grams` >= 0))
) ENGINE=InnoDB AUTO_INCREMENT=89 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `orders_orderitem`
--

LOCK TABLES `orders_orderitem` WRITE;
/*!40000 ALTER TABLE `orders_orderitem` DISABLE KEYS */;
INSERT INTO `orders_orderitem` VALUES (81,'protein111','Thanh năng lượng protein',100000.00,1,100000.00,59,2,'dry_goods',5,1),(82,'wh111','Whey',200000.00,3,600000.00,59,1,'drink',0,0),(87,'wh111','Whey',200000.00,2,400000.00,64,1,'drink',0,0);
/*!40000 ALTER TABLE `orders_orderitem` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `orders_orderpiiaccesslog`
--

DROP TABLE IF EXISTS `orders_orderpiiaccesslog`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `orders_orderpiiaccesslog` (
  `id` bigint NOT NULL AUTO_INCREMENT,
  `reason` varchar(500) COLLATE utf8mb4_unicode_ci NOT NULL,
  `accessed_at` datetime(6) NOT NULL,
  `accessed_by_id` bigint DEFAULT NULL,
  `order_id` bigint NOT NULL,
  PRIMARY KEY (`id`),
  KEY `orders_orderpiiacces_accessed_by_id_60ce44e1_fk_accounts_` (`accessed_by_id`),
  KEY `orders_orde_order_i_8d46cd_idx` (`order_id`,`accessed_at`),
  CONSTRAINT `orders_orderpiiacces_accessed_by_id_60ce44e1_fk_accounts_` FOREIGN KEY (`accessed_by_id`) REFERENCES `accounts_user` (`id`),
  CONSTRAINT `orders_orderpiiaccesslog_order_id_95276944_fk_orders_order_id` FOREIGN KEY (`order_id`) REFERENCES `orders_order` (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `orders_orderpiiaccesslog`
--

LOCK TABLES `orders_orderpiiaccesslog` WRITE;
/*!40000 ALTER TABLE `orders_orderpiiaccesslog` DISABLE KEYS */;
/*!40000 ALTER TABLE `orders_orderpiiaccesslog` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `payments_paymenttransaction`
--

DROP TABLE IF EXISTS `payments_paymenttransaction`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `payments_paymenttransaction` (
  `id` bigint NOT NULL AUTO_INCREMENT,
  `transaction_ref` varchar(32) COLLATE utf8mb4_unicode_ci NOT NULL,
  `amount` decimal(14,2) NOT NULL,
  `status` varchar(10) COLLATE utf8mb4_unicode_ci NOT NULL,
  `gateway_transaction_no` varchar(64) COLLATE utf8mb4_unicode_ci NOT NULL,
  `response_code` varchar(10) COLLATE utf8mb4_unicode_ci NOT NULL,
  `expires_at` datetime(6) NOT NULL,
  `paid_at` datetime(6) DEFAULT NULL,
  `created_at` datetime(6) NOT NULL,
  `updated_at` datetime(6) NOT NULL,
  `order_id` bigint NOT NULL,
  `bank_transfer_code` varchar(16) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `provider` varchar(16) COLLATE utf8mb4_unicode_ci NOT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `transaction_ref` (`transaction_ref`),
  UNIQUE KEY `order_id` (`order_id`),
  UNIQUE KEY `bank_transfer_code` (`bank_transfer_code`),
  KEY `payments_pa_status_ace706_idx` (`status`,`expires_at`),
  CONSTRAINT `payments_paymenttransaction_order_id_543b42e1_fk_orders_order_id` FOREIGN KEY (`order_id`) REFERENCES `orders_order` (`id`)
) ENGINE=InnoDB AUTO_INCREMENT=8 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `payments_paymenttransaction`
--

LOCK TABLES `payments_paymenttransaction` WRITE;
/*!40000 ALTER TABLE `payments_paymenttransaction` DISABLE KEYS */;
/*!40000 ALTER TABLE `payments_paymenttransaction` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `products_inventoryrestockrequest`
--

DROP TABLE IF EXISTS `products_inventoryrestockrequest`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `products_inventoryrestockrequest` (
  `id` bigint NOT NULL AUTO_INCREMENT,
  `product_name` varchar(120) COLLATE utf8mb4_unicode_ci NOT NULL,
  `product_sku` varchar(32) COLLATE utf8mb4_unicode_ci NOT NULL,
  `requested_quantity` int unsigned NOT NULL,
  `available_quantity` int unsigned NOT NULL,
  `attempt_count` int unsigned NOT NULL,
  `status` varchar(16) COLLATE utf8mb4_unicode_ci NOT NULL,
  `created_at` datetime(6) NOT NULL,
  `updated_at` datetime(6) NOT NULL,
  `fulfilled_at` datetime(6) DEFAULT NULL,
  `fulfilled_by_id` bigint DEFAULT NULL,
  `product_id` bigint DEFAULT NULL,
  `requested_by_id` bigint DEFAULT NULL,
  PRIMARY KEY (`id`),
  KEY `products_inventoryre_fulfilled_by_id_b04ebdc9_fk_accounts_` (`fulfilled_by_id`),
  KEY `products_inventoryre_product_id_ee884918_fk_products_` (`product_id`),
  KEY `products_inventoryre_requested_by_id_a4057f73_fk_accounts_` (`requested_by_id`),
  KEY `products_in_status_ced2ed_idx` (`status`,`updated_at`),
  CONSTRAINT `products_inventoryre_fulfilled_by_id_b04ebdc9_fk_accounts_` FOREIGN KEY (`fulfilled_by_id`) REFERENCES `accounts_user` (`id`),
  CONSTRAINT `products_inventoryre_product_id_ee884918_fk_products_` FOREIGN KEY (`product_id`) REFERENCES `products_product` (`id`),
  CONSTRAINT `products_inventoryre_requested_by_id_a4057f73_fk_accounts_` FOREIGN KEY (`requested_by_id`) REFERENCES `accounts_user` (`id`),
  CONSTRAINT `products_inventoryrestockrequest_chk_1` CHECK ((`requested_quantity` >= 0)),
  CONSTRAINT `products_inventoryrestockrequest_chk_2` CHECK ((`available_quantity` >= 0)),
  CONSTRAINT `products_inventoryrestockrequest_chk_3` CHECK ((`attempt_count` >= 0))
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `products_inventoryrestockrequest`
--

LOCK TABLES `products_inventoryrestockrequest` WRITE;
/*!40000 ALTER TABLE `products_inventoryrestockrequest` DISABLE KEYS */;
/*!40000 ALTER TABLE `products_inventoryrestockrequest` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `products_product`
--

DROP TABLE IF EXISTS `products_product`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `products_product` (
  `id` bigint NOT NULL AUTO_INCREMENT,
  `sku` varchar(32) COLLATE utf8mb4_unicode_ci NOT NULL,
  `slug` varchar(140) COLLATE utf8mb4_unicode_ci NOT NULL,
  `name` varchar(120) COLLATE utf8mb4_unicode_ci NOT NULL,
  `category` varchar(16) COLLATE utf8mb4_unicode_ci NOT NULL,
  `description` varchar(500) COLLATE utf8mb4_unicode_ci NOT NULL,
  `price` decimal(10,2) NOT NULL,
  `image` varchar(100) COLLATE utf8mb4_unicode_ci NOT NULL,
  `is_available` tinyint(1) NOT NULL,
  `is_featured` tinyint(1) NOT NULL,
  `calories` smallint unsigned NOT NULL,
  `protein` decimal(6,2) NOT NULL,
  `carbs` decimal(6,2) NOT NULL,
  `fat` decimal(6,2) NOT NULL,
  `ingredients` longtext COLLATE utf8mb4_unicode_ci NOT NULL,
  `allergens` varchar(250) COLLATE utf8mb4_unicode_ci NOT NULL,
  `serving` varchar(80) COLLATE utf8mb4_unicode_ci NOT NULL,
  `created_at` datetime(6) NOT NULL,
  `updated_at` datetime(6) NOT NULL,
  `low_stock_threshold` int unsigned NOT NULL,
  `stock_quantity` int unsigned DEFAULT NULL,
  `expiry_date` date DEFAULT NULL,
  `shipping_weight_grams` int unsigned NOT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `sku` (`sku`),
  UNIQUE KEY `slug` (`slug`),
  KEY `products_pr_categor_f9fe54_idx` (`category`,`is_available`),
  KEY `products_pr_is_feat_ce1607_idx` (`is_featured`,`is_available`),
  CONSTRAINT `product_inventory_only_for_dry_goods` CHECK (((`category` = _utf8mb4'dry_goods') or (`stock_quantity` is null))),
  CONSTRAINT `products_product_chk_1` CHECK ((`calories` >= 0)),
  CONSTRAINT `products_product_chk_2` CHECK ((`low_stock_threshold` >= 0)),
  CONSTRAINT `products_product_chk_3` CHECK ((`stock_quantity` >= 0)),
  CONSTRAINT `products_product_chk_4` CHECK ((`shipping_weight_grams` >= 0))
) ENGINE=InnoDB AUTO_INCREMENT=4 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `products_product`
--

LOCK TABLES `products_product` WRITE;
/*!40000 ALTER TABLE `products_product` DISABLE KEYS */;
INSERT INTO `products_product` VALUES (1,'wh111','whey','Whey','drink','Phù hợp mọi lứa tuổi',200000.00,'products/2026/11/Word_sheet_preview.png',1,1,100,100.00,100.00,200.00,'','','','2026-11-15 16:55:56.977160','2026-11-17 05:31:05.735951',5,NULL,NULL,0),(2,'protein111','protein','Thanh năng lượng protein','dry_goods','khj',100000.00,'products/2026/11/Word_sheet_preview_lJTbqJ7.png',1,0,9997,1000.00,1000.00,1000.00,'ikh','kh','đạm','2026-11-16 08:02:25.043662','2026-11-17 16:58:14.564776',5,99997,NULL,5),(3,'FM-1C254F859E','bot-whey-ngu-vi-1c254f859e','Bột Whey ngũ vị','dry_goods','Ngon',2000000.00,'products/2026/11/images_X1urnOh.jfif',1,1,13,0.13,0.18,0.12,'cab','không có','500','2026-11-16 11:39:19.411429','2026-11-17 09:33:00.827803',5,50,'2026-11-30',500);
/*!40000 ALTER TABLE `products_product` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `products_productactivity`
--

DROP TABLE IF EXISTS `products_productactivity`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `products_productactivity` (
  `id` bigint NOT NULL AUTO_INCREMENT,
  `product_name` varchar(120) COLLATE utf8mb4_unicode_ci NOT NULL,
  `product_sku` varchar(32) COLLATE utf8mb4_unicode_ci NOT NULL,
  `action` varchar(24) COLLATE utf8mb4_unicode_ci NOT NULL,
  `old_value` varchar(120) COLLATE utf8mb4_unicode_ci NOT NULL,
  `new_value` varchar(120) COLLATE utf8mb4_unicode_ci NOT NULL,
  `created_at` datetime(6) NOT NULL,
  `actor_id` bigint DEFAULT NULL,
  `product_id` bigint DEFAULT NULL,
  PRIMARY KEY (`id`),
  KEY `products_productactivity_actor_id_fa614399_fk_accounts_user_id` (`actor_id`),
  KEY `products_productacti_product_id_75aa9062_fk_products_` (`product_id`),
  KEY `products_pr_action_4be722_idx` (`action`,`created_at`),
  CONSTRAINT `products_productacti_product_id_75aa9062_fk_products_` FOREIGN KEY (`product_id`) REFERENCES `products_product` (`id`),
  CONSTRAINT `products_productactivity_actor_id_fa614399_fk_accounts_user_id` FOREIGN KEY (`actor_id`) REFERENCES `accounts_user` (`id`)
) ENGINE=InnoDB AUTO_INCREMENT=64 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `products_productactivity`
--

LOCK TABLES `products_productactivity` WRITE;
/*!40000 ALTER TABLE `products_productactivity` DISABLE KEYS */;
INSERT INTO `products_productactivity` VALUES (1,'Thanh năng lượng protein','protein111','created','','100000.00','2026-11-16 08:02:25.045765',7,2),(2,'Thanh năng lượng protein','protein111','inventory_changed','','100000 · ngưỡng 5','2026-11-16 08:02:25.047190',7,2),(3,'Whey','wh111','availability_changed','Đang bán','Tạm ngưng','2026-11-16 10:19:06.208055',5,1),(4,'Bột Whey ngũ vị','FM-1C254F859E','created','','2000000.00','2026-11-16 11:39:19.413201',7,3),(5,'Bột Whey ngũ vị','FM-1C254F859E','inventory_changed','','15 · ngưỡng 5','2026-11-16 11:39:19.413714',7,3),(6,'Bột Whey ngũ vị','FM-1C254F859E','inventory_changed','15 · ngưỡng 5','14 · ngưỡng 5','2026-11-16 15:05:43.946964',7,3),(7,'Bột Whey ngũ vị','FM-1C254F859E','inventory_changed','14','13','2026-11-16 16:49:37.836599',6,3),(8,'Thanh năng lượng protein','protein111','inventory_changed','100000','99999','2026-11-16 16:56:27.022454',6,2),(9,'Bột Whey ngũ vị','FM-1C254F859E','inventory_changed','13','4','2026-11-16 17:04:40.300897',6,3),(10,'Bột Whey ngũ vị','FM-1C254F859E','inventory_changed','4','1','2026-11-16 17:18:35.051081',6,3),(11,'Whey','wh111','availability_changed','Tạm ngưng','Đang bán','2026-11-16 17:37:44.441582',5,1),(12,'Bột Whey ngũ vị','FM-1C254F859E','inventory_changed','1 · ngưỡng 5','50 · ngưỡng 5','2026-11-16 17:57:02.308151',7,3),(13,'Whey','wh111','availability_changed','Đang bán','Tạm ngưng','2026-11-16 17:58:39.868027',5,1),(14,'Whey','wh111','availability_changed','Tạm ngưng','Đang bán','2026-11-16 17:58:41.559961',5,1),(15,'Whey','wh111','availability_changed','Đang bán','Tạm ngưng','2026-11-16 17:59:14.606897',5,1),(16,'Bột Whey ngũ vị','FM-1C254F859E','availability_changed','Đang bán','Tạm ngưng','2026-11-16 17:59:15.621554',5,3),(17,'Thanh năng lượng protein','protein111','availability_changed','Đang bán','Tạm ngưng','2026-11-16 17:59:16.551865',5,2),(18,'Whey','wh111','availability_changed','Tạm ngưng','Đang bán','2026-11-17 05:31:05.737150',5,1),(19,'Bột Whey ngũ vị','FM-1C254F859E','availability_changed','Tạm ngưng','Đang bán','2026-11-17 05:31:06.850358',5,3),(20,'Thanh năng lượng protein','protein111','availability_changed','Tạm ngưng','Đang bán','2026-11-17 05:31:07.988813',5,2),(21,'Thanh năng lượng protein','protein111','inventory_changed','99999','99998','2026-11-17 07:39:53.160934',6,2),(22,'Thanh năng lượng protein','protein111','inventory_changed','99998','99999','2026-11-17 07:57:35.173036',NULL,2),(23,'Thanh năng lượng protein','protein111','inventory_changed','99999','99998','2026-11-17 07:57:35.212027',6,2),(24,'Thanh năng lượng protein','protein111','inventory_changed','99998','99999','2026-11-17 08:19:28.138195',NULL,2),(25,'Thanh năng lượng protein','protein111','inventory_changed','99999','99998','2026-11-17 08:19:28.176888',6,2),(26,'Thanh năng lượng protein','protein111','inventory_changed','99998','99997','2026-11-17 08:32:10.379139',6,2),(27,'Thanh năng lượng protein','protein111','inventory_changed','99997','99998','2026-11-17 08:48:26.517433',NULL,2),(28,'Thanh năng lượng protein','protein111','inventory_changed','99998','99997','2026-11-17 08:48:49.781407',6,2),(29,'Thanh năng lượng protein','protein111','inventory_changed','99997','99996','2026-11-17 08:57:36.506009',6,2),(30,'Thanh năng lượng protein','protein111','inventory_changed','99996','99997','2026-11-17 09:03:52.169543',NULL,2),(31,'Thanh năng lượng protein','protein111','inventory_changed','99997','99998','2026-11-17 09:12:37.162549',NULL,2),(32,'Bột Whey ngũ vị','FM-1C254F859E','inventory_changed','50','49','2026-11-17 09:31:41.220650',6,3),(33,'Thanh năng lượng protein','protein111','inventory_changed','99998','99997','2026-11-17 09:31:57.297250',6,2),(34,'Thanh năng lượng protein','protein111','inventory_changed','99997','99998','2026-11-17 09:32:59.731856',7,2),(35,'Bột Whey ngũ vị','FM-1C254F859E','inventory_changed','49','50','2026-11-17 09:33:00.828453',7,3),(62,'Thanh năng lượng protein','protein111','inventory_changed','99998','99997','2026-11-17 16:58:14.570978',8,2);
/*!40000 ALTER TABLE `products_productactivity` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `socialaccount_socialaccount`
--

DROP TABLE IF EXISTS `socialaccount_socialaccount`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `socialaccount_socialaccount` (
  `id` int NOT NULL AUTO_INCREMENT,
  `provider` varchar(200) COLLATE utf8mb4_unicode_ci NOT NULL,
  `uid` varchar(191) COLLATE utf8mb4_unicode_ci NOT NULL,
  `last_login` datetime(6) NOT NULL,
  `date_joined` datetime(6) NOT NULL,
  `extra_data` json NOT NULL,
  `user_id` bigint NOT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `socialaccount_socialaccount_provider_uid_fc810c6e_uniq` (`provider`,`uid`),
  KEY `socialaccount_socialaccount_user_id_8146e70c_fk_accounts_user_id` (`user_id`),
  CONSTRAINT `socialaccount_socialaccount_user_id_8146e70c_fk_accounts_user_id` FOREIGN KEY (`user_id`) REFERENCES `accounts_user` (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `socialaccount_socialaccount`
--

LOCK TABLES `socialaccount_socialaccount` WRITE;
/*!40000 ALTER TABLE `socialaccount_socialaccount` DISABLE KEYS */;
/*!40000 ALTER TABLE `socialaccount_socialaccount` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `socialaccount_socialapp`
--

DROP TABLE IF EXISTS `socialaccount_socialapp`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `socialaccount_socialapp` (
  `id` int NOT NULL AUTO_INCREMENT,
  `provider` varchar(30) COLLATE utf8mb4_unicode_ci NOT NULL,
  `name` varchar(40) COLLATE utf8mb4_unicode_ci NOT NULL,
  `client_id` varchar(191) COLLATE utf8mb4_unicode_ci NOT NULL,
  `secret` varchar(191) COLLATE utf8mb4_unicode_ci NOT NULL,
  `key` varchar(191) COLLATE utf8mb4_unicode_ci NOT NULL,
  `provider_id` varchar(200) COLLATE utf8mb4_unicode_ci NOT NULL,
  `settings` json NOT NULL DEFAULT (_utf8mb4'{}'),
  PRIMARY KEY (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `socialaccount_socialapp`
--

LOCK TABLES `socialaccount_socialapp` WRITE;
/*!40000 ALTER TABLE `socialaccount_socialapp` DISABLE KEYS */;
/*!40000 ALTER TABLE `socialaccount_socialapp` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `socialaccount_socialtoken`
--

DROP TABLE IF EXISTS `socialaccount_socialtoken`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `socialaccount_socialtoken` (
  `id` int NOT NULL AUTO_INCREMENT,
  `token` longtext COLLATE utf8mb4_unicode_ci NOT NULL,
  `token_secret` longtext COLLATE utf8mb4_unicode_ci NOT NULL,
  `expires_at` datetime(6) DEFAULT NULL,
  `account_id` int NOT NULL,
  `app_id` int DEFAULT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `socialaccount_socialtoken_app_id_account_id_fca4e0ac_uniq` (`app_id`,`account_id`),
  KEY `socialaccount_social_account_id_951f210e_fk_socialacc` (`account_id`),
  CONSTRAINT `socialaccount_social_account_id_951f210e_fk_socialacc` FOREIGN KEY (`account_id`) REFERENCES `socialaccount_socialaccount` (`id`),
  CONSTRAINT `socialaccount_social_app_id_636a42d7_fk_socialacc` FOREIGN KEY (`app_id`) REFERENCES `socialaccount_socialapp` (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `socialaccount_socialtoken`
--

LOCK TABLES `socialaccount_socialtoken` WRITE;
/*!40000 ALTER TABLE `socialaccount_socialtoken` DISABLE KEYS */;
/*!40000 ALTER TABLE `socialaccount_socialtoken` ENABLE KEYS */;
UNLOCK TABLES;
/*!40103 SET TIME_ZONE=@OLD_TIME_ZONE */;

/*!40101 SET SQL_MODE=@OLD_SQL_MODE */;
/*!40014 SET FOREIGN_KEY_CHECKS=@OLD_FOREIGN_KEY_CHECKS */;
/*!40014 SET UNIQUE_CHECKS=@OLD_UNIQUE_CHECKS */;
/*!40101 SET CHARACTER_SET_CLIENT=@OLD_CHARACTER_SET_CLIENT */;
/*!40101 SET CHARACTER_SET_RESULTS=@OLD_CHARACTER_SET_RESULTS */;
/*!40101 SET COLLATION_CONNECTION=@OLD_COLLATION_CONNECTION */;
/*!40111 SET SQL_NOTES=@OLD_SQL_NOTES */;

-- Dump completed
