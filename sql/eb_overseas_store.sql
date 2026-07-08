/*
 Navicat Premium Data Transfer

 Source Server         : 财务
 Source Server Type    : MySQL
 Source Server Version : 80013
 Source Host           : pc-2ze310c8v8184x0r5.rwlb.rds.aliyuncs.com:3306
 Source Schema         : ads_finance

 Target Server Type    : MySQL
 Target Server Version : 80013
 File Encoding         : 65001

 Date: 08/07/2026 09:54:33
*/

SET NAMES utf8mb4;
SET FOREIGN_KEY_CHECKS = 0;

-- ----------------------------
-- Table structure for eb_overseas_store
-- ----------------------------
DROP TABLE IF EXISTS `eb_overseas_store`;
CREATE TABLE `eb_overseas_store`  (
  `id` int(11) NOT NULL AUTO_INCREMENT,
  `name` varchar(255) CHARACTER SET utf8mb4 COLLATE utf8mb4_general_ci NOT NULL COMMENT '店铺名称',
  `product_id` varchar(255) CHARACTER SET utf8mb4 COLLATE utf8mb4_general_ci NOT NULL COMMENT '项目',
  `region_id` tinyint(1) NOT NULL COMMENT '区域：',
  `platform_id` tinyint(1) NOT NULL DEFAULT 1 COMMENT '平台 ',
  `shop_code` varchar(255) CHARACTER SET utf8mb4 COLLATE utf8mb4_general_ci NOT NULL DEFAULT '' COMMENT '店铺唯一编码',
  `host` varchar(255) CHARACTER SET utf8mb4 COLLATE utf8mb4_general_ci NOT NULL DEFAULT '' COMMENT '店铺网站域名',
  `account_id` int(11) NOT NULL DEFAULT 0 COMMENT '账户id',
  `browser_oauth` varchar(255) CHARACTER SET utf8mb4 COLLATE utf8mb4_general_ci NOT NULL DEFAULT '' COMMENT ' 浏览器里店铺的标识',
  `status` tinyint(1) NOT NULL DEFAULT 1 COMMENT '1:正常 2：已删除 3:关闭所有订单',
  `manage_order` tinyint(1) NOT NULL DEFAULT 1 COMMENT '管理订单 1:打开 0：关闭',
  `manage_return` tinyint(1) NOT NULL DEFAULT 1 COMMENT '退货订单 1:打开 0：关闭',
  `affiliate_creator` tinyint(1) NOT NULL DEFAULT 1 COMMENT ' 1:打开 0：关闭 达人订单',
  `affiliate_partner` tinyint(1) NOT NULL DEFAULT 1 COMMENT ' 1:打开 0：关闭 联盟服务商订单',
  `finance_statements` tinyint(1) NOT NULL DEFAULT 1 COMMENT ' 1:打开 0：关闭 结算单',
  `finance_on_hold` tinyint(1) NOT NULL DEFAULT 1 COMMENT ' 1:打开 0：关闭 未结算单',
  `ad` tinyint(1) NOT NULL DEFAULT 0 COMMENT ' 1:打开 0：关闭 广告费',
  `balance` tinyint(1) NOT NULL DEFAULT 0 COMMENT '1:打开 0：关闭  到账资金',
  PRIMARY KEY (`id`) USING BTREE
) ENGINE = InnoDB AUTO_INCREMENT = 50 CHARACTER SET = utf8mb4 COLLATE = utf8mb4_general_ci ROW_FORMAT = Dynamic;

-- ----------------------------
-- Records of eb_overseas_store
-- ----------------------------
INSERT INTO `eb_overseas_store` VALUES (1, 'HKKA美国accu店铺', '5', 14, 16, 'USUSLCGMEK63', 'seller-us.tiktok.com', 131, 'N+JOP3yzsac+ZhUM2xOVlw==', 1, 1, 1, 1, 1, 1, 1, 0, 0);
INSERT INTO `eb_overseas_store` VALUES (2, '香港海卓保健品主体', '5', 14, 16, 'HKUSCBHLEL8Y', 'seller.us.tiktokshopglobalselling.com', 131, 'WcoCCVP5NwNXbYOSM6Zlzg==', 3, 1, 1, 1, 1, 1, 1, 0, 0);
INSERT INTO `eb_overseas_store` VALUES (3, '平衡贴美国本土店铺', '5', 14, 16, 'USLCQPEV3N', 'seller-us.tiktok.com', 131, 'zPaHir05mtQ+ZBTfaZxwMQ==', 1, 1, 1, 1, 1, 1, 1, 0, 0);
INSERT INTO `eb_overseas_store` VALUES (4, '润博美妆个护', '5', 14, 16, 'CNUSCBH6ELNM', 'seller.us.tiktokshopglobalselling.com', 131, 'buXR4Eg20LO6FZ4LPKI8Ww==', 1, 1, 1, 0, 0, 1, 1, 0, 0);
INSERT INTO `eb_overseas_store` VALUES (5, '宠物星链跨境店manysun', '5', 14, 16, '', '', 131, '2s/iMJTXB1r/vOAfY58dww==', 3, 0, 0, 0, 0, 0, 0, 0, 0);
INSERT INTO `eb_overseas_store` VALUES (6, 'Tik Tok-OLZZ Cosmetic.PH', '3', 9, 16, 'PHLCDRL2UT', 'seller-ph.tiktok.com', 132, 'kzxlTOiJOxvVpKmbS9Y/Tw==', 3, 1, 1, 1, 1, 1, 1, 0, 0);
INSERT INTO `eb_overseas_store` VALUES (7, 'Tik Tok-OLZZ Beauty.PH', '3', 9, 16, 'PHLCERL2G4', 'seller-ph.tiktok.com', 132, 'sKO3yttuQfYFQAtC/TjAjQ==', 1, 1, 1, 1, 1, 1, 1, 0, 0);
INSERT INTO `eb_overseas_store` VALUES (8, 'OLZZ BEAUTY 2', '3', 9, 16, 'PHLC3TL23F', 'seller-ph.tiktok.com', 132, 'qBUzO9f1qMvsHn/ButNvJQ==', 1, 1, 1, 1, 1, 1, 1, 0, 0);
INSERT INTO `eb_overseas_store` VALUES (9, 'OLZZ BEAUTY 1', '3', 9, 16, 'PHLCETL2QC', 'seller-ph.tiktok.com', 132, 'QPeA+LqUTwg5fQbKKb24BA==', 1, 1, 1, 1, 1, 1, 1, 0, 0);
INSERT INTO `eb_overseas_store` VALUES (10, 'MY-hkka跨境', '1', 8, 16, 'CNMYCB46LHVQ', 'seller.tiktokshopglobalselling.com', 133, 'H8Xrx2hwfWWU44SEUqQb5g==', 1, 1, 1, 1, 1, 1, 1, 0, 0);
INSERT INTO `eb_overseas_store` VALUES (11, 'TikTok shop o l z z马来子账号', '1', 8, 16, 'MYLCEWL2FT', 'seller-my.tiktok.com', 133, 'cxn9ejq8cEXu5XLD+IZk6A==', 1, 1, 1, 1, 1, 1, 1, 0, 0);
INSERT INTO `eb_overseas_store` VALUES (12, 'TikTok MY Olzz主账号', '1', 8, 16, 'MYLCEWL2FT', 'seller-my.tiktok.com', 133, 'wjBPxcaIpdUnU/AaJF6Wuw==', 1, 1, 1, 1, 1, 1, 1, 0, 0);
INSERT INTO `eb_overseas_store` VALUES (13, 'tidora-mx', '6', 14, 16, 'MXMXLCVFLL4L', 'seller-mx.tiktok.com', 134, 'HxnB1Dv74vANsCE6id6FDQ==', 3, 1, 1, 1, 1, 1, 1, 0, 0);
INSERT INTO `eb_overseas_store` VALUES (14, '店铺2 自运营', '6', 14, 16, 'USUSLCQ2EQ3X', 'seller-us.tiktok.com', 134, 'msTnSsIvy0MhhxiO+bay4g==', 3, 1, 1, 0, 0, 1, 1, 0, 0);
INSERT INTO `eb_overseas_store` VALUES (15, '店铺1', '6', 14, 16, 'USUSLCU3EPRV', 'seller-us.tiktok.com', 134, 'T9q7eda8QqV5unuHKMqOZA==', 3, 1, 1, 0, 0, 1, 1, 0, 0);
INSERT INTO `eb_overseas_store` VALUES (16, '印尼自注册TTS企业店-财务', '7', 15, 16, 'IDIDLCF7PLWCU', 'seller-id.tokopedia.com', 136, '3286246', 1, 1, 1, 0, 0, 1, 1, 0, 0);
INSERT INTO `eb_overseas_store` VALUES (17, 'SK-孙刊-财务-洗发水', '7', 15, 16, 'IDIDLCPW7LWU3', 'seller-id.tokopedia.com', 136, '2890008', 1, 1, 1, 1, 1, 1, 1, 0, 0);
INSERT INTO `eb_overseas_store` VALUES (18, 'Shopee-OLZZ Beauty.PH', '3', 9, 24, 'p8eicngmk1', 'seller.shopee.ph', 132, 'YP04DS0OXWgBYQRh5Vp7Xg==', 1, 1, 0, 0, 0, 0, 0, 1, 0);
INSERT INTO `eb_overseas_store` VALUES (19, 'Shopee-OLZZ Cosmetic.PH', '3', 9, 24, '1ncozmvm46', 'seller.shopee.ph', 132, '98fk/Bb7sKOe+QAkFmmtzg==', 1, 1, 0, 0, 0, 0, 0, 1, 0);
INSERT INTO `eb_overseas_store` VALUES (20, 'shopee-OLZZ BEAUTY 3', '3', 9, 24, 'rc2s004mlg', 'seller.shopee.ph', 132, 'u9ewKXj3f0OkKhXBZWRuPA==', 1, 1, 0, 0, 0, 0, 0, 1, 0);
INSERT INTO `eb_overseas_store` VALUES (21, 'shopee-OLZZ BEAUTY 2', '3', 9, 24, '6yykh7ovhs', 'seller.shopee.ph', 132, 'qojXd7h/RjCEzqr9MdTGXQ==', 1, 1, 0, 0, 0, 0, 0, 1, 0);
INSERT INTO `eb_overseas_store` VALUES (22, 'shopee-OLZZ BEAUTY 1', '3', 9, 24, 'l51cv50g84', 'seller.shopee.ph', 132, 'hYiKj7t6ILtOGwzpF1ZAcw==', 1, 1, 0, 0, 0, 0, 0, 1, 0);
INSERT INTO `eb_overseas_store` VALUES (23, 'HKKA-虾皮', '1', 8, 24, 'hkka_store', 'seller.shopee.com.my', 133, 'fPuFgWZCXVVkUN2390grXA==', 1, 1, 0, 0, 0, 0, 0, 1, 0);
INSERT INTO `eb_overseas_store` VALUES (24, '马来本土2店', '1', 8, 24, 'olzz_mall', 'seller.shopee.com.my', 133, 'JMPpE42+iAMio9eTdNMRJw==', 1, 1, 0, 0, 0, 0, 0, 1, 0);
INSERT INTO `eb_overseas_store` VALUES (25, 'Myolzz shopee1店', '1', 8, 24, 'olzz_beauty', 'seller.shopee.com.my', 133, 'hIdTqGlqURBA21yKO5W75A==', 1, 1, 0, 0, 0, 0, 0, 1, 0);
INSERT INTO `eb_overseas_store` VALUES (26, '海卓-虾皮', '2', 10, 24, 'HAIZHUOGROUP:main', 'seller.shopee.cn', 139, '2744516', 1, 1, 0, 0, 0, 0, 0, 1, 0);
INSERT INTO `eb_overseas_store` VALUES (27, 'HKKA-VN-Shopee', '2', 10, 24, 'hkka_vn', 'banhang.shopee.vn', 139, '2731989', 1, 1, 0, 0, 0, 0, 0, 1, 0);
INSERT INTO `eb_overseas_store` VALUES (28, 'shoppe-1', '3', 9, 24, 'o44klmaie_', 'seller.shopee.ph', 140, '1808732', 1, 1, 0, 0, 0, 0, 0, 1, 0);
INSERT INTO `eb_overseas_store` VALUES (29, 'Lazada-OLZZ Cosmetic.PH', '3', 9, 27, '501532592728', 'sellercenter.lazada.com.ph', 132, '//HXZhJb8sxZcFIPqQNVwA==', 1, 1, 0, 0, 0, 1, 0, 1, 1);
INSERT INTO `eb_overseas_store` VALUES (30, 'Lazada-OLZZ Beauty.PH', '3', 9, 27, '501533072630', 'sellercenter.lazada.com.ph', 132, '2kON+3rjkXQIpcqfVT0gXA==', 1, 1, 0, 0, 0, 1, 0, 1, 1);
INSERT INTO `eb_overseas_store` VALUES (31, 'olzz lazada', '1', 8, 27, '300814704010', 'sellercenter.lazada.com.my', 133, 'H2e3ppmHJSWV2TnXX/10FQ==', 1, 1, 0, 0, 0, 1, 0, 1, 1);
INSERT INTO `eb_overseas_store` VALUES (32, 'HKKA Body Care-MY', '2', 8, 16, 'CNMYCBY8LTTJ', 'seller.tiktokshopglobalselling.com', 159, 'Malaysia', 1, 1, 1, 0, 0, 1, 1, 0, 0);
INSERT INTO `eb_overseas_store` VALUES (33, 'HKKA Body Care-PH', '2', 9, 16, 'CNPHCBE6LTY3', 'seller.tiktokshopglobalselling.com', 159, 'Philippines', 1, 1, 1, 0, 0, 1, 1, 0, 0);
INSERT INTO `eb_overseas_store` VALUES (34, 'HKKA Body Care-SG', '2', 12, 16, 'CNSGCBAXLTP3', 'seller.tiktokshopglobalselling.com', 159, 'Singapore', 1, 1, 1, 0, 0, 1, 1, 0, 0);
INSERT INTO `eb_overseas_store` VALUES (35, 'HKKA Body Care-TH', '2', 13, 16, 'HKTHCBAWLLWM', 'seller.tiktokshopglobalselling.com', 159, 'Thailand', 1, 1, 1, 0, 0, 1, 1, 0, 0);
INSERT INTO `eb_overseas_store` VALUES (36, 'HKKA Body Care-VN', '2', 10, 16, 'CNVNCBWVLTKD', 'seller.tiktokshopglobalselling.com', 159, 'Vietnam', 1, 1, 1, 0, 0, 1, 1, 0, 0);
INSERT INTO `eb_overseas_store` VALUES (37, 'UQB Body Care-MY', '2', 8, 16, 'HKMYCB9WLLHW', 'seller.tiktokshopglobalselling.com', 158, 'Malaysia', 1, 1, 1, 0, 0, 1, 1, 0, 0);
INSERT INTO `eb_overseas_store` VALUES (38, 'UQB Body Care-PH', '2', 9, 16, 'HKPHCBQWLLHB', 'seller.tiktokshopglobalselling.com', 158, 'Philippines', 1, 1, 1, 0, 0, 1, 1, 0, 0);
INSERT INTO `eb_overseas_store` VALUES (39, 'UQB Body Care-SG', '2', 12, 16, 'HKSGCB9WLLH2', 'seller.tiktokshopglobalselling.com', 158, 'Singapore', 1, 1, 1, 0, 0, 1, 1, 0, 0);
INSERT INTO `eb_overseas_store` VALUES (40, 'UQB Body Care-TH', '2', 13, 16, 'HKTHCB9WLLHL', 'seller.tiktokshopglobalselling.com', 158, 'Thailand', 1, 1, 1, 0, 0, 1, 1, 0, 0);
INSERT INTO `eb_overseas_store` VALUES (41, 'UQB Body Care-VN', '2', 10, 16, 'HKVNCB7WLLHM', 'seller.tiktokshopglobalselling.com', 158, 'Vietnam', 1, 1, 1, 0, 0, 1, 1, 0, 0);
INSERT INTO `eb_overseas_store` VALUES (42, 'Beauty-SHOP-MY', '2', 8, 16, 'CNMYCB3YLTPK', 'seller.tiktokshopglobalselling.com', 157, 'Malaysia', 1, 1, 1, 1, 1, 1, 1, 0, 0);
INSERT INTO `eb_overseas_store` VALUES (44, 'HKKA-SHOP-SG', '2', 12, 16, 'CNSGCBVTLTMB', 'seller.tiktokshopglobalselling.com', 157, 'Singapore', 1, 1, 1, 1, 1, 1, 1, 0, 0);
INSERT INTO `eb_overseas_store` VALUES (45, 'HKKA-SHOP-TH', '2', 13, 16, 'CNTHCB4QLYWT', 'seller.tiktokshopglobalselling.com', 157, 'Thailand', 1, 1, 1, 1, 1, 1, 1, 0, 0);
INSERT INTO `eb_overseas_store` VALUES (46, 'HKKA-SHOP-VN', '2', 10, 16, 'CNVNCBL2LTSW', 'seller.tiktokshopglobalselling.com', 157, 'Vietnam', 1, 1, 1, 1, 1, 1, 1, 0, 0);
INSERT INTO `eb_overseas_store` VALUES (47, 'Herbi Care', '2', 10, 16, 'CNVNCBYBLH9B', 'seller.tiktokshopglobalselling.com', 156, 'Vietnam', 1, 1, 1, 1, 1, 1, 1, 0, 0);
INSERT INTO `eb_overseas_store` VALUES (48, 'HKKA-2', '2', 10, 16, 'VNLC67LW3F', 'seller-vn.tiktok.com', 139, '2534419', 1, 1, 1, 1, 1, 1, 1, 0, 0);
INSERT INTO `eb_overseas_store` VALUES (49, 'HKKA-1', '2', 10, 16, 'VNLC67LW3C', 'seller-vn.tiktok.com', 139, '2234732', 1, 1, 1, 1, 1, 1, 1, 0, 0);

SET FOREIGN_KEY_CHECKS = 1;
