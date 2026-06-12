/*
 Navicat Premium Data Transfer

 Source Server         : 智慧公交
 Source Server Type    : MySQL
 Source Server Version : 80045 (8.0.45)
 Source Host           : 172.31.210.57:16336
 Source Schema         : busx_tms

 Target Server Type    : MySQL
 Target Server Version : 80045 (8.0.45)
 File Encoding         : 65001

 Date: 02/06/2026 11:20:09
*/

SET NAMES utf8mb4;
SET FOREIGN_KEY_CHECKS = 0;

-- ----------------------------
-- Table structure for bus_apk_dispatch_task
-- ----------------------------
DROP TABLE IF EXISTS `bus_apk_dispatch_task`;
CREATE TABLE `bus_apk_dispatch_task`  (
  `id` bigint NOT NULL AUTO_INCREMENT COMMENT '主键',
  `task_no` varchar(32) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci NOT NULL COMMENT '任务编号',
  `target_version_id` bigint NOT NULL COMMENT '目标APK版本ID',
  `target_version_no` varchar(32) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci NULL DEFAULT NULL COMMENT '目标版本号(冗余)',
  `scope` varchar(20) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci NOT NULL COMMENT '下发范围:specified/all',
  `target_devices_json` longtext CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci NULL COMMENT '目标设备ID列表JSON',
  `effective_time` datetime NULL DEFAULT NULL COMMENT '生效起始时间',
  `status` varchar(20) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci NULL DEFAULT 'pending' COMMENT '状态:pending/rejected/dispatching/completed/partial_failed',
  `audit_remark` varchar(500) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci NULL DEFAULT NULL COMMENT '审核/驳回意见',
  `audit_by` varchar(64) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci NULL DEFAULT NULL COMMENT '审核人',
  `audit_time` datetime NULL DEFAULT NULL COMMENT '审核时间',
  `success_cnt` int NULL DEFAULT 0 COMMENT '成功数量',
  `fail_cnt` int NULL DEFAULT 0 COMMENT '失败数量',
  `create_time` datetime NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
  `create_by` varchar(64) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci NULL DEFAULT NULL COMMENT '操作人',
  `update_time` datetime NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
  `update_by` varchar(64) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci NULL DEFAULT NULL COMMENT '更新人',
  `tenant_id` varchar(32) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci NULL DEFAULT NULL COMMENT '租户ID',
  `del_flag` varchar(1) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci NULL DEFAULT '0' COMMENT '删除标记',
  PRIMARY KEY (`id`) USING BTREE,
  UNIQUE INDEX `uk_badt_task_no`(`task_no` ASC) USING BTREE,
  INDEX `idx_badt_status`(`status` ASC) USING BTREE,
  INDEX `idx_badt_tenant`(`tenant_id` ASC) USING BTREE
) ENGINE = InnoDB AUTO_INCREMENT = 1 CHARACTER SET = utf8mb4 COLLATE = utf8mb4_0900_ai_ci COMMENT = 'APK程序下发任务表' ROW_FORMAT = DYNAMIC;

-- ----------------------------
-- Records of bus_apk_dispatch_task
-- ----------------------------

-- ----------------------------
-- Table structure for bus_apk_version
-- ----------------------------
DROP TABLE IF EXISTS `bus_apk_version`;
CREATE TABLE `bus_apk_version`  (
  `id` bigint NOT NULL AUTO_INCREMENT COMMENT '主键',
  `version_no` varchar(32) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci NOT NULL COMMENT '版本号(主.次.修订)',
  `file_url` varchar(512) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci NULL DEFAULT NULL COMMENT 'APK文件地址',
  `file_md5` varchar(64) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci NULL DEFAULT NULL COMMENT '文件MD5',
  `upgrade_policy` varchar(20) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci NULL DEFAULT 'recommend' COMMENT '升级策略:force/recommend',
  `status` varchar(20) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci NULL DEFAULT 'active' COMMENT '状态:active/deprecated',
  `release_note` varchar(1000) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci NULL DEFAULT NULL COMMENT '版本说明',
  `create_time` datetime NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
  `create_by` varchar(64) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci NULL DEFAULT NULL COMMENT '创建人',
  `update_time` datetime NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
  `update_by` varchar(64) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci NULL DEFAULT NULL COMMENT '更新人',
  `tenant_id` varchar(32) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci NULL DEFAULT NULL COMMENT '租户ID',
  `del_flag` varchar(1) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci NULL DEFAULT '0' COMMENT '删除标记',
  PRIMARY KEY (`id`) USING BTREE,
  UNIQUE INDEX `uk_bav_tenant_version`(`tenant_id` ASC, `version_no` ASC, `del_flag` ASC) USING BTREE,
  INDEX `idx_bav_status`(`status` ASC) USING BTREE
) ENGINE = InnoDB AUTO_INCREMENT = 1 CHARACTER SET = utf8mb4 COLLATE = utf8mb4_0900_ai_ci COMMENT = 'APK版本表' ROW_FORMAT = DYNAMIC;

-- ----------------------------
-- Records of bus_apk_version
-- ----------------------------

-- ----------------------------
-- Table structure for bus_area
-- ----------------------------
DROP TABLE IF EXISTS `bus_area`;
CREATE TABLE `bus_area`  (
  `id` bigint NOT NULL AUTO_INCREMENT COMMENT '区域ID',
  `org_id` bigint NOT NULL COMMENT '机构ID',
  `dept_id` bigint NULL DEFAULT NULL COMMENT '部门ID（数据权限）',
  `org_name` varchar(100) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci NULL DEFAULT NULL COMMENT '机构名称',
  `name` varchar(50) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci NOT NULL COMMENT '区域名称',
  `code` varchar(20) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci NOT NULL COMMENT '区域编码',
  `type` varchar(20) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci NULL DEFAULT NULL COMMENT '区域类型',
  `status` varchar(20) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci NOT NULL DEFAULT 'pending' COMMENT '启用状态：pending-待审核，disabled-未启用，enabled-已启用，rejected-已驳回',
  `area_control` text CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci NULL COMMENT '地理围栏数据',
  `area_type` varchar(50) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci NULL DEFAULT NULL COMMENT '区域类型：服务区/限行区/站点覆盖区等',
  `city_code` varchar(64) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci NULL DEFAULT NULL COMMENT '城市编码',
  `city_name` varchar(100) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci NULL DEFAULT NULL COMMENT '城市名称',
  `area_shape` varchar(20) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci NULL DEFAULT NULL COMMENT '区域形状：circle-圆形，polygon-多边形',
  `area_points` text CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci NULL COMMENT '区域坐标点',
  `area_polygon` text CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci NULL COMMENT '多边形数据',
  `area_center` varchar(100) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci NULL DEFAULT NULL COMMENT '区域中心点',
  `area_radius` decimal(10, 2) NULL DEFAULT NULL COMMENT '区域半径(米)',
  `area_area` decimal(10, 2) NULL DEFAULT NULL COMMENT '区域面积(km²)',
  `nearest_station_distance` int NULL DEFAULT NULL COMMENT '最近站点距离(米)',
  `surrounding_station_distance` int NULL DEFAULT NULL COMMENT '周边站点距离(米)',
  `max_return_stops` int NULL DEFAULT NULL COMMENT '最大返程站点数',
  `time_rule` varchar(50) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci NULL DEFAULT NULL COMMENT '时间规则',
  `start_time` varchar(20) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci NULL DEFAULT NULL COMMENT '开始时间',
  `end_time` varchar(20) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci NULL DEFAULT NULL COMMENT '结束时间',
  `audit_status` varchar(20) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci NOT NULL DEFAULT 'pending' COMMENT '审核状态：pending-待审核，approved-审核通过，rejected-审核驳回',
  `audit_message` varchar(500) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci NULL DEFAULT NULL COMMENT '审核意见',
  `audit_user` varchar(50) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci NULL DEFAULT NULL COMMENT '审核人',
  `audit_time` datetime NULL DEFAULT NULL COMMENT '审核时间',
  `version` int NOT NULL DEFAULT 1 COMMENT '版本号',
  `is_deleted` tinyint(1) NOT NULL DEFAULT 0 COMMENT '是否删除：0-否，1-是',
  `create_time` datetime NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
  `create_by` varchar(50) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci NULL DEFAULT NULL COMMENT '创建人',
  `update_time` datetime NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
  `update_by` varchar(50) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci NULL DEFAULT NULL COMMENT '更新人',
  `tenant_id` varchar(20) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci NULL DEFAULT '000000' COMMENT '租户ID',
  PRIMARY KEY (`id`) USING BTREE,
  UNIQUE INDEX `uk_org_code`(`org_id` ASC, `code` ASC) USING BTREE,
  INDEX `idx_org_id`(`org_id` ASC) USING BTREE,
  INDEX `idx_name`(`name` ASC) USING BTREE,
  INDEX `idx_status`(`status` ASC) USING BTREE,
  INDEX `idx_audit_status`(`audit_status` ASC) USING BTREE,
  INDEX `idx_area_type`(`area_type` ASC) USING BTREE,
  INDEX `idx_create_time`(`create_time` ASC) USING BTREE
) ENGINE = InnoDB AUTO_INCREMENT = 228 CHARACTER SET = utf8mb4 COLLATE = utf8mb4_0900_ai_ci COMMENT = '运营区域表' ROW_FORMAT = DYNAMIC;

-- ----------------------------
-- Records of bus_area
-- ----------------------------
INSERT INTO `bus_area` VALUES (1, 1, NULL, '北京公交集团', '朝阳区服务区', 'BJ_CY_001', 'service', 'enabled', NULL, '服务区', NULL, NULL, 'polygon', NULL, '[[116.4,39.9],[116.5,39.9],[116.5,40.0],[116.4,40.0]]', '116.45,39.95', 5000.00, 25.50, 300, 500, 5, 'weekday', '06:00', '22:00', 'approved', NULL, NULL, NULL, 1, 1, '2026-03-29 15:57:35', 'admin', '2026-04-07 10:30:01', 'admin', '1');
INSERT INTO `bus_area` VALUES (2, 1, NULL, '北京公交集团', '海淀区服务区', 'BJ_HD_001', 'service', 'enabled', NULL, '服务区', NULL, NULL, 'polygon', NULL, '[[116.2,39.9],[116.3,39.9],[116.3,40.0],[116.2,40.0]]', '116.25,39.95', 4500.00, 20.25, 250, 450, 4, 'weekday', '06:00', '22:00', 'approved', NULL, NULL, NULL, 1, 1, '2026-03-29 15:57:35', 'admin', '2026-04-07 10:29:58', 'admin', '1');
INSERT INTO `bus_area` VALUES (3, 1, NULL, '北京公交集团', '东城区限行区', 'BJ_DC_001', 'restriction', 'disabled', NULL, '限行区', NULL, NULL, 'polygon', NULL, '[[116.3,39.8],[116.4,39.8],[116.4,39.9],[116.3,39.9]]', '116.35,39.85', 3000.00, 9.00, 200, 350, 3, 'all', '00:00', '23:59', 'approved', NULL, NULL, NULL, 1, 1, '2026-03-29 15:57:35', 'admin', '2026-04-07 10:29:55', 'admin', '1');
INSERT INTO `bus_area` VALUES (4, 2, NULL, '上海公交集团', '浦东新区服务区', 'SH_PD_001', 'service', 'pending', NULL, '服务区', NULL, NULL, 'polygon', NULL, '[[121.5,31.2],[121.6,31.2],[121.6,31.3],[121.5,31.3]]', '121.55,31.25', 6000.00, 36.00, 400, 600, 6, 'weekday', '06:00', '22:00', 'pending', NULL, NULL, NULL, 1, 1, '2026-03-29 15:57:35', 'admin', '2026-04-07 10:29:45', 'admin', '1');
INSERT INTO `bus_area` VALUES (5, 2, NULL, '上海公交集团', '黄浦区限行区', 'SH_HP_001', 'restriction', 'pending', NULL, '限行区', NULL, NULL, 'polygon', NULL, '[[121.4,31.2],[121.5,31.2],[121.5,31.3],[121.4,31.3]]', '121.45,31.25', 2500.00, 6.25, 150, 300, 2, 'all', '00:00', '23:59', 'pending', NULL, NULL, NULL, 1, 1, '2026-03-29 15:57:35', 'admin', '2026-04-07 10:29:41', 'admin', '1');
INSERT INTO `bus_area` VALUES (6, 1, NULL, NULL, '海珠区', 'GZ-HZ-001', 'residential', 'enabled', '', 'residential', 'GZ', '广州市', 'polygon', NULL, '', '', 0.00, 0.00, 300, 500, 5, 'weekday', '06:00', '22:00', 'approved', '通过', NULL, NULL, 2, 0, '2026-04-07 10:02:02', NULL, '2026-05-21 15:23:51', NULL, '1');
INSERT INTO `bus_area` VALUES (7, 1, NULL, NULL, '荔湾区', 'GZ-LW-001', 'residential', 'enabled', '', 'residential', 'GZ', '广州市', 'polygon', NULL, '[[113.235666,23.137072],[113.244507,23.134388],[113.24176,23.115997],[113.239443,23.110313],[113.232061,23.115997],[113.231374,23.124995],[113.230859,23.13352],[113.235323,23.137466]]', '113.237683,23.12389', 0.00, 2.98, 300, 500, 5, 'weekday', '06:00', '22:00', 'approved', '通过', NULL, NULL, 2, 0, '2026-04-07 10:33:08', NULL, '2026-05-21 15:23:51', NULL, '1');
INSERT INTO `bus_area` VALUES (8, 1, NULL, NULL, '越秀区', 'xxx', 'residential', 'enabled', '[[[113.25654,23.127726],[113.25787,23.126621],[113.257097,23.125398],[113.255982,23.12595]]]', 'residential', 'GZ', '广州市', 'polygon', NULL, '[[113.255124,23.130706],[113.261539,23.130686],[113.26199,23.125536],[113.254694,23.125299],[113.254716,23.125378]]', '113.258342,23.128003', 0.00, 0.41, 300, 500, 5, 'weekday', '06:00', '22:00', 'approved', '通过', NULL, NULL, 1, 0, '2026-04-08 10:17:33', NULL, '2026-05-21 15:23:51', NULL, '1');
INSERT INTO `bus_area` VALUES (9, 1, NULL, NULL, '模拟', 'x01', 'service', 'enabled', '', 'service', 'GZ', '广州市', 'polygon', NULL, '', '', 0.00, 0.00, 300, 500, 5, 'weekday', '06:00', '22:00', 'approved', '通过', NULL, NULL, 2, 0, '2026-04-24 15:56:46', NULL, '2026-05-21 15:23:51', NULL, '1');
INSERT INTO `bus_area` VALUES (10, 1, NULL, NULL, '天河区', '0001', 'administrative', 'disabled', '', 'administrative', 'GZ', '广州市', 'circle', NULL, '', '', 0.00, 0.00, 300, 500, 5, 'weekday', '06:00', '22:00', 'approved', '123', NULL, NULL, 3, 0, '2026-04-30 15:38:45', NULL, '2026-06-01 17:55:21', 'felix', '1');
INSERT INTO `bus_area` VALUES (11, 1, NULL, NULL, '天河体育中心', '15', 'service', 'enabled', '', 'service', 'GZ', '广州市', 'polygon', NULL, '[[116.366809,39.902479],[116.367238,39.902479],[116.373032,39.902939],[116.370296,39.904199],[116.366112,39.904149]]', '116.369572,39.903339', 0.00, 0.08, 300, 500, 5, 'weekday', '06:00', '22:00', 'approved', '审核通过', NULL, NULL, 5, 0, '2026-05-07 11:45:22', NULL, '2026-05-21 15:23:51', NULL, '1');
INSERT INTO `bus_area` VALUES (12, 1, NULL, NULL, '天河区123', '13465465', 'administrative', 'enabled', NULL, 'administrative', 'GZ', '广州市', 'polygon', NULL, NULL, NULL, 0.00, 0.00, 300, 500, 5, 'weekday', '06:00', '22:00', 'approved', '21312', NULL, NULL, 1, 0, '2026-05-13 14:12:52', NULL, '2026-05-21 15:23:51', NULL, '1');
INSERT INTO `bus_area` VALUES (13, 1, NULL, NULL, '创展中心区域', '20260513', 'service', 'enabled', NULL, 'service', 'GZ', '广州市', 'polygon', NULL, '[[113.321587,23.140969],[113.321373,23.129169],[113.32133,23.127748],[113.327896,23.127156],[113.333518,23.126919],[113.340513,23.126367],[113.347422,23.125933],[113.351499,23.124867],[113.352915,23.12467],[113.352958,23.125617],[113.352186,23.126169],[113.351585,23.132444],[113.353602,23.134931],[113.357164,23.137338],[113.358709,23.140337],[113.35961,23.144362],[113.359953,23.145152],[113.356821,23.145665],[113.35004,23.145112],[113.34386,23.145901],[113.338367,23.147717],[113.334376,23.1489],[113.330642,23.150163],[113.326222,23.152688],[113.322703,23.154464],[113.322188,23.155017],[113.320514,23.155608],[113.319527,23.154267],[113.315236,23.152333],[113.313519,23.151781],[113.312918,23.15186],[113.313648,23.147717],[113.314506,23.140337],[113.314506,23.140337]]', '113.336436,23.140139', 0.00, 9.59, 300, 500, 5, 'weekday', '06:00', '22:00', 'approved', '审核通过', NULL, NULL, 2, 0, '2026-05-13 15:23:16', NULL, '2026-05-21 15:23:51', NULL, '1');
INSERT INTO `bus_area` VALUES (14, 1, NULL, NULL, '1001区域', '04878', 'administrative', 'enabled', NULL, 'administrative', 'GZ', '广州市', 'polygon', NULL, '[[116.355805,39.924167],[116.373487,39.923969],[116.379752,39.921863],[116.391253,39.906853],[116.374602,39.907577],[116.357436,39.907182],[116.337438,39.907577],[116.345162,39.917452],[116.349883,39.924298]]', '116.364346,39.915576', 0.00, 20.45, 300, 500, 5, 'weekday', '06:00', '22:00', 'approved', '1', NULL, NULL, 2, 0, '2026-05-14 16:16:52', NULL, '2026-06-01 17:08:38', 'felix', '1');
INSERT INTO `bus_area` VALUES (15, 1, NULL, NULL, '石牌试点区', '580100000001', 'service', 'disabled', '', 'service', 'GZ', '广州市', 'polygon', NULL, '', '', 0.00, 0.00, 300, 500, 5, 'weekday', '06:00', '22:00', 'approved', '1', NULL, NULL, 2, 0, '2026-05-18 14:33:57', NULL, '2026-05-21 15:23:51', NULL, '1');
INSERT INTO `bus_area` VALUES (16, 1, NULL, NULL, '创展中心区域_复制', '20260513_COPY', 'service', 'enabled', NULL, 'service', 'GZ', '广州市', 'polygon', NULL, '[[113.304863,23.156723],[113.30213,23.124789],[113.382124,23.110264],[113.390192,23.151624],[113.31861,23.156832],[113.318438,23.15699]]', '113.346161,23.133627', 0.00, 35.59, 300, 500, 5, 'weekday', '06:00', '22:00', 'approved', '审核通过。', NULL, NULL, 2, 0, '2026-05-20 18:07:21', NULL, '2026-05-21 15:23:51', NULL, '1');
INSERT INTO `bus_area` VALUES (17, 1, NULL, NULL, '创展中心区域_复制_复制', '20260513_COPY_COPY', 'service', 'pending', NULL, 'service', 'GZ', '广州市', 'polygon', NULL, '[[113.304863,23.156723],[113.30213,23.124789],[113.382124,23.110264],[113.390192,23.151624],[113.31861,23.156832],[113.318438,23.15699]]', '113.346161,23.133627', 0.00, 35.59, 300, 500, 5, 'weekday', '06:00', '22:00', 'pending', NULL, NULL, NULL, 1, 0, '2026-05-22 11:05:09', NULL, '2026-05-22 11:05:04', NULL, '1');
INSERT INTO `bus_area` VALUES (18, 1, NULL, NULL, '天河体育中心_复制', '15_COPY', 'service', 'pending', NULL, 'service', 'GZ', '广州市', 'polygon', NULL, '[[116.366809,39.902479],[116.367238,39.902479],[116.373032,39.902939],[116.370296,39.904199],[116.366112,39.904149]]', '116.369572,39.903339', 0.00, 0.08, 300, 500, 5, 'weekday', '06:00', '22:00', 'pending', NULL, NULL, NULL, 1, 0, '2026-05-22 11:06:05', NULL, '2026-05-22 11:06:00', NULL, '1');
INSERT INTO `bus_area` VALUES (25, 1, NULL, NULL, '123123', '123123123213', 'service', 'enabled', '[[[113.269893,23.139647],[113.259937,23.121335],[113.338214,23.121966]]]', 'service', 'GZ', '广州市', 'polygon', NULL, '[[113.232299,23.152763],[113.235046,23.106667],[113.360015,23.106035],[113.368255,23.167598]]', '113.300277,23.136817', 0.00, 79.80, 300, 500, 5, 'weekday', '06:00', '22:00', 'approved', '123', NULL, NULL, 1, 1, '2026-05-26 11:07:07', NULL, '2026-05-28 16:17:11', NULL, '1');
INSERT INTO `bus_area` VALUES (201, 1, NULL, '广州公交集团', '天河核心区', 'GZ_TH_CORE', 'service', 'enabled', NULL, 'service', '440100', '广州市', 'polygon', NULL, '[[113.30,23.10],[113.35,23.10],[113.35,23.15],[113.30,23.15]]', '113.325,23.125', 5000.00, 25.00, NULL, NULL, NULL, 'weekday', '06:00', '22:00', 'approved', NULL, NULL, NULL, 1, 0, '2026-05-27 10:57:13', NULL, '2026-05-27 10:57:13', NULL, '1');
INSERT INTO `bus_area` VALUES (202, 1, NULL, '广州公交集团', '海珠滨江带', 'GZ_HZ_BIN', 'service', 'enabled', NULL, 'service', '440100', '广州市', 'polygon', NULL, '[[113.25,23.08],[113.30,23.08],[113.30,23.12],[113.25,23.12]]', '113.275,23.10', 4500.00, 20.00, NULL, NULL, NULL, 'all', '00:00', '23:59', 'approved', NULL, NULL, NULL, 1, 0, '2026-05-27 10:57:13', NULL, '2026-05-27 10:57:13', NULL, '1');
INSERT INTO `bus_area` VALUES (203, 1, NULL, '广州公交集团', '番禺大学城', 'GZ_PY_DXC', 'service', 'enabled', NULL, 'service', '440100', '广州市', 'polygon', NULL, '[[113.37,23.04],[113.41,23.04],[113.41,23.08],[113.37,23.08]]', '113.39,23.06', 6000.00, 32.00, NULL, NULL, NULL, 'weekday', '07:00', '21:00', 'approved', NULL, NULL, NULL, 1, 0, '2026-05-27 10:57:13', NULL, '2026-05-27 10:57:13', NULL, '1');
INSERT INTO `bus_area` VALUES (204, 1, NULL, '广州公交集团', '越秀老城区', 'GZ_YX_OLD', 'service', 'enabled', NULL, 'service', '440100', '广州市', 'polygon', NULL, '[[113.26,23.12],[113.28,23.12],[113.28,23.14],[113.26,23.14]]', '113.27,23.13', 3000.00, 8.00, NULL, NULL, NULL, 'all', '00:00', '23:59', 'approved', NULL, NULL, NULL, 1, 0, '2026-05-27 10:57:13', NULL, '2026-05-27 10:57:13', NULL, '1');
INSERT INTO `bus_area` VALUES (205, 1, NULL, '广州公交集团', '荔湾老西关', 'GZ_LW_XG', 'service', 'enabled', NULL, 'service', '440100', '广州市', 'polygon', NULL, '[[113.22,23.10],[113.25,23.10],[113.25,23.13],[113.22,23.13]]', '113.235,23.115', 3500.00, 12.00, NULL, NULL, NULL, 'weekday', '06:30', '21:30', 'approved', NULL, NULL, NULL, 1, 0, '2026-05-27 10:57:13', NULL, '2026-05-27 10:57:13', NULL, '1');
INSERT INTO `bus_area` VALUES (206, 1, NULL, '广州公交集团', '白云山风景区', 'GZ_BY_SCENIC', 'service', 'pending', NULL, 'service', '440100', '广州市', 'polygon', NULL, '[[113.28,23.16],[113.31,23.16],[113.31,23.20],[113.28,23.20]]', '113.295,23.18', 8000.00, 40.00, NULL, NULL, NULL, 'weekend', '08:00', '18:00', 'pending', NULL, NULL, NULL, 1, 0, '2026-05-27 10:57:13', NULL, '2026-05-27 10:57:13', NULL, '1');
INSERT INTO `bus_area` VALUES (207, 1, NULL, '广州公交集团', '黄埔开发区', 'GZ_HP_DEV', 'service', 'disabled', NULL, 'service', '440100', '广州市', 'polygon', NULL, '[[113.46,23.07],[113.52,23.07],[113.52,23.12],[113.46,23.12]]', '113.49,23.095', 7000.00, 35.00, NULL, NULL, NULL, 'weekday', '07:00', '20:00', 'rejected', NULL, NULL, NULL, 1, 0, '2026-05-27 10:57:13', NULL, '2026-05-27 10:57:13', NULL, '1');
INSERT INTO `bus_area` VALUES (208, 1, NULL, '广州公交集团', '南沙自贸区', 'GZ_NS_FTA', 'service', 'pending', NULL, 'service', '440100', '广州市', 'polygon', NULL, '[[113.52,22.75],[113.60,22.75],[113.60,22.82],[113.52,22.82]]', '113.56,22.785', 10000.00, 60.00, NULL, NULL, NULL, 'all', '00:00', '23:59', 'pending', NULL, NULL, NULL, 1, 0, '2026-05-27 10:57:13', NULL, '2026-05-27 10:57:13', NULL, '1');
INSERT INTO `bus_area` VALUES (209, 1, NULL, '广州公交集团', '增城新塘', 'GZ_ZC_XT', 'service', 'disabled', '', 'service', '440100', '广州市', 'polygon', NULL, '', '', 0.00, 0.00, NULL, NULL, NULL, 'weekday', '06:00', '22:00', 'pending', NULL, NULL, NULL, 3, 0, '2026-05-27 10:57:13', NULL, '2026-05-27 10:57:13', NULL, '1');
INSERT INTO `bus_area` VALUES (210, 1, NULL, '广州公交集团', '花都空港区', 'GZ_HD_AIR', 'service', 'enabled', NULL, 'service', '440100', '广州市', 'polygon', NULL, '[[113.18,23.38],[113.24,23.38],[113.24,23.44],[113.18,23.44]]', '113.21,23.41', 7500.00, 42.00, NULL, NULL, NULL, 'all', '00:00', '23:59', 'approved', NULL, NULL, NULL, 1, 0, '2026-05-27 10:57:13', NULL, '2026-05-27 10:57:13', NULL, '1');
INSERT INTO `bus_area` VALUES (211, 1, 1, NULL, '天河南街道', '123456789', 'station_cover', 'enabled', NULL, 'station_cover', NULL, NULL, 'polygon', NULL, NULL, NULL, 0.00, 30.00, 300, 500, 5, 'weekday', '06:00', '22:00', 'approved', '通过', NULL, NULL, 1, 1, '2026-05-28 14:11:27', NULL, '2026-05-28 14:22:25', NULL, '1');
INSERT INTO `bus_area` VALUES (212, 1, NULL, NULL, '天河南二路街道', '123456789_COPY', 'service', 'enabled', NULL, 'service', NULL, NULL, 'polygon', NULL, NULL, NULL, 0.00, 30.00, 300, 500, 5, 'weekday', '06:00', '22:00', 'approved', '12314', NULL, NULL, 2, 1, '2026-05-28 14:22:01', NULL, '2026-06-01 18:01:03', NULL, '1');
INSERT INTO `bus_area` VALUES (213, 1, 1, NULL, '宏发大厦', 'GZ_HD_HF', 'administrative', 'enabled', '', 'administrative', NULL, NULL, 'circle', NULL, '[[113.36852494137868,23.144696],[113.36667527595252,23.163475968231786],[113.3611973612791,23.18153423281635],[113.35230171054722,23.198176824772904],[113.34033017862582,23.212764178625825],[113.3257428247729,23.224735710547233],[113.30910023281635,23.233631361279095],[113.29104196823178,23.239109275952526],[113.272262,23.240958941378675],[113.25348203176821,23.239109275952526],[113.23542376718365,23.233631361279095],[113.2187811752271,23.224735710547233],[113.20419382137418,23.212764178625825],[113.19222228945277,23.198176824772904],[113.1833266387209,23.18153423281635],[113.17784872404748,23.163475968231786],[113.17599905862131,23.144696],[113.17784872404748,23.125916031768213],[113.1833266387209,23.10785776718365],[113.19222228945277,23.091215175227095],[113.20419382137418,23.076627821374174],[113.2187811752271,23.064656289452767],[113.23542376718365,23.055760638720905],[113.25348203176821,23.050282724047474],[113.272262,23.048433058621324],[113.29104196823178,23.050282724047474],[113.30910023281635,23.055760638720905],[113.3257428247729,23.064656289452767],[113.34033017862582,23.076627821374174],[113.35230171054722,23.091215175227095],[113.3611973612791,23.10785776718365],[113.36667527595252,23.125916031768213]]', '113.272262,23.144696', 10715.98, 360.76, 300, 500, 2, 'all', '15:00', '19:00', 'approved', '12321', NULL, NULL, 5, 1, '2026-05-28 14:52:28', NULL, '2026-06-01 18:01:08', NULL, '1');
INSERT INTO `bus_area` VALUES (214, 1, NULL, NULL, '宏发大厦_复制', 'GZ_HD_HF_COPY', 'administrative', 'pending', '', 'administrative', NULL, NULL, 'circle', NULL, '[[113.375246251313,23.164061],[113.37415271757713,23.175163834344996],[113.3709141402577,23.18583999299265],[113.36565497606487,23.195679197153403],[113.35857733172924,23.204303331729236],[113.34995319715341,23.211380976064873],[113.34011399299266,23.216640140257688],[113.329437834345,23.21987871757712],[113.318335,23.220972251313],[113.30723216565501,23.21987871757712],[113.29655600700735,23.216640140257688],[113.2867168028466,23.211380976064873],[113.27809266827077,23.204303331729236],[113.27101502393513,23.195679197153403],[113.26575585974231,23.18583999299265],[113.26251728242288,23.175163834344996],[113.26142374868701,23.164061],[113.26251728242288,23.152958165655004],[113.26575585974231,23.14228200700735],[113.27101502393513,23.132442802846597],[113.27809266827077,23.123818668270765],[113.2867168028466,23.116741023935127],[113.29655600700735,23.111481859742312],[113.30723216565501,23.10824328242288],[113.318335,23.107149748687],[113.329437834345,23.10824328242288],[113.34011399299266,23.111481859742312],[113.34995319715341,23.116741023935127],[113.35857733172924,23.123818668270765],[113.36565497606487,23.132442802846597],[113.3709141402577,23.14228200700735],[113.37415271757713,23.152958165655004]]', '113.318335,23.164061', 6335.35, 126.09, 300, 500, 2, 'weekend', '15:00', '19:00', 'pending', NULL, NULL, NULL, 5, 1, '2026-05-28 15:15:06', NULL, '2026-06-01 18:01:12', NULL, '1');
INSERT INTO `bus_area` VALUES (215, 1, 2059155512602853378, NULL, '123124', '124567', 'service', 'pending', NULL, 'service', NULL, NULL, 'polygon', NULL, '[[113.203941,23.164899],[113.350883,23.079332],[113.32376,23.148484]]', '113.277412,23.122115', 0.00, 44.67, 300, 500, 5, 'weekday', '06:00', '22:00', 'pending', NULL, NULL, NULL, 1, 1, '2026-05-28 16:56:38', NULL, '2026-05-28 17:15:30', NULL, '1');
INSERT INTO `bus_area` VALUES (216, 1, 2059155512602853378, NULL, '1245', '125214', 'service', 'pending', NULL, 'service', NULL, NULL, 'polygon', NULL, NULL, NULL, 0.00, 0.00, 300, 500, 5, 'weekday', '06:00', '22:00', 'pending', NULL, NULL, NULL, 1, 1, '2026-05-28 16:57:13', NULL, '2026-05-28 17:15:34', NULL, '1');
INSERT INTO `bus_area` VALUES (217, 1, 2059155512602853378, NULL, '89453', '1235', 'service', 'pending', '[[[113.243182,23.148422],[113.235629,23.129164],[113.259318,23.130269],[113.255027,23.147948]]]', 'service', NULL, NULL, 'polygon', NULL, '[[113.199443,23.161869],[113.200816,23.10125],[113.270854,23.100303],[113.269824,23.151767]]', '113.235148,23.131086', 0.00, 44.77, 300, 500, 5, 'weekday', '06:00', '22:00', 'pending', NULL, NULL, NULL, 1, 1, '2026-05-28 17:00:22', NULL, '2026-05-28 17:15:37', NULL, '1');
INSERT INTO `bus_area` VALUES (218, 1, 2059155603103350785, NULL, '白云大厦', 'by368', 'service', 'enabled', '[[[113.287135,23.120004],[113.286299,23.119525],[113.286443,23.119259],[113.288273,23.120433],[113.288037,23.120605]],[[113.286958,23.120319],[113.286787,23.118227],[113.288761,23.118366],[113.288954,23.121148]]]', 'service', NULL, NULL, 'polygon', NULL, '[[113.281982,23.121668],[113.281746,23.117465],[113.289385,23.117386],[113.289471,23.121826],[113.285287,23.122408]]', '113.285609,23.119897', 0.00, 0.40, 300, 500, 5, 'weekday', '06:00', '22:00', 'approved', '审核同意', NULL, NULL, 1, 1, '2026-05-28 17:36:09', NULL, '2026-06-01 18:01:18', 'alex01', '1');
INSERT INTO `bus_area` VALUES (219, 1, 2059155512602853378, NULL, '数据中心区域', 'part1', 'service', 'pending', '[[[113.330459,23.130506],[113.330051,23.130723],[113.329885,23.130324]]]', 'service', NULL, NULL, 'polygon', NULL, '[[113.33462,23.127755],[113.335135,23.132925],[113.327904,23.133398],[113.326638,23.127695],[113.333311,23.126571]]', '113.330887,23.129984', 0.00, 0.53, 300, 500, 5, 'weekday', '06:00', '22:00', 'pending', NULL, NULL, NULL, 2, 1, '2026-05-29 17:10:04', NULL, '2026-06-01 18:01:25', NULL, '1');
INSERT INTO `bus_area` VALUES (220, 1, 1, NULL, '123', '111', 'service', 'pending', NULL, 'service', NULL, NULL, 'polygon', NULL, NULL, NULL, 0.00, 0.00, 300, 500, 5, 'weekday', '06:00', '22:00', 'pending', NULL, NULL, NULL, 1, 1, '2026-05-30 15:08:51', NULL, '2026-05-30 15:09:02', NULL, '1');
INSERT INTO `bus_area` VALUES (223, 1, 2059155512602853378, '广州巴士集团有限公司', '白云路', 'AR000001', 'service', 'enabled', NULL, 'service', NULL, NULL, 'polygon', NULL, '[[113.283131,23.120552],[113.283131,23.118421],[113.287111,23.118549],[113.286993,23.121154]]', '113.285121,23.119788', 0.00, 0.11, 300, 500, 5, 'weekday', '06:00', '22:00', 'approved', '过', 'alex01', '2026-06-01 10:29:11', 1, 0, '2026-06-01 10:28:34', 'alex01', '2026-06-01 10:29:14', 'alex01', '1');
INSERT INTO `bus_area` VALUES (224, 1, 2059155512602853378, '广州巴士集团有限公司', '白云路1', 'AR000002', 'service', 'enabled', NULL, 'service', NULL, NULL, 'polygon', NULL, '[[113.28508,23.120022],[113.282983,23.119714],[113.282816,23.118873],[113.282983,23.117852],[113.286727,23.117812],[113.286973,23.120032]]', '113.284895,23.118922', 0.00, 0.09, 300, 500, 5, 'weekday', '06:00', '22:00', 'approved', '是的', 'alex01', '2026-06-01 10:31:56', 2, 0, '2026-06-01 10:30:04', 'alex01', '2026-06-01 10:32:00', 'alex01', '1');
INSERT INTO `bus_area` VALUES (225, 1, 2059155512602853378, '广州巴士集团有限公司', '汉溪长隆', 'AR000003', 'administrative', 'enabled', NULL, 'administrative', 'GZ', '广州市', 'polygon', NULL, '[[113.324832,22.991698],[113.331012,22.989406],[113.346568,22.994266],[113.350881,23.004023],[113.347598,23.005426],[113.347105,23.005841],[113.3432,23.007282],[113.339122,23.005268],[113.330591,23.000867],[113.32781,22.995675]]', '113.337857,22.998344', 0.00, 2.98, 300, 500, 5, 'weekday', '06:00', '22:00', 'approved', '审核', 'felix', '2026-06-01 17:17:59', 1, 0, '2026-06-01 17:17:47', 'felix', '2026-06-01 17:37:03', 'felix', '1');
INSERT INTO `bus_area` VALUES (226, 1, 2059155512602853378, '广州巴士集团有限公司', '天河南二路61', 'AR000004', 'administrative', 'enabled', NULL, 'administrative', NULL, NULL, 'polygon', NULL, '[[113.322645,23.141066],[113.321186,23.130647],[113.336549,23.126464],[113.351999,23.134357],[113.338695,23.146669],[113.323074,23.152036]]', '113.336593,23.13925', 0.00, 5.40, 300, 500, 5, 'weekday', '06:00', '22:00', 'approved', '123', 'felix', '2026-06-01 18:00:53', 1, 0, '2026-06-01 18:00:43', 'felix', '2026-06-01 18:01:32', 'felix', '1');
INSERT INTO `bus_area` VALUES (227, 1, 2061273631362301953, '广州市公共交通数据管理中心有限公司', '石牌区', 'AR000005', 'service', 'enabled', NULL, 'service', NULL, NULL, 'polygon', NULL, '[[113.328516,23.14161],[113.328387,23.127363],[113.338043,23.126929],[113.338043,23.134191],[113.335983,23.14165],[113.335811,23.141768],[113.335811,23.141768],[113.328558,23.14161],[113.328558,23.14161]]', '113.333215,23.134349', 0.00, 1.50, 300, 500, 5, 'weekday', '06:00', '22:00', 'approved', '1', 'admin', '2026-06-02 10:12:52', 1, 0, '2026-06-02 10:12:03', 'admin', '2026-06-02 10:13:51', 'admin', '1');

-- ----------------------------
-- Table structure for bus_customroute_schedule
-- ----------------------------
DROP TABLE IF EXISTS `bus_customroute_schedule`;
CREATE TABLE `bus_customroute_schedule`  (
  `id` bigint NOT NULL AUTO_INCREMENT COMMENT '主键',
  `schedule_no` varchar(64) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci NOT NULL COMMENT '班次号',
  `schedule_name` varchar(128) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci NOT NULL COMMENT '班次名称',
  `schedule_date` date NOT NULL COMMENT '班次日期',
  `route_id` varchar(64) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci NOT NULL COMMENT '路线ID',
  `route_name` varchar(128) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci NULL DEFAULT NULL COMMENT '路线名称',
  `allow_standing` varchar(1) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci NULL DEFAULT '0' COMMENT '是否允许站票:0否1是',
  `lock_minutes` int NULL DEFAULT 0 COMMENT '提前运力锁定分钟',
  `seat_count` int NULL DEFAULT 0 COMMENT '座位数',
  `seat_inventory` int NULL DEFAULT 0 COMMENT '库存座位',
  `first_departure_time` varchar(5) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci NULL DEFAULT NULL COMMENT '首站发车时间HH:mm',
  `class_start_time` varchar(5) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci NULL DEFAULT NULL COMMENT '开班时间HH:mm',
  `order_count` int NULL DEFAULT 0 COMMENT '订单数',
  `boarding_count` int NULL DEFAULT 0 COMMENT '上车人数',
  `class_status` varchar(20) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci NULL DEFAULT 'not_started' COMMENT '班次状态:not_started/in_trip/ended',
  `report_status` varchar(20) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci NULL DEFAULT 'pending' COMMENT '报班状态:pending/reported',
  `report_driver_id` bigint NULL DEFAULT NULL COMMENT '报班司机ID',
  `report_driver_name` varchar(64) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci NULL DEFAULT NULL COMMENT '报班司机',
  `report_vehicle_id` bigint NULL DEFAULT NULL COMMENT '报班车辆ID',
  `report_vehicle_no` varchar(32) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci NULL DEFAULT NULL COMMENT '报班车辆',
  `dept_id` bigint NULL DEFAULT NULL COMMENT '部门ID（数据权限）',
  `create_time` datetime NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
  `create_by` varchar(64) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci NULL DEFAULT NULL COMMENT '创建人',
  `update_time` datetime NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
  `update_by` varchar(64) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci NULL DEFAULT NULL COMMENT '更新人',
  `tenant_id` varchar(32) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci NULL DEFAULT NULL COMMENT '租户ID',
  `del_flag` varchar(1) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci NULL DEFAULT '0' COMMENT '删除标记',
  PRIMARY KEY (`id`) USING BTREE,
  UNIQUE INDEX `uk_bcs_schedule_no`(`schedule_no` ASC) USING BTREE,
  INDEX `idx_bcs_date`(`schedule_date` ASC) USING BTREE,
  INDEX `idx_bcs_route`(`route_id` ASC) USING BTREE,
  INDEX `idx_bcs_report_status`(`report_status` ASC) USING BTREE,
  INDEX `idx_bcs_class_status`(`class_status` ASC) USING BTREE,
  INDEX `idx_bcs_tenant`(`tenant_id` ASC) USING BTREE
) ENGINE = InnoDB AUTO_INCREMENT = 62 CHARACTER SET = utf8mb4 COLLATE = utf8mb4_0900_ai_ci COMMENT = '班次管理表' ROW_FORMAT = DYNAMIC;

-- ----------------------------
-- Records of bus_customroute_schedule
-- ----------------------------
INSERT INTO `bus_customroute_schedule` VALUES (1, '0001', 'Test', '2026-04-06', 'BUS004', '常规公交202路', '0', 0, 16, 1, '22:35', '22:35', 0, 0, 'not_started', 'reported', 1, '郑育明', 2, '京B67890', NULL, '2026-04-06 22:38:09', 'admin', '2026-05-14 17:11:18', 'admin', '1', '0');
INSERT INTO `bus_customroute_schedule` VALUES (2, 'bc001', '测试班次', '2026-04-08', 'Test001', '测试线路', '0', 0, 1, 1, '10:42', '10:42', 0, 0, 'not_started', 'reported', 1, '郑育明', 1, '京A12345', NULL, '2026-04-08 10:43:52', 'admin', '2026-04-08 10:44:12', 'admin', '1', '0');
INSERT INTO `bus_customroute_schedule` VALUES (3, '12313', '常规公交101路', '2026-04-23', 'BUS001', '常规公交101路', '0', 0, 1, 1, '16:04', '16:04', 0, 0, 'not_started', 'reported', 2, '张伟', 1, '京A12345', NULL, '2026-04-23 16:07:14', 'admin', '2026-04-23 16:08:15', 'admin', '1', '0');
INSERT INTO `bus_customroute_schedule` VALUES (4, '20260424', '20260424', '2026-04-24', 'xx01', 'A线', '0', 0, 1, 1, '16:01', '17:01', 0, 0, 'not_started', 'reported', 2, '张伟', 3, '京C54321', NULL, '2026-04-24 16:02:01', 'admin', '2026-04-24 16:05:48', 'admin', '1', '0');
INSERT INTO `bus_customroute_schedule` VALUES (5, 'RY1001', '体育中心站->石牌桥站', '2026-04-30', 'BUS001', '常规公交101路', '1', 0, 1, 1, '17:00', '17:00', 0, 0, 'not_started', 'reported', 3, '李娜', 5, '粤A16465D', NULL, '2026-04-30 16:59:59', 'admin', '2026-04-30 17:00:13', 'admin', '1', '0');
INSERT INTO `bus_customroute_schedule` VALUES (6, 'RY1002', '体育中心站->鹿鸣山站', '2026-04-30', 'Test001', '测试线路', '0', 0, 1, 1, '18:00', '19:00', 0, 0, 'not_started', 'pending', NULL, NULL, NULL, NULL, NULL, '2026-04-30 17:02:21', 'admin', '2026-04-30 17:15:45', 'admin', '1', '1');
INSERT INTO `bus_customroute_schedule` VALUES (7, '123123', '1321', '2026-05-06', 'Test001', '测试线路', '0', 0, 1, 1, '17:46', '17:46', 0, 0, 'not_started', 'reported', 4, '通达寄给数据中心', 2, '京B67890', NULL, '2026-05-06 17:46:03', 'admin', '2026-05-06 17:46:12', 'admin', '1', '0');
INSERT INTO `bus_customroute_schedule` VALUES (8, 'T-S01', '模拟测试班次', '2026-05-12', '02830', '283路', '0', 0, 1, 1, '08:30', '09:00', 0, 0, 'not_started', 'reported', 1, '郑育明', 1, '京A12345', NULL, '2026-05-12 11:26:31', 'admin', '2026-05-12 11:26:38', 'admin', '1', '0');
INSERT INTO `bus_customroute_schedule` VALUES (9, '1234888', '班次ABC', '2026-05-13', '888', '测试线路888', '1', 0, 1, 1, '10:33', '12:33', 0, 0, 'not_started', 'reported', 4, '通达寄给数据中心', 1, '京A12345', NULL, '2026-05-13 10:32:28', 'admin', '2026-05-13 10:32:43', 'admin', '1', '0');
INSERT INTO `bus_customroute_schedule` VALUES (10, '9990', 'A9990', '2026-05-13', 'A990', '990', '1', 3, 2, 1, '14:17', '14:17', 0, 0, 'not_started', 'reported', 1, '郑育明', 3, '京C54321', NULL, '2026-05-13 14:16:28', 'admin', '2026-05-13 14:18:58', 'admin', '1', '0');
INSERT INTO `bus_customroute_schedule` VALUES (11, 'A9990', 'A9990', '2026-05-13', 'A990', '990', '0', 0, 1, 1, '14:19', '14:19', 0, 0, 'not_started', 'reported', 2, '张伟', 2, '京B67890', NULL, '2026-05-13 14:18:47', 'admin', '2026-05-13 14:46:39', 'admin', '1', '0');
INSERT INTO `bus_customroute_schedule` VALUES (12, 'RY00001', '体育中心->石牌桥', '2026-05-13', '02830', '283路', '0', 0, 1, 1, '18:00', '18:00', 0, 0, 'not_started', 'reported', 2, '张伟', 5, '粤A16465D', NULL, '2026-05-13 15:14:04', 'admin', '2026-05-13 15:15:28', 'admin', '1', '0');
INSERT INTO `bus_customroute_schedule` VALUES (13, 'RY00002', '体育中心->车陂南', '2026-05-13', '02830', '283路', '0', 0, 1, 1, '18:00', '18:00', 0, 0, 'not_started', 'reported', 1, '郑育明', 6, '粤AVC990', NULL, '2026-05-13 15:16:34', 'admin', '2026-05-13 15:17:32', 'admin', '1', '0');
INSERT INTO `bus_customroute_schedule` VALUES (14, '1', 'A11-1', '2026-05-13', 'A11', '创展中心东-创展中心西', '1', 0, 1, 1, '15:33', '15:33', 0, 0, 'not_started', 'reported', 1, '郑育明', 3, '京C54321', NULL, '2026-05-13 15:34:37', 'admin', '2026-05-14 17:15:17', 'admin', '1', '0');
INSERT INTO `bus_customroute_schedule` VALUES (15, 'A1-1', 'A线1-1', '2026-05-13', 'xx01', 'A线', '1', 0, 1, 1, '15:35', '15:35', 0, 0, 'not_started', 'pending', NULL, NULL, NULL, NULL, NULL, '2026-05-13 15:36:14', 'admin', '2026-05-13 15:36:13', NULL, '1', '0');
INSERT INTO `bus_customroute_schedule` VALUES (16, 'RY1000', '体育中心-车陂南', '2026-05-14', 'BUS001', '常规公交101路', '1', 0, 1, 1, '18:00', '18:00', 0, 0, 'not_started', 'pending', NULL, NULL, NULL, NULL, NULL, '2026-05-14 17:08:46', 'admin', '2026-05-14 17:08:44', NULL, '1', '0');
INSERT INTO `bus_customroute_schedule` VALUES (17, 'RY1005', '石牌桥-员村', '2026-05-15', 'xx01', 'A线', '1', 0, 1, 1, '09:00', '08:00', 0, 0, 'not_started', 'reported', 5, '测试司机', 2, '京B67890', NULL, '2026-05-14 17:09:31', 'admin', '2026-05-19 17:55:39', 'admin', '1', '0');
INSERT INTO `bus_customroute_schedule` VALUES (18, 'A11', 'A11', '2026-05-18', 'A11', '创展中心东-创展中心西', '1', 0, 1, 1, '10:30', '10:30', 0, 0, 'not_started', 'reported', 5, '测试司机', 5, '粤A16465D', NULL, '2026-05-18 10:30:32', 'admin', '2026-05-18 10:30:40', 'admin', '1', '0');
INSERT INTO `bus_customroute_schedule` VALUES (19, 'A23', 'A23', '2026-05-18', 'xx01', 'A线', '1', 0, 1, 1, '10:31', '10:31', 0, 0, 'not_started', 'reported', 2, '张伟', 4, '京D98765', NULL, '2026-05-18 10:32:06', 'admin', '2026-05-18 10:32:16', 'admin', '1', '0');
INSERT INTO `bus_customroute_schedule` VALUES (20, '213', '123', '2026-05-19', 'A11', '创展中心东-创展中心西', '0', 0, 1, 1, '17:52', '17:52', 0, 0, 'not_started', 'reported', 5, '测试司机', 2, '京B67890', NULL, '2026-05-19 17:53:10', 'admin', '2026-05-19 17:54:37', 'admin', '1', '0');
INSERT INTO `bus_customroute_schedule` VALUES (28, 'RY2002', '体育中心', '2026-05-19', 'Test001', '测试线路', '1', 0, 1, 1, '17:52', '17:52', 0, 0, 'not_started', 'reported', 6, '张三', 1, '京A12345', NULL, '2026-05-19 17:53:38', 'admin', '2026-05-19 17:54:13', 'admin', '1', '0');
INSERT INTO `bus_customroute_schedule` VALUES (29, '0001_COPY_1779418976162', 'Test', '2026-05-23', 'BUS004', '常规公交202路', '0', 0, 16, 1, '22:35', '22:35', 0, 0, 'not_started', 'pending', NULL, NULL, NULL, NULL, NULL, '2026-05-22 11:02:56', 'admin', '2026-05-22 11:02:51', NULL, '1', '0');
INSERT INTO `bus_customroute_schedule` VALUES (30, 'A123', 'A123', '2026-05-24', '101', '101路', '1', 0, 1, 1, '09:16', '09:16', 0, 0, 'not_started', 'reported', 6, '张三', 1, '京A12345', NULL, '2026-05-24 09:16:33', 'admin', '2026-05-24 09:16:44', 'admin', '1', '0');
INSERT INTO `bus_customroute_schedule` VALUES (31, 'A9901', 'A9901', '2026-05-26', 'A990', '990', '0', 0, 1, 1, '16:35', '16:35', 0, 0, 'not_started', 'reported', 6, '张三', 1, '京A12345', NULL, '2026-05-26 16:32:06', 'admin', '2026-05-26 16:32:17', 'admin', '1', '0');
INSERT INTO `bus_customroute_schedule` VALUES (32, 'A9902', 'A9902', '2026-05-26', 'A990', '990', '0', 0, 1, 1, '19:49', '19:49', 0, 0, 'not_started', 'reported', 6, '张三', 1, '京A12345', NULL, '2026-05-26 16:49:22', 'admin', '2026-05-26 16:49:31', 'admin', '1', '0');
INSERT INTO `bus_customroute_schedule` VALUES (33, 'A9903', 'A9903', '2026-05-26', 'Test001', '测试线路', '1', 0, 1, 1, '18:50', '18:50', 0, 0, 'not_started', 'reported', 6, '张三', 1, '京A12345', NULL, '2026-05-26 16:51:23', 'admin', '2026-05-26 16:51:31', 'admin', '1', '0');
INSERT INTO `bus_customroute_schedule` VALUES (34, '213_COPY_1779845690811', '123', '2026-05-27', 'A11', '创展中心东-创展中心西', '0', 0, 1, 1, '17:52', '17:52', 0, 0, 'not_started', 'reported', 5, '刘罗瑞', 4, '京D98765', NULL, '2026-05-27 09:34:51', 'admin', '2026-05-27 09:35:01', 'admin', '1', '0');
INSERT INTO `bus_customroute_schedule` VALUES (35, 'SCH20260527001', '天河穿梭线早班', '2026-05-27', 'R_GZ_201', '天河穿梭线', '1', 0, 45, 43, '07:00', '07:00', 0, 0, 'not_started', 'reported', NULL, NULL, NULL, NULL, NULL, '2026-05-27 10:58:45', NULL, '2026-05-27 10:58:45', NULL, '1', '0');
INSERT INTO `bus_customroute_schedule` VALUES (36, 'SCH20260527002', '天河穿梭线午班', '2026-05-27', 'R_GZ_201', '天河穿梭线', '1', 0, 45, 45, '12:00', '12:00', 0, 0, 'not_started', 'pending', NULL, NULL, NULL, NULL, NULL, '2026-05-27 10:58:45', NULL, '2026-05-27 10:58:45', NULL, '1', '0');
INSERT INTO `bus_customroute_schedule` VALUES (37, 'SCH20260527003', '海珠滨江线早班', '2026-05-27', 'R_GZ_202', '海珠滨江线', '1', 0, 45, 41, '07:30', '07:30', 0, 0, 'not_started', 'reported', NULL, NULL, NULL, NULL, NULL, '2026-05-27 10:58:45', NULL, '2026-05-27 10:58:45', NULL, '1', '0');
INSERT INTO `bus_customroute_schedule` VALUES (38, 'SCH20260527004', '大学城专线早班', '2026-05-27', 'R_GZ_203', '大学城专线', '0', 0, 30, 26, '08:00', '08:00', 0, 0, 'not_started', 'reported', NULL, NULL, NULL, NULL, NULL, '2026-05-27 10:58:45', NULL, '2026-05-27 10:58:45', NULL, '1', '0');
INSERT INTO `bus_customroute_schedule` VALUES (39, 'SCH20260527005', '越秀经典线早班', '2026-05-27', 'R_GZ_204', '越秀经典线', '1', 0, 45, 44, '09:00', '09:00', 0, 0, 'not_started', 'reported', NULL, NULL, NULL, NULL, NULL, '2026-05-27 10:58:45', NULL, '2026-05-27 10:58:45', NULL, '1', '0');
INSERT INTO `bus_customroute_schedule` VALUES (40, 'SCH20260527006', '荔湾风情线早班', '2026-05-27', 'R_GZ_205', '荔湾风情线', '1', 0, 30, 28, '08:30', '08:30', 0, 0, 'not_started', 'pending', NULL, NULL, NULL, NULL, NULL, '2026-05-27 10:58:45', NULL, '2026-05-27 10:58:45', NULL, '1', '0');
INSERT INTO `bus_customroute_schedule` VALUES (41, 'SCH20260527007', '花都机场线早班', '2026-05-27', 'R_GZ_210', '花都机场线', '0', 0, 45, 45, '06:30', '06:30', 0, 0, 'not_started', 'reported', NULL, NULL, NULL, NULL, NULL, '2026-05-27 10:58:45', NULL, '2026-05-27 10:58:45', NULL, '1', '0');
INSERT INTO `bus_customroute_schedule` VALUES (42, 'SCH20260527008', '花都机场线午班', '2026-05-27', 'R_GZ_210', '花都机场线', '0', 0, 45, 43, '13:00', '13:00', 0, 0, 'not_started', 'reported', NULL, NULL, NULL, NULL, NULL, '2026-05-27 10:58:45', NULL, '2026-05-27 10:58:45', NULL, '1', '0');
INSERT INTO `bus_customroute_schedule` VALUES (43, 'SCH20260527009', '天河穿梭线晚班', '2026-05-27', 'R_GZ_201', '天河穿梭线', '1', 0, 45, 38, '17:30', '17:30', 0, 0, 'not_started', 'reported', NULL, NULL, NULL, NULL, NULL, '2026-05-27 10:58:45', NULL, '2026-05-27 10:58:45', NULL, '1', '0');
INSERT INTO `bus_customroute_schedule` VALUES (44, 'SCH20260528001', '大学城专线早班', '2026-05-28', 'R_GZ_203', '大学城专线', '0', 0, 30, 30, '08:00', '08:00', 0, 0, 'not_started', 'pending', NULL, NULL, NULL, NULL, NULL, '2026-05-27 10:58:45', NULL, '2026-05-27 10:58:45', NULL, '1', '0');
INSERT INTO `bus_customroute_schedule` VALUES (45, 'SCH20260527001_COPY_1779862677505', '天河穿梭线早班', '2026-05-27', 'R_GZ_201', '天河穿梭线', '1', 0, 45, 43, '07:00', '07:00', 0, 0, 'not_started', 'pending', NULL, NULL, NULL, NULL, NULL, '2026-05-27 14:17:58', 'admin', '2026-05-27 14:17:50', NULL, '1', '0');
INSERT INTO `bus_customroute_schedule` VALUES (46, 'SCH20260527001_COPY_1779862677505_COPY_1779931235847', '天河穿梭线早班', '2026-05-28', 'R_GZ_201', '天河穿梭线 体育西-珠江新城', '1', 0, 45, 43, '09:30', '09:30', 0, 0, 'not_started', 'reported', 2008, '林振华', 4005, '粤A00005D', 1, '2026-05-28 09:20:36', 'admin', '2026-05-28 09:22:04', 'admin', '1', '0');
INSERT INTO `bus_customroute_schedule` VALUES (47, 'SCH20260527001_COPY_1779862677505_COPY_1779933205756', '天河穿梭线早班', '2026-05-28', 'R_GZ_201', '天河穿梭线 体育西-珠江新城', '1', 0, 45, 43, '10:30', '10:30', 0, 0, 'not_started', 'reported', 2001, '陈伟强', 4010, '粤A00010D', 1, '2026-05-28 09:53:26', 'admin', '2026-05-28 10:01:22', 'admin', '1', '0');
INSERT INTO `bus_customroute_schedule` VALUES (48, 'Test202605291', 'Test202605291', '2026-05-29', 'R_GZ_201', '天河穿梭线 体育西-珠江新城', '0', 0, 10, 10, '10:26', '10:26', 0, 0, 'not_started', 'reported', 2001, '陈伟强', 4012, '粤A88888D', 1, '2026-05-29 09:27:29', 'admin', '2026-05-29 09:27:49', 'admin', '1', '0');
INSERT INTO `bus_customroute_schedule` VALUES (49, 'A202605291', 'A202605291', '2026-05-29', 'xx01', 'A线', '1', 0, 10, 10, '10:29', '10:29', 0, 0, 'not_started', 'reported', 2005, '刘淑华', 4004, '粤A00004D', 1, '2026-05-29 09:29:44', 'admin', '2026-05-29 09:29:56', 'admin', '1', '0');
INSERT INTO `bus_customroute_schedule` VALUES (50, '1_COPY_1780018830045', 'A11-1', '2026-05-29', 'A11', '创展中心东-创展中心西', '1', 0, 1, 1, '15:33', '15:33', 0, 0, 'not_started', 'reported', 1, '郑育明', 4010, '粤A00010D', 1, '2026-05-29 09:40:30', 'admin', '2026-05-29 10:03:36', 'admin', '1', '1');
INSERT INTO `bus_customroute_schedule` VALUES (51, '1_COPY_1780020349818', 'A11-1', '2026-05-29', 'A11', '创展中心东-创展中心西', '1', 0, 1, 1, '15:33', '15:33', 0, 0, 'not_started', 'reported', 1, '郑育明', 4012, '粤A88888D', 1, '2026-05-29 10:05:50', 'admin', '2026-05-29 10:07:19', 'admin', '1', '1');
INSERT INTO `bus_customroute_schedule` VALUES (52, '1_COPY_1780020410898', 'A11-1', '2026-05-29', 'A11', '创展中心东-创展中心西', '1', 0, 1, 1, '15:33', '15:33', 0, 0, 'not_started', 'pending', NULL, NULL, NULL, NULL, 1, '2026-05-29 10:06:51', 'admin', '2026-05-29 10:07:24', NULL, '1', '1');
INSERT INTO `bus_customroute_schedule` VALUES (53, 'A052901', 'A052901', '2026-05-29', 'A0529', '0529线路', '0', 0, 10, 0, '11:17', '11:17', 1, 0, 'not_started', 'reported', 2003, '王美芳', 4007, '粤A00007D', 1, '2026-05-29 10:17:27', 'admin', '2026-05-29 10:22:48', 'admin', '1', '0');
INSERT INTO `bus_customroute_schedule` VALUES (54, '66668888', '快线', '2026-05-30', 'line1', '线路1', '0', 0, 5, 4, '16:23', '16:25', 0, 0, 'not_started', 'reported', 2011, '鸿聪测试', 4013, '粤A88999D', 2059155512602853378, '2026-05-30 16:15:03', 'alex01', '2026-05-30 16:15:59', 'alex01', '1', '0');
INSERT INTO `bus_customroute_schedule` VALUES (55, '66668889', '快线', '2026-05-30', 'line1', '线路1', '0', 0, 4, 1, '16:28', '16:32', 0, 0, 'not_started', 'reported', 2011, '鸿聪测试', 4013, '粤A88999D', 2059155512602853378, '2026-05-30 16:19:11', 'alex01', '2026-05-30 16:19:19', 'alex01', '1', '0');
INSERT INTO `bus_customroute_schedule` VALUES (56, '66668890', '班次3', '2026-05-30', 'line1', '线路1', '0', 0, 1, 1, '16:30', '16:30', 0, 0, 'not_started', 'pending', NULL, NULL, NULL, NULL, 2059155512602853378, '2026-05-30 16:29:26', 'alex01', '2026-05-30 16:30:20', 'alex01', '1', '0');
INSERT INTO `bus_customroute_schedule` VALUES (57, '66668891', '班次4', '2026-05-30', 'line1', '线路1', '0', 0, 1, 1, '16:33', '16:33', 0, 0, 'not_started', 'reported', 2011, '鸿聪测试', 4013, '粤A88999D', 2059155512602853378, '2026-05-30 16:32:13', 'alex01', '2026-05-30 16:32:18', 'alex01', '1', '0');
INSERT INTO `bus_customroute_schedule` VALUES (58, '66668893', '班次5', '2026-05-30', 'line1', '线路1', '0', 0, 1, 1, '16:33', '16:33', 0, 0, 'not_started', 'pending', NULL, NULL, NULL, NULL, 2059155512602853378, '2026-05-30 16:32:37', 'alex01', '2026-05-30 16:32:28', NULL, '1', '0');
INSERT INTO `bus_customroute_schedule` VALUES (59, 'DTGJ0001', '通勤测试线路', '2026-05-31', 'Test001', '测试线路', '0', 0, 35, 35, '10:15', '10:00', 0, 0, 'not_started', 'reported', 2012, '刘测试', 4010, '粤A00010D', 1, '2026-05-31 09:46:50', 'admin', '2026-05-31 09:47:01', 'admin', '1', '0');
INSERT INTO `bus_customroute_schedule` VALUES (60, 'shift‌1', '班次1', '2026-06-01', '234gfdg', '发顺丰', '0', 0, 3, 3, '11:04', '11:04', 0, 0, 'not_started', 'pending', NULL, NULL, NULL, NULL, 2059155512602853378, '2026-06-01 11:05:33', 'alex04', '2026-06-01 11:05:24', NULL, '1', '0');
INSERT INTO `bus_customroute_schedule` VALUES (61, 'H123', 'H123', '2026-06-01', 'RT000001', 'H测试线路', '0', 0, 5, 7, '17:01', '19:01', 0, 0, 'not_started', 'reported', 2014, '鸿聪测试', 4009, '粤A00009D', 2059155512602853378, '2026-06-01 17:00:10', 'felix', '2026-06-01 17:01:36', 'felix', '1', '0');

-- ----------------------------
-- Table structure for bus_device
-- ----------------------------
DROP TABLE IF EXISTS `bus_device`;
CREATE TABLE `bus_device`  (
  `id` bigint NOT NULL AUTO_INCREMENT COMMENT '主键',
  `serial_no` varchar(64) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci NOT NULL COMMENT '设备序列号',
  `device_name` varchar(128) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci NULL DEFAULT NULL COMMENT '设备名称',
  `model` varchar(64) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci NULL DEFAULT NULL COMMENT '设备型号',
  `os_version` varchar(64) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci NULL DEFAULT NULL COMMENT '操作系统版本',
  `status` varchar(20) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci NULL DEFAULT 'warehouse' COMMENT '状态:warehouse/enabled/pending_maint/maintaining/scrapped',
  `bound_vehicle_id` bigint NULL DEFAULT NULL COMMENT '绑定车辆ID',
  `bound_plate_number` varchar(32) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci NULL DEFAULT NULL COMMENT '绑定车牌(冗余)',
  `current_apk_version` varchar(32) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci NULL DEFAULT NULL COMMENT '当前APK版本',
  `last_online_at` datetime NULL DEFAULT NULL COMMENT '最后在线时间',
  `last_lng` decimal(12, 8) NULL DEFAULT NULL COMMENT '最近经度',
  `last_lat` decimal(12, 8) NULL DEFAULT NULL COMMENT '最近纬度',
  `last_address` varchar(256) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci NULL DEFAULT NULL COMMENT '最近地址',
  `remark` varchar(500) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci NULL DEFAULT NULL COMMENT '备注',
  `create_time` datetime NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
  `create_by` varchar(64) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci NULL DEFAULT NULL COMMENT '创建人',
  `update_time` datetime NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
  `update_by` varchar(64) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci NULL DEFAULT NULL COMMENT '更新人',
  `tenant_id` varchar(32) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci NULL DEFAULT NULL COMMENT '租户ID',
  `del_flag` varchar(1) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci NULL DEFAULT '0' COMMENT '删除标记',
  PRIMARY KEY (`id`) USING BTREE,
  UNIQUE INDEX `uk_bd_serial`(`serial_no` ASC, `del_flag` ASC) USING BTREE,
  INDEX `idx_bd_status`(`status` ASC) USING BTREE,
  INDEX `idx_bd_vehicle`(`bound_vehicle_id` ASC) USING BTREE,
  INDEX `idx_bd_apk_version`(`current_apk_version` ASC) USING BTREE,
  INDEX `idx_bd_tenant`(`tenant_id` ASC) USING BTREE
) ENGINE = InnoDB AUTO_INCREMENT = 1 CHARACTER SET = utf8mb4 COLLATE = utf8mb4_0900_ai_ci COMMENT = '司机端平板设备表' ROW_FORMAT = DYNAMIC;

-- ----------------------------
-- Records of bus_device
-- ----------------------------

-- ----------------------------
-- Table structure for bus_device_location_log
-- ----------------------------
DROP TABLE IF EXISTS `bus_device_location_log`;
CREATE TABLE `bus_device_location_log`  (
  `id` bigint NOT NULL AUTO_INCREMENT COMMENT '主键',
  `device_id` bigint NOT NULL COMMENT '设备ID',
  `serial_no` varchar(64) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci NOT NULL COMMENT '设备序列号',
  `report_type` varchar(20) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci NOT NULL COMMENT '上报类型:boot/scheduled',
  `lng` decimal(12, 8) NULL DEFAULT NULL COMMENT '经度',
  `lat` decimal(12, 8) NULL DEFAULT NULL COMMENT '纬度',
  `address` varchar(256) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci NULL DEFAULT NULL COMMENT '地址',
  `battery` int NULL DEFAULT NULL COMMENT '电量百分比',
  `network_type` varchar(32) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci NULL DEFAULT NULL COMMENT '网络类型',
  `driver_id` bigint NULL DEFAULT NULL COMMENT '当前登录司机ID',
  `report_time` datetime NULL DEFAULT CURRENT_TIMESTAMP COMMENT '上报时间',
  `tenant_id` varchar(32) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci NULL DEFAULT NULL COMMENT '租户ID',
  PRIMARY KEY (`id`) USING BTREE,
  INDEX `idx_bdll_device`(`device_id` ASC) USING BTREE,
  INDEX `idx_bdll_report_time`(`report_time` ASC) USING BTREE
) ENGINE = InnoDB AUTO_INCREMENT = 1 CHARACTER SET = utf8mb4 COLLATE = utf8mb4_0900_ai_ci COMMENT = '设备位置上报日志' ROW_FORMAT = DYNAMIC;

-- ----------------------------
-- Records of bus_device_location_log
-- ----------------------------

-- ----------------------------
-- Table structure for bus_device_status_log
-- ----------------------------
DROP TABLE IF EXISTS `bus_device_status_log`;
CREATE TABLE `bus_device_status_log`  (
  `id` bigint NOT NULL AUTO_INCREMENT COMMENT '主键',
  `device_id` bigint NOT NULL COMMENT '设备ID',
  `from_status` varchar(20) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci NULL DEFAULT NULL COMMENT '变更前状态',
  `to_status` varchar(20) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci NOT NULL COMMENT '变更后状态',
  `reason` varchar(500) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci NULL DEFAULT NULL COMMENT '变更原因',
  `operate_by` varchar(64) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci NULL DEFAULT NULL COMMENT '操作人',
  `operate_time` datetime NULL DEFAULT CURRENT_TIMESTAMP COMMENT '操作时间',
  `tenant_id` varchar(32) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci NULL DEFAULT NULL COMMENT '租户ID',
  PRIMARY KEY (`id`) USING BTREE,
  INDEX `idx_bdsl_device`(`device_id` ASC) USING BTREE,
  INDEX `idx_bdsl_time`(`operate_time` ASC) USING BTREE
) ENGINE = InnoDB AUTO_INCREMENT = 1 CHARACTER SET = utf8mb4 COLLATE = utf8mb4_0900_ai_ci COMMENT = '设备状态变更日志' ROW_FORMAT = DYNAMIC;

-- ----------------------------
-- Records of bus_device_status_log
-- ----------------------------

-- ----------------------------
-- Table structure for bus_discount_publish_log
-- ----------------------------
DROP TABLE IF EXISTS `bus_discount_publish_log`;
CREATE TABLE `bus_discount_publish_log`  (
  `id` bigint NOT NULL AUTO_INCREMENT COMMENT '主键',
  `discount_id` varchar(64) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci NOT NULL COMMENT '优惠ID',
  `version` varchar(20) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci NOT NULL COMMENT '版本号',
  `terminal_id` varchar(64) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci NULL DEFAULT NULL COMMENT '终端ID',
  `terminal_name` varchar(128) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci NULL DEFAULT NULL COMMENT '终端名称',
  `publish_status` varchar(20) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci NULL DEFAULT NULL COMMENT '下发状态:success/failed',
  `error_msg` varchar(500) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci NULL DEFAULT NULL COMMENT '错误信息',
  `retry_count` int NULL DEFAULT 0 COMMENT '重试次数',
  `publish_time` datetime NULL DEFAULT CURRENT_TIMESTAMP COMMENT '下发时间',
  `tenant_id` varchar(32) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci NULL DEFAULT NULL COMMENT '租户ID',
  PRIMARY KEY (`id`) USING BTREE,
  INDEX `idx_bdpl_discount`(`discount_id` ASC) USING BTREE,
  INDEX `idx_bdpl_status`(`publish_status` ASC) USING BTREE,
  INDEX `idx_bdpl_time`(`publish_time` ASC) USING BTREE
) ENGINE = InnoDB AUTO_INCREMENT = 20 CHARACTER SET = utf8mb4 COLLATE = utf8mb4_0900_ai_ci COMMENT = '优惠规则下发日志表' ROW_FORMAT = DYNAMIC;

-- ----------------------------
-- Records of bus_discount_publish_log
-- ----------------------------
INSERT INTO `bus_discount_publish_log` VALUES (1, '33166947e4f64dc4', '1.1', 'ALL', '全部终端', 'success', NULL, 0, '2026-05-07 16:40:16', '1');
INSERT INTO `bus_discount_publish_log` VALUES (2, '6422ceaaab204d6f', '1.0', 'ALL', '全部终端', 'success', NULL, 0, '2026-05-07 17:53:11', '1');
INSERT INTO `bus_discount_publish_log` VALUES (3, 'e743c615a3fe46fb', '1', 'ALL', '全部终端', 'success', NULL, 0, '2026-05-14 17:28:58', '1');
INSERT INTO `bus_discount_publish_log` VALUES (4, 'e743c615a3fe46fb', '2', 'ALL', '全部终端', 'success', NULL, 0, '2026-05-14 17:29:33', '1');
INSERT INTO `bus_discount_publish_log` VALUES (5, '33166947e4f64dc4', '1.1', 'ALL', '全部终端', 'success', NULL, 1, '2026-05-25 14:32:09', '1');
INSERT INTO `bus_discount_publish_log` VALUES (6, '33166947e4f64dc4', '1.1', 'ALL', '全部终端', 'success', NULL, 2, '2026-05-25 14:32:23', '1');
INSERT INTO `bus_discount_publish_log` VALUES (7, '33166947e4f64dc4', '1.1', 'ALL', '全部终端', 'failed', '重试超过3次，标记下发异常', 3, '2026-05-25 14:32:24', '1');
INSERT INTO `bus_discount_publish_log` VALUES (8, '33166947e4f64dc4', '1.1', 'ALL', '全部终端', 'failed', '重试超过3次，标记下发异常', 4, '2026-05-25 14:32:25', '1');
INSERT INTO `bus_discount_publish_log` VALUES (9, '33166947e4f64dc4', '1.1', 'ALL', '全部终端', 'failed', '重试超过3次，标记下发异常', 5, '2026-05-25 14:32:25', '1');
INSERT INTO `bus_discount_publish_log` VALUES (10, 'DSC_2025_011', '1.0', 'ALL', '全部终端', 'success', NULL, 0, '2026-05-27 10:59:35', '1');
INSERT INTO `bus_discount_publish_log` VALUES (11, 'DSC_2025_012', '1.0', 'ALL', '全部终端', 'success', NULL, 0, '2026-05-27 10:59:35', '1');
INSERT INTO `bus_discount_publish_log` VALUES (12, 'DSC_2025_013', '1.0', 'ALL', '全部终端', 'success', NULL, 0, '2026-05-27 10:59:35', '1');
INSERT INTO `bus_discount_publish_log` VALUES (13, 'DSC_2025_014', '1.0', 'ALL', '全部终端', 'success', NULL, 0, '2026-05-27 10:59:35', '1');
INSERT INTO `bus_discount_publish_log` VALUES (14, 'DSC_2025_015', '1.0', 'ALL', '全部终端', 'success', NULL, 0, '2026-05-27 10:59:35', '1');
INSERT INTO `bus_discount_publish_log` VALUES (15, 'DSC_2025_016', '1.0', 'TERM_001', '天河终端', 'failed', '网络超时', 2, '2026-05-27 10:59:35', '1');
INSERT INTO `bus_discount_publish_log` VALUES (16, 'DSC_2025_016', '1.0', 'TERM_002', '海珠终端', 'failed', '设备离线', 1, '2026-05-27 10:59:35', '1');
INSERT INTO `bus_discount_publish_log` VALUES (17, 'DSC_2025_017', '1.0', 'ALL', '全部终端', 'success', NULL, 0, '2026-05-27 10:59:35', '1');
INSERT INTO `bus_discount_publish_log` VALUES (18, 'DSC_2025_018', '1.0', 'ALL', '全部终端', 'success', NULL, 0, '2026-05-27 10:59:35', '1');
INSERT INTO `bus_discount_publish_log` VALUES (19, 'DSC_2025_019', '1.0', 'ALL', '全部终端', 'success', NULL, 0, '2026-05-27 10:59:35', '1');

-- ----------------------------
-- Table structure for bus_discount_rule
-- ----------------------------
DROP TABLE IF EXISTS `bus_discount_rule`;
CREATE TABLE `bus_discount_rule`  (
  `id` bigint NOT NULL AUTO_INCREMENT COMMENT '主键',
  `discount_id` varchar(64) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci NOT NULL COMMENT '优惠ID',
  `name` varchar(128) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci NOT NULL COMMENT '优惠名称',
  `description` varchar(500) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci NULL DEFAULT NULL COMMENT '优惠描述',
  `type` varchar(20) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci NOT NULL COMMENT '优惠类型:online/offline',
  `enterprise_ids` varchar(1000) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci NULL DEFAULT NULL COMMENT '适用企业ID列表(逗号分隔)',
  `valid_type` varchar(20) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci NULL DEFAULT 'date' COMMENT '有效期类型:long/date/permanent',
  `start_date` varchar(20) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci NULL DEFAULT NULL COMMENT '开始日期',
  `end_date` varchar(20) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci NULL DEFAULT NULL COMMENT '结束日期',
  `status` varchar(20) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci NULL DEFAULT 'pending' COMMENT '状态:pending/effective/expired/rejected',
  `version` varchar(20) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci NULL DEFAULT '1.0' COMMENT '版本号',
  `online_config_json` longtext CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci NULL COMMENT '线上配置JSON',
  `offline_config_json` longtext CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci NULL COMMENT '线下配置JSON',
  `submit_remark` varchar(500) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci NULL DEFAULT NULL COMMENT '提交审核备注',
  `audit_opinion` varchar(500) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci NULL DEFAULT NULL COMMENT '审核意见',
  `audit_by` varchar(64) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci NULL DEFAULT NULL COMMENT '审核人',
  `audit_time` datetime NULL DEFAULT NULL COMMENT '审核时间',
  `push_status` varchar(20) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci NULL DEFAULT 'none' COMMENT '下发状态:none/success/exception',
  `push_retry` int NULL DEFAULT 0 COMMENT '下发重试次数',
  `dept_id` bigint NULL DEFAULT NULL COMMENT '部门ID（数据权限）',
  `create_time` datetime NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
  `create_by` varchar(64) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci NULL DEFAULT NULL COMMENT '创建人',
  `update_time` datetime NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
  `update_by` varchar(64) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci NULL DEFAULT NULL COMMENT '更新人',
  `tenant_id` varchar(32) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci NULL DEFAULT NULL COMMENT '租户ID',
  `del_flag` varchar(1) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci NULL DEFAULT '0' COMMENT '删除标记',
  PRIMARY KEY (`id`) USING BTREE,
  UNIQUE INDEX `uk_bdr_discount_id`(`discount_id` ASC) USING BTREE,
  INDEX `idx_bdr_type`(`type` ASC) USING BTREE,
  INDEX `idx_bdr_status`(`status` ASC) USING BTREE,
  INDEX `idx_bdr_version`(`version` ASC) USING BTREE,
  INDEX `idx_bdr_create_time`(`create_time` ASC) USING BTREE,
  INDEX `idx_bdr_tenant`(`tenant_id` ASC) USING BTREE
) ENGINE = InnoDB AUTO_INCREMENT = 15 CHARACTER SET = utf8mb4 COLLATE = utf8mb4_0900_ai_ci COMMENT = '优惠规则主表' ROW_FORMAT = DYNAMIC;

-- ----------------------------
-- Records of bus_discount_rule
-- ----------------------------
INSERT INTO `bus_discount_rule` VALUES (1, '33166947e4f64dc4', '优惠1', NULL, 'offline', 'ENT001', 'date', '2026-04-30', '2026-04-30', 'effective', '1.1', '{\"discountType\":\"coupon\",\"discountRate\":95.0,\"reduceAmount\":0.0,\"fullAmount\":0.0,\"routeIds\":[\"Test001\"],\"minAmount\":0.0,\"userStatus\":[],\"allow叠加\":false,\"叠加Type\":\"all\"}', '{\"specialDiscount\":{\"cardTypes\":[\"老人免费卡\"],\"discountType\":\"discount\",\"discountRate\":100.0,\"reduceAmount\":0.0},\"transferDiscount\":{\"cardTypes\":[\"普通卡\"],\"periodType\":\"month\",\"intervals\":[{\"minAmount\":0.0,\"maxAmount\":80.0,\"discountRate\":100.0}]},\"employeeDiscount\":{\"discountRate\":100.0},\"routeIds\":[],\"areaIds\":[],\"priorityMode\":\"exclusive\"}', '', '', 'admin', '2026-05-25 14:32:09', 'exception', 6, NULL, '2026-04-30 17:23:33', 'admin', '2026-05-25 14:32:25', 'admin', '1', '0');
INSERT INTO `bus_discount_rule` VALUES (2, '6422ceaaab204d6f', '老人优惠', NULL, 'offline', 'ENT001', 'date', '2026-05-07', '2026-05-07', 'pending', '1.0', NULL, '{\"specialDiscount\":{\"cardTypes\":[\"老人免费卡\"],\"discountType\":\"discount\",\"discountRate\":100.0,\"reduceAmount\":0.0},\"transferDiscount\":{\"cardTypes\":[\"普通卡\"],\"periodType\":\"month\",\"intervals\":[{\"minAmount\":0.0,\"maxAmount\":80.0,\"discountRate\":100.0}]},\"employeeDiscount\":{\"discountRate\":100.0},\"routeIds\":[],\"areaIds\":[],\"priorityMode\":\"exclusive\"}', '', '', 'admin', '2026-05-07 17:53:11', 'success', 1, NULL, '2026-05-07 17:21:13', 'admin', '2026-05-07 17:57:21', 'admin', '1', '0');
INSERT INTO `bus_discount_rule` VALUES (3, 'e743c615a3fe46fb', '老人卡优惠', NULL, 'offline', 'ENT001', 'date', '2026-05-14', '2031-06-30', 'pending', '3', NULL, '{\"specialDiscount\":{\"cardTypes\":[\"老人免费卡\"],\"discountType\":\"discount\",\"discountRate\":0.0,\"reduceAmount\":0.0},\"transferDiscount\":{\"cardTypes\":[\"普通卡\"],\"periodType\":\"month\",\"intervals\":[{\"minAmount\":0.0,\"maxAmount\":80.0,\"discountRate\":100.0}]},\"employeeDiscount\":{\"discountRate\":0.0},\"routeIds\":[\"Test001\"],\"areaIds\":[\"14\"],\"priorityMode\":\"exclusive\"}', '', NULL, NULL, NULL, 'none', 0, NULL, '2026-05-14 16:32:32', 'admin', '2026-05-14 17:30:09', 'admin', '1', '0');
INSERT INTO `bus_discount_rule` VALUES (4, '2168136867d54753', '优惠1-复制', NULL, 'offline', 'ENT001', 'date', '2026-04-30', '2026-04-30', 'pending', '2', '{\"discountType\":\"coupon\",\"discountRate\":95.0,\"reduceAmount\":0.0,\"fullAmount\":0.0,\"routeIds\":[\"Test001\"],\"minAmount\":0.0,\"userStatus\":[],\"allow叠加\":false,\"叠加Type\":\"all\"}', '{\"specialDiscount\":{\"cardTypes\":[\"老人免费卡\"],\"discountType\":\"discount\",\"discountRate\":100.0,\"reduceAmount\":0.0},\"transferDiscount\":{\"cardTypes\":[\"普通卡\"],\"periodType\":\"month\",\"intervals\":[{\"minAmount\":0.0,\"maxAmount\":80.0,\"discountRate\":100.0}]},\"employeeDiscount\":{\"discountRate\":100.0},\"routeIds\":[],\"areaIds\":[],\"priorityMode\":\"exclusive\"}', NULL, NULL, NULL, NULL, 'none', 0, NULL, '2026-05-25 14:31:50', 'admin', '2026-05-25 14:31:44', NULL, '1', '0');
INSERT INTO `bus_discount_rule` VALUES (5, 'DSC_2025_011', '学生卡5折优惠', '中小学生持学生卡乘车5折', 'offline', 'ENT001', 'permanent', NULL, NULL, 'effective', '1.0', NULL, NULL, NULL, NULL, NULL, NULL, 'success', 0, NULL, '2026-05-27 10:59:29', 'system', '2026-05-27 10:59:29', NULL, '1', '0');
INSERT INTO `bus_discount_rule` VALUES (6, 'DSC_2025_012', '老人卡免费', '65岁以上老人持老人卡免费', 'offline', 'ENT001', 'permanent', NULL, NULL, 'effective', '1.0', NULL, NULL, NULL, NULL, NULL, NULL, 'success', 0, NULL, '2026-05-27 10:59:29', 'system', '2026-05-27 10:59:29', NULL, '1', '0');
INSERT INTO `bus_discount_rule` VALUES (7, 'DSC_2025_013', '普通卡8折', '普通公交卡乘车8折', 'offline', 'ENT001', 'date', '2025-01-01', '2025-12-31', 'effective', '1.0', NULL, NULL, NULL, NULL, NULL, NULL, 'success', 0, NULL, '2026-05-27 10:59:29', 'system', '2026-05-27 10:59:29', NULL, '1', '0');
INSERT INTO `bus_discount_rule` VALUES (8, 'DSC_2025_014', '早高峰优惠', '早7-9点乘车立减1元', 'online', 'ENT001', 'date', '2025-01-01', '2025-12-31', 'effective', '1.0', NULL, NULL, NULL, NULL, NULL, NULL, 'success', 0, NULL, '2026-05-27 10:59:29', 'system', '2026-05-27 10:59:29', NULL, '1', '0');
INSERT INTO `bus_discount_rule` VALUES (9, 'DSC_2025_015', '新客首单5折', '新用户首次乘车5折优惠', 'online', 'ENT001', 'date', '2025-01-01', '2025-06-30', 'effective', '1.0', NULL, NULL, NULL, NULL, NULL, NULL, 'success', 0, NULL, '2026-05-27 10:59:29', 'system', '2026-05-27 10:59:29', NULL, '1', '0');
INSERT INTO `bus_discount_rule` VALUES (10, 'DSC_2025_016', '周末半价', '周六日乘车5折优惠', 'online', 'ENT001', 'date', '2025-01-01', '2025-12-31', 'pending', '1.0', NULL, NULL, NULL, NULL, NULL, NULL, 'none', 0, NULL, '2026-05-27 10:59:29', 'admin', '2026-05-27 10:59:29', NULL, '1', '0');
INSERT INTO `bus_discount_rule` VALUES (11, 'DSC_2025_017', '会员日优惠', '每月8号会员日立减2元', 'online', 'ENT001', 'date', '2025-01-01', '2025-12-31', 'pending', '1.0', NULL, NULL, NULL, NULL, NULL, NULL, 'none', 0, NULL, '2026-05-27 10:59:29', 'admin', '2026-05-27 10:59:29', NULL, '1', '0');
INSERT INTO `bus_discount_rule` VALUES (12, 'DSC_2025_018', '换乘优惠', '1小时内换乘减1元', 'offline', 'ENT001', 'permanent', NULL, NULL, 'effective', '1.0', NULL, NULL, NULL, NULL, NULL, NULL, 'success', 0, NULL, '2026-05-27 10:59:29', 'system', '2026-05-27 10:59:29', NULL, '1', '0');
INSERT INTO `bus_discount_rule` VALUES (13, 'DSC_2025_019', '残疾人免费', '残疾人持证免费乘车', 'offline', 'ENT001', 'permanent', NULL, NULL, 'effective', '1.0', NULL, NULL, NULL, NULL, NULL, NULL, 'success', 0, NULL, '2026-05-27 10:59:29', 'system', '2026-05-27 10:59:29', NULL, '1', '0');
INSERT INTO `bus_discount_rule` VALUES (14, 'DSC_2025_020', '团体票8折', '3人以上团体购票8折', 'online', 'ENT001', 'date', '2025-01-01', '2025-12-31', 'rejected', '1.0', NULL, NULL, NULL, NULL, NULL, NULL, 'exception', 0, NULL, '2026-05-27 10:59:29', 'admin', '2026-05-27 10:59:29', NULL, '1', '0');

-- ----------------------------
-- Table structure for bus_discount_rule_history
-- ----------------------------
DROP TABLE IF EXISTS `bus_discount_rule_history`;
CREATE TABLE `bus_discount_rule_history`  (
  `id` bigint NOT NULL AUTO_INCREMENT COMMENT '主键',
  `discount_id` varchar(64) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci NOT NULL COMMENT '优惠ID',
  `version` varchar(20) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci NOT NULL COMMENT '版本号',
  `snapshot_json` longtext CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci NULL COMMENT '快照JSON',
  `operate_type` varchar(32) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci NULL DEFAULT NULL COMMENT '操作类型:create/update/audit/rollback/copy',
  `operate_by` varchar(64) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci NULL DEFAULT NULL COMMENT '操作人',
  `operate_time` datetime NULL DEFAULT CURRENT_TIMESTAMP COMMENT '操作时间',
  `tenant_id` varchar(32) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci NULL DEFAULT NULL COMMENT '租户ID',
  PRIMARY KEY (`id`) USING BTREE,
  INDEX `idx_bdrh_discount`(`discount_id` ASC) USING BTREE,
  INDEX `idx_bdrh_version`(`version` ASC) USING BTREE,
  INDEX `idx_bdrh_time`(`operate_time` ASC) USING BTREE
) ENGINE = InnoDB AUTO_INCREMENT = 26 CHARACTER SET = utf8mb4 COLLATE = utf8mb4_0900_ai_ci COMMENT = '优惠规则历史版本表' ROW_FORMAT = DYNAMIC;

-- ----------------------------
-- Records of bus_discount_rule_history
-- ----------------------------
INSERT INTO `bus_discount_rule_history` VALUES (1, '33166947e4f64dc4', '1.0', NULL, 'create', 'admin', '2026-04-30 17:23:33', '1');
INSERT INTO `bus_discount_rule_history` VALUES (2, '33166947e4f64dc4', '1.0', NULL, 'audit', 'admin', '2026-04-30 17:23:41', '1');
INSERT INTO `bus_discount_rule_history` VALUES (3, '33166947e4f64dc4', '1.0', NULL, 'audit', 'admin', '2026-04-30 17:24:12', '1');
INSERT INTO `bus_discount_rule_history` VALUES (4, '33166947e4f64dc4', '1.0', NULL, 'audit', 'admin', '2026-04-30 18:18:46', '1');
INSERT INTO `bus_discount_rule_history` VALUES (5, '33166947e4f64dc4', '1.1', NULL, 'update', 'admin', '2026-05-07 11:07:46', '1');
INSERT INTO `bus_discount_rule_history` VALUES (6, '33166947e4f64dc4', '1.1', NULL, 'audit', 'admin', '2026-05-07 16:40:16', '1');
INSERT INTO `bus_discount_rule_history` VALUES (7, '6422ceaaab204d6f', '1.0', NULL, 'create', 'admin', '2026-05-07 17:21:13', '1');
INSERT INTO `bus_discount_rule_history` VALUES (8, '6422ceaaab204d6f', '1.0', NULL, 'audit', 'admin', '2026-05-07 17:53:11', '1');
INSERT INTO `bus_discount_rule_history` VALUES (9, 'e743c615a3fe46fb', '1', NULL, 'create', 'admin', '2026-05-14 16:32:32', '1');
INSERT INTO `bus_discount_rule_history` VALUES (10, 'e743c615a3fe46fb', '1', NULL, 'audit', 'admin', '2026-05-14 17:28:58', '1');
INSERT INTO `bus_discount_rule_history` VALUES (11, 'e743c615a3fe46fb', '2', NULL, 'submit', 'admin', '2026-05-14 17:29:05', '1');
INSERT INTO `bus_discount_rule_history` VALUES (12, 'e743c615a3fe46fb', '2', NULL, 'audit', 'admin', '2026-05-14 17:29:33', '1');
INSERT INTO `bus_discount_rule_history` VALUES (13, 'e743c615a3fe46fb', '3', NULL, 'submit', 'admin', '2026-05-14 17:30:09', '1');
INSERT INTO `bus_discount_rule_history` VALUES (14, '2168136867d54753', '2', NULL, 'copy', 'admin', '2026-05-25 14:31:51', '1');
INSERT INTO `bus_discount_rule_history` VALUES (15, '33166947e4f64dc4', '1.1', NULL, 'audit', 'admin', '2026-05-25 14:32:09', '1');
INSERT INTO `bus_discount_rule_history` VALUES (16, 'DSC_2025_011', '1.0', NULL, 'create', 'system', '2026-05-27 10:59:39', '1');
INSERT INTO `bus_discount_rule_history` VALUES (17, 'DSC_2025_011', '1.0', NULL, 'audit', 'admin', '2026-05-27 10:59:39', '1');
INSERT INTO `bus_discount_rule_history` VALUES (18, 'DSC_2025_012', '1.0', NULL, 'create', 'system', '2026-05-27 10:59:39', '1');
INSERT INTO `bus_discount_rule_history` VALUES (19, 'DSC_2025_012', '1.0', NULL, 'audit', 'admin', '2026-05-27 10:59:39', '1');
INSERT INTO `bus_discount_rule_history` VALUES (20, 'DSC_2025_013', '1.0', NULL, 'create', 'system', '2026-05-27 10:59:39', '1');
INSERT INTO `bus_discount_rule_history` VALUES (21, 'DSC_2025_013', '1.0', NULL, 'audit', 'admin', '2026-05-27 10:59:39', '1');
INSERT INTO `bus_discount_rule_history` VALUES (22, 'DSC_2025_016', '1.0', NULL, 'create', 'admin', '2026-05-27 10:59:39', '1');
INSERT INTO `bus_discount_rule_history` VALUES (23, 'DSC_2025_016', '1.0', NULL, 'submit', 'admin', '2026-05-27 10:59:39', '1');
INSERT INTO `bus_discount_rule_history` VALUES (24, 'DSC_2025_017', '1.0', NULL, 'create', 'admin', '2026-05-27 10:59:39', '1');
INSERT INTO `bus_discount_rule_history` VALUES (25, 'DSC_2025_020', '1.0', NULL, 'create', 'admin', '2026-05-27 10:59:39', '1');

-- ----------------------------
-- Table structure for bus_dispatch_config
-- ----------------------------
DROP TABLE IF EXISTS `bus_dispatch_config`;
CREATE TABLE `bus_dispatch_config`  (
  `id` bigint NOT NULL AUTO_INCREMENT COMMENT '主键',
  `config_group` varchar(64) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci NOT NULL COMMENT '配置分组',
  `config_key` varchar(128) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci NOT NULL COMMENT '配置键',
  `config_value` varchar(512) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci NOT NULL COMMENT '配置值',
  `config_desc` varchar(255) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci NULL DEFAULT NULL COMMENT '配置说明',
  `create_time` datetime NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
  `update_time` datetime NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
  `tenant_id` varchar(32) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci NULL DEFAULT NULL COMMENT '租户ID',
  `del_flag` varchar(1) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci NULL DEFAULT '0' COMMENT '删除标记',
  PRIMARY KEY (`id`) USING BTREE,
  UNIQUE INDEX `uk_group_key_tenant`(`config_group` ASC, `config_key` ASC, `tenant_id` ASC) USING BTREE,
  INDEX `idx_config_group`(`config_group` ASC) USING BTREE
) ENGINE = InnoDB AUTO_INCREMENT = 111 CHARACTER SET = utf8mb4 COLLATE = utf8mb4_0900_ai_ci COMMENT = '调度参数配置' ROW_FORMAT = DYNAMIC;

-- ----------------------------
-- Records of bus_dispatch_config
-- ----------------------------
INSERT INTO `bus_dispatch_config` VALUES (1, 'vehicle_search', 'search_radius_km', '15', '自动调度搜索半径(km)', '2026-05-17 10:40:08', '2026-05-17 10:40:08', NULL, '0');
INSERT INTO `bus_dispatch_config` VALUES (2, 'vehicle_search', 'global_search_radius_km', '20', '全局调度搜索半径(km)', '2026-05-17 10:40:08', '2026-05-17 10:40:08', NULL, '0');
INSERT INTO `bus_dispatch_config` VALUES (3, 'vehicle_search', 'candidate_limit', '5', '自动调度候选车辆数', '2026-05-17 10:40:08', '2026-05-17 10:40:08', NULL, '0');
INSERT INTO `bus_dispatch_config` VALUES (4, 'vehicle_search', 'global_candidate_limit', '10', '全局调度候选车辆数', '2026-05-17 10:40:08', '2026-05-17 10:40:08', NULL, '0');
INSERT INTO `bus_dispatch_config` VALUES (5, 'vehicle_search', 'gps_fresh_minutes', '15', 'GPS有效时长(分钟)', '2026-05-17 10:40:08', '2026-05-17 10:40:08', NULL, '0');
INSERT INTO `bus_dispatch_config` VALUES (6, 'vehicle_search', 'batch_limit', '50', '每轮扫描需求上限', '2026-05-17 10:40:08', '2026-05-17 10:40:08', NULL, '0');
INSERT INTO `bus_dispatch_config` VALUES (7, 'scoring', 'weight_distance', '35', '距离权重(%)', '2026-05-17 10:40:08', '2026-05-17 10:40:08', NULL, '0');
INSERT INTO `bus_dispatch_config` VALUES (8, 'scoring', 'weight_wait_time', '25', '候车时间权重(%)', '2026-05-17 10:40:08', '2026-05-17 10:40:08', NULL, '0');
INSERT INTO `bus_dispatch_config` VALUES (9, 'scoring', 'weight_seat_utilization', '20', '座位利用率权重(%)', '2026-05-17 10:40:08', '2026-05-17 10:40:08', NULL, '0');
INSERT INTO `bus_dispatch_config` VALUES (10, 'scoring', 'weight_direction', '20', '方向一致性权重(%)', '2026-05-17 10:40:08', '2026-05-17 10:40:08', NULL, '0');
INSERT INTO `bus_dispatch_config` VALUES (11, 'scoring', 'avg_speed_kmh', '30', '平均车速(km/h)', '2026-05-17 10:40:08', '2026-05-17 10:40:08', NULL, '0');
INSERT INTO `bus_dispatch_config` VALUES (12, 'grouping', 'time_window_minutes', '15', '组客时间窗口(分钟)', '2026-05-17 10:40:08', '2026-05-17 10:40:08', NULL, '0');
INSERT INTO `bus_dispatch_config` VALUES (13, 'grouping', 'origin_radius_km', '2.0', '出发点聚合半径(km)', '2026-05-17 10:40:08', '2026-05-17 10:40:08', NULL, '0');
INSERT INTO `bus_dispatch_config` VALUES (14, 'grouping', 'direction_threshold_deg', '45', '方向偏差阈值(度)', '2026-05-17 10:40:08', '2026-05-17 10:40:08', NULL, '0');
INSERT INTO `bus_dispatch_config` VALUES (15, 'grouping', 'max_group_passengers', '8', '分组最大乘客数', '2026-05-17 10:40:08', '2026-05-17 10:40:08', NULL, '0');
INSERT INTO `bus_dispatch_config` VALUES (16, 'grouping', 'scan_limit', '200', '组客扫描批次上限', '2026-05-17 10:40:08', '2026-05-17 10:40:08', NULL, '0');
INSERT INTO `bus_dispatch_config` VALUES (17, 'business', 'max_reject_redispatch', '3', '最大改派次数', '2026-05-17 10:40:08', '2026-05-17 10:40:08', NULL, '0');
INSERT INTO `bus_dispatch_config` VALUES (18, 'business', 'reject_extend_minutes', '30', '改派续期时长(分钟)', '2026-05-17 10:40:08', '2026-05-17 10:40:08', NULL, '0');
INSERT INTO `bus_dispatch_config` VALUES (19, 'business', 'request_expire_minutes', '30', '需求默认过期时长(分钟)', '2026-05-17 10:40:08', '2026-05-17 10:40:08', NULL, '0');
INSERT INTO `bus_dispatch_config` VALUES (22, 'business', 'notify_expire_seconds', '3600', '推送消息过期时间(秒)', '2026-05-17 10:40:08', '2026-05-17 10:40:08', NULL, '0');
INSERT INTO `bus_dispatch_config` VALUES (23, 'business', 'route_opt_iterations', '200', '路径优化迭代次数', '2026-05-17 10:40:08', '2026-05-17 10:40:08', NULL, '0');

-- ----------------------------
-- Table structure for bus_dispatch_log
-- ----------------------------
DROP TABLE IF EXISTS `bus_dispatch_log`;
CREATE TABLE `bus_dispatch_log`  (
  `id` bigint NOT NULL AUTO_INCREMENT COMMENT '主键',
  `task_id` bigint NOT NULL COMMENT '调度任务ID',
  `action` varchar(32) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci NOT NULL COMMENT '操作类型:CREATE/DISPATCH/ACCEPT/REJECT/CANCEL/REASSIGN/COMPLETE',
  `from_status` varchar(20) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci NULL DEFAULT NULL COMMENT '变更前状态',
  `to_status` varchar(20) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci NULL DEFAULT NULL COMMENT '变更后状态',
  `operator` varchar(64) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci NULL DEFAULT NULL COMMENT '操作人',
  `remark` varchar(500) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci NULL DEFAULT NULL COMMENT '备注',
  `create_time` datetime NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
  `tenant_id` varchar(32) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci NULL DEFAULT NULL COMMENT '租户ID',
  PRIMARY KEY (`id`) USING BTREE,
  INDEX `idx_bdl_task`(`task_id` ASC) USING BTREE,
  INDEX `idx_bdl_tenant`(`tenant_id` ASC) USING BTREE
) ENGINE = InnoDB AUTO_INCREMENT = 79 CHARACTER SET = utf8mb4 COLLATE = utf8mb4_0900_ai_ci COMMENT = '调度操作日志表' ROW_FORMAT = DYNAMIC;

-- ----------------------------
-- Records of bus_dispatch_log
-- ----------------------------
INSERT INTO `bus_dispatch_log` VALUES (1, 1, 'CREATE', NULL, 'PENDING', 'admin', '创建调度任务', '2026-05-18 10:20:16', '1');
INSERT INTO `bus_dispatch_log` VALUES (41, 37, 'AUTO_GROUP_DISPATCH', NULL, 'DISPATCHED', 'system', '组客调度: 分组=GR20260516197020, 车辆=粤AF09091, 3个需求, 距离=1.69km', '2026-05-16 21:33:39', '1');
INSERT INTO `bus_dispatch_log` VALUES (42, 38, 'AUTO_DISPATCH', NULL, 'DISPATCHED', 'system', '自动调度匹配: 车辆=粤AF09091, 距离=1.00km', '2026-05-16 21:33:40', '1');
INSERT INTO `bus_dispatch_log` VALUES (43, 39, 'AUTO_DISPATCH', NULL, 'DISPATCHED', 'system', '自动调度匹配: 车辆=粤AF09091, 距离=0.90km', '2026-05-16 21:33:40', '1');
INSERT INTO `bus_dispatch_log` VALUES (44, 40, 'AUTO_DISPATCH', NULL, 'DISPATCHED', 'system', '自动调度匹配: 车辆=粤AF09091, 距离=1.90km', '2026-05-16 21:33:41', '1');
INSERT INTO `bus_dispatch_log` VALUES (45, 41, 'AUTO_DISPATCH', NULL, 'DISPATCHED', 'system', '自动调度匹配: 车辆=粤AF09091, 距离=0.38km', '2026-05-16 21:33:41', '1');
INSERT INTO `bus_dispatch_log` VALUES (46, 42, 'AUTO_DISPATCH', NULL, 'DISPATCHED', 'system', '自动调度匹配: 车辆=粤AF09091, 距离=1.12km', '2026-05-16 21:33:41', '1');
INSERT INTO `bus_dispatch_log` VALUES (47, 43, 'AUTO_DISPATCH', NULL, 'DISPATCHED', 'system', '自动调度匹配: 车辆=粤AF09091, 距离=0.97km', '2026-05-16 21:33:42', '1');
INSERT INTO `bus_dispatch_log` VALUES (48, 44, 'AUTO_DISPATCH', NULL, 'DISPATCHED', 'system', '自动调度匹配: 车辆=粤AF09091, 距离=3.42km', '2026-05-16 21:33:42', '1');
INSERT INTO `bus_dispatch_log` VALUES (49, 44, 'DISPATCH', 'DISPATCHED', 'DISPATCHED', 'admin', '指派司机: 测试司机, 车辆: 京D98765', '2026-05-21 16:07:47', '1');
INSERT INTO `bus_dispatch_log` VALUES (50, 44, 'CANCEL', 'DISPATCHED', 'CANCELLED', 'admin', '取消调度任务', '2026-05-21 16:19:51', '1');
INSERT INTO `bus_dispatch_log` VALUES (51, 45, 'CREATE', NULL, 'PENDING', 'admin', '创建调度任务', '2026-05-22 14:14:54', '1');
INSERT INTO `bus_dispatch_log` VALUES (52, 45, 'DISPATCH', 'PENDING', 'DISPATCHED', 'admin', '指派司机: 范工, 车辆: 粤A147230', '2026-05-22 14:14:59', '1');
INSERT INTO `bus_dispatch_log` VALUES (53, 45, 'DISPATCH', 'DISPATCHED', 'DISPATCHED', 'admin', '指派司机: 范工, 车辆: 粤A147230', '2026-05-22 14:43:41', '1');
INSERT INTO `bus_dispatch_log` VALUES (54, 1, 'CREATE', NULL, 'PENDING', 'system', '创建调度任务', '2026-05-27 10:59:04', '1');
INSERT INTO `bus_dispatch_log` VALUES (55, 1, 'DISPATCH', 'PENDING', 'DISPATCHED', 'system', '自动调度匹配: 车辆=粤A00001D, 距离=0.8km', '2026-05-27 10:59:04', '1');
INSERT INTO `bus_dispatch_log` VALUES (56, 1, 'ACCEPT', 'DISPATCHED', 'ACCEPTED', '陈伟强', '司机已接单', '2026-05-27 10:59:04', '1');
INSERT INTO `bus_dispatch_log` VALUES (57, 1, 'COMPLETE', 'ACCEPTED', 'COMPLETED', 'system', '订单完成', '2026-05-27 10:59:04', '1');
INSERT INTO `bus_dispatch_log` VALUES (58, 2, 'CREATE', NULL, 'PENDING', 'system', '创建调度任务', '2026-05-27 10:59:04', '1');
INSERT INTO `bus_dispatch_log` VALUES (59, 2, 'DISPATCH', 'PENDING', 'DISPATCHED', 'system', '自动调度匹配: 车辆=粤A00001D, 距离=0.75km', '2026-05-27 10:59:04', '1');
INSERT INTO `bus_dispatch_log` VALUES (60, 2, 'ACCEPT', 'DISPATCHED', 'ACCEPTED', '陈伟强', '司机已接单', '2026-05-27 10:59:04', '1');
INSERT INTO `bus_dispatch_log` VALUES (61, 2, 'COMPLETE', 'ACCEPTED', 'COMPLETED', 'system', '订单完成', '2026-05-27 10:59:04', '1');
INSERT INTO `bus_dispatch_log` VALUES (62, 5, 'CREATE', NULL, 'PENDING', 'system', '创建调度任务', '2026-05-27 10:59:04', '1');
INSERT INTO `bus_dispatch_log` VALUES (63, 5, 'DISPATCH', 'PENDING', 'DISPATCHED', 'system', '自动调度匹配: 车辆=粤A00004D, 距离=0.6km', '2026-05-27 10:59:04', '1');
INSERT INTO `bus_dispatch_log` VALUES (64, 56, 'AUTO_DISPATCH', NULL, 'DISPATCHED', 'system', '自动调度匹配: 车辆=京D98765, 距离=2.85km', '2026-05-28 17:18:30', '1');
INSERT INTO `bus_dispatch_log` VALUES (65, 57, 'AUTO_DISPATCH', NULL, 'DISPATCHED', 'system', '自动调度匹配: 车辆=京D98765, 距离=2.85km', '2026-05-28 17:18:32', '1');
INSERT INTO `bus_dispatch_log` VALUES (66, 58, 'AUTO_DISPATCH', NULL, 'DISPATCHED', 'system', '自动调度匹配: 车辆=京D98765, 距离=2.85km', '2026-05-28 17:18:33', '1');
INSERT INTO `bus_dispatch_log` VALUES (67, 59, 'AUTO_DISPATCH', NULL, 'DISPATCHED', 'system', '自动调度匹配: 车辆=京D98765, 距离=2.85km', '2026-05-28 17:18:33', '1');
INSERT INTO `bus_dispatch_log` VALUES (68, 60, 'AUTO_DISPATCH', NULL, 'DISPATCHED', 'system', '自动调度匹配: 车辆=京D98765, 距离=2.85km', '2026-05-28 17:18:34', '1');
INSERT INTO `bus_dispatch_log` VALUES (69, 61, 'AUTO_DISPATCH', NULL, 'DISPATCHED', 'system', '自动调度匹配: 车辆=京D98765, 距离=2.85km', '2026-05-28 17:18:34', '1');
INSERT INTO `bus_dispatch_log` VALUES (70, 62, 'AUTO_DISPATCH', NULL, 'DISPATCHED', 'system', '自动调度匹配: 车辆=京D98765, 距离=2.64km', '2026-05-28 17:58:55', '1');
INSERT INTO `bus_dispatch_log` VALUES (71, 63, 'AUTO_DISPATCH', NULL, 'DISPATCHED', 'system', '自动调度匹配: 车辆=京D98765, 距离=2.64km', '2026-05-28 17:58:58', '1');
INSERT INTO `bus_dispatch_log` VALUES (72, 64, 'AUTO_DISPATCH', NULL, 'DISPATCHED', 'system', '自动调度匹配: 车辆=京D98765, 距离=2.64km', '2026-05-28 17:59:02', '1');
INSERT INTO `bus_dispatch_log` VALUES (73, 65, 'AUTO_DISPATCH', NULL, 'DISPATCHED', 'system', '自动调度匹配: 车辆=京D98765, 距离=2.64km', '2026-05-28 18:02:40', '1');
INSERT INTO `bus_dispatch_log` VALUES (74, 66, 'AUTO_DISPATCH', NULL, 'DISPATCHED', 'system', '自动调度匹配: 车辆=粤A00009D, 距离=0.19km', '2026-05-29 10:29:06', '1');
INSERT INTO `bus_dispatch_log` VALUES (75, 67, 'AUTO_DISPATCH', NULL, 'DISPATCHED', 'system', '自动调度匹配: 车辆=粤A00010D, 距离=6.46km', '2026-05-30 10:57:34', '1');
INSERT INTO `bus_dispatch_log` VALUES (76, 68, 'AUTO_DISPATCH', NULL, 'DISPATCHED', 'system', '自动调度匹配: 车辆=粤A00010D, 距离=6.46km', '2026-05-30 10:57:35', '1');
INSERT INTO `bus_dispatch_log` VALUES (77, 68, 'DISPATCH', 'DISPATCHED', 'DISPATCHED', 'admin', '指派司机: 刘测试, 车辆: 粤A00010D', '2026-05-30 11:05:27', '1');
INSERT INTO `bus_dispatch_log` VALUES (78, 68, 'DISPATCH', 'DISPATCHED', 'DISPATCHED', 'admin', '指派司机: 刘测试, 车辆: 粤A00010D', '2026-05-30 11:08:03', '1');

-- ----------------------------
-- Table structure for bus_dispatch_route
-- ----------------------------
DROP TABLE IF EXISTS `bus_dispatch_route`;
CREATE TABLE `bus_dispatch_route`  (
  `id` bigint NOT NULL AUTO_INCREMENT COMMENT '主键',
  `dispatch_task_id` bigint NOT NULL COMMENT '关联调度任务ID',
  `ride_request_id` bigint NULL DEFAULT NULL COMMENT '关联约车需求ID',
  `vehicle_lng` double NULL DEFAULT NULL COMMENT '车辆出发经度',
  `vehicle_lat` double NULL DEFAULT NULL COMMENT '车辆出发纬度',
  `pickup_lng` double NULL DEFAULT NULL COMMENT '接客点经度',
  `pickup_lat` double NULL DEFAULT NULL COMMENT '接客点纬度',
  `pickup_address` varchar(255) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci NULL DEFAULT NULL COMMENT '接客地址',
  `dropoff_lng` double NULL DEFAULT NULL COMMENT '送达点经度',
  `dropoff_lat` double NULL DEFAULT NULL COMMENT '送达点纬度',
  `dropoff_address` varchar(255) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci NULL DEFAULT NULL COMMENT '送达地址',
  `pickup_distance_meters` int NULL DEFAULT NULL COMMENT '车辆到接客点距离(米)',
  `pickup_duration_seconds` int NULL DEFAULT NULL COMMENT '车辆到接客点预计时长(秒)',
  `trip_distance_meters` int NULL DEFAULT NULL COMMENT '接客点到送达点距离(米)',
  `trip_duration_seconds` int NULL DEFAULT NULL COMMENT '接客点到送达点预计时长(秒)',
  `total_distance_meters` int NULL DEFAULT NULL COMMENT '总距离(米)',
  `total_duration_seconds` int NULL DEFAULT NULL COMMENT '总时长(秒)',
  `pickup_polyline` text CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci NULL COMMENT '车辆到接客点路径编码',
  `trip_polyline` text CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci NULL COMMENT '接客到送达路径编码',
  `waypoints_json` text CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci NULL COMMENT '途经点JSON',
  `estimated_pickup_time` datetime NULL DEFAULT NULL COMMENT '预计到达接客点时间',
  `estimated_arrival_time` datetime NULL DEFAULT NULL COMMENT '预计到达目的地时间',
  `create_time` datetime NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
  `update_time` datetime NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
  `tenant_id` varchar(32) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci NULL DEFAULT NULL COMMENT '租户ID',
  PRIMARY KEY (`id`) USING BTREE,
  UNIQUE INDEX `uk_bdr_task`(`dispatch_task_id` ASC) USING BTREE,
  INDEX `idx_bdr_request`(`ride_request_id` ASC) USING BTREE,
  INDEX `idx_bdr_tenant`(`tenant_id` ASC) USING BTREE
) ENGINE = InnoDB AUTO_INCREMENT = 65 CHARACTER SET = utf8mb4 COLLATE = utf8mb4_0900_ai_ci COMMENT = '调度路径信息' ROW_FORMAT = DYNAMIC;

-- ----------------------------
-- Records of bus_dispatch_route
-- ----------------------------
INSERT INTO `bus_dispatch_route` VALUES (35, 37, NULL, 113.321045, 23.126591, 113.3215, 23.1268, '体育西路地铁站A口', 113.34, 23.155, '沙河服装城', 570, 0, 7492, 0, 8062, 0, '113.321049,23.126653;113.321179,23.126644;113.321179,23.126644;113.321179,23.126585;113.321179,23.126494;113.321179,23.126333;113.321179,23.12622;113.321174,23.125721;113.321174,23.125668;113.321179,23.125431;113.321195,23.124729;113.321206,23.124343;113.321372,23.124337;113.321372,23.124557;113.321372,23.124793;113.321367,23.124836;113.321372,23.125421;113.321372,23.125668;113.321394,23.126134;113.321399,23.12622;113.321405,23.12637;113.321324,23.126515;113.321324,23.126515;113.321624,23.126488;113.321624,23.126488;113.321643,23.126792', '113.321643,23.126792;113.321624,23.126488;113.321624,23.126488;113.321324,23.126515;113.321324,23.126515;113.32127,23.126655;113.321281,23.127202;113.321281,23.127202;113.321292,23.127309;113.321335,23.127379;113.321598,23.127566;113.323459,23.127448;113.323899,23.127416;113.323969,23.127416;113.324484,23.127368;113.324725,23.127341;113.325041,23.127304;113.325041,23.127304;113.325261,23.127261;113.325503,23.127239;113.325696,23.127223;113.326088,23.127196;113.326184,23.127191;113.327396,23.127121;113.327659,23.127116;113.327976,23.127127;113.328126,23.127406;113.328142,23.127668;113.328148,23.127738;113.32818,23.128098;113.32825,23.129267;113.328314,23.129755;113.328335,23.130023;113.328357,23.130404;113.328368,23.130705;113.328378,23.130876;113.328137,23.130957;113.327976,23.130962;113.327772,23.130968;113.327241,23.130978;113.327032,23.130984;113.326393,23.131021;113.325814,23.131021;113.325814,23.131021;113.325819,23.131155;113.325825,23.131257;113.32583,23.131348;113.325841,23.131649;113.325851,23.13189;113.325862,23.132126;113.325868,23.13233;113.325878,23.132523;113.325884,23.132679;113.325895,23.132893;113.325905,23.133054;113.325911,23.133135;113.325911,23.133215;113.325921,23.133451;113.326243,23.13343;113.326372,23.133425;113.326597,23.133408;113.32708,23.133392;113.327504,23.133381;113.327611,23.133379;113.327611,23.133379;113.327751,23.133376;113.327879,23.133371;113.327965,23.133371;113.328228,23.133365;113.328448,23.133516;113.328443,23.13416;113.328443,23.13505;113.328432,23.135581;113.328426,23.136375;113.328432,23.137121;113.328432,23.137206;113.328432,23.137582;113.328432,23.138086;113.328426,23.138666;113.328426,23.139674;113.328426,23.139915;113.328426,23.139953;113.328426,23.140924;113.328443,23.14138;113.328448,23.141503;113.328437,23.14175;113.328421,23.142437;113.328421,23.142485;113.328421,23.142651;113.328426,23.142893;113.328346,23.142909;113.328341,23.142549;113.328346,23.142142;113.328346,23.142142;113.328244,23.142142;113.32819,23.142142;113.328097,23.142137;113.328097,23.142137;113.328078,23.142136;113.328078,23.142136;113.32819,23.142142;113.328244,23.142142;113.328346,23.142142;113.328346,23.142142;113.328362,23.141815;113.328362,23.141815;113.328292,23.141653;113.328206,23.141578;113.328083,23.141503;113.328083,23.141503;113.327284,23.14146;113.327091,23.14145;113.326077,23.141396;113.326077,23.141396;113.325932,23.141482;113.325862,23.141536;113.325744,23.14168;113.325744,23.14168;113.32575,23.141949;113.32575,23.142206;113.32575,23.142759;113.325739,23.142973;113.325733,23.143118;113.325508,23.143606;113.325347,23.14396;113.325294,23.14411;113.325256,23.144266;113.32524,23.14469;113.325213,23.145087;113.325229,23.1452;113.325567,23.145752;113.325567,23.145752;113.325793,23.145639;113.326474,23.145532;113.327246,23.145393;113.327573,23.145333;113.328346,23.145194;113.328346,23.145194;113.328341,23.144749;113.328346,23.143858;113.328346,23.143655;113.328351,23.143096;113.328432,23.143091;113.32849,23.143096;113.32849,23.143096;113.329183,23.14315;113.329709,23.143209;113.329998,23.143236;113.330325,23.143268;113.330352,23.143274;113.330674,23.143306;113.331093,23.143349;113.331329,23.143376;113.331736,23.143418;113.331806,23.143424;113.331956,23.143435;113.332123,23.143408;113.332123,23.143408;113.332187,23.143376;113.332278,23.143274;113.332353,23.142796;113.332412,23.142463;113.332487,23.142136;113.332487,23.142136;113.332584,23.142099;113.332648,23.142093;113.332788,23.142179;113.332616,23.143134;113.332546,23.143644;113.332493,23.143848;113.332428,23.144153;113.332428,23.144454;113.332461,23.144953;113.332498,23.145248;113.332578,23.145602;113.332745,23.146128;113.333051,23.146954;113.333249,23.147458;113.333249,23.147458;113.333378,23.147903;113.333378,23.147903;113.333474,23.147994;113.333544,23.148193;113.333807,23.148938;113.333903,23.149185;113.333925,23.149228;113.334113,23.149566;113.334113,23.149566;113.334504,23.150043;113.334547,23.150135;113.334633,23.150338;113.334746,23.150575;113.334848,23.150709;113.33496,23.1508;113.335395,23.151111;113.335454,23.151159;113.335481,23.151224;113.335556,23.151336;113.335647,23.151481;113.335819,23.151739;113.33584,23.151765;113.33584,23.151765;113.33569,23.1519;113.335518,23.152055;113.335518,23.152055;113.335272,23.151787;113.335272,23.151787;113.33496,23.151449;113.334719,23.151186;113.334719,23.151186;113.33496,23.151449;113.335518,23.152055;113.335518,23.152055;113.33569,23.1519;113.33584,23.151765;113.33584,23.151765;113.336092,23.152098;113.336269,23.152329;113.336376,23.152479;113.336414,23.152538;113.336468,23.152608;113.33657,23.152785;113.336613,23.152988;113.336623,23.153471;113.336591,23.15411;113.336516,23.154818;113.336511,23.154893;113.336478,23.155177;113.336473,23.155708;113.336473,23.155885;113.336473,23.156052;113.336478,23.156266;113.336478,23.156427;113.336478,23.156427;113.336715,23.156416;113.336886,23.156416;113.337053,23.156422;113.337235,23.156422;113.337342,23.156422;113.337921,23.156411;113.337921,23.156411;113.3379,23.156062;113.337879,23.15581;113.337852,23.155558;113.33783,23.155338;113.33783,23.155338;113.338646,23.155327;113.339869,23.155317;113.339869,23.155317;113.339886,23.154994', '[{\"type\":\"PICKUP\",\"requestId\":\"60\",\"lng\":113.328,\"lat\":23.142,\"address\":\"林和西地铁站\",\"passengerCount\":1,\"seq\":1},{\"type\":\"DROPOFF\",\"requestId\":\"60\",\"lng\":113.3285,\"lat\":23.143,\"address\":\"中信广场\",\"passengerCount\":1,\"seq\":2},{\"type\":\"PICKUP\",\"requestId\":\"61\",\"lng\":113.335,\"lat\":23.152,\"address\":\"沙河顶地铁站\",\"passengerCount\":2,\"seq\":3},{\"type\":\"DROPOFF\",\"requestId\":\"61\",\"lng\":113.34,\"lat\":23.155,\"address\":\"沙河服装城\",\"passengerCount\":2,\"seq\":4},{\"type\":\"PICKUP\",\"requestId\":\"53\",\"lng\":113.3215,\"lat\":23.1268,\"address\":\"体育西路地铁站A口\",\"passengerCount\":1,\"seq\":5},{\"type\":\"DROPOFF\",\"requestId\":\"53\",\"lng\":113.3276,\"lat\":23.1329,\"address\":\"天河城购物中心\",\"passengerCount\":1,\"seq\":6}]', '2026-05-16 21:33:39', '2026-05-16 21:33:39', '2026-05-16 21:33:39', '2026-05-16 21:33:34', '1');
INSERT INTO `bus_dispatch_route` VALUES (36, 38, 59, 113.321045, 23.126591, 113.312, 23.13, '杨箕地铁站', 113.325, 23.144, '广州动物园', 2013, 0, 4218, 0, 6231, 0, '113.321049,23.126653;113.321179,23.126644;113.321179,23.126644;113.321179,23.126585;113.321179,23.126494;113.321179,23.126333;113.321179,23.12622;113.321174,23.125721;113.321174,23.125668;113.321179,23.125431;113.321195,23.124729;113.321206,23.124343;113.321206,23.124241;113.321077,23.123983;113.321077,23.123983;113.320879,23.123908;113.32075,23.123881;113.319806,23.123972;113.319216,23.124005;113.318663,23.124042;113.318572,23.124058;113.318159,23.124112;113.317837,23.12415;113.317762,23.124155;113.317628,23.124166;113.316861,23.12423;113.316587,23.124251;113.316464,23.124262;113.316265,23.124278;113.31589,23.124316;113.315316,23.124326;113.315316,23.124326;113.315321,23.124434;113.315332,23.12497;113.315343,23.125512;113.315343,23.125646;113.315348,23.12599;113.315348,23.126161;113.315348,23.126161;113.31537,23.12622;113.315434,23.126386;113.315445,23.12651;113.315536,23.126665;113.315616,23.128875;113.315621,23.128951;113.315702,23.129117;113.315702,23.129117;113.31575,23.129176;113.315825,23.129299;113.315858,23.129444;113.315863,23.12953;113.315836,23.129659;113.315772,23.129803;113.315557,23.129981;113.315391,23.130023;113.315193,23.130018;113.315112,23.129997;113.315064,23.129959;113.314956,23.129884;113.314881,23.129787;113.314828,23.129659;113.314806,23.129541;113.314806,23.129541;113.31471,23.129546;113.314479,23.129626;113.313985,23.129675;113.313706,23.129648;113.313347,23.129605;113.313224,23.129589;113.313036,23.129562;113.312988,23.129557;113.31266,23.129514;113.312569,23.129498;113.312221,23.129455;113.311856,23.129412;113.311856,23.129412;113.311974,23.129798;113.31196,23.129997', '113.31196,23.129997;113.311974,23.129798;113.311856,23.129412;113.311856,23.129412;113.311555,23.129364;113.310949,23.129213;113.310633,23.129111;113.310423,23.128945;113.310048,23.128811;113.309356,23.128516;113.309356,23.128516;113.309501,23.128516;113.309678,23.128495;113.310515,23.128843;113.310928,23.129004;113.311287,23.129106;113.311598,23.129176;113.312167,23.129267;113.312623,23.12931;113.312693,23.129315;113.312988,23.129348;113.31317,23.129369;113.313637,23.129428;113.314232,23.129455;113.314629,23.129428;113.314967,23.129374;113.315064,23.129342;113.315064,23.129342;113.31516,23.129256;113.315193,23.129235;113.31523,23.129224;113.315273,23.129213;113.315407,23.129197;113.31552,23.129224;113.315552,23.12923;113.315579,23.129246;113.315616,23.129273;113.315697,23.129401;113.315713,23.129551;113.315707,23.129616;113.31567,23.129718;113.315579,23.129803;113.315536,23.129825;113.315536,23.129825;113.315504,23.129948;113.315455,23.130329;113.315461,23.130415;113.315466,23.130496;113.315482,23.131257;113.315525,23.132411;113.315541,23.13351;113.315595,23.133741;113.315595,23.133741;113.315659,23.133795;113.315713,23.133859;113.315723,23.133891;113.31574,23.13395;113.31574,23.134079;113.315718,23.134138;113.315681,23.134186;113.315541,23.134267;113.315541,23.134267;113.315482,23.134755;113.315402,23.135506;113.315326,23.136251;113.315321,23.136305;113.315316,23.136359;113.315289,23.136536;113.315257,23.136788;113.315214,23.137206;113.315214,23.137228;113.315208,23.137287;113.315176,23.137652;113.315155,23.138049;113.315123,23.138397;113.315123,23.138397;113.315026,23.13925;113.31494,23.139846;113.314892,23.140307;113.314892,23.140307;113.314887,23.140393;113.314801,23.1413;113.314785,23.141423;113.314667,23.142657;113.314651,23.142818;113.314597,23.143429;113.31456,23.143982;113.314447,23.145291;113.314425,23.145516;113.315208,23.145532;113.316238,23.145548;113.317505,23.145602;113.318475,23.14565;113.319162,23.145688;113.31943,23.145698;113.31986,23.145714;113.320305,23.145736;113.32127,23.145741;113.321962,23.145741;113.32237,23.145741;113.322435,23.145741;113.32259,23.145746;113.323014,23.145736;113.323722,23.145736;113.323835,23.145784;113.323835,23.145784;113.323877,23.145114;113.323883,23.144534;113.323851,23.143655;113.323851,23.143579;113.323845,23.143279;113.323845,23.143016;113.324253,23.143027;113.324301,23.143032;113.324371,23.143043;113.324784,23.143107;113.324784,23.143107;113.324741,23.1433;113.324746,23.143418;113.324746,23.143418;113.324972,23.143418;113.324988,23.143483;113.324988,23.143644;113.324995,23.144', NULL, '2026-05-16 21:33:40', '2026-05-16 21:33:40', '2026-05-16 21:33:40', '2026-05-16 21:33:35', '1');
INSERT INTO `bus_dispatch_route` VALUES (37, 39, 58, 113.321045, 23.126591, 113.316, 23.12, '五羊邨', 113.3245, 23.1317, '天河体育中心', 1302, 0, 3040, 0, 4342, 0, '113.321049,23.126653;113.321179,23.126644;113.321179,23.126644;113.321179,23.126585;113.321179,23.126494;113.321179,23.126333;113.321179,23.12622;113.321174,23.125721;113.321174,23.125668;113.321179,23.125431;113.321195,23.124729;113.321206,23.124343;113.321206,23.124241;113.321077,23.123983;113.321077,23.123983;113.320991,23.123886;113.320959,23.123742;113.320981,23.123608;113.321061,23.123511;113.321061,23.123511;113.321141,23.123195;113.321163,23.123103;113.321152,23.12225;113.321115,23.121086;113.321104,23.120738;113.321099,23.120131;113.321099,23.12003;113.321093,23.119858;113.321093,23.119858;113.320948,23.119686;113.32089,23.119643;113.320739,23.119547;113.320739,23.119547;113.320251,23.119574;113.320192,23.119579;113.320047,23.11959;113.319951,23.119595;113.319688,23.119616;113.319114,23.119649;113.318905,23.119681;113.31847,23.119724;113.31839,23.11974;113.31796,23.119777;113.317113,23.119836;113.317113,23.119836;113.317032,23.119922;113.316011,23.12007', '113.315982,23.119898;113.315927,23.119906;113.315927,23.119906;113.315643,23.12003;113.315579,23.120073;113.315407,23.120282;113.315407,23.120282;113.315402,23.120319;113.315396,23.120464;113.315391,23.120968;113.315396,23.121151;113.315396,23.121274;113.315396,23.121725;113.315386,23.122605;113.315364,23.122787;113.3153,23.123055;113.315305,23.123393;113.31531,23.123543;113.315316,23.123978;113.315316,23.124326;113.315321,23.124434;113.315332,23.12497;113.315343,23.125512;113.315343,23.125646;113.315348,23.12599;113.315348,23.126161;113.315348,23.126161;113.315348,23.12622;113.315353,23.12659;113.31537,23.127443;113.31538,23.128301;113.31538,23.128301;113.315418,23.130249;113.315407,23.130619;113.315418,23.130764;113.315418,23.130764;113.315525,23.131155;113.315563,23.131413;113.315595,23.133741;113.315595,23.133741;113.315659,23.133795;113.315713,23.133859;113.315713,23.133859;113.316539,23.133827;113.317161,23.133805;113.317639,23.133784;113.3178,23.133773;113.318942,23.133709;113.319151,23.133779;113.321217,23.133671;113.321469,23.133639;113.32163,23.133618;113.321941,23.133564;113.323598,23.133489;113.323598,23.133489;113.323598,23.133097;113.323593,23.133006;113.323582,23.132765;113.323566,23.132534;113.323561,23.132448;113.32355,23.132336;113.32354,23.132164;113.323486,23.131499;113.323459,23.131118;113.323459,23.131118;113.32414,23.131102;113.324425,23.131096;113.324505,23.131091;113.324543,23.131091;113.324671,23.131086;113.325004,23.131064;113.325085,23.131059;113.325149,23.131059;113.32524,23.131053;113.325342,23.131048;113.325814,23.131021;113.325814,23.131021;113.325819,23.131155;113.325825,23.131257;113.32583,23.131348;113.325841,23.131649;113.325841,23.131649;113.325739,23.13167;113.325642,23.131676;113.325605,23.13166;113.325455,23.131563;113.32517,23.131466;113.325004,23.131413;113.324982,23.131391', NULL, '2026-05-16 21:33:40', '2026-05-16 21:33:40', '2026-05-16 21:33:40', '2026-05-16 21:33:35', '1');
INSERT INTO `bus_dispatch_route` VALUES (38, 40, 56, 113.321045, 23.126591, 113.3382, 23.12, '猎德地铁站', 113.332, 23.126, '冼村', 2841, 0, 2362, 0, 5203, 0, '113.321049,23.126653;113.321179,23.126644;113.321179,23.126644;113.321179,23.126585;113.321179,23.126494;113.321179,23.126333;113.321179,23.12622;113.321174,23.125721;113.321174,23.125668;113.321179,23.125431;113.321195,23.124729;113.321206,23.124343;113.321206,23.124241;113.321077,23.123983;113.321077,23.123983;113.320991,23.123886;113.320959,23.123742;113.320981,23.123608;113.321061,23.123511;113.321174,23.123468;113.321281,23.123452;113.321458,23.1235;113.321458,23.1235;113.32171,23.123608;113.321855,23.123613;113.323261,23.1235;113.323261,23.1235;113.323352,23.12349;113.323513,23.123479;113.32583,23.123302;113.326077,23.12328;113.327429,23.123173;113.327885,23.123125;113.328088,23.123109;113.328603,23.123034;113.328974,23.123007;113.32944,23.122969;113.330208,23.122921;113.330208,23.122921;113.330948,23.122905;113.332804,23.122755;113.332804,23.122755;113.334295,23.122605;113.33496,23.122524;113.3362,23.122368;113.337026,23.122218;113.338141,23.122014;113.339032,23.121961;113.339402,23.121961;113.339756,23.121961;113.339976,23.121955;113.340615,23.121955;113.340679,23.12195;113.340679,23.12195;113.340641,23.121585;113.340641,23.121531;113.340641,23.121414;113.340636,23.12128;113.340636,23.121043;113.340636,23.121043;113.34048,23.121043;113.34004,23.121038;113.339826,23.121022;113.339413,23.120925;113.339321,23.120899;113.339048,23.120807;113.338941,23.120786;113.338619,23.120732;113.338211,23.120657;113.338061,23.12062;113.337863,23.120502;113.337863,23.120501;113.337986,23.12033;113.338018,23.120217;113.338206,23.120115;113.338222,23.120083;113.338231,23.120002', '113.338231,23.120002;113.338222,23.120083;113.338206,23.120115;113.338018,23.120217;113.337986,23.12033;113.337863,23.120501;113.337863,23.120502;113.338061,23.12062;113.338211,23.120657;113.338619,23.120732;113.338941,23.120786;113.339048,23.120807;113.339321,23.120899;113.339413,23.120925;113.339826,23.121022;113.34004,23.121038;113.34048,23.121043;113.340636,23.121043;113.340754,23.121043;113.340754,23.121274;113.340759,23.121414;113.340759,23.121531;113.340759,23.121575;113.340765,23.12195;113.340765,23.12195;113.340904,23.12195;113.341028,23.121945;113.341349,23.121934;113.342959,23.12188;113.343372,23.12187;113.343522,23.122358;113.343527,23.12247;113.343527,23.122529;113.343538,23.123018;113.343543,23.123457;113.34356,23.123876;113.34357,23.124187;113.34357,23.124487;113.34357,23.124563;113.343586,23.125174;113.343586,23.125201;113.343586,23.125544;113.343592,23.126021;113.343463,23.126392;113.34312,23.126419;113.342819,23.126435;113.342583,23.126451;113.342326,23.126467;113.342293,23.126472;113.341709,23.12651;113.341521,23.12652;113.340979,23.126553;113.340716,23.12651;113.340437,23.12652;113.339788,23.126569;113.339466,23.126596;113.339321,23.126606;113.338555,23.126665;113.338501,23.126665;113.338329,23.126671;113.338034,23.126676;113.337739,23.126676;113.337417,23.126676;113.337219,23.126676;113.336784,23.12674;113.336698,23.126746;113.336698,23.126746;113.336634,23.1268;113.335953,23.126901;113.335792,23.126912;113.335105,23.126966;113.33496,23.126976;113.334327,23.127014;113.334156,23.127025;113.333995,23.12703;113.333995,23.12703;113.333721,23.127046;113.333555,23.127003;113.333442,23.126955;113.333244,23.12681;113.333174,23.126719;113.333174,23.126719;113.333169,23.126397;113.333169,23.126306;113.333169,23.12622;113.333185,23.125941;113.333185,23.125941;113.333067,23.125941;113.333002,23.125941;113.33297,23.125957;113.332793,23.12622;113.332702,23.126349;113.332591,23.126468', NULL, '2026-05-16 21:33:41', '2026-05-16 21:33:41', '2026-05-16 21:33:41', '2026-05-16 21:33:35', '1');
INSERT INTO `bus_dispatch_route` VALUES (39, 41, 54, 113.321045, 23.126591, 113.324, 23.1245, '珠江新城地铁站', 113.325, 23.1085, '广州塔', NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, '2026-05-16 21:33:41', '2026-05-16 21:33:36', '1');
INSERT INTO `bus_dispatch_route` VALUES (40, 42, 62, 113.321045, 23.126591, 113.331, 23.1225, '黄埔大道西', 113.342, 23.119, '跑马场', 1509, 0, 1944, 0, 3453, 0, '113.321049,23.126653;113.321179,23.126644;113.321179,23.126644;113.321179,23.126585;113.321179,23.126494;113.321179,23.126333;113.321179,23.12622;113.321174,23.125721;113.321174,23.125668;113.321179,23.125431;113.321195,23.124729;113.321206,23.124343;113.321206,23.124241;113.321077,23.123983;113.321077,23.123983;113.320991,23.123886;113.320959,23.123742;113.320981,23.123608;113.321061,23.123511;113.321174,23.123468;113.321281,23.123452;113.321458,23.1235;113.321458,23.1235;113.32171,23.123608;113.321855,23.123613;113.323261,23.1235;113.323261,23.1235;113.323352,23.12349;113.323513,23.123479;113.32583,23.123302;113.326077,23.12328;113.327429,23.123173;113.327885,23.123125;113.328088,23.123109;113.328603,23.123034;113.328974,23.123007;113.32944,23.122969;113.330208,23.122921;113.330208,23.122921;113.330272,23.122873;113.330594,23.122819;113.330594,23.122819;113.330706,23.122706;113.330749,23.122642;113.330755,23.122605;113.330749,23.122068;113.330792,23.122068;113.330803,23.122583;113.330803,23.122583;113.3309,23.122588;113.330958,23.122607', '113.330958,23.122607;113.3309,23.122588;113.330803,23.122583;113.330803,23.122583;113.330835,23.122674;113.330964,23.122787;113.330964,23.122787;113.332101,23.122696;113.332171,23.12269;113.332874,23.122626;113.333024,23.12261;113.333211,23.122572;113.333211,23.122572;113.333313,23.122524;113.333469,23.122417;113.333474,23.122095;113.33348,23.121918;113.33349,23.121698;113.333501,23.121054;113.333501,23.121054;113.333426,23.120802;113.333415,23.120394;113.333426,23.119869;113.333442,23.119493;113.333448,23.118989;113.333474,23.118506;113.333882,23.118259;113.334316,23.118211;113.334574,23.11819;113.33496,23.118152;113.335041,23.118141;113.335743,23.118082;113.336258,23.118039;113.336521,23.118018;113.338238,23.117846;113.338597,23.117809;113.339134,23.117771;113.33922,23.11776;113.339617,23.117718;113.340732,23.11761;113.340802,23.1176;113.341505,23.11753;113.342937,23.117449;113.34327,23.117423;113.343281,23.117664;113.343077,23.117675;113.342873,23.117691;113.342224,23.117744;113.342224,23.117744;113.342235,23.1179;113.342251,23.118141;113.342261,23.118265;113.342272,23.11857;113.342251,23.118672;113.342143,23.118828;113.342056,23.119021', NULL, '2026-05-16 21:33:42', '2026-05-16 21:33:42', '2026-05-16 21:33:41', '2026-05-16 21:33:36', '1');
INSERT INTO `bus_dispatch_route` VALUES (41, 43, 55, 113.321045, 23.126591, 113.3302, 23.1289, '天河南一路', 113.338, 23.134, '石牌桥', 1814, 0, NULL, NULL, NULL, NULL, '113.321049,23.126653;113.321179,23.126644;113.321179,23.126644;113.321179,23.126585;113.321179,23.126494;113.321179,23.126333;113.321179,23.12622;113.321174,23.125721;113.321174,23.125668;113.321179,23.125431;113.321195,23.124729;113.321206,23.124343;113.321372,23.124337;113.321372,23.124557;113.321372,23.124793;113.321367,23.124836;113.321372,23.125421;113.321372,23.125668;113.321394,23.126134;113.321399,23.12622;113.321405,23.12637;113.321324,23.126515;113.32127,23.126655;113.321281,23.127202;113.321281,23.127202;113.321292,23.127309;113.321335,23.127379;113.321598,23.127566;113.323459,23.127448;113.323899,23.127416;113.323969,23.127416;113.324484,23.127368;113.324725,23.127341;113.325041,23.127304;113.325041,23.127304;113.325261,23.127261;113.325503,23.127239;113.325696,23.127223;113.326088,23.127196;113.326184,23.127191;113.327396,23.127121;113.327659,23.127116;113.327976,23.127127;113.328126,23.127406;113.328142,23.127668;113.328148,23.127738;113.32818,23.128098;113.32825,23.129267;113.32825,23.129267;113.328882,23.129224;113.329494,23.129219;113.329596,23.129213;113.329596,23.129213;113.329591,23.129047;113.32958,23.128886;113.329569,23.128441;113.329569,23.128441;113.330068,23.12843;113.330068,23.12843;113.330095,23.128693;113.330105,23.128903', NULL, NULL, '2026-05-16 21:33:42', NULL, '2026-05-16 21:33:42', '2026-05-16 21:33:37', '1');
INSERT INTO `bus_dispatch_route` VALUES (42, 44, 57, 113.321045, 23.126591, 113.3478, 23.145, '华师地铁站', 113.342, 23.137, '岗顶', 6027, 0, 6409, 0, 12436, 0, '113.321049,23.126653;113.321179,23.126644;113.321179,23.126644;113.321179,23.126585;113.321179,23.126494;113.321179,23.126333;113.321179,23.12622;113.321174,23.125721;113.321174,23.125668;113.321179,23.125431;113.321195,23.124729;113.321206,23.124343;113.321372,23.124337;113.321372,23.124557;113.321372,23.124793;113.321367,23.124836;113.321372,23.125421;113.321372,23.125668;113.321394,23.126134;113.321399,23.12622;113.321405,23.12637;113.321324,23.126515;113.32127,23.126655;113.321281,23.127202;113.321281,23.127202;113.321292,23.127309;113.321335,23.127379;113.321598,23.127566;113.323459,23.127448;113.323899,23.127416;113.323969,23.127416;113.324484,23.127368;113.324725,23.127341;113.325041,23.127304;113.325041,23.127304;113.325261,23.127261;113.325503,23.127239;113.325696,23.127223;113.326088,23.127196;113.326184,23.127191;113.327396,23.127121;113.327659,23.127116;113.327976,23.127127;113.328083,23.127121;113.32825,23.127078;113.328416,23.127051;113.328475,23.127046;113.328534,23.127046;113.328641,23.12703;113.329773,23.126944;113.331012,23.126869;113.332246,23.126789;113.333174,23.126719;113.334123,23.126665;113.334123,23.126665;113.334231,23.126558;113.334252,23.12651;113.334274,23.126435;113.334274,23.126333;113.334258,23.12629;113.334225,23.126236;113.334215,23.12622;113.334188,23.126188;113.334134,23.126145;113.334054,23.126081;113.333995,23.126048;113.333903,23.126011;113.333823,23.126;113.333726,23.126011;113.333641,23.126048;113.333576,23.126107;113.33355,23.12615;113.333523,23.12622;113.333512,23.126252;113.333458,23.12651;113.333496,23.127116;113.333496,23.127153;113.333539,23.127524;113.333796,23.129176;113.333882,23.129696;113.333893,23.129761;113.333909,23.129873;113.333941,23.130093;113.333957,23.1302;113.334016,23.130608;113.334016,23.130608;113.334054,23.13115;113.334236,23.132432;113.334236,23.132432;113.334274,23.132797;113.334279,23.133253;113.334258,23.133601;113.334204,23.133956;113.33414,23.134315;113.333861,23.135844;113.333823,23.136123;113.333753,23.136536;113.333721,23.136718;113.333619,23.137206;113.33356,23.137496;113.333539,23.137609;113.333496,23.137845;113.33349,23.137893;113.333228,23.139358;113.333228,23.139358;113.332927,23.140903;113.332927,23.140903;113.332686,23.142228;113.332445,23.143542;113.332423,23.143751;113.332428,23.144153;113.332428,23.144454;113.332461,23.144953;113.332498,23.145248;113.332578,23.145602;113.332745,23.146128;113.333051,23.146954;113.333249,23.147458;113.333249,23.147458;113.333464,23.147667;113.333598,23.147941;113.333786,23.148193;113.333893,23.148338;113.333984,23.148402;113.334027,23.148423;113.334097,23.14844;113.334172,23.148434;113.334215,23.148423;113.334402,23.148365;113.334585,23.148305;113.334842,23.14822;113.334928,23.148193;113.33496,23.148182;113.335808,23.147919;113.336156,23.147823;113.336328,23.147785;113.336596,23.147748;113.336897,23.147646;113.337632,23.147393;113.33768,23.147377;113.339032,23.146927;113.340523,23.146444;113.341478,23.146133;113.342272,23.145875;113.342605,23.145784;113.343098,23.145661;113.343753,23.145543;113.34474,23.145393;113.34474,23.145393;113.344847,23.145409;113.344965,23.145414;113.345083,23.145403;113.345367,23.145366;113.345995,23.145285;113.346033,23.145275;113.346537,23.145205;113.346537,23.145205;113.347797,23.144986', '113.347797,23.144986;113.348302,23.144899;113.350099,23.14476;113.350254,23.144733;113.350844,23.144727;113.351542,23.144749;113.353457,23.144867;113.35431,23.144947;113.356101,23.145071;113.356933,23.145092;113.357078,23.145092;113.357786,23.14506;113.358408,23.144985;113.358907,23.144904;113.359224,23.14484;113.359701,23.144716;113.360034,23.14462;113.360093,23.144604;113.360892,23.144373;113.361691,23.144137;113.362421,23.143944;113.363145,23.14374;113.363145,23.14374;113.363241,23.143633;113.363295,23.143595;113.363569,23.143488;113.364239,23.143274;113.364395,23.143204;113.364486,23.14314;113.364534,23.143096;113.364701,23.142914;113.364733,23.142887;113.364776,23.142855;113.364851,23.142818;113.364888,23.142807;113.364969,23.142796;113.365103,23.142812;113.36521,23.142861;113.365275,23.142903;113.365275,23.142903;113.36536,23.143016;113.365376,23.14307;113.365382,23.143188;113.365376,23.143231;113.365355,23.143274;113.365226,23.143483;113.364749,23.143611;113.363864,23.143864;113.363563,23.143923;113.363483,23.143928;113.363343,23.143923;113.363134,23.143982;113.362796,23.144073;113.362206,23.14425;113.361788,23.144352;113.360162,23.144824;113.359964,23.144867;113.359798,23.14491;113.359272,23.145044;113.358955,23.145108;113.358322,23.145215;113.357791,23.145269;113.356933,23.145307;113.356187,23.145285;113.351933,23.144985;113.351413,23.144958;113.350876,23.144936;113.350646,23.144926;113.350646,23.144926;113.35041,23.144953;113.349551,23.145049;113.348532,23.145124;113.347358,23.145275;113.347358,23.145275;113.347288,23.145382;113.347218,23.145505;113.347218,23.145709;113.347213,23.145768;113.347202,23.145838;113.347175,23.145897;113.347084,23.146031;113.346955,23.146149;113.34666,23.146321;113.346585,23.146369;113.34651,23.146433;113.34651,23.146433;113.346757,23.147082;113.34681,23.14727;113.346805,23.147335;113.347052,23.147785;113.347089,23.14785;113.347089,23.14785;113.347159,23.147876;113.34725,23.147978;113.347384,23.148193;113.347556,23.148461;113.347744,23.148794;113.347744,23.148794;113.347728,23.148901;113.347695,23.148944;113.347626,23.148965;113.347524,23.148955;113.347095,23.148193;113.347052,23.148118;113.346998,23.147855;113.346746,23.147393;113.346746,23.147393;113.346537,23.146905;113.346338,23.146337;113.346193,23.145773;113.346129,23.145495;113.346118,23.145457;113.346033,23.145065;113.345963,23.144716;113.345957,23.144674;113.34592,23.144379;113.345909,23.144019;113.345915,23.143842;113.345941,23.143472;113.345957,23.142828;113.345979,23.141933;113.345979,23.141933;113.345952,23.141815;113.345925,23.141745;113.345866,23.141696;113.345802,23.141659;113.345641,23.141653;113.345566,23.141653;113.345421,23.141648;113.345244,23.141643;113.345078,23.141637;113.344976,23.141637;113.344402,23.141595;113.344069,23.141568;113.343667,23.141551;113.343254,23.14153;113.343023,23.141509;113.342615,23.141487;113.341575,23.141455;113.340244,23.141423;113.340201,23.141192;113.34018,23.141101;113.340169,23.141069;113.340132,23.140806;113.340126,23.140774;113.340094,23.14057;113.340078,23.140436;113.340073,23.14042;113.340019,23.140098;113.339955,23.139717;113.339955,23.139717;113.340105,23.139636;113.340207,23.13954;113.340303,23.1394;113.340384,23.139266;113.340529,23.139068;113.340646,23.138896;113.340759,23.138746;113.340829,23.138644;113.340915,23.13851;113.340995,23.138408;113.341054,23.138247;113.341092,23.138118;113.341172,23.137856;113.341194,23.137754;113.341221,23.137448;113.341237,23.137281;113.341242,23.137206;113.341253,23.137105;113.341263,23.136852;113.341269,23.136697;113.341263,23.136219;113.341263,23.136219;113.341467,23.136337;113.341666,23.136466;113.341666,23.136466;113.341698,23.136445;113.341741,23.13645;113.341768,23.136477;113.341768,23.136515;113.341768,23.136515;113.342133,23.136536;113.342175,23.136557;113.342218,23.136627;113.342218,23.136708;113.342186,23.136858;113.342143,23.136906;113.342143,23.136906;113.341988,23.136926', NULL, '2026-05-16 21:33:42', '2026-05-16 21:33:43', '2026-05-16 21:33:42', '2026-05-16 21:33:37', '1');
INSERT INTO `bus_dispatch_route` VALUES (43, 1, NULL, NULL, NULL, 113.3215, 23.1268, '体育西路站', 113.322, 23.127, '珠江新城站', 800, NULL, 1500, NULL, 2300, NULL, NULL, NULL, NULL, '2026-05-27 08:30:00', '2026-05-27 08:45:00', '2026-05-27 10:58:59', '2026-05-27 10:58:59', '1');
INSERT INTO `bus_dispatch_route` VALUES (44, 2, NULL, NULL, NULL, 113.3215, 23.1268, '体育西路站', 113.322, 23.127, '珠江新城站', 750, NULL, 1500, NULL, 2250, NULL, NULL, NULL, NULL, '2026-05-27 09:00:00', '2026-05-27 09:15:00', '2026-05-27 10:58:59', '2026-05-27 10:58:59', '1');
INSERT INTO `bus_dispatch_route` VALUES (45, 3, NULL, NULL, NULL, 113.325, 23.109, '广州塔站', 113.3175, 23.1005, '客村站', 1200, NULL, 2500, NULL, 3700, NULL, NULL, NULL, NULL, '2026-05-27 08:45:00', '2026-05-27 09:00:00', '2026-05-27 10:58:59', '2026-05-27 10:58:59', '1');
INSERT INTO `bus_dispatch_route` VALUES (46, 4, NULL, NULL, NULL, 113.325, 23.109, '广州塔站', 113.3175, 23.1005, '客村站', 1150, NULL, 2500, NULL, 3650, NULL, NULL, NULL, NULL, '2026-05-27 10:00:00', '2026-05-27 10:15:00', '2026-05-27 10:58:59', '2026-05-27 10:58:59', '1');
INSERT INTO `bus_dispatch_route` VALUES (47, 5, NULL, NULL, NULL, 113.267, 23.128, '公园前站', 113.272, 23.122, '北京路站', 600, NULL, 1800, NULL, 2400, NULL, NULL, NULL, NULL, '2026-05-27 11:00:00', '2026-05-27 11:10:00', '2026-05-27 10:58:59', '2026-05-27 10:58:59', '1');
INSERT INTO `bus_dispatch_route` VALUES (48, 7, NULL, NULL, NULL, 113.3215, 23.1268, '体育西路站', 113.325, 23.109, '广州塔站', 3500, NULL, 4200, NULL, 7700, NULL, NULL, NULL, NULL, '2026-05-27 07:30:00', '2026-05-27 08:00:00', '2026-05-27 10:58:59', '2026-05-27 10:58:59', '1');
INSERT INTO `bus_dispatch_route` VALUES (49, 8, NULL, NULL, NULL, 113.365, 22.945, '番禺广场站', 113.385, 23.058, '大学城北站', 5000, NULL, 12500, NULL, 17500, NULL, NULL, NULL, NULL, '2026-05-27 14:00:00', '2026-05-27 14:30:00', '2026-05-27 10:58:59', '2026-05-27 10:58:59', '1');
INSERT INTO `bus_dispatch_route` VALUES (50, 9, NULL, NULL, NULL, 113.365, 22.945, '番禺广场站', 113.385, 23.058, '大学城北站', 5000, NULL, 12500, NULL, 17500, NULL, NULL, NULL, NULL, '2026-05-27 14:00:00', '2026-05-27 14:30:00', '2026-05-27 10:58:59', '2026-05-27 10:58:59', '1');
INSERT INTO `bus_dispatch_route` VALUES (51, 10, NULL, NULL, NULL, 113.3215, 23.1268, '体育西路站', 113.322, 23.127, '珠江新城站', 820, NULL, 1500, NULL, 2320, NULL, NULL, NULL, NULL, '2026-05-28 08:00:00', '2026-05-28 08:15:00', '2026-05-27 10:58:59', '2026-05-27 10:58:59', '1');
INSERT INTO `bus_dispatch_route` VALUES (52, 59, 77, 113.330045, 23.131807, 113.3245, 23.1067, '广州塔站', 113.314474, 23.150741, '沙河', 3988, 478, 7004, 840, 10992, 1318, NULL, NULL, NULL, '2026-05-28 17:26:38', '2026-05-28 17:40:38', '2026-05-28 17:18:33', '2026-05-28 17:18:33', '1');
INSERT INTO `bus_dispatch_route` VALUES (53, 61, 77, 113.330045, 23.131807, 113.3245, 23.1067, '广州塔站', 113.314474, 23.150741, '沙河', 3988, 478, 7004, 840, 10992, 1318, NULL, NULL, NULL, '2026-05-28 17:26:38', '2026-05-28 17:40:38', '2026-05-28 17:18:34', '2026-05-28 17:18:33', '1');
INSERT INTO `bus_dispatch_route` VALUES (54, 60, 77, 113.330045, 23.131807, 113.3245, 23.1067, '广州塔站', 113.314474, 23.150741, '沙河', 3988, 478, 7004, 840, 10992, 1318, NULL, NULL, NULL, '2026-05-28 17:26:38', '2026-05-28 17:40:38', '2026-05-28 17:18:34', '2026-05-28 17:18:33', '1');
INSERT INTO `bus_dispatch_route` VALUES (55, 58, 77, 113.330045, 23.131807, 113.3245, 23.1067, '广州塔站', 113.314474, 23.150741, '沙河', 3988, 478, 7004, 840, 10992, 1318, NULL, NULL, NULL, '2026-05-28 17:26:38', '2026-05-28 17:40:38', '2026-05-28 17:18:33', '2026-05-28 17:18:33', '1');
INSERT INTO `bus_dispatch_route` VALUES (56, 57, 77, 113.330045, 23.131807, 113.3245, 23.1067, '广州塔站', 113.314474, 23.150741, '沙河', 3988, 478, 7004, 840, 10992, 1318, NULL, NULL, NULL, '2026-05-28 17:26:38', '2026-05-28 17:40:38', '2026-05-28 17:18:32', '2026-05-28 17:18:33', '1');
INSERT INTO `bus_dispatch_route` VALUES (57, 56, 77, 113.330045, 23.131807, 113.3245, 23.1067, '广州塔站', 113.314474, 23.150741, '沙河', 3988, 478, 7004, 840, 10992, 1318, NULL, NULL, NULL, '2026-05-28 17:26:38', '2026-05-28 17:40:38', '2026-05-28 17:18:30', '2026-05-28 17:18:33', '1');
INSERT INTO `bus_dispatch_route` VALUES (58, 62, 78, 113.330016, 23.13181, 113.314474, 23.150741, '沙河', 113.326576, 23.148611, '广州东站', 3692, 443, 1763, 211, 5455, 654, NULL, NULL, NULL, '2026-05-28 18:06:28', '2026-05-28 18:09:59', '2026-05-28 17:58:55', '2026-05-28 17:58:58', '1');
INSERT INTO `bus_dispatch_route` VALUES (59, 63, 78, 113.330016, 23.13181, 113.314474, 23.150741, '沙河', 113.326576, 23.148611, '广州东站', 3692, 443, 1763, 211, 5455, 654, NULL, NULL, NULL, '2026-05-28 18:06:28', '2026-05-28 18:09:59', '2026-05-28 17:58:58', '2026-05-28 17:58:58', '1');
INSERT INTO `bus_dispatch_route` VALUES (60, 64, 78, 113.330016, 23.13181, 113.314474, 23.150741, '沙河', 113.326576, 23.148611, '广州东站', 3692, 443, 1763, 211, 5455, 654, NULL, NULL, NULL, '2026-05-28 18:06:28', '2026-05-28 18:09:59', '2026-05-28 17:59:02', '2026-05-28 17:58:58', '1');
INSERT INTO `bus_dispatch_route` VALUES (61, 65, 79, 113.330016, 23.13181, 113.314474, 23.150741, '沙河', 113.326576, 23.148611, '广州东站', 3692, 443, 1763, 211, 5455, 654, NULL, NULL, NULL, '2026-05-28 18:10:13', '2026-05-28 18:13:44', '2026-05-28 18:02:40', '2026-05-28 18:02:43', '1');
INSERT INTO `bus_dispatch_route` VALUES (62, 66, 83, 113.330067, 23.131856, 113.331482, 23.133003, '石牌桥地铁站口站', 113.331482, 23.133003, '石牌桥A口公交站', 270, 32, 0, 0, 270, 32, NULL, NULL, NULL, '2026-05-29 10:29:48', '2026-05-29 10:29:48', '2026-05-29 10:29:06', '2026-05-29 10:29:08', '1');
INSERT INTO `bus_dispatch_route` VALUES (63, 68, 86, 113.330017, 23.131809, 113.267, 23.128, '公园前站', 113.272, 23.122, '北京路站', 9040, 1085, 1176, 141, 10216, 1226, NULL, NULL, NULL, '2026-05-30 11:15:49', '2026-05-30 11:18:10', '2026-05-30 10:57:35', '2026-05-30 10:57:36', '1');
INSERT INTO `bus_dispatch_route` VALUES (64, 67, 86, 113.330017, 23.131809, 113.267, 23.128, '公园前站', 113.272, 23.122, '北京路站', 9040, 1085, 1176, 141, 10216, 1226, NULL, NULL, NULL, '2026-05-30 11:15:49', '2026-05-30 11:18:10', '2026-05-30 10:57:34', '2026-05-30 10:57:36', '1');

-- ----------------------------
-- Table structure for bus_dispatch_task
-- ----------------------------
DROP TABLE IF EXISTS `bus_dispatch_task`;
CREATE TABLE `bus_dispatch_task`  (
  `id` bigint NOT NULL AUTO_INCREMENT COMMENT '主键',
  `task_no` varchar(64) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci NOT NULL COMMENT '调度任务编号',
  `order_id` varchar(64) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci NULL DEFAULT NULL COMMENT '关联订单ID',
  `order_no` varchar(64) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci NULL DEFAULT NULL COMMENT '订单编号',
  `passenger_phone` varchar(32) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci NULL DEFAULT NULL COMMENT '乘客手机号',
  `passenger_count` int NULL DEFAULT 1 COMMENT '乘客人数',
  `start_station` varchar(128) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci NULL DEFAULT NULL COMMENT '出发站点',
  `end_station` varchar(128) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci NULL DEFAULT NULL COMMENT '目的站点',
  `route_id` varchar(64) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci NULL DEFAULT NULL COMMENT '路线ID',
  `route_name` varchar(128) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci NULL DEFAULT NULL COMMENT '路线名称',
  `schedule_id` bigint NULL DEFAULT NULL COMMENT '匹配排班ID',
  `driver_id` bigint NULL DEFAULT NULL COMMENT '指派司机ID',
  `driver_name` varchar(64) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci NULL DEFAULT NULL COMMENT '司机姓名',
  `driver_phone` varchar(32) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci NULL DEFAULT NULL COMMENT '司机手机号',
  `vehicle_id` bigint NULL DEFAULT NULL COMMENT '指派车辆ID',
  `vehicle_no` varchar(32) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci NULL DEFAULT NULL COMMENT '车牌号',
  `dispatch_status` varchar(20) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci NOT NULL DEFAULT 'PENDING' COMMENT '调度状态:PENDING/DISPATCHED/ACCEPTED/REJECTED/PICKING_UP/IN_SERVICE/COMPLETED/CANCELLED',
  `dispatch_type` varchar(20) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci NOT NULL DEFAULT 'MANUAL' COMMENT '调度方式:MANUAL/AUTO',
  `dispatch_time` datetime NULL DEFAULT NULL COMMENT '调度时间',
  `planned_departure_time` datetime NULL DEFAULT NULL COMMENT '计划发车时间',
  `actual_departure_time` datetime NULL DEFAULT NULL COMMENT '实际发车时间',
  `driver_respond_time` datetime NULL DEFAULT NULL COMMENT '司机响应时间',
  `reject_reason` varchar(255) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci NULL DEFAULT NULL COMMENT '拒绝原因',
  `remark` varchar(500) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci NULL DEFAULT NULL COMMENT '调度备注',
  `create_time` datetime NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
  `create_by` varchar(64) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci NULL DEFAULT NULL COMMENT '创建人',
  `update_time` datetime NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
  `update_by` varchar(64) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci NULL DEFAULT NULL COMMENT '更新人',
  `tenant_id` varchar(32) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci NULL DEFAULT NULL COMMENT '租户ID',
  `del_flag` varchar(1) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci NULL DEFAULT '0' COMMENT '删除标记',
  PRIMARY KEY (`id`) USING BTREE,
  UNIQUE INDEX `uk_bdt_task_no`(`task_no` ASC) USING BTREE,
  INDEX `idx_bdt_order`(`order_id` ASC) USING BTREE,
  INDEX `idx_bdt_status`(`dispatch_status` ASC) USING BTREE,
  INDEX `idx_bdt_driver`(`driver_id` ASC) USING BTREE,
  INDEX `idx_bdt_schedule`(`schedule_id` ASC) USING BTREE,
  INDEX `idx_bdt_tenant`(`tenant_id` ASC) USING BTREE
) ENGINE = InnoDB AUTO_INCREMENT = 69 CHARACTER SET = utf8mb4 COLLATE = utf8mb4_0900_ai_ci COMMENT = '调度任务表' ROW_FORMAT = DYNAMIC;

-- ----------------------------
-- Records of bus_dispatch_task
-- ----------------------------
INSERT INTO `bus_dispatch_task` VALUES (1, 'DT20260518335328', '59a3dd42b5fe4e879aed5a763f447e9e', 'ORD_20260518094215_604928', NULL, 1, '12', '11', NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, 'ACCEPTED', 'AUTO', NULL, NULL, NULL, '2026-05-18 20:31:35', NULL, NULL, '2026-05-18 10:20:12', 'admin', '2026-05-18 10:20:12', 'admin', '1', '0');
INSERT INTO `bus_dispatch_task` VALUES (37, 'AT20260516211687', 'NEAR_ORD_001', 'NEAR20260516001', '13912340001', 4, '体育西路地铁站A口', '天河城购物中心', NULL, NULL, NULL, 5, '温俊业', '13725277480', 4, '粤AF09091', 'DISPATCHED', 'AUTO', '2026-05-16 21:33:39', NULL, NULL, NULL, NULL, '组客分组: GR20260516197020, 3个需求, 4人', '2026-05-16 21:33:34', 'admin', '2026-05-16 21:33:34', 'admin', '1', '0');
INSERT INTO `bus_dispatch_task` VALUES (38, 'AT20260516839341', 'NEAR_ORD_007', 'NEAR20260516007', '13912340007', 2, '杨箕地铁站', '广州动物园', NULL, NULL, NULL, 5, '温俊业', '13725277480', 4, '粤AF09091', 'DISPATCHED', 'AUTO', '2026-05-16 21:33:40', NULL, NULL, NULL, NULL, NULL, '2026-05-16 21:33:34', 'admin', '2026-05-16 21:33:34', 'admin', '1', '0');
INSERT INTO `bus_dispatch_task` VALUES (39, 'AT20260516148083', 'NEAR_ORD_006', 'NEAR20260516006', '13912340006', 1, '五羊邨', '天河体育中心', 'R_GZ07', '体育中心专线', NULL, 5, '温俊业', '13725277480', 4, '粤AF09091', 'DISPATCHED', 'AUTO', '2026-05-16 21:33:40', NULL, NULL, NULL, NULL, NULL, '2026-05-16 21:33:35', 'admin', '2026-05-16 21:33:35', 'admin', '1', '0');
INSERT INTO `bus_dispatch_task` VALUES (40, 'AT20260516431503', 'NEAR_ORD_004', 'NEAR20260516004', '13912340004', 3, '猎德地铁站', '冼村', NULL, NULL, NULL, 5, '温俊业', '13725277480', 4, '粤AF09091', 'DISPATCHED', 'AUTO', '2026-05-16 21:33:41', NULL, NULL, NULL, NULL, NULL, '2026-05-16 21:33:35', 'admin', '2026-05-16 21:33:35', 'admin', '1', '0');
INSERT INTO `bus_dispatch_task` VALUES (41, 'AT20260516263020', 'NEAR_ORD_002', 'NEAR20260516002', '13912340002', 2, '珠江新城地铁站', '广州塔', NULL, NULL, NULL, 5, '温俊业', '13725277480', 4, '粤AF09091', 'DISPATCHED', 'AUTO', '2026-05-16 21:33:41', NULL, NULL, NULL, NULL, NULL, '2026-05-16 21:33:36', 'admin', '2026-05-16 21:33:36', 'admin', '1', '0');
INSERT INTO `bus_dispatch_task` VALUES (42, 'AT20260516566037', 'NEAR_ORD_010', 'NEAR20260516010', '13912340010', 1, '黄埔大道西', '跑马场', NULL, NULL, NULL, 5, '温俊业', '13725277480', 4, '粤AF09091', 'DISPATCHED', 'AUTO', '2026-05-16 21:33:41', NULL, NULL, NULL, NULL, NULL, '2026-05-16 21:33:36', 'admin', '2026-05-16 21:33:36', 'admin', '1', '0');
INSERT INTO `bus_dispatch_task` VALUES (43, 'AT20260516864473', 'NEAR_ORD_003', 'NEAR20260516003', '13912340003', 1, '天河南一路', '石牌桥', NULL, NULL, NULL, 5, '温俊业', '13725277480', 4, '粤AF09091', 'DISPATCHED', 'AUTO', '2026-05-16 21:33:42', NULL, NULL, NULL, NULL, NULL, '2026-05-16 21:33:36', 'admin', '2026-05-16 21:33:36', 'admin', '1', '0');
INSERT INTO `bus_dispatch_task` VALUES (44, 'AT20260516752202', 'NEAR_ORD_005', 'NEAR20260516005', '13912340005', 1, '华师地铁站', '岗顶', NULL, NULL, NULL, 5, '测试司机', '13432496354', 4, '京D98765', 'CANCELLED', 'AUTO', '2026-05-21 16:07:47', NULL, NULL, NULL, NULL, NULL, '2026-05-16 21:33:37', 'admin', '2026-05-16 21:33:37', 'admin', '1', '0');
INSERT INTO `bus_dispatch_task` VALUES (45, 'DT20260522453201', '1f37e6a70d66444c87fae320798a88d4', 'ORD_20260515173553_308416', NULL, 1, '13', '12', NULL, NULL, NULL, 4, '范工', '13802402145', 8, '粤A147230', 'ACCEPTED', 'MANUAL', '2026-05-22 14:43:41', NULL, NULL, '2026-05-25 10:08:25', NULL, NULL, '2026-05-22 14:14:48', 'admin', '2026-05-22 14:14:48', 'admin', '1', '0');
INSERT INTO `bus_dispatch_task` VALUES (46, 'DT202605270001', 'ORD_2025001', 'ORD202605270001', '13900010001', 1, '体育西路站', '珠江新城站', 'R_GZ_201', NULL, NULL, 2001, '陈伟强', NULL, NULL, '粤A00001D', 'COMPLETED', 'AUTO', '2026-05-27 08:25:00', NULL, NULL, NULL, NULL, NULL, '2026-05-27 10:58:53', NULL, '2026-05-27 10:58:53', NULL, '1', '0');
INSERT INTO `bus_dispatch_task` VALUES (47, 'DT202605270002', 'ORD_2025002', 'ORD202605270002', '13900010002', 2, '体育西路站', '珠江新城站', 'R_GZ_201', NULL, NULL, 2001, '陈伟强', NULL, NULL, '粤A00001D', 'COMPLETED', 'AUTO', '2026-05-27 08:55:00', NULL, NULL, NULL, NULL, NULL, '2026-05-27 10:58:53', NULL, '2026-05-27 10:58:53', NULL, '1', '0');
INSERT INTO `bus_dispatch_task` VALUES (48, 'DT202605270003', 'ORD_2025003', 'ORD202605270003', '13900010003', 1, '广州塔站', '客村站', 'R_GZ_202', NULL, NULL, 2002, '李俊杰', NULL, NULL, '粤A00002D', 'COMPLETED', 'AUTO', '2026-05-27 08:40:00', NULL, NULL, NULL, NULL, NULL, '2026-05-27 10:58:53', NULL, '2026-05-27 10:58:53', NULL, '1', '0');
INSERT INTO `bus_dispatch_task` VALUES (49, 'DT202605270004', 'ORD_2025004', 'ORD202605270004', '13900010004', 3, '广州塔站', '客村站', 'R_GZ_202', NULL, NULL, 2002, '李俊杰', NULL, NULL, '粤A00002D', 'COMPLETED', 'AUTO', '2026-05-27 09:55:00', NULL, NULL, NULL, NULL, NULL, '2026-05-27 10:58:53', NULL, '2026-05-27 10:58:53', NULL, '1', '0');
INSERT INTO `bus_dispatch_task` VALUES (50, 'DT202605270005', 'ORD_2025005', 'ORD202605270005', '13900010005', 1, '公园前站', '北京路站', 'R_GZ_204', NULL, NULL, 2003, '王美芳', NULL, NULL, '粤A00004D', 'ACCEPTED', 'AUTO', '2026-05-27 10:55:00', NULL, NULL, NULL, NULL, NULL, '2026-05-27 10:58:53', NULL, '2026-05-27 10:58:53', NULL, '1', '0');
INSERT INTO `bus_dispatch_task` VALUES (51, 'DT202605270006', 'ORD_2025006', 'ORD202605270006', '13900010006', 2, '陈家祠站', '长寿路站', 'R_GZ_205', NULL, NULL, NULL, NULL, NULL, NULL, NULL, 'PENDING', 'AUTO', NULL, NULL, NULL, NULL, NULL, NULL, '2026-05-27 10:58:53', NULL, '2026-05-27 10:58:53', NULL, '1', '0');
INSERT INTO `bus_dispatch_task` VALUES (52, 'DT202605270007', 'ORD_2025009', 'ORD202605270009', '13900010009', 2, '体育西路站', '广州塔站', NULL, NULL, NULL, 2006, '黄志强', NULL, NULL, '粤A00006D', 'DISPATCHED', 'MANUAL', '2026-05-27 07:25:00', NULL, NULL, NULL, NULL, NULL, '2026-05-27 10:58:53', NULL, '2026-05-27 10:58:53', NULL, '1', '0');
INSERT INTO `bus_dispatch_task` VALUES (53, 'DT202605270008', 'ORD_2025010', 'ORD202605270010', '13900010010', 4, '番禺广场站', '大学城北站', 'R_GZ_203', NULL, NULL, 2008, '林振华', NULL, NULL, '粤A00008D', 'COMPLETED', 'AUTO', '2026-05-27 13:55:00', NULL, NULL, NULL, NULL, NULL, '2026-05-27 10:58:53', NULL, '2026-05-27 10:58:53', NULL, '1', '0');
INSERT INTO `bus_dispatch_task` VALUES (54, 'DT202605270009', 'ORD_2025010', 'ORD202605270010', '13900010010', 4, '番禺广场站', '大学城北站', 'R_GZ_203', NULL, NULL, 2008, '林振华', NULL, NULL, '粤A00008D', 'COMPLETED', 'AUTO', '2026-05-27 13:55:00', NULL, NULL, NULL, NULL, NULL, '2026-05-27 10:58:53', NULL, '2026-05-27 10:58:53', NULL, '1', '0');
INSERT INTO `bus_dispatch_task` VALUES (55, 'DT202605280001', NULL, NULL, '13900010011', 1, '体育西路站', '珠江新城站', 'R_GZ_201', NULL, NULL, 2001, '陈伟强', NULL, NULL, '粤A00001D', 'CANCELLED', 'MANUAL', '2026-05-28 08:00:00', NULL, NULL, NULL, NULL, NULL, '2026-05-27 10:58:53', NULL, '2026-05-27 10:58:53', NULL, '1', '0');
INSERT INTO `bus_dispatch_task` VALUES (56, 'AT20260528121274', '1f641c34605749b8a55e8bc6349665e0', 'ORD_20260528171807_195776', NULL, 1, '2019', '2013', NULL, NULL, NULL, 5, '刘罗瑞', '13652944754', 4, '京D98765', 'DISPATCHED', 'AUTO', '2026-05-28 17:18:30', NULL, NULL, NULL, NULL, NULL, '2026-05-28 17:18:23', 'admin', '2026-05-28 17:18:23', 'admin', '1', '0');
INSERT INTO `bus_dispatch_task` VALUES (57, 'AT20260528319225', '1f641c34605749b8a55e8bc6349665e0', 'ORD_20260528171807_195776', NULL, 1, '2019', '2013', NULL, NULL, NULL, 5, '刘罗瑞', '13652944754', 4, '京D98765', 'DISPATCHED', 'AUTO', '2026-05-28 17:18:32', NULL, NULL, NULL, NULL, NULL, '2026-05-28 17:18:25', 'admin', '2026-05-28 17:18:25', 'admin', '1', '0');
INSERT INTO `bus_dispatch_task` VALUES (58, 'AT20260528362205', '1f641c34605749b8a55e8bc6349665e0', 'ORD_20260528171807_195776', NULL, 1, '2019', '2013', NULL, NULL, NULL, 5, '刘罗瑞', '13652944754', 4, '京D98765', 'DISPATCHED', 'AUTO', '2026-05-28 17:18:33', NULL, NULL, NULL, NULL, NULL, '2026-05-28 17:18:25', 'admin', '2026-05-28 17:18:25', 'admin', '1', '0');
INSERT INTO `bus_dispatch_task` VALUES (59, 'AT20260528204689', '1f641c34605749b8a55e8bc6349665e0', 'ORD_20260528171807_195776', NULL, 1, '2019', '2013', NULL, NULL, NULL, 5, '刘罗瑞', '13652944754', 4, '京D98765', 'DISPATCHED', 'AUTO', '2026-05-28 17:18:33', NULL, NULL, NULL, NULL, NULL, '2026-05-28 17:18:26', 'admin', '2026-05-28 17:18:26', 'admin', '1', '0');
INSERT INTO `bus_dispatch_task` VALUES (60, 'AT20260528595841', '1f641c34605749b8a55e8bc6349665e0', 'ORD_20260528171807_195776', NULL, 1, '2019', '2013', NULL, NULL, NULL, 5, '刘罗瑞', '13652944754', 4, '京D98765', 'DISPATCHED', 'AUTO', '2026-05-28 17:18:34', NULL, NULL, NULL, NULL, NULL, '2026-05-28 17:18:26', 'admin', '2026-05-28 17:18:26', 'admin', '1', '0');
INSERT INTO `bus_dispatch_task` VALUES (61, 'AT20260528789106', '1f641c34605749b8a55e8bc6349665e0', 'ORD_20260528171807_195776', NULL, 1, '2019', '2013', NULL, NULL, NULL, 5, '刘罗瑞', '13652944754', 4, '京D98765', 'DISPATCHED', 'AUTO', '2026-05-28 17:18:34', NULL, NULL, NULL, NULL, NULL, '2026-05-28 17:18:26', 'admin', '2026-05-28 17:18:26', 'admin', '1', '0');
INSERT INTO `bus_dispatch_task` VALUES (62, 'AT20260528577726', '139f11dec5df439398070737451dcd23', 'ORD_20260528175725_268928', NULL, 1, '2013', '2014', NULL, NULL, NULL, 5, '刘罗瑞', '13652944754', 4, '京D98765', 'DISPATCHED', 'AUTO', '2026-05-28 17:58:55', NULL, NULL, NULL, NULL, NULL, '2026-05-28 17:58:48', 'admin', '2026-05-28 17:58:48', 'admin', '1', '0');
INSERT INTO `bus_dispatch_task` VALUES (63, 'AT20260528457569', '139f11dec5df439398070737451dcd23', 'ORD_20260528175725_268928', NULL, 1, '2013', '2014', NULL, NULL, NULL, 5, '刘罗瑞', '13652944754', 4, '京D98765', 'DISPATCHED', 'AUTO', '2026-05-28 17:58:58', NULL, NULL, NULL, NULL, NULL, '2026-05-28 17:58:50', 'admin', '2026-05-28 17:58:50', 'admin', '1', '0');
INSERT INTO `bus_dispatch_task` VALUES (64, 'AT20260528257531', '139f11dec5df439398070737451dcd23', 'ORD_20260528175725_268928', NULL, 1, '2013', '2014', NULL, NULL, NULL, 5, '刘罗瑞', '13652944754', 4, '京D98765', 'DISPATCHED', 'AUTO', '2026-05-28 17:59:02', NULL, NULL, NULL, NULL, NULL, '2026-05-28 17:58:55', 'admin', '2026-05-28 17:58:55', 'admin', '1', '0');
INSERT INTO `bus_dispatch_task` VALUES (65, 'AT20260528655560', '45ba93a1d6194c05a28f69d6c328196a', 'ORD_20260528180232_085632', NULL, 1, '2013', '2014', NULL, NULL, NULL, 5, '刘罗瑞', '13652944754', 4, '京D98765', 'DISPATCHED', 'AUTO', '2026-05-28 18:02:40', NULL, NULL, NULL, NULL, NULL, '2026-05-28 18:02:33', 'admin', '2026-05-28 18:02:33', 'admin', '1', '0');
INSERT INTO `bus_dispatch_task` VALUES (66, 'AT20260529198724', '8cd9743567404874b060d3033290ac8d', 'ORD_20260529102858_880896', NULL, 1, '13', '20', NULL, NULL, NULL, 700045867025624230, NULL, NULL, 4009, '粤A00009D', 'DISPATCHED', 'AUTO', '2026-05-29 10:29:06', NULL, NULL, NULL, NULL, NULL, '2026-05-29 10:28:58', 'admin', '2026-05-29 10:28:58', 'admin', '1', '0');
INSERT INTO `bus_dispatch_task` VALUES (67, 'AT20260530785029', '585b3e1050844e24b0ff09dc45da1c5b', 'ORD_20260530105548_574848', NULL, 1, '2007', '2008', NULL, NULL, NULL, 28888, NULL, NULL, 4010, '粤A00010D', 'DISPATCHED', 'AUTO', '2026-05-30 10:57:34', NULL, NULL, NULL, NULL, NULL, '2026-05-30 10:57:26', 'admin', '2026-05-30 10:57:26', 'admin', '1', '0');
INSERT INTO `bus_dispatch_task` VALUES (68, 'AT20260530258293', '585b3e1050844e24b0ff09dc45da1c5b', 'ORD_20260530105548_574848', NULL, 1, '2007', '2008', NULL, NULL, NULL, 2012, '刘测试', '19102053473', 4010, '粤A00010D', 'DISPATCHED', 'AUTO', '2026-05-30 11:08:03', NULL, NULL, NULL, NULL, NULL, '2026-05-30 10:57:27', 'admin', '2026-05-30 10:57:27', 'admin', '1', '0');

-- ----------------------------
-- Table structure for bus_driver
-- ----------------------------
DROP TABLE IF EXISTS `bus_driver`;
CREATE TABLE `bus_driver`  (
  `id` bigint NOT NULL AUTO_INCREMENT COMMENT '主键ID',
  `driver_id` varchar(50) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci NULL DEFAULT NULL COMMENT '司机ID',
  `driver_name` varchar(50) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci NULL DEFAULT NULL COMMENT '司机姓名',
  `work_number` varchar(20) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci NULL DEFAULT NULL COMMENT '工号',
  `phone` varchar(20) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci NULL DEFAULT NULL COMMENT '手机号',
  `city_id` varchar(10) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci NULL DEFAULT NULL COMMENT '城市ID',
  `city_name` varchar(50) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci NULL DEFAULT NULL COMMENT '城市名称',
  `id_no` varchar(20) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci NULL DEFAULT NULL COMMENT '身份证号',
  `id_valid_date` varchar(20) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci NULL DEFAULT NULL COMMENT '身份证有效期',
  `lic_class` varchar(10) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci NULL DEFAULT NULL COMMENT '驾驶证类型',
  `lic_valid_date` varchar(20) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci NULL DEFAULT NULL COMMENT '驾驶证有效期',
  `driver_state_text` varchar(20) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci NULL DEFAULT NULL COMMENT '司机状态文本',
  `listen_status` varchar(20) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci NOT NULL DEFAULT 'listening' COMMENT '听单状态：listening-听单中，paused-暂停听单',
  `status` varchar(10) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci NULL DEFAULT '0' COMMENT '账号状态：0-正常，1-封禁，2-注销，3-待审核',
  `ic_front_url` varchar(255) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci NULL DEFAULT NULL COMMENT '身份证正面URL',
  `ic_back_url` varchar(255) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci NULL DEFAULT NULL COMMENT '身份证背面URL',
  `licence_front_url` varchar(255) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci NULL DEFAULT NULL COMMENT '驾驶证正面URL',
  `licence_back_url` varchar(255) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci NULL DEFAULT NULL COMMENT '驾驶证背面URL',
  `ic_front_url_gift` varchar(255) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci NULL DEFAULT NULL COMMENT '身份证正面URL(备用)',
  `ic_back_url_gift` varchar(255) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci NULL DEFAULT NULL COMMENT '身份证背面URL(备用)',
  `licence_front_url_gift` varchar(255) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci NULL DEFAULT NULL COMMENT '驾驶证正面URL(备用)',
  `licence_back_url_gift` varchar(255) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci NULL DEFAULT NULL COMMENT '驾驶证背面URL(备用)',
  `remark` varchar(500) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci NULL DEFAULT NULL COMMENT '备注',
  `dept_id` bigint NULL DEFAULT NULL COMMENT '部门ID（数据权限）',
  `create_time` datetime NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
  `create_by` varchar(64) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci NULL DEFAULT NULL COMMENT '创建人',
  `update_time` datetime NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
  `update_by` varchar(64) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci NULL DEFAULT NULL COMMENT '更新人',
  `tenant_id` varchar(32) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci NULL DEFAULT NULL COMMENT '租户ID',
  `del_flag` varchar(1) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci NULL DEFAULT '0' COMMENT '删除标记：0-未删除，1-已删除',
  PRIMARY KEY (`id`) USING BTREE,
  INDEX `idx_driver_id`(`driver_id` ASC) USING BTREE,
  INDEX `idx_work_number`(`work_number` ASC) USING BTREE,
  INDEX `idx_phone`(`phone` ASC) USING BTREE,
  INDEX `idx_city_id`(`city_id` ASC) USING BTREE,
  INDEX `idx_status`(`status` ASC) USING BTREE
) ENGINE = InnoDB AUTO_INCREMENT = 2016 CHARACTER SET = utf8mb4 COLLATE = utf8mb4_0900_ai_ci COMMENT = '司机信息表' ROW_FORMAT = DYNAMIC;

-- ----------------------------
-- Records of bus_driver
-- ----------------------------
INSERT INTO `bus_driver` VALUES (1, '700045867025624230', '三杰测试', '00230909', '13432496353', '3', '广州市', '440183198004123433', '2036-03-29', 'A1', '长期有效', '正常', 'listening', '0', '/api/admin/sys-file/oss/file?fileName=c1dbd982cc754cdc864429ec28aa6620.png', '/api/admin/sys-file/oss/file?fileName=b99f419f4e6d48558e64b508a406de75.png', '/api/admin/sys-file/oss/file?fileName=4fe5e06596724d0e9c43f89d245875d8.png', '', '', '', '', '', '测试司机1', NULL, '2026-05-28 17:17:42', 'admin', '2026-05-29 16:44:48', 'felix', '1', '0');
INSERT INTO `bus_driver` VALUES (2, '700045867025624231', '张伟', '6800D166', '13800138000', '3', '广州市', '440183198501011234', '2030-12-31', 'A2', '2030-12-31', '正常', 'listening', '0', '', '', '', '', '', '', '', '', '测试司机2', NULL, '2026-04-04 17:17:42', 'admin', '2026-04-04 17:17:42', 'admin', '1', '0');
INSERT INTO `bus_driver` VALUES (3, '700045867025624232', '李娜', '6800D167', '13900139000', '4', '深圳市', '440301199005055678', '2035-06-15', 'B1', '长期有效', '正常', 'listening', '0', '', '', '', '', '', '', '', '', '测试司机3', NULL, '2026-04-04 17:17:42', 'admin', '2026-04-04 17:17:42', 'admin', '1', '0');
INSERT INTO `bus_driver` VALUES (4, NULL, '范工', 'DRV260522', '13802402145', NULL, '广州市', '440101199001011235', '2030-12-31', 'A1', '长期有效', '正常', 'listening', '0', NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, '2026-04-30 16:43:44', 'admin', '2026-05-22 14:09:02', 'admin', '1', '0');
INSERT INTO `bus_driver` VALUES (5, 'DRV260513', '刘罗瑞', 'DRV260513', '13652944754', NULL, '广州市', '440101199001011234', '2030-12-31', 'A1', '长期有效', '注销', 'listening', '2', NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, '2026-05-13 14:43:11', 'admin', '2026-05-30 15:49:03', 'admin', '1', '0');
INSERT INTO `bus_driver` VALUES (6, NULL, '张三', 'DRV001', '13800138000', NULL, '广州市', '440101199001011234', '2030-12-31', 'A1', '长期有效', '正常', 'listening', '0', NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, '2026-05-15 15:35:50', 'admin', '2026-05-15 15:35:47', NULL, '1', '0');
INSERT INTO `bus_driver` VALUES (2001, 'DRI_GZ_201', '陈伟强', 'GZ02001', '13800020001', NULL, '广州市', '440101198503151234', NULL, 'A1', '长期有效', NULL, 'listening', '0', NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, '2026-05-27 10:57:45', NULL, '2026-05-27 10:57:45', NULL, '1', '0');
INSERT INTO `bus_driver` VALUES (2002, 'DRI_GZ_202', '李俊杰', 'GZ02002', '13800020002', NULL, '广州市', '440101198810201256', NULL, 'A1', '长期有效', NULL, 'listening', '0', NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, '2026-05-27 10:57:45', NULL, '2026-05-27 10:57:45', NULL, '1', '0');
INSERT INTO `bus_driver` VALUES (2003, 'DRI_GZ_203', '王美芳', 'GZ02003', '13800020003', NULL, '广州市', '440101199210051289', NULL, 'A3', '2030-12-31', NULL, 'listening', '0', NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, '2026-05-27 10:57:45', NULL, '2026-05-27 10:57:45', NULL, '1', '0');
INSERT INTO `bus_driver` VALUES (2004, 'DRI_GZ_204', '张建平', 'GZ02004', '13800020004', NULL, '广州市', '440101197512181278', NULL, 'A1', '长期有效', NULL, 'listening', '0', NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, '2026-05-27 10:57:45', NULL, '2026-05-27 10:57:45', NULL, '1', '0');
INSERT INTO `bus_driver` VALUES (2005, 'DRI_GZ_205', '刘淑华', 'GZ02005', '13800020005', NULL, '广州市', '440101198902051302', NULL, 'A3', '2035-06-30', NULL, 'listening', '0', NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, '2026-05-27 10:57:45', NULL, '2026-05-27 10:57:45', NULL, '1', '0');
INSERT INTO `bus_driver` VALUES (2006, 'DRI_GZ_206', '黄志强', 'GZ02006', '13800020006', NULL, '广州市', '440101198812151234', NULL, 'A1', '长期有效', NULL, 'listening', '0', NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, '2026-05-27 10:57:45', NULL, '2026-05-27 10:57:45', NULL, '1', '0');
INSERT INTO `bus_driver` VALUES (2007, 'DRI_GZ_207', '吴敏仪', 'GZ02007', '13800020007', NULL, '广州市', '440101199505201288', NULL, 'A3', '长期有效', NULL, 'listening', '0', NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, '2026-05-27 10:57:45', NULL, '2026-05-27 10:57:45', NULL, '1', '0');
INSERT INTO `bus_driver` VALUES (2008, 'DRI_GZ_208', '林振华', 'GZ02008', '13800020008', NULL, '广州市', '440101198003101256', NULL, 'A1', '2032-12-31', NULL, 'listening', '0', NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, '2026-05-27 10:57:45', NULL, '2026-05-27 10:57:45', NULL, '1', '0');
INSERT INTO `bus_driver` VALUES (2009, 'DRI_GZ_209', '郭志勇', 'GZ02009', '13042071722', NULL, '广州市', '440101197808081234', NULL, 'A2', '2028-06-30', '注销', 'listening', '2', NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, '2026-05-27 10:57:45', NULL, '2026-05-30 10:21:13', 'admin', '1', '0');
INSERT INTO `bus_driver` VALUES (2010, 'DRI_GZ_210', '梁淑芬', 'GZ02010', '13800020010', NULL, '广州市', '440101199109151289', NULL, 'A3', '长期有效', NULL, 'listening', '0', NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, '2026-05-27 10:57:45', NULL, '2026-05-27 10:57:45', NULL, '1', '0');
INSERT INTO `bus_driver` VALUES (2011, '00018888', '无法修改手机号', '00018888', '13533746722', '', '广东广州', '440106200007286614', '', 'A2', '', '正常', 'listening', '0', '/api/admin/sys-file/oss/file?fileName=7d54547c6b6143b2b2573fc69685fac1.png', '/api/admin/sys-file/oss/file?fileName=6d9bb24dfdbb49e594e0db7f15626c82.png', '/api/admin/sys-file/oss/file?fileName=2e34f392369d42ae9139427dfe9442fd.png', '', '', '', '', '', NULL, 2059155512602853378, '2026-05-29 16:04:31', 'felix', '2026-06-01 17:00:54', 'felix', '1', '0');
INSERT INTO `bus_driver` VALUES (2012, '00028888', '刘测试', '00028888', '19102053473', '', '广州市', '443110199307071475', '2026-05-30', 'A1', '2026-05-31', '正常', 'listening', '0', '/api/admin/sys-file/oss/file?fileName=bb6b14f0331a4fcead7b033d69615e27.png', '', '', '', '', '', '', '', NULL, 1, '2026-05-29 18:35:19', 'admin', '2026-05-30 15:35:06', 'admin', '1', '0');
INSERT INTO `bus_driver` VALUES (2013, 'DRV2013', '阿萨德', '', '15588889999', '', '广州', '440111155805080212', '', 'A2', '', '正常', 'listening', '0', '', '', '', '', '', '', '', '', NULL, 2060278231323074561, '2026-05-30 16:44:24', 'alex03', '2026-05-30 16:44:29', 'alex03', '1', '0');
INSERT INTO `bus_driver` VALUES (2014, '00018886', '鸿聪测试', '00018886', '13533746715', '', '广东广州', '44010619960728721X', '', 'A2', '', '正常', 'listening', '0', '/api/admin/sys-file/oss/file?fileName=9e16bd0da8144d6987446ab65ce92e10.png', '/api/admin/sys-file/oss/file?fileName=df908f6214e940e088acbe6e6a241cc3.png', '/api/admin/sys-file/oss/file?fileName=2e5ed21537ed4a95aaee203161ebb164.png', '', '', '', '', '', NULL, 2059155512602853378, '2026-06-01 10:14:15', 'felix', '2026-06-01 10:14:22', 'felix', '1', '0');
INSERT INTO `bus_driver` VALUES (2015, '88885566', '杨测试', '88885566', '13417037248', '', '广州市', '110511000011020611', '2026-06-01', 'A1', '2031-06-07', '正常', 'listening', '0', '', '', '', '', '', '', '', '', NULL, 2061273780239122433, '2026-06-01 18:05:27', 'admin', '2026-06-01 18:08:36', 'admin', '1', '0');

-- ----------------------------
-- Table structure for bus_driver_break_record
-- ----------------------------
DROP TABLE IF EXISTS `bus_driver_break_record`;
CREATE TABLE `bus_driver_break_record`  (
  `id` bigint NOT NULL AUTO_INCREMENT COMMENT '主键',
  `break_no` varchar(64) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci NOT NULL COMMENT '业务小休编号，如 BRK_yyyyMMddHHmmss_xxx',
  `driver_pk_id` bigint NOT NULL COMMENT '司机主键 bus_driver.id',
  `driver_code` varchar(64) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci NULL DEFAULT NULL COMMENT '司机业务编号 bus_driver.driver_id',
  `schedule_id` bigint NULL DEFAULT NULL COMMENT '关联排班 bus_schedule.id',
  `break_date` date NOT NULL COMMENT '小休自然日',
  `start_time` datetime NOT NULL COMMENT '开始时间',
  `expire_time` datetime NOT NULL COMMENT '计划结束时间',
  `end_time` datetime NULL DEFAULT NULL COMMENT '实际结束时间（提前结束）',
  `duration_minutes` int NOT NULL COMMENT '计划时长(分钟)',
  `lng` decimal(10, 7) NULL DEFAULT NULL COMMENT '申请经度',
  `lat` decimal(10, 7) NULL DEFAULT NULL COMMENT '申请纬度',
  `status` varchar(16) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci NOT NULL DEFAULT 'active' COMMENT '状态：active-进行中, ended-已结束, expired-已过期',
  `create_time` datetime NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
  `create_by` varchar(64) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci NULL DEFAULT NULL COMMENT '创建人',
  `update_time` datetime NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
  `update_by` varchar(64) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci NULL DEFAULT NULL COMMENT '更新人',
  `tenant_id` varchar(32) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci NULL DEFAULT NULL COMMENT '租户ID',
  `del_flag` varchar(1) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci NULL DEFAULT '0' COMMENT '删除标记：0-未删除，1-已删除',
  PRIMARY KEY (`id`) USING BTREE,
  UNIQUE INDEX `uk_bdbr_break_no`(`break_no` ASC) USING BTREE,
  INDEX `idx_bdbr_driver_date`(`driver_pk_id` ASC, `break_date` ASC, `del_flag` ASC) USING BTREE,
  INDEX `idx_bdbr_driver_status`(`driver_pk_id` ASC, `status` ASC, `del_flag` ASC) USING BTREE,
  INDEX `idx_bdbr_expire`(`expire_time` ASC, `status` ASC) USING BTREE
) ENGINE = InnoDB AUTO_INCREMENT = 8 CHARACTER SET = utf8mb4 COLLATE = utf8mb4_0900_ai_ci COMMENT = '司机小休执行记录' ROW_FORMAT = DYNAMIC;

-- ----------------------------
-- Records of bus_driver_break_record
-- ----------------------------
INSERT INTO `bus_driver_break_record` VALUES (1, 'BRK_20260527093711_FCB45B1E', 5, '5', 45, '2026-05-27', '2026-05-27 09:37:13', '2026-05-27 09:52:13', '2026-05-27 09:37:19', 15, 113.3300070, 23.1317800, 'ended', '2026-05-27 09:37:13', '13652944754', '2026-05-27 09:37:19', '13652944754', '1', '0');
INSERT INTO `bus_driver_break_record` VALUES (2, 'BRK_20260527093721_0F7567E2', 5, '5', 45, '2026-05-27', '2026-05-27 09:37:23', '2026-05-27 09:52:23', '2026-05-27 09:37:24', 15, 113.3300070, 23.1317800, 'ended', '2026-05-27 09:37:23', '13652944754', '2026-05-27 09:37:24', '13652944754', '1', '0');
INSERT INTO `bus_driver_break_record` VALUES (3, 'BRK_20260527093806_10358044', 5, '5', 45, '2026-05-27', '2026-05-27 09:38:08', '2026-05-27 09:53:08', '2026-05-27 09:38:10', 15, 113.3300070, 23.1317800, 'ended', '2026-05-27 09:38:08', '13652944754', '2026-05-27 09:38:10', '13652944754', '1', '0');
INSERT INTO `bus_driver_break_record` VALUES (4, 'BRK_20260529164842_E1C5380B', 1, '700045867025624230', 40, '2026-05-29', '2026-05-29 16:48:44', '2026-05-29 17:03:44', '2026-05-29 17:03:44', 15, 113.3300490, 23.1318300, 'expired', '2026-05-29 16:48:44', '13432496353', '2026-05-29 18:42:25', 'admin', '1', '0');
INSERT INTO `bus_driver_break_record` VALUES (5, 'BRK_20260531095809_7D6B155D', 2012, '00028888', 116, '2026-05-31', '2026-05-31 09:58:12', '2026-05-31 10:13:12', '2026-05-31 09:58:14', 15, 113.3300340, 23.1317990, 'ended', '2026-05-31 09:58:12', '19102053473', '2026-05-31 09:58:14', '19102053473', '1', '0');
INSERT INTO `bus_driver_break_record` VALUES (6, 'BRK_20260531095813_F09D4225', 2012, '00028888', 116, '2026-05-31', '2026-05-31 09:58:16', '2026-05-31 10:13:16', '2026-05-31 09:58:17', 15, 113.3300340, 23.1317990, 'ended', '2026-05-31 09:58:16', '19102053473', '2026-05-31 09:58:17', '19102053473', '1', '0');
INSERT INTO `bus_driver_break_record` VALUES (7, 'BRK_20260531095816_163FC3EC', 2012, '00028888', 116, '2026-05-31', '2026-05-31 09:58:19', '2026-05-31 10:13:19', '2026-05-31 09:58:20', 15, 113.3300340, 23.1317990, 'ended', '2026-05-31 09:58:19', '19102053473', '2026-05-31 09:58:20', '19102053473', '1', '0');

-- ----------------------------
-- Table structure for bus_driver_daily_stats
-- ----------------------------
DROP TABLE IF EXISTS `bus_driver_daily_stats`;
CREATE TABLE `bus_driver_daily_stats`  (
  `id` bigint NOT NULL AUTO_INCREMENT COMMENT '主键',
  `stat_date` date NOT NULL COMMENT '统计日期',
  `driver_pk_id` bigint NOT NULL COMMENT '司机主键 bus_driver.id',
  `driver_name` varchar(64) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci NULL DEFAULT NULL COMMENT '司机姓名',
  `driver_code` varchar(32) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci NULL DEFAULT NULL COMMENT '司机工号',
  `phone` varchar(20) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci NULL DEFAULT NULL COMMENT '手机号',
  `vehicle_id` bigint NULL DEFAULT NULL COMMENT '当日绑定车辆ID',
  `plate_number` varchar(32) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci NULL DEFAULT NULL COMMENT '车牌号',
  `scheduled` tinyint NOT NULL DEFAULT 0 COMMENT '是否应出车：当日有有效排班(非休息/请假)',
  `departed` tinyint NOT NULL DEFAULT 0 COMMENT '是否实际出车：签到/有完成订单/GPS上报',
  `online_passenger_count` int NOT NULL DEFAULT 0 COMMENT '线上客运量(人)',
  `offline_passenger_count` int NOT NULL DEFAULT 0 COMMENT '线下客运量(人)',
  `order_income` decimal(12, 2) NOT NULL DEFAULT 0.00 COMMENT '订单收入(元)',
  `online_order_count` int NOT NULL DEFAULT 0 COMMENT '线上完成订单数',
  `offline_order_count` int NOT NULL DEFAULT 0 COMMENT '线下完成订单数',
  `last_sync_time` datetime NOT NULL COMMENT '最近同步时间',
  `create_time` datetime NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
  `update_time` datetime NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
  `tenant_id` varchar(32) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci NULL DEFAULT NULL COMMENT '租户ID',
  PRIMARY KEY (`id`) USING BTREE,
  UNIQUE INDEX `uk_bdds_date_driver`(`stat_date` ASC, `driver_pk_id` ASC, `tenant_id` ASC) USING BTREE,
  INDEX `idx_bdds_date`(`stat_date` ASC) USING BTREE,
  INDEX `idx_bdds_driver`(`driver_pk_id` ASC) USING BTREE,
  INDEX `idx_bdds_tenant`(`tenant_id` ASC) USING BTREE
) ENGINE = InnoDB AUTO_INCREMENT = 11 CHARACTER SET = utf8mb4 COLLATE = utf8mb4_0900_ai_ci COMMENT = '司机每日运营统计' ROW_FORMAT = DYNAMIC;

-- ----------------------------
-- Records of bus_driver_daily_stats
-- ----------------------------
INSERT INTO `bus_driver_daily_stats` VALUES (1, '2026-05-27', 2001, '陈伟强', 'GZ02001', '13800020001', NULL, NULL, 1, 1, 15, 2, 225.00, 10, 2, '2026-05-27 11:00:48', '2026-05-27 11:00:48', '2026-05-27 11:00:48', '1');
INSERT INTO `bus_driver_daily_stats` VALUES (2, '2026-05-27', 2002, '李俊杰', 'GZ02002', '13800020002', NULL, NULL, 1, 1, 12, 1, 180.00, 8, 1, '2026-05-27 11:00:48', '2026-05-27 11:00:48', '2026-05-27 11:00:48', '1');
INSERT INTO `bus_driver_daily_stats` VALUES (3, '2026-05-27', 2003, '王美芳', 'GZ02003', '13800020003', NULL, NULL, 1, 1, 8, 2, 120.00, 5, 2, '2026-05-27 11:00:48', '2026-05-27 11:00:48', '2026-05-27 11:00:48', '1');
INSERT INTO `bus_driver_daily_stats` VALUES (4, '2026-05-27', 2004, '张建平', 'GZ02004', '13800020004', NULL, NULL, 1, 1, 6, 0, 90.00, 4, 0, '2026-05-27 11:00:48', '2026-05-27 11:00:48', '2026-05-27 11:00:48', '1');
INSERT INTO `bus_driver_daily_stats` VALUES (5, '2026-05-27', 2005, '刘淑华', 'GZ02005', '13800020005', NULL, NULL, 1, 0, 0, 0, 0.00, 0, 0, '2026-05-27 11:00:48', '2026-05-27 11:00:48', '2026-05-27 11:00:48', '1');
INSERT INTO `bus_driver_daily_stats` VALUES (6, '2026-05-26', 2001, '陈伟强', 'GZ02001', '13800020001', NULL, NULL, 1, 1, 18, 3, 270.00, 12, 3, '2026-05-27 11:00:48', '2026-05-27 11:00:48', '2026-05-27 11:00:48', '1');
INSERT INTO `bus_driver_daily_stats` VALUES (7, '2026-05-26', 2002, '李俊杰', 'GZ02002', '13800020002', NULL, NULL, 1, 1, 14, 2, 210.00, 9, 2, '2026-05-27 11:00:48', '2026-05-27 11:00:48', '2026-05-27 11:00:48', '1');
INSERT INTO `bus_driver_daily_stats` VALUES (8, '2026-05-26', 2003, '王美芳', 'GZ02003', '13800020003', NULL, NULL, 1, 1, 10, 1, 150.00, 7, 1, '2026-05-27 11:00:48', '2026-05-27 11:00:48', '2026-05-27 11:00:48', '1');
INSERT INTO `bus_driver_daily_stats` VALUES (9, '2026-05-25', 2001, '陈伟强', 'GZ02001', '13800020001', NULL, NULL, 1, 1, 20, 4, 300.00, 14, 4, '2026-05-27 11:00:48', '2026-05-27 11:00:48', '2026-05-27 11:00:48', '1');
INSERT INTO `bus_driver_daily_stats` VALUES (10, '2026-05-25', 2002, '李俊杰', 'GZ02002', '13800020002', NULL, NULL, 1, 1, 16, 2, 240.00, 11, 2, '2026-05-27 11:00:48', '2026-05-27 11:00:48', '2026-05-27 11:00:48', '1');

-- ----------------------------
-- Table structure for bus_driver_resident_parking
-- ----------------------------
DROP TABLE IF EXISTS `bus_driver_resident_parking`;
CREATE TABLE `bus_driver_resident_parking`  (
  `id` bigint NOT NULL AUTO_INCREMENT COMMENT '主键',
  `driver_pk_id` bigint NOT NULL COMMENT '司机主键 bus_driver.id',
  `station_id` bigint NOT NULL COMMENT '停车场站点 bus_station.id',
  `sort_no` int NOT NULL DEFAULT 0 COMMENT '展示顺序，小在前',
  `create_time` datetime NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
  `tenant_id` varchar(32) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci NULL DEFAULT NULL COMMENT '租户ID',
  PRIMARY KEY (`id`) USING BTREE,
  UNIQUE INDEX `uk_bdrp_driver_station`(`driver_pk_id` ASC, `station_id` ASC) USING BTREE,
  INDEX `idx_bdrp_driver`(`driver_pk_id` ASC) USING BTREE,
  INDEX `idx_bdrp_tenant`(`tenant_id` ASC) USING BTREE
) ENGINE = InnoDB AUTO_INCREMENT = 9 CHARACTER SET = utf8mb4 COLLATE = utf8mb4_0900_ai_ci COMMENT = '司机常驻停车场' ROW_FORMAT = DYNAMIC;

-- ----------------------------
-- Records of bus_driver_resident_parking
-- ----------------------------
INSERT INTO `bus_driver_resident_parking` VALUES (8, 5, 2012, 0, '2026-05-29 18:22:19', '1');

-- ----------------------------
-- Table structure for bus_exception_alert
-- ----------------------------
DROP TABLE IF EXISTS `bus_exception_alert`;
CREATE TABLE `bus_exception_alert`  (
  `id` bigint NOT NULL AUTO_INCREMENT COMMENT '主键',
  `alert_type` varchar(32) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci NOT NULL COMMENT '异常类型：speed/route/timeout/deviation',
  `alert_level` varchar(16) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci NOT NULL DEFAULT 'medium' COMMENT '级别：high/medium/low',
  `alert_content` varchar(512) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci NOT NULL COMMENT '异常内容摘要',
  `vehicle_id` bigint NULL DEFAULT NULL COMMENT '车辆ID',
  `vehicle_no` varchar(32) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci NULL DEFAULT NULL COMMENT '车牌号',
  `driver_pk_id` bigint NULL DEFAULT NULL COMMENT '司机主键 bus_driver.id',
  `driver_name` varchar(64) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci NULL DEFAULT NULL COMMENT '司机姓名',
  `order_id` varchar(64) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci NULL DEFAULT NULL COMMENT '关联订单ID',
  `handle_status` char(1) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci NOT NULL DEFAULT '0' COMMENT '处理状态：0-未处理 1-已处理 2-已忽略',
  `detail_data` json NULL COMMENT '详细数据 JSON',
  `push_status` char(1) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci NOT NULL DEFAULT '0' COMMENT '是否已推送司机：0-否 1-是',
  `push_time` datetime NULL DEFAULT NULL COMMENT '推送时间',
  `handle_time` datetime NULL DEFAULT NULL COMMENT '处理时间',
  `handle_by` varchar(64) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci NULL DEFAULT NULL COMMENT '处理人',
  `create_time` datetime NULL DEFAULT CURRENT_TIMESTAMP COMMENT '发现时间',
  `update_time` datetime NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
  `tenant_id` varchar(32) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci NULL DEFAULT NULL COMMENT '租户ID',
  `del_flag` char(1) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci NOT NULL DEFAULT '0' COMMENT '删除标记：0-未删除 1-已删除',
  PRIMARY KEY (`id`) USING BTREE,
  INDEX `idx_bea_status_time`(`handle_status` ASC, `create_time` ASC, `del_flag` ASC) USING BTREE,
  INDEX `idx_bea_type_time`(`alert_type` ASC, `create_time` ASC, `del_flag` ASC) USING BTREE,
  INDEX `idx_bea_driver`(`driver_pk_id` ASC, `del_flag` ASC) USING BTREE
) ENGINE = InnoDB AUTO_INCREMENT = 1 CHARACTER SET = utf8mb4 COLLATE = utf8mb4_0900_ai_ci COMMENT = '异常监控告警' ROW_FORMAT = DYNAMIC;

-- ----------------------------
-- Records of bus_exception_alert
-- ----------------------------

-- ----------------------------
-- Table structure for bus_fare_version
-- ----------------------------
DROP TABLE IF EXISTS `bus_fare_version`;
CREATE TABLE `bus_fare_version`  (
  `id` bigint NOT NULL AUTO_INCREMENT COMMENT '主键',
  `version_code` varchar(32) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci NOT NULL COMMENT '版本号(V1.0/V2.0)',
  `version_name` varchar(64) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci NOT NULL COMMENT '版本名称',
  `operation_type` varchar(20) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci NOT NULL COMMENT '运营类型:dynamic/normal/commuter/custom',
  `effective_start` datetime NULL DEFAULT NULL COMMENT '生效开始时间',
  `effective_end` datetime NULL DEFAULT NULL COMMENT '生效结束时间',
  `time_rule_json` longtext CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci NULL COMMENT '版本级时间规则JSON',
  `status` varchar(20) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci NULL DEFAULT 'draft' COMMENT '状态:draft/pending/approved/rejected/effective/expired',
  `remark` varchar(500) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci NULL DEFAULT NULL COMMENT '版本描述',
  `submit_remark` varchar(500) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci NULL DEFAULT NULL COMMENT '提交审核说明',
  `audit_remark` varchar(500) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci NULL DEFAULT NULL COMMENT '审核/驳回意见',
  `audit_by` varchar(64) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci NULL DEFAULT NULL COMMENT '审核人',
  `audit_time` datetime NULL DEFAULT NULL COMMENT '审核时间',
  `create_time` datetime NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
  `create_by` varchar(64) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci NULL DEFAULT NULL COMMENT '创建人',
  `update_time` datetime NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
  `update_by` varchar(64) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci NULL DEFAULT NULL COMMENT '更新人',
  `tenant_id` varchar(32) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci NULL DEFAULT NULL COMMENT '租户ID',
  `del_flag` varchar(1) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci NULL DEFAULT '0' COMMENT '删除标记',
  PRIMARY KEY (`id`) USING BTREE,
  UNIQUE INDEX `uk_bfv_tenant_name`(`tenant_id` ASC, `version_name` ASC, `del_flag` ASC) USING BTREE,
  INDEX `idx_bfv_operation_type`(`operation_type` ASC) USING BTREE,
  INDEX `idx_bfv_status`(`status` ASC) USING BTREE,
  INDEX `idx_bfv_create_time`(`create_time` ASC) USING BTREE
) ENGINE = InnoDB AUTO_INCREMENT = 1 CHARACTER SET = utf8mb4 COLLATE = utf8mb4_0900_ai_ci COMMENT = '票价版本表' ROW_FORMAT = DYNAMIC;

-- ----------------------------
-- Records of bus_fare_version
-- ----------------------------

-- ----------------------------
-- Table structure for bus_fare_version_history
-- ----------------------------
DROP TABLE IF EXISTS `bus_fare_version_history`;
CREATE TABLE `bus_fare_version_history`  (
  `id` bigint NOT NULL AUTO_INCREMENT COMMENT '主键',
  `version_id` bigint NOT NULL COMMENT '票价版本ID',
  `version_code` varchar(32) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci NOT NULL COMMENT '版本号',
  `snapshot_json` longtext CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci NULL COMMENT '快照JSON',
  `operate_type` varchar(32) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci NULL DEFAULT NULL COMMENT '操作类型:create/update/submit/audit/copy/enable/disable',
  `operate_by` varchar(64) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci NULL DEFAULT NULL COMMENT '操作人',
  `operate_time` datetime NULL DEFAULT CURRENT_TIMESTAMP COMMENT '操作时间',
  `tenant_id` varchar(32) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci NULL DEFAULT NULL COMMENT '租户ID',
  PRIMARY KEY (`id`) USING BTREE,
  INDEX `idx_bfv_h_version`(`version_id` ASC) USING BTREE,
  INDEX `idx_bfv_h_time`(`operate_time` ASC) USING BTREE
) ENGINE = InnoDB AUTO_INCREMENT = 1 CHARACTER SET = utf8mb4 COLLATE = utf8mb4_0900_ai_ci COMMENT = '票价版本历史表' ROW_FORMAT = DYNAMIC;

-- ----------------------------
-- Records of bus_fare_version_history
-- ----------------------------

-- ----------------------------
-- Table structure for bus_finance_share_rule
-- ----------------------------
DROP TABLE IF EXISTS `bus_finance_share_rule`;
CREATE TABLE `bus_finance_share_rule`  (
  `id` bigint NOT NULL AUTO_INCREMENT COMMENT '主键',
  `enterprise_id` bigint NULL DEFAULT NULL COMMENT '公交企业ID（sys_tenant.id），NULL=默认规则',
  `enterprise_name` varchar(128) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci NULL DEFAULT NULL COMMENT '企业名称（冗余，便于列表展示）',
  `enterprise_rate` decimal(7, 4) NOT NULL DEFAULT 0.8000 COMMENT '公交企业分账比例（0~1）',
  `platform_rate` decimal(7, 4) NOT NULL DEFAULT 0.2000 COMMENT '平台分账比例（0~1）',
  `effective_date` date NULL DEFAULT NULL COMMENT '生效日期，NULL=立即生效',
  `status` varchar(1) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci NOT NULL DEFAULT '1' COMMENT '启用状态：1启用 0禁用',
  `remark` varchar(255) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci NULL DEFAULT NULL COMMENT '备注',
  `create_time` datetime NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
  `create_by` varchar(64) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci NULL DEFAULT NULL COMMENT '创建人',
  `update_time` datetime NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
  `update_by` varchar(64) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci NULL DEFAULT NULL COMMENT '更新人',
  `tenant_id` varchar(32) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci NULL DEFAULT NULL COMMENT '所属租户',
  `del_flag` varchar(1) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci NULL DEFAULT '0' COMMENT '删除标记',
  PRIMARY KEY (`id`) USING BTREE,
  UNIQUE INDEX `uk_bfsr_enterprise`(`enterprise_id` ASC, `tenant_id` ASC, `del_flag` ASC) USING BTREE,
  INDEX `idx_bfsr_tenant`(`tenant_id` ASC) USING BTREE,
  INDEX `idx_bfsr_status`(`status` ASC) USING BTREE
) ENGINE = InnoDB AUTO_INCREMENT = 11 CHARACTER SET = utf8mb4 COLLATE = utf8mb4_0900_ai_ci COMMENT = '财务分账规则表' ROW_FORMAT = DYNAMIC;

-- ----------------------------
-- Records of bus_finance_share_rule
-- ----------------------------

-- ----------------------------
-- Table structure for bus_line_fare_rule
-- ----------------------------
DROP TABLE IF EXISTS `bus_line_fare_rule`;
CREATE TABLE `bus_line_fare_rule`  (
  `id` bigint NOT NULL AUTO_INCREMENT COMMENT '主键',
  `version_id` bigint NOT NULL COMMENT '所属票价版本ID',
  `route_id` varchar(64) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci NULL DEFAULT NULL COMMENT '线路ID(空=默认规则)',
  `route_name` varchar(128) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci NULL DEFAULT NULL COMMENT '线路名称(冗余)',
  `pricing_type` varchar(20) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci NOT NULL COMMENT '计价方式:fixed/dynamic',
  `pricing_params_json` longtext CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci NULL COMMENT '计价参数JSON',
  `time_rule_json` longtext CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci NULL COMMENT '线路级时间规则JSON',
  `user_types_json` varchar(500) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci NULL DEFAULT NULL COMMENT '适用用户类型JSON',
  `priority` int NULL DEFAULT 1 COMMENT '优先级',
  `config_status` varchar(20) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci NULL DEFAULT 'configured' COMMENT '配置状态:configured/unconfigured',
  `create_time` datetime NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
  `create_by` varchar(64) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci NULL DEFAULT NULL COMMENT '创建人',
  `update_time` datetime NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
  `update_by` varchar(64) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci NULL DEFAULT NULL COMMENT '更新人',
  `tenant_id` varchar(32) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci NULL DEFAULT NULL COMMENT '租户ID',
  `del_flag` varchar(1) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci NULL DEFAULT '0' COMMENT '删除标记',
  PRIMARY KEY (`id`) USING BTREE,
  INDEX `idx_blfr_version`(`version_id` ASC) USING BTREE,
  INDEX `idx_blfr_route`(`route_id` ASC) USING BTREE,
  INDEX `idx_blfr_tenant`(`tenant_id` ASC) USING BTREE
) ENGINE = InnoDB AUTO_INCREMENT = 1 CHARACTER SET = utf8mb4 COLLATE = utf8mb4_0900_ai_ci COMMENT = '线路票价规则表' ROW_FORMAT = DYNAMIC;

-- ----------------------------
-- Records of bus_line_fare_rule
-- ----------------------------

-- ----------------------------
-- Table structure for bus_order
-- ----------------------------
DROP TABLE IF EXISTS `bus_order`;
CREATE TABLE `bus_order`  (
  `id` varchar(64) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci NOT NULL COMMENT '订单ID',
  `order_no` varchar(64) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci NOT NULL COMMENT '订单编号',
  `qr_code` text CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci NULL COMMENT '乘车/核销二维码载荷',
  `order_type` varchar(20) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci NULL DEFAULT 'ONLINE' COMMENT '订单类型',
  `order_status` varchar(64) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci NULL DEFAULT NULL COMMENT '订单状态',
  `pay_status` varchar(20) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci NULL DEFAULT 'UNPAID' COMMENT '支付状态:PAID/UNPAID/REFUNDED',
  `passenger_phone` varchar(32) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci NULL DEFAULT NULL COMMENT '乘客手机号',
  `passenger_id` varchar(64) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci NULL DEFAULT NULL COMMENT '乘客ID',
  `driver_name` varchar(64) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci NULL DEFAULT NULL COMMENT '司机姓名',
  `driver_id` varchar(64) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci NULL DEFAULT NULL COMMENT '司机ID',
  `driver_phone` varchar(32) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci NULL DEFAULT NULL COMMENT '司机手机号',
  `driver_job_no` varchar(64) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci NULL DEFAULT NULL COMMENT '司机工号',
  `vehicle_no` varchar(32) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci NULL DEFAULT NULL COMMENT '车牌号',
  `order_time` datetime NULL DEFAULT NULL COMMENT '下单时间',
  `pay_amount` decimal(10, 2) NULL DEFAULT 0.00 COMMENT '支付金额',
  `estimated_amount` decimal(10, 2) NULL DEFAULT 0.00 COMMENT '预估金额',
  `red_packet_amount` decimal(10, 2) NULL DEFAULT 0.00 COMMENT '红包金额',
  `bus_subsidy_amount` decimal(10, 2) NOT NULL DEFAULT 0.00 COMMENT '公交承担补贴金额（元）',
  `merchant_subsidy_amount` decimal(10, 2) NOT NULL DEFAULT 0.00 COMMENT '商家承担补贴金额（元）',
  `bus_transit_subsidy` decimal(10, 2) NOT NULL DEFAULT 0.00 COMMENT '公交通行补贴金额（元）',
  `receivable_amount` decimal(10, 2) NOT NULL DEFAULT 0.00 COMMENT '收消金额（元）',
  `change_amount` decimal(10, 2) NOT NULL DEFAULT 0.00 COMMENT '改签金额（元）',
  `pay_method` varchar(32) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci NULL DEFAULT NULL COMMENT '支付方式',
  `pay_time` datetime NULL DEFAULT NULL COMMENT '支付时间',
  `refund_amount` decimal(10, 2) NULL DEFAULT 0.00 COMMENT '退款金额',
  `refund_status` varchar(20) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci NULL DEFAULT NULL COMMENT '退款状态',
  `cancel_time` datetime NULL DEFAULT NULL COMMENT '取消时间',
  `order_channel` varchar(32) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci NULL DEFAULT NULL COMMENT '下单渠道',
  `passenger_count` int NULL DEFAULT 1 COMMENT '乘客人数',
  `city` varchar(64) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci NULL DEFAULT NULL COMMENT '城市',
  `start_station` varchar(128) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci NULL DEFAULT NULL COMMENT '出发站点',
  `end_station` varchar(128) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci NULL DEFAULT NULL COMMENT '目的站点',
  `response_time` datetime NULL DEFAULT NULL COMMENT '应答时间',
  `boarding_time` datetime NULL DEFAULT NULL COMMENT '上车时间',
  `arrival_time` datetime NULL DEFAULT NULL COMMENT '到站时间',
  `pickup_duration` int NULL DEFAULT 0 COMMENT '接驾时长',
  `delivery_duration` int NULL DEFAULT 0 COMMENT '送驾时长',
  `estimated_mileage` decimal(10, 2) NULL DEFAULT 0.00 COMMENT '预估里程',
  `actual_mileage` decimal(10, 2) NULL DEFAULT 0.00 COMMENT '实际里程',
  `invoice_status` varchar(20) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci NULL DEFAULT NULL COMMENT '开票状态',
  `shift_no` varchar(64) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci NULL DEFAULT NULL COMMENT '班次号',
  `shift_date` varchar(20) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci NULL DEFAULT NULL COMMENT '班次日期',
  `first_station_departure_time` varchar(20) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci NULL DEFAULT NULL COMMENT '首站发车时间',
  `route_id` varchar(64) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci NULL DEFAULT NULL COMMENT '路线ID',
  `route_name` varchar(128) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci NULL DEFAULT NULL COMMENT '路线名称',
  `seat_inventory` int NULL DEFAULT 0 COMMENT '座位库存',
  `close_processed` varchar(1) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci NULL DEFAULT '0' COMMENT '关单已处理:0否1是',
  `refund_processed` varchar(1) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci NULL DEFAULT '0' COMMENT '退款已处理:0否1是',
  `close_type` varchar(20) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci NULL DEFAULT NULL COMMENT '关单类型',
  `close_reason` varchar(255) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci NULL DEFAULT NULL COMMENT '关单原因',
  `refund_reason` varchar(255) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci NULL DEFAULT NULL COMMENT '退款原因',
  `create_time` datetime NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
  `create_by` varchar(64) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci NULL DEFAULT NULL COMMENT '创建人',
  `update_time` datetime NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
  `update_by` varchar(64) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci NULL DEFAULT NULL COMMENT '更新人',
  `tenant_id` varchar(32) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci NULL DEFAULT NULL COMMENT '租户ID',
  `del_flag` varchar(1) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci NULL DEFAULT '0' COMMENT '删除标记',
  PRIMARY KEY (`id`) USING BTREE,
  UNIQUE INDEX `uk_bo_order_no`(`order_no` ASC) USING BTREE,
  INDEX `idx_bo_time`(`order_time` ASC) USING BTREE,
  INDEX `idx_bo_type`(`order_type` ASC) USING BTREE,
  INDEX `idx_bo_status`(`order_status` ASC) USING BTREE,
  INDEX `idx_bo_pay_status`(`pay_status` ASC) USING BTREE,
  INDEX `idx_bo_shift_no`(`shift_no` ASC) USING BTREE,
  INDEX `idx_bo_route`(`route_id` ASC) USING BTREE,
  INDEX `idx_bo_tenant`(`tenant_id` ASC) USING BTREE
) ENGINE = InnoDB CHARACTER SET = utf8mb4 COLLATE = utf8mb4_0900_ai_ci COMMENT = '订单表' ROW_FORMAT = DYNAMIC;

-- ----------------------------
-- Records of bus_order
-- ----------------------------
INSERT INTO `bus_order` VALUES ('0082a39631c4484689c987516ae38887', 'ORD_20260528154614_816576', NULL, 'dynamic_bus', 'cancelled', 'refunding', NULL, '2059902964167528449', NULL, NULL, NULL, NULL, NULL, '2026-05-28 15:46:14', 6.00, 6.00, 0.00, 0.00, 0.00, 0.00, 0.00, 0.00, 'auto_deduct', NULL, 6.00, 'REFUNDING', '2026-05-28 17:56:42', NULL, 1, NULL, '13', '20', NULL, NULL, NULL, 0, 0, 0.00, 0.00, NULL, NULL, NULL, NULL, NULL, NULL, 0, '0', '0', 'passenger_cancel', '不想去了，行程取消', NULL, '2026-05-28 15:46:14', '13560004373', '2026-05-28 17:56:42', '13560004373', '1', '0');
INSERT INTO `bus_order` VALUES ('00941a0909924b40809e0b0ffde35323', 'ORD_20260530143555_709056', NULL, 'dynamic_bus', 'cancelled', 'refunding', NULL, '2059902964167528449', NULL, NULL, NULL, NULL, NULL, '2026-05-30 14:35:55', 7.01, 7.01, 0.00, 0.00, 0.00, 0.00, 0.00, 0.00, 'auto_deduct', NULL, 7.01, 'REFUNDING', '2026-06-01 11:48:31', NULL, 1, NULL, '2007', '2008', NULL, NULL, NULL, 0, 0, 0.00, 0.00, NULL, NULL, NULL, NULL, NULL, NULL, 0, '0', '0', 'passenger_cancel', '不想去了，行程取消', NULL, '2026-05-30 14:35:55', '13560004373', '2026-06-01 11:48:31', '13560004373', '1', '0');
INSERT INTO `bus_order` VALUES ('08bd1d827b794ca19c5139e7e80e1e9a', 'ORD_20260601183009_683584', NULL, 'dynamic_bus', 'cancelled', 'refunding', NULL, '2061296189767847937', NULL, NULL, NULL, NULL, NULL, '2026-06-01 18:30:09', 6.00, 6.00, 0.00, 0.00, 0.00, 0.00, 0.00, 0.00, 'auto_deduct', NULL, 6.00, 'REFUNDING', '2026-06-01 18:35:51', NULL, 1, NULL, '2027', '2028', NULL, NULL, NULL, 0, 0, 0.00, 0.00, NULL, NULL, NULL, NULL, NULL, NULL, 0, '0', '0', 'passenger_cancel', '不想去了，行程取消', NULL, '2026-06-01 18:30:09', '13560004373', '2026-06-01 18:35:51', '13560004373', '1', '0');
INSERT INTO `bus_order` VALUES ('139f11dec5df439398070737451dcd23', 'ORD_20260528175725_268928', '630169240101000001120220100106271000000404003303A3055E7A6F1B61A990CD800F75D469BFF780E661816094E90CADF1F266090EB203A83716543D1CC9B62D9D573ACEE43314DF3CDC2472FB872F458D2BEEA691C371D948E9ECAA34CC42D6863C85515328326488D3DD291C8FBD00B6674DEA7B19139f11dec5df439398070737451dcd230205990296416752844902201001022010010106000002b07aa46c793681d22b30cab415fd96a25f479b1bd31045fb7dc7a5503590ed426A1812A700142000000000000000000000000000000000000000000000000000000000000000001573670619D7DBF49DB1BB9E2D13CDDA2DA8ED4FE3D3A20F9807070148BFF4547C979E0D35FD32F6DA9F131A58FD0D250727CE3930AE6BA168F3A6E955937C9E6F6A1812A715A4FDB320F998E4C8386D0B8768E412A7444D910238E89D3EE49B75D23D6423F2AAE48B1DDA57B64EFBB62CD69CE1ADFD8185758E90D3AAD7C0E2270DE81F3A54', 'dynamic_bus', 'cancelled', 'refunding', NULL, '2059902964167528449', '刘罗瑞', '5', '13652944754', NULL, '京D98765', '2026-05-28 17:57:25', 7.51, 7.51, 0.00, 0.00, 0.00, 0.00, 0.00, 0.00, 'auto_deduct', NULL, 6.01, 'REFUNDING', '2026-05-28 18:02:27', NULL, 1, NULL, '2013', '2014', NULL, NULL, NULL, 0, 0, 0.00, 0.00, NULL, NULL, NULL, NULL, NULL, NULL, 0, '0', '0', 'passenger_cancel', '不想去了，行程取消', NULL, '2026-05-28 17:57:25', '13560004373', '2026-05-28 18:02:27', '13560004373', '1', '0');
INSERT INTO `bus_order` VALUES ('1e9b16a7633c41de953bc5544d0d6118', 'ORD_20260528154231_285440', NULL, 'dynamic_bus', 'cancelled', 'refunding', NULL, '2059902964167528449', NULL, NULL, NULL, NULL, NULL, '2026-05-28 15:42:32', 6.00, 6.00, 0.00, 0.00, 0.00, 0.00, 0.00, 0.00, 'auto_deduct', NULL, 6.00, 'REFUNDING', '2026-05-28 15:42:56', NULL, 1, NULL, '13', '20', NULL, NULL, NULL, 0, 0, 0.00, 0.00, NULL, NULL, NULL, NULL, NULL, NULL, 0, '0', '0', 'passenger_cancel', '不想去了，行程取消', NULL, '2026-05-28 15:42:32', '13560004373', '2026-05-28 15:42:56', '13560004373', '1', '0');
INSERT INTO `bus_order` VALUES ('1f37e6a70d66444c87fae320798a88d4', 'ORD_20260515173553_308416', '630169240101000001120220100106271000000404003303A3055E7A6F1B61A990CD800F75D469BFF780E661816094E90CADF1F266090EB203A83716543D1CC9B62D9D573ACEE43314DF3CDC2472FB872F458D2BEEA691C371D948E9ECAA34CC42D6863C85515328326488D3DD291C8FBD00B6674DEA7B191f37e6a70d66444c87fae320798a88d40205257573008373350602201001022010010106000002b07aa46c793681d22b30cab415fd96a25f479b1bd31045fb7dc7a5503590ed426A13AF180014200000000000000000000000000000000000000000000000000000000000000000158EA4991912899C99EE596457C156AE089572A75AD745C6F5B853703EC0DD692D5F4930FE40119AC0EE143F43E1D052F768B09E077F6B1F7342722D91179E7EF06A13AF191586145BE064A53E299E77F13CE6F31750072180B0F3B69CCE0E8925A91A5A5B7A7B5F72E19492D15AE214ED57BD82FB564C086FB0820E83B602ACFB292CD037B5', 'dynamic_bus', 'completed', 'paid', NULL, '2052575730083733506', '郑育明', '700045867025624230', '13432496353', 'DRV001', '京A12345', '2026-05-15 17:35:54', 10.03, 10.03, 0.00, 0.00, 0.00, 0.00, 0.00, 0.00, 'auto_deduct', NULL, 0.00, NULL, NULL, NULL, 1, NULL, '13', '12', NULL, '2026-05-29 14:34:37', '2026-05-29 14:34:43', 0, 0, 0.00, 0.00, NULL, NULL, NULL, NULL, NULL, NULL, 0, '0', '0', NULL, NULL, NULL, '2026-05-15 17:35:54', '13560004373', '2026-05-29 14:34:43', '13432496353', '1', '0');
INSERT INTO `bus_order` VALUES ('1f641c34605749b8a55e8bc6349665e0', 'ORD_20260528171807_195776', NULL, 'dynamic_bus', 'cancelled', 'refunding', NULL, '2059892109837258754', '刘罗瑞', '5', '13652944754', NULL, '京D98765', '2026-05-28 17:18:07', 12.00, 12.00, 0.00, 0.00, 0.00, 0.00, 0.00, 0.00, 'auto_deduct', NULL, 9.60, 'REFUNDING', '2026-05-28 17:27:04', NULL, 1, NULL, '2019', '2013', NULL, NULL, NULL, 0, 0, 0.00, 0.00, NULL, NULL, NULL, NULL, NULL, NULL, 0, '0', '0', 'passenger_cancel', '不想去了，行程取消', NULL, '2026-05-28 17:18:07', '13560004373', '2026-05-28 17:27:04', '13560004373', '1', '0');
INSERT INTO `bus_order` VALUES ('202605160002', 'GZ202605160002', '630169240101000001120220100106271000000404003303A3055E7A6F1B61A990CD800F75D469BFF780E661816094E90CADF1F266090EB203A83716543D1CC9B62D9D573ACEE43314DF3CDC2472FB872F458D2BEEA691C371D948E9ECAA34CC42D6863C85515328326488D3DD291C8FBD00B6674DEA7B19000000000000000000002026051600020000000000000000000202201001022010010106000002b07aa46c793681d22b30cab415fd96a25f479b1bd31045fb7dc7a5503590ed426A0A9E5700142000000000000000000000000000000000000000000000000000000000000000001546CDE2CEA4750788C60FCC15E3925178E7DB1283A90A3D31DE5C3D0289D4F57D342E2DA5B463479E30D7ABD5990196D282DC52DE735EE7E5AFF39BC7BB77D1E16A0A9E571563A44E537140826B183CA212471C3512D3E898DC91FF422B660AE4E13583AABBF6810011A3367B7BF6FA99B5D9DC127FE49A26D7084364D246C5F52EF0D58F85', 'ONLINE', 'driver_arriving', 'PAID', '13922220002', '002', NULL, '700045867025624302', '13912341002', 'JOBGZ02', '粤AD67890', '2026-05-16 09:20:00', 45.00, 48.00, 3.00, 0.00, 0.00, 0.00, 0.00, 0.00, 'WECHAT', '2026-05-16 09:21:00', 0.00, NULL, NULL, 'APP', 2, '广州', '珠江新城', '天河客运站', '2026-05-16 09:23:00', '2026-05-16 09:35:00', NULL, 12, 0, 15.00, NULL, 'NOT_ISSUED', 'GZ20260516002', '2026-05-16', '09:00:00', 'R_GZ02', '天河穿梭线', 38, '0', '0', NULL, NULL, NULL, '2026-05-16 20:48:52', 'system', '2026-05-18 13:06:32', 'appuser', '1', '0');
INSERT INTO `bus_order` VALUES ('23a28db9a73448918ea39ea5c9c2cc80', 'ORD_20260529094322_941248', NULL, 'dynamic_bus', 'pending_dispatch', 'pending', NULL, '2060174941524512769', NULL, NULL, NULL, NULL, NULL, '2026-05-29 09:43:23', 15.02, 15.02, 0.00, 0.00, 0.00, 0.00, 0.00, 0.00, 'auto_deduct', NULL, 0.00, NULL, NULL, NULL, 2, NULL, '2014', '2013', NULL, NULL, NULL, 0, 0, 0.00, 0.00, NULL, NULL, NULL, NULL, NULL, NULL, 0, '0', '0', NULL, NULL, NULL, '2026-05-29 09:43:23', '13560004373', '2026-05-29 09:43:27', '13560004373', '1', '0');
INSERT INTO `bus_order` VALUES ('277d695ec19c44319f31e556e406e470', 'ORD_20260529093004_001088', NULL, 'dynamic_bus', 'cancelled', 'refunding', NULL, '2059902964167528449', NULL, NULL, NULL, NULL, NULL, '2026-05-29 09:30:04', 6.00, 6.00, 0.00, 0.00, 0.00, 0.00, 0.00, 0.00, 'auto_deduct', NULL, 6.00, 'REFUNDING', '2026-05-29 10:27:57', NULL, 1, NULL, '13', '20', NULL, NULL, NULL, 0, 0, 0.00, 0.00, NULL, NULL, NULL, NULL, NULL, NULL, 0, '0', '0', 'passenger_cancel', '不想去了，行程取消', NULL, '2026-05-29 09:30:04', '13560004373', '2026-05-29 10:27:57', '13560004373', '1', '0');
INSERT INTO `bus_order` VALUES ('35a26b307f36465dbf3d0ab26382fe30', 'ORD_20260528150740_502976', NULL, 'dynamic_bus', 'pending_dispatch', 'pending', NULL, '2053666005677953025', NULL, NULL, NULL, NULL, NULL, '2026-05-28 15:07:40', 16.52, 16.52, 0.00, 0.00, 0.00, 0.00, 0.00, 0.00, 'auto_deduct', NULL, 0.00, NULL, NULL, NULL, 2, NULL, '2012', '2014', NULL, NULL, NULL, 0, 0, 0.00, 0.00, NULL, NULL, NULL, NULL, NULL, NULL, 0, '0', '0', NULL, NULL, NULL, '2026-05-28 15:07:40', '13560004373', '2026-05-28 15:07:42', '13560004373', '1', '0');
INSERT INTO `bus_order` VALUES ('36f926d087754ff789f126747863d826', 'ORD_20260529184919_060096', NULL, 'dynamic_bus', 'pending_dispatch', 'pending', NULL, '2059902964167528449', NULL, NULL, NULL, NULL, NULL, '2026-05-29 18:49:20', 6.00, 6.00, 0.00, 0.00, 0.00, 0.00, 0.00, 0.00, 'auto_deduct', NULL, 0.00, NULL, NULL, NULL, 1, NULL, '13', '20', NULL, NULL, NULL, 0, 0, 0.00, 0.00, NULL, NULL, NULL, NULL, NULL, NULL, 0, '0', '0', NULL, NULL, NULL, '2026-05-29 18:49:20', '13560004373', '2026-05-29 18:49:24', '13560004373', '1', '0');
INSERT INTO `bus_order` VALUES ('37877331c0684fcdbfbe0babec5fb44f', 'ORD_20260601182837_099136', NULL, 'dynamic_bus', 'cancelled', 'refunding', NULL, '2061296189767847937', NULL, NULL, NULL, NULL, NULL, '2026-06-01 18:28:37', 6.00, 6.00, 0.00, 0.00, 0.00, 0.00, 0.00, 0.00, 'auto_deduct', NULL, 6.00, 'REFUNDING', '2026-06-01 18:29:52', NULL, 1, NULL, '2027', '2028', NULL, NULL, NULL, 0, 0, 0.00, 0.00, NULL, NULL, NULL, NULL, NULL, NULL, 0, '0', '0', 'passenger_cancel', '不想去了，行程取消', NULL, '2026-06-01 18:28:37', '13560004373', '2026-06-01 18:29:52', '13560004373', '1', '0');
INSERT INTO `bus_order` VALUES ('45ba93a1d6194c05a28f69d6c328196a', 'ORD_20260528180232_085632', '630169240101000001120220100106271000000404003303A3055E7A6F1B61A990CD800F75D469BFF780E661816094E90CADF1F266090EB203A83716543D1CC9B62D9D573ACEE43314DF3CDC2472FB872F458D2BEEA691C371D948E9ECAA34CC42D6863C85515328326488D3DD291C8FBD00B6674DEA7B1945ba93a1d6194c05a28f69d6c328196a0205990296416752844902201001022010010106000002b07aa46c793681d22b30cab415fd96a25f479b1bd31045fb7dc7a5503590ed426A18F0670014200000000000000000000000000000000000000000000000000000000000000000150DC6E79D76DD49AF2A812A6DC6D29FB7A7E9C95593F6998FF7A0D65843FE627A765459DC35C4F89BC0AEA7306B606076961E19116E1FAC13C62A83C47945013F6A18F067153EDAD2E4DCCD246F9942D5E34C2DC01F73EDD563BFB3EEA3C0878D6095ADE8AC42A955AD05105CEEB768CFA791411DB4C1218F9BA396751DC46767713F6038E0', 'dynamic_bus', 'completed', 'pending', NULL, '2059902964167528449', '刘罗瑞', '5', '13652944754', NULL, '京D98765', '2026-05-28 18:02:33', 7.51, 7.51, 0.00, 0.00, 0.00, 0.00, 0.00, 0.00, 'auto_deduct', NULL, 0.00, NULL, NULL, NULL, 1, NULL, '2013', '2014', NULL, '2026-05-29 15:16:16', '2026-05-29 15:16:24', 0, 0, 0.00, 0.00, NULL, NULL, NULL, NULL, NULL, NULL, 0, '0', '0', NULL, NULL, NULL, '2026-05-28 18:02:33', '13560004373', '2026-05-29 15:16:24', '13652944754', '1', '0');
INSERT INTO `bus_order` VALUES ('49ee96c52c624e3ebe7f427d635d2d78', 'ORD_20260601170930_935296', NULL, 'dynamic_bus', 'cancelled', 'refunding', NULL, '2061296189767847937', NULL, NULL, NULL, NULL, NULL, '2026-06-01 17:09:31', 7.51, 7.51, 0.00, 0.00, 0.00, 0.00, 0.00, 0.00, 'auto_deduct', NULL, 7.51, 'REFUNDING', '2026-06-01 17:11:25', NULL, 1, NULL, '2013', '2014', NULL, NULL, NULL, 0, 0, 0.00, 0.00, NULL, NULL, NULL, NULL, NULL, NULL, 0, '0', '0', 'passenger_cancel', '不想去了，行程取消', NULL, '2026-06-01 17:09:31', '13560004373', '2026-06-01 17:11:25', '13560004373', '1', '0');
INSERT INTO `bus_order` VALUES ('4a4034cb56ee42419de0774c29bf425f', 'ORD_20260529184206_666560', NULL, 'dynamic_bus', 'cancelled', 'refunding', NULL, '2059902964167528449', NULL, NULL, NULL, NULL, NULL, '2026-05-29 18:42:06', 7.51, 7.51, 0.00, 0.00, 0.00, 0.00, 0.00, 0.00, 'auto_deduct', NULL, 7.51, 'REFUNDING', '2026-05-29 18:49:11', NULL, 1, NULL, '2013', '2014', NULL, NULL, NULL, 0, 0, 0.00, 0.00, NULL, NULL, NULL, NULL, NULL, NULL, 0, '0', '0', 'passenger_cancel', '不想去了，行程取消', NULL, '2026-05-29 18:42:06', '13560004373', '2026-05-29 18:49:11', '13560004373', '1', '0');
INSERT INTO `bus_order` VALUES ('585b3e1050844e24b0ff09dc45da1c5b', 'ORD_20260530105548_574848', NULL, 'dynamic_bus', 'cancelled', 'refunding', NULL, '2059902964167528449', NULL, '28888', NULL, NULL, '粤A00010D', '2026-05-30 10:55:58', 7.01, 7.01, 0.00, 0.00, 0.00, 0.00, 0.00, 0.00, 'auto_deduct', NULL, 5.61, 'REFUNDING', '2026-05-30 14:29:26', NULL, 1, NULL, '2007', '2008', NULL, NULL, NULL, 0, 0, 0.00, 0.00, NULL, NULL, NULL, NULL, NULL, NULL, 0, '0', '0', 'passenger_cancel', '不想去了，行程取消', NULL, '2026-05-30 10:55:58', '13560004373', '2026-05-30 14:29:26', '13560004373', '1', '0');
INSERT INTO `bus_order` VALUES ('59a3dd42b5fe4e879aed5a763f447e9e', 'ORD_20260518094215_604928', '630169240101000001120220100106271000000404003303A3055E7A6F1B61A990CD800F75D469BFF780E661816094E90CADF1F266090EB203A83716543D1CC9B62D9D573ACEE43314DF3CDC2472FB872F458D2BEEA691C371D948E9ECAA34CC42D6863C85515328326488D3DD291C8FBD00B6674DEA7B1959a3dd42b5fe4e879aed5a763f447e9e0205366600567795302502201001022010010106000002b07aa46c793681d22b30cab415fd96a25f479b1bd31045fb7dc7a5503590ed426A0B06A700142000000000000000000000000000000000000000000000000000000000000000001586D3A092BBE1FF3972AD826525B3A1F411EEC9D762D2A082B39918DC3B72E132F492C776EFB976838A61A2E31D0F5734F84E6456D373B000E11F6393F4B9EB356A0B06A71527EF92E7A6DE3F70976C1D77CD1A8EC63356A39380993AC10AC3F2EF5D9C2114AEC8CCD801D1ACBD6B697B9C617169F14FB0A97B7AC2965717AE800C14EFD480', 'dynamic_bus', 'cancelled', 'refunding', NULL, '2053666005677953025', NULL, NULL, NULL, NULL, NULL, '2026-05-18 09:42:25', 6.26, 6.26, 0.00, 0.00, 0.00, 0.00, 0.00, 0.00, 'auto_deduct', NULL, 6.26, 'REFUNDING', '2026-05-18 15:41:31', NULL, 1, NULL, '12', '11', NULL, NULL, NULL, 0, 0, 0.00, 0.00, NULL, NULL, NULL, NULL, NULL, NULL, 0, '0', '0', 'passenger_cancel', '行程有变，需要修改路线', NULL, '2026-05-18 09:42:25', '13560004373', '2026-05-18 20:31:36', '13432496353', '1', '0');
INSERT INTO `bus_order` VALUES ('5fabc01d22c14e308f4da7bafff2f651', 'ORD_20260601184100_707392', NULL, 'dynamic_bus', 'cancelled', 'refunding', NULL, '2061296189767847937', NULL, NULL, NULL, NULL, NULL, '2026-06-01 18:41:01', 6.24, 6.24, 0.00, 0.00, 0.00, 0.00, 0.00, 0.00, 'auto_deduct', NULL, 6.24, 'REFUNDING', '2026-06-01 18:42:20', NULL, 1, NULL, '13', '2027', NULL, NULL, NULL, 0, 0, 0.00, 0.00, NULL, NULL, NULL, NULL, NULL, NULL, 0, '0', '0', 'passenger_cancel', '不想去了，行程取消', NULL, '2026-06-01 18:41:01', '13560004373', '2026-06-01 18:42:20', '13560004373', '1', '0');
INSERT INTO `bus_order` VALUES ('70172de873f742a89940b130f098e7b4', 'ORD_20260601153544_931264', NULL, 'dynamic_bus', 'pending_dispatch', 'pending', NULL, '2053666005677953025', NULL, NULL, NULL, NULL, NULL, '2026-06-01 15:35:44', 6.00, 6.00, 0.00, 0.00, 0.00, 0.00, 0.00, 0.00, 'auto_deduct', NULL, 0.00, NULL, NULL, NULL, 1, NULL, '13', '20', NULL, NULL, NULL, 0, 0, 0.00, 0.00, NULL, NULL, NULL, NULL, NULL, NULL, 0, '0', '0', NULL, NULL, NULL, '2026-06-01 15:35:44', '13560004373', '2026-06-01 15:35:46', '13560004373', '1', '0');
INSERT INTO `bus_order` VALUES ('761d129cfd91409cac30a287b1c501fa', 'ORD_20260601183603_094656', NULL, 'dynamic_bus', 'cancelled', 'refunding', NULL, '2061296189767847937', NULL, NULL, NULL, NULL, NULL, '2026-06-01 18:36:04', 6.24, 6.24, 0.00, 0.00, 0.00, 0.00, 0.00, 0.00, 'auto_deduct', NULL, 6.24, 'REFUNDING', '2026-06-01 18:39:01', NULL, 1, NULL, '13', '2028', NULL, NULL, NULL, 0, 0, 0.00, 0.00, NULL, NULL, NULL, NULL, NULL, NULL, 0, '0', '0', 'passenger_cancel', '不想去了，行程取消', NULL, '2026-06-01 18:36:04', '13560004373', '2026-06-01 18:39:01', '13560004373', '1', '0');
INSERT INTO `bus_order` VALUES ('778d8f49dad743428388346dffa60748', 'ORD_20260601153413_325632', NULL, 'dynamic_bus', 'cancelled', 'refunding', NULL, '2053666005677953025', NULL, NULL, NULL, NULL, NULL, '2026-06-01 15:34:23', 6.00, 6.00, 0.00, 0.00, 0.00, 0.00, 0.00, 0.00, 'auto_deduct', NULL, 6.00, 'REFUNDING', '2026-06-01 15:35:42', NULL, 1, NULL, '13', '20', NULL, NULL, NULL, 0, 0, 0.00, 0.00, NULL, NULL, NULL, NULL, NULL, NULL, 0, '0', '0', 'passenger_cancel', '不想去了，行程取消', NULL, '2026-06-01 15:34:23', '13560004373', '2026-06-01 15:35:42', '13560004373', '1', '0');
INSERT INTO `bus_order` VALUES ('77f082300d004983b3f74dcd4d4d3262', 'ORD_20260528090948_111936', NULL, 'dynamic_bus', 'pending_dispatch', 'pending', NULL, '2053666005677953025', NULL, NULL, NULL, NULL, NULL, '2026-05-28 09:09:58', 6.00, 6.00, 0.00, 0.00, 0.00, 0.00, 0.00, 0.00, 'auto_deduct', NULL, 0.00, NULL, NULL, NULL, 1, NULL, '13', '20', NULL, NULL, NULL, 0, 0, 0.00, 0.00, NULL, NULL, NULL, NULL, NULL, NULL, 0, '0', '0', NULL, NULL, NULL, '2026-05-28 09:09:58', '13560004373', '2026-05-28 09:10:00', '13560004373', '1', '0');
INSERT INTO `bus_order` VALUES ('8bd375f3c276463186759801e22ec4f8', 'ORD_20260529093123_506304', NULL, 'dynamic_bus', 'pending_dispatch', 'pending', NULL, '2053666005677953025', NULL, NULL, NULL, NULL, NULL, '2026-05-29 09:31:23', 12.00, 12.00, 0.00, 0.00, 0.00, 0.00, 0.00, 0.00, 'auto_deduct', NULL, 0.00, NULL, NULL, NULL, 2, NULL, '13', '20', NULL, NULL, NULL, 0, 0, 0.00, 0.00, NULL, NULL, NULL, NULL, NULL, NULL, 0, '0', '0', NULL, NULL, NULL, '2026-05-29 09:31:23', '13560004373', '2026-05-29 09:31:26', '13560004373', '1', '0');
INSERT INTO `bus_order` VALUES ('8c29756ff24f49fda4281ee3edf24f4c', 'ORD_20260529184145_459904', NULL, 'dynamic_bus', 'pending_confirm', 'pending', NULL, '2059902964167528449', NULL, NULL, NULL, NULL, NULL, '2026-05-29 18:41:55', 7.51, 7.51, 0.00, 0.00, 0.00, 0.00, 0.00, 0.00, 'auto_deduct', NULL, 0.00, NULL, NULL, NULL, 1, NULL, '2013', '2014', NULL, NULL, NULL, 0, 0, 0.00, 0.00, NULL, NULL, NULL, NULL, NULL, NULL, 0, '0', '0', NULL, NULL, NULL, '2026-05-29 18:41:55', '13560004373', '2026-05-29 18:41:55', '13560004373', '1', '0');
INSERT INTO `bus_order` VALUES ('8cd9743567404874b060d3033290ac8d', 'ORD_20260529102858_880896', NULL, 'dynamic_bus', 'cancelled', 'refunding', NULL, '2059902964167528449', NULL, '700045867025624230', NULL, NULL, '粤A00009D', '2026-05-29 10:28:59', 6.00, 6.00, 0.00, 0.00, 0.00, 0.00, 0.00, 0.00, 'auto_deduct', NULL, 4.80, 'REFUNDING', '2026-05-29 18:42:04', NULL, 1, NULL, '13', '20', NULL, NULL, NULL, 0, 0, 0.00, 0.00, NULL, NULL, NULL, NULL, NULL, NULL, 0, '0', '0', 'passenger_cancel', '不想去了，行程取消', NULL, '2026-05-29 10:28:59', '13560004373', '2026-05-29 18:42:04', '13560004373', '1', '0');
INSERT INTO `bus_order` VALUES ('b24c2b75841b4405a77a7c9b8e6ebf71', 'ORD_20260529184156_157056', NULL, 'dynamic_bus', 'pending_confirm', 'pending', NULL, '2059902964167528449', NULL, NULL, NULL, NULL, NULL, '2026-05-29 18:41:57', 7.51, 7.51, 0.00, 0.00, 0.00, 0.00, 0.00, 0.00, 'auto_deduct', NULL, 0.00, NULL, NULL, NULL, 1, NULL, '2013', '2014', NULL, NULL, NULL, 0, 0, 0.00, 0.00, NULL, NULL, NULL, NULL, NULL, NULL, 0, '0', '0', NULL, NULL, NULL, '2026-05-29 18:41:57', '13560004373', '2026-05-29 18:41:57', '13560004373', '1', '0');
INSERT INTO `bus_order` VALUES ('cda653a49cca451cbce27bd0eb1073b1', 'ORD_20260602111622_013056', NULL, 'dynamic_bus', 'pending_dispatch', 'pending', NULL, '2061647851355279361', NULL, NULL, NULL, NULL, NULL, '2026-06-02 11:16:23', 6.24, 6.24, 0.00, 0.00, 0.00, 0.00, 0.00, 0.00, 'auto_deduct', NULL, 0.00, NULL, NULL, NULL, 1, NULL, '13', '2028', NULL, NULL, NULL, 0, 0, 0.00, 0.00, NULL, NULL, NULL, NULL, NULL, NULL, 0, '0', '0', NULL, NULL, NULL, '2026-06-02 11:16:23', '13560004373', '2026-06-02 11:16:25', '13560004373', '1', '0');
INSERT INTO `bus_order` VALUES ('GZ202605160001', 'GZ202605160001', NULL, 'ONLINE', 'COMPLETED', 'PAID', '13922220001', 'P_GZ001', NULL, '700045867025624301', '13912341001', 'JOBGZ01', '粤AD12345', '2026-05-16 08:00:00', 38.50, 40.00, 1.50, 0.00, 0.00, 0.00, 0.00, 0.00, 'ALIPAY', '2026-05-16 08:01:00', 0.00, NULL, NULL, 'APP', 1, '广州', '天河体育中心', '广州东站', '2026-05-16 08:02:00', '2026-05-16 08:15:00', '2026-05-16 08:45:00', 13, 30, 12.50, 13.20, 'ISSUED', 'GZ20260516001', '2026-05-16', '07:30:00', 'R_GZ01', '东站快线', 45, '1', '0', NULL, NULL, NULL, '2026-05-16 20:48:52', 'system', '2026-05-16 20:49:41', 'system', '1', '0');
INSERT INTO `bus_order` VALUES ('GZ202605160003', 'GZ202605160003', NULL, 'ONLINE', 'WAITING_PAY', 'UNPAID', '13922220003', 'P_GZ003', NULL, NULL, NULL, NULL, NULL, '2026-05-16 10:05:00', 26.50, 26.50, 0.00, 0.00, 0.00, 0.00, 0.00, 0.00, NULL, NULL, 0.00, NULL, NULL, 'H5', 1, '广州', '广州塔', '猎德', NULL, NULL, NULL, 0, 0, 7.00, NULL, 'NOT_ISSUED', NULL, NULL, NULL, NULL, NULL, 0, '0', '0', NULL, NULL, NULL, '2026-05-16 20:48:52', 'system', '2026-05-16 20:48:52', 'system', '1', '0');
INSERT INTO `bus_order` VALUES ('GZ202605160004', 'GZ202605160004', NULL, 'ONLINE', 'CANCELLED', 'UNPAID', '13922220004', 'P_GZ004', NULL, '700045867025624303', NULL, NULL, NULL, '2026-05-16 07:45:00', 0.00, 58.00, 0.00, 0.00, 0.00, 0.00, 0.00, 0.00, NULL, NULL, 0.00, NULL, '2026-05-16 07:50:00', 'APP', 3, '广州', '天河城', '广州南站', NULL, NULL, NULL, 0, 0, 28.00, NULL, 'NOT_ISSUED', NULL, NULL, NULL, NULL, NULL, 0, '1', '0', 'USER_CANCEL', '临时有事', NULL, '2026-05-16 20:48:52', 'system', '2026-05-16 20:48:52', 'system', '1', '0');
INSERT INTO `bus_order` VALUES ('GZ202605160005', 'GZ202605160005', NULL, 'ONLINE', 'CANCELLED', 'REFUNDED', '13922220005', 'P_GZ005', NULL, '700045867025624304', '13912341004', 'JOBGZ04', '粤AD98765', '2026-05-15 19:00:00', 72.00, 75.00, 3.00, 0.00, 0.00, 0.00, 0.00, 0.00, 'ALIPAY', '2026-05-15 19:02:00', 72.00, 'SUCCESS', '2026-05-15 19:30:00', 'APP', 2, '广州', '石牌桥', '科学城', '2026-05-15 19:03:00', NULL, NULL, 3, 0, 25.00, NULL, 'NOT_ISSUED', 'GZ20260515001', '2026-05-15', '18:30:00', 'R_GZ05', '科学城晚班', 22, '1', '1', 'DRIVER_CANCEL', '车辆故障', '行程取消全额退款', '2026-05-16 20:48:52', 'system', '2026-05-16 20:49:41', 'system', '1', '0');
INSERT INTO `bus_order` VALUES ('GZ202605160006', 'GZ202605160006', NULL, 'ONLINE', 'COMPLETED', 'PAID', '13922220006', 'P_GZ006', NULL, '700045867025624305', '13912341005', 'JOBGZ05', '粤AD24680', '2026-05-16 11:00:00', 55.00, 58.00, 3.00, 0.00, 0.00, 0.00, 0.00, 0.00, 'WECHAT', '2026-05-16 11:01:00', 0.00, NULL, NULL, 'APP', 1, '广州', '华师', '广州白云机场', '2026-05-16 11:03:00', '2026-05-16 11:20:00', '2026-05-16 12:10:00', 17, 50, 35.00, 36.40, 'NOT_ISSUED', 'GZ20260516003', '2026-05-16', '10:30:00', 'R_GZ06', '机场快线', 40, '1', '0', NULL, NULL, NULL, '2026-05-16 20:48:52', 'system', '2026-05-16 20:49:41', 'system', '1', '0');
INSERT INTO `bus_order` VALUES ('NEAR_ORD_001', 'NEAR20260516001', NULL, 'ONLINE', 'WAITING_PAY', 'UNPAID', '13912340001', 'P_Near001', NULL, NULL, NULL, NULL, NULL, '2026-05-16 20:30:00', 12.00, 12.00, 0.00, 0.00, 0.00, 0.00, 0.00, 0.00, NULL, NULL, 0.00, NULL, NULL, 'APP', 1, '广州', '体育西路地铁站A口', '天河城购物中心', NULL, NULL, NULL, 0, 0, 3.50, NULL, 'NOT_ISSUED', NULL, NULL, NULL, NULL, NULL, 0, '0', '0', NULL, NULL, NULL, '2026-05-16 21:02:38', 'user001', '2026-05-16 21:02:38', 'user001', '1', '0');
INSERT INTO `bus_order` VALUES ('NEAR_ORD_002', 'NEAR20260516002', NULL, 'ONLINE', 'WAITING_PAY', 'UNPAID', '13912340002', 'P_Near002', NULL, NULL, NULL, NULL, NULL, '2026-05-16 20:25:00', 18.00, 18.00, 0.00, 0.00, 0.00, 0.00, 0.00, 0.00, NULL, NULL, 0.00, NULL, NULL, 'APP', 2, '广州', '珠江新城地铁站', '广州塔', NULL, NULL, NULL, 0, 0, 5.00, NULL, 'NOT_ISSUED', NULL, NULL, NULL, NULL, NULL, 0, '0', '0', NULL, NULL, NULL, '2026-05-16 21:02:38', 'user002', '2026-05-16 21:02:38', 'user002', '1', '0');
INSERT INTO `bus_order` VALUES ('NEAR_ORD_003', 'NEAR20260516003', NULL, 'ONLINE', 'WAITING_PAY', 'UNPAID', '13912340003', 'P_Near003', NULL, NULL, NULL, NULL, NULL, '2026-05-16 20:35:00', 10.00, 10.00, 0.00, 0.00, 0.00, 0.00, 0.00, 0.00, NULL, NULL, 0.00, NULL, NULL, 'H5', 1, '广州', '天河南一路', '石牌桥', NULL, NULL, NULL, 0, 0, 2.80, NULL, 'NOT_ISSUED', NULL, NULL, NULL, NULL, NULL, 0, '0', '0', NULL, NULL, NULL, '2026-05-16 21:02:38', 'user003', '2026-05-16 21:02:38', 'user003', '1', '0');
INSERT INTO `bus_order` VALUES ('NEAR_ORD_004', 'NEAR20260516004', NULL, 'ONLINE', 'WAITING_PAY', 'UNPAID', '13912340004', 'P_Near004', NULL, NULL, NULL, NULL, NULL, '2026-05-16 20:20:00', 8.00, 8.00, 0.00, 0.00, 0.00, 0.00, 0.00, 0.00, NULL, NULL, 0.00, NULL, NULL, 'APP', 3, '广州', '猎德地铁站', '冼村', NULL, NULL, NULL, 0, 0, 2.00, NULL, 'NOT_ISSUED', NULL, NULL, NULL, NULL, NULL, 0, '0', '0', NULL, NULL, NULL, '2026-05-16 21:02:38', 'user004', '2026-05-16 21:02:38', 'system', '1', '0');
INSERT INTO `bus_order` VALUES ('NEAR_ORD_005', 'NEAR20260516005', NULL, 'ONLINE', 'WAITING_PAY', 'UNPAID', '13912340005', 'P_Near005', NULL, NULL, NULL, NULL, NULL, '2026-05-16 20:40:00', 10.00, 10.00, 0.00, 0.00, 0.00, 0.00, 0.00, 0.00, NULL, NULL, 0.00, NULL, NULL, 'APP', 1, '广州', '华师地铁站', '岗顶', NULL, NULL, NULL, 0, 0, 2.90, NULL, 'NOT_ISSUED', NULL, NULL, NULL, NULL, NULL, 0, '0', '0', NULL, NULL, NULL, '2026-05-16 21:02:38', 'user005', '2026-05-16 21:02:38', 'user005', '1', '0');
INSERT INTO `bus_order` VALUES ('NEAR_ORD_006', 'NEAR20260516006', NULL, 'ONLINE', 'DRIVING', 'REFUNDED', '13912340006', 'P_Near006', '张伟', '700045867025624230', '13912340001', 'JOB001', '粤AD12345', '2026-05-16 19:50:00', 15.00, 15.00, 0.00, 0.00, 0.00, 0.00, 0.00, 0.00, 'WECHAT', '2026-05-16 19:52:00', 15.00, 'REFUNDED', NULL, 'APP', 1, '广州', '五羊邨', '天河体育中心', '2026-05-16 19:55:00', '2026-05-16 20:10:00', NULL, 5, 0, 4.20, NULL, 'NOT_ISSUED', 'GZ20260516007', '2026-05-16', '19:30:00', 'R_GZ07', '体育中心专线', 35, '0', '1', NULL, NULL, '', '2026-05-16 19:50:00', 'user006', '2026-05-21 16:01:04', 'admin', '1', '0');
INSERT INTO `bus_order` VALUES ('NEAR_ORD_007', 'NEAR20260516007', NULL, 'ONLINE', 'CANCELLED', 'UNPAID', '13912340007', 'P_Near007', NULL, NULL, NULL, NULL, NULL, '2026-05-16 19:00:00', 0.00, 13.00, 0.00, 0.00, 0.00, 0.00, 0.00, 0.00, NULL, NULL, 0.00, NULL, '2026-05-16 20:00:00', 'APP', 2, '广州', '杨箕地铁站', '广州动物园', NULL, NULL, NULL, 0, 0, 3.80, NULL, 'NOT_ISSUED', NULL, NULL, NULL, NULL, NULL, 0, '1', '0', 'TIMEOUT_CANCEL', '支付超时自动取消', NULL, '2026-05-16 19:00:00', 'user007', '2026-05-16 21:02:38', 'system', '1', '0');
INSERT INTO `bus_order` VALUES ('NEAR_ORD_008', 'NEAR20260516008', NULL, 'ONLINE', 'CANCELLED', 'UNPAID', '13912340008', 'P_Near008', NULL, NULL, NULL, NULL, NULL, '2026-05-16 20:15:00', 0.00, 8.00, 0.00, 0.00, 0.00, 0.00, 0.00, 0.00, NULL, NULL, 0.00, NULL, '2026-05-16 20:28:00', 'APP', 1, '广州', '林和西地铁站', '中信广场', NULL, NULL, NULL, 0, 0, 1.50, NULL, 'NOT_ISSUED', NULL, NULL, NULL, NULL, NULL, 0, '1', '0', 'USER_CANCEL', '用户手动取消', NULL, '2026-05-16 20:15:00', 'user008', '2026-05-16 21:02:38', 'user008', '1', '0');
INSERT INTO `bus_order` VALUES ('NEAR_ORD_009', 'NEAR20260516009', NULL, 'ONLINE', 'WAITING_PAY', 'UNPAID', '13912340009', 'P_Near009', NULL, NULL, NULL, NULL, NULL, '2026-05-16 20:28:00', 8.00, 8.00, 0.00, 0.00, 0.00, 0.00, 0.00, 0.00, NULL, NULL, 0.00, NULL, NULL, 'APP', 2, '广州', '沙河顶地铁站', '沙河服装城', NULL, NULL, NULL, 0, 0, 1.80, NULL, 'NOT_ISSUED', NULL, NULL, NULL, NULL, NULL, 0, '0', '0', NULL, NULL, NULL, '2026-05-16 21:02:38', 'user009', '2026-05-16 21:02:38', 'system', '1', '0');
INSERT INTO `bus_order` VALUES ('NEAR_ORD_010', 'NEAR20260516010', NULL, 'ONLINE', 'WAITING_PAY', 'UNPAID', '13912340010', 'P_Near010', NULL, NULL, NULL, NULL, NULL, '2026-05-16 20:32:00', 9.00, 9.00, 0.00, 0.00, 0.00, 0.00, 0.00, 0.00, NULL, NULL, 0.00, NULL, NULL, 'H5', 1, '广州', '黄埔大道西', '跑马场', NULL, NULL, NULL, 0, 0, 2.50, NULL, 'NOT_ISSUED', NULL, NULL, NULL, NULL, NULL, 0, '0', '0', NULL, NULL, NULL, '2026-05-16 21:02:38', 'user010', '2026-05-16 21:02:38', 'user010', '1', '0');
INSERT INTO `bus_order` VALUES ('ORD_2025001', 'ORD202605270001', NULL, 'ONLINE', 'COMPLETED', 'PAID', '13900010001', 'P10001', '陈伟强', NULL, NULL, NULL, '粤A00001D', '2026-05-27 08:30:00', 15.00, 0.00, 0.00, 0.00, 0.00, 0.00, 0.00, 0.00, NULL, NULL, 0.00, NULL, NULL, NULL, 1, NULL, '体育西路站', '珠江新城站', NULL, NULL, NULL, 0, 0, 0.00, 0.00, NULL, NULL, NULL, NULL, 'R_GZ_201', '天河穿梭线', 0, '0', '0', NULL, NULL, NULL, '2026-05-27 10:58:28', NULL, '2026-05-27 10:58:28', NULL, '1', '0');
INSERT INTO `bus_order` VALUES ('ORD_2025002', 'ORD202605270002', NULL, 'ONLINE', 'COMPLETED', 'PAID', '13900010002', 'P10002', '陈伟强', NULL, NULL, NULL, '粤A00001D', '2026-05-27 09:00:00', 15.00, 0.00, 0.00, 0.00, 0.00, 0.00, 0.00, 0.00, NULL, NULL, 0.00, NULL, NULL, NULL, 2, NULL, '体育西路站', '珠江新城站', NULL, NULL, NULL, 0, 0, 0.00, 0.00, NULL, NULL, NULL, NULL, 'R_GZ_201', '天河穿梭线', 0, '0', '0', NULL, NULL, NULL, '2026-05-27 10:58:28', NULL, '2026-05-27 10:58:28', NULL, '1', '0');
INSERT INTO `bus_order` VALUES ('ORD_2025003', 'ORD202605270003', NULL, 'ONLINE', 'COMPLETED', 'PAID', '13900010003', 'P10003', '李俊杰', NULL, NULL, NULL, '粤A00002D', '2026-05-27 08:45:00', 12.00, 0.00, 0.00, 0.00, 0.00, 0.00, 0.00, 0.00, NULL, NULL, 0.00, NULL, NULL, NULL, 1, NULL, '广州塔站', '客村站', NULL, NULL, NULL, 0, 0, 0.00, 0.00, NULL, NULL, NULL, NULL, 'R_GZ_202', '海珠滨江线', 0, '0', '0', NULL, NULL, NULL, '2026-05-27 10:58:28', NULL, '2026-05-27 10:58:28', NULL, '1', '0');
INSERT INTO `bus_order` VALUES ('ORD_2025004', 'ORD202605270004', NULL, 'ONLINE', 'COMPLETED', 'PAID', '13900010004', 'P10004', '李俊杰', NULL, NULL, NULL, '粤A00002D', '2026-05-27 10:00:00', 12.00, 0.00, 0.00, 0.00, 0.00, 0.00, 0.00, 0.00, NULL, NULL, 0.00, NULL, NULL, NULL, 3, NULL, '广州塔站', '客村站', NULL, NULL, NULL, 0, 0, 0.00, 0.00, NULL, NULL, NULL, NULL, 'R_GZ_202', '海珠滨江线', 0, '0', '0', NULL, NULL, NULL, '2026-05-27 10:58:28', NULL, '2026-05-27 10:58:28', NULL, '1', '0');
INSERT INTO `bus_order` VALUES ('ORD_2025005', 'ORD202605270005', NULL, 'ONLINE', 'DRIVER_ARRIVING', 'PAID', '13900010005', 'P10005', '王美芳', NULL, NULL, NULL, '粤A00004D', '2026-05-27 11:00:00', 8.00, 0.00, 0.00, 0.00, 0.00, 0.00, 0.00, 0.00, NULL, NULL, 0.00, NULL, NULL, NULL, 1, NULL, '公园前站', '北京路站', NULL, NULL, NULL, 0, 0, 0.00, 0.00, NULL, NULL, NULL, NULL, 'R_GZ_204', '越秀经典线', 0, '0', '0', NULL, NULL, NULL, '2026-05-27 10:58:28', NULL, '2026-05-27 10:58:28', NULL, '1', '0');
INSERT INTO `bus_order` VALUES ('ORD_2025006', 'ORD202605270006', NULL, 'ONLINE', 'PENDING_DISPATCH', 'PAID', '13900010006', 'P10006', NULL, NULL, NULL, NULL, NULL, '2026-05-27 11:30:00', 8.00, 0.00, 0.00, 0.00, 0.00, 0.00, 0.00, 0.00, NULL, NULL, 0.00, NULL, NULL, NULL, 2, NULL, '陈家祠站', '长寿路站', NULL, NULL, NULL, 0, 0, 0.00, 0.00, NULL, NULL, NULL, NULL, 'R_GZ_205', '荔湾风情线', 0, '0', '0', NULL, NULL, NULL, '2026-05-27 10:58:28', NULL, '2026-05-27 10:58:28', NULL, '1', '0');
INSERT INTO `bus_order` VALUES ('ORD_2025007', 'ORD202605270007', NULL, 'ONLINE', 'PENDING_DISPATCH', 'UNPAID', '13900010007', 'P10007', NULL, NULL, NULL, NULL, NULL, '2026-05-27 12:00:00', 0.00, 0.00, 0.00, 0.00, 0.00, 0.00, 0.00, 0.00, NULL, NULL, 0.00, NULL, NULL, NULL, 1, NULL, '大学城北站', '番禺广场站', NULL, NULL, NULL, 0, 0, 0.00, 0.00, NULL, NULL, NULL, NULL, 'R_GZ_203', '大学城专线', 0, '0', '0', NULL, NULL, NULL, '2026-05-27 10:58:28', NULL, '2026-05-27 10:58:28', NULL, '1', '0');
INSERT INTO `bus_order` VALUES ('ORD_2025008', 'ORD202605270008', NULL, 'ONLINE', 'CANCELLED', 'UNPAID', '13900010008', 'P10008', NULL, NULL, NULL, NULL, NULL, '2026-05-27 09:30:00', 0.00, 0.00, 0.00, 0.00, 0.00, 0.00, 0.00, 0.00, NULL, NULL, 0.00, NULL, NULL, NULL, 1, NULL, '花都广场站', '机场南站', NULL, NULL, NULL, 0, 0, 0.00, 0.00, NULL, NULL, NULL, NULL, 'R_GZ_210', '花都机场线', 0, '0', '0', NULL, NULL, NULL, '2026-05-27 10:58:28', NULL, '2026-05-27 10:58:28', NULL, '1', '0');
INSERT INTO `bus_order` VALUES ('ORD_2025009', 'ORD202605270009', NULL, 'ONLINE', 'COMPLETED', 'PAID', '13900010009', 'P10009', '黄志强', NULL, NULL, NULL, '粤A00006D', '2026-05-27 07:30:00', 20.00, 0.00, 0.00, 0.00, 0.00, 0.00, 0.00, 0.00, NULL, NULL, 0.00, NULL, NULL, NULL, 2, NULL, '体育西路站', '广州塔站', NULL, NULL, NULL, 0, 0, 0.00, 0.00, NULL, NULL, NULL, NULL, NULL, NULL, 0, '0', '0', NULL, NULL, NULL, '2026-05-27 10:58:28', NULL, '2026-05-27 10:58:28', NULL, '1', '0');
INSERT INTO `bus_order` VALUES ('ORD_2025010', 'ORD202605270010', NULL, 'ONLINE', 'COMPLETED', 'PAID', '13900010010', 'P10010', '林振华', NULL, NULL, NULL, '粤A00008D', '2026-05-27 14:00:00', 25.00, 0.00, 0.00, 0.00, 0.00, 0.00, 0.00, 0.00, NULL, NULL, 0.00, NULL, NULL, NULL, 4, NULL, '番禺广场站', '大学城北站', NULL, NULL, NULL, 0, 0, 0.00, 0.00, NULL, NULL, NULL, NULL, 'R_GZ_203', '大学城专线', 0, '0', '0', NULL, NULL, NULL, '2026-05-27 10:58:28', NULL, '2026-05-27 10:58:28', NULL, '1', '0');
INSERT INTO `bus_order` VALUES ('ORD_EXP_20260529_219072', 'E20260529368019', 'RIDE|ORD_EXP_20260529_219072|E20260529368019|SEATS=A1', 'express_line', 'paid', 'paid', NULL, '2053666005677953025', '王美芳', '2003', NULL, NULL, '粤A00007D', '2026-05-29 10:22:48', 8.00, 8.00, 0.00, 0.00, 0.00, 0.00, 0.00, 0.00, 'auto_deduct', '2026-05-29 10:22:48', 0.00, NULL, NULL, 'miniprogram', 1, NULL, '2007', '2006', NULL, NULL, NULL, 0, 0, 0.00, 0.00, NULL, 'A052901', '2026-05-29', '11:17', 'A0529', '0529线路', 0, '0', '0', NULL, NULL, NULL, '2026-05-29 10:22:48', '13560004373', '2026-05-29 10:22:48', '13560004373', '1', '0');

-- ----------------------------
-- Table structure for bus_order_column_config
-- ----------------------------
DROP TABLE IF EXISTS `bus_order_column_config`;
CREATE TABLE `bus_order_column_config`  (
  `id` bigint NOT NULL AUTO_INCREMENT COMMENT '主键',
  `username` varchar(64) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci NOT NULL COMMENT '用户名',
  `order_type` varchar(20) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci NOT NULL COMMENT '订单类型',
  `columns_json` text CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci NULL COMMENT '列配置(按顺序csv)',
  `create_time` datetime NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
  `update_time` datetime NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
  `tenant_id` varchar(32) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci NULL DEFAULT NULL COMMENT '租户ID',
  PRIMARY KEY (`id`) USING BTREE,
  UNIQUE INDEX `uk_bocc_user_type`(`username` ASC, `order_type` ASC) USING BTREE,
  INDEX `idx_bocc_tenant`(`tenant_id` ASC) USING BTREE
) ENGINE = InnoDB AUTO_INCREMENT = 1 CHARACTER SET = utf8mb4 COLLATE = utf8mb4_0900_ai_ci COMMENT = '订单列表字段配置' ROW_FORMAT = DYNAMIC;

-- ----------------------------
-- Records of bus_order_column_config
-- ----------------------------

-- ----------------------------
-- Table structure for bus_passenger
-- ----------------------------
DROP TABLE IF EXISTS `bus_passenger`;
CREATE TABLE `bus_passenger`  (
  `id` bigint NOT NULL AUTO_INCREMENT COMMENT '主键',
  `nickname` varchar(100) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci NULL DEFAULT NULL COMMENT '昵称',
  `phone` varchar(20) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci NOT NULL COMMENT '手机号',
  `register_source` varchar(32) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci NOT NULL COMMENT '注册途径',
  `account_status` varchar(32) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci NULL DEFAULT 'new_user' COMMENT '账户状态',
  `gender` varchar(10) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci NULL DEFAULT 'unknown' COMMENT '性别',
  `first_trade_time` datetime NULL DEFAULT NULL COMMENT '首次交易时间',
  `last_trade_time` datetime NULL DEFAULT NULL COMMENT '最近交易时间',
  `trade_days_seven` int NULL DEFAULT 0 COMMENT '近7日使用天数',
  `continuous_inactive_days` int NULL DEFAULT 0 COMMENT '连续未使用天数',
  `status_calc_flag` varchar(20) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci NULL DEFAULT 'normal' COMMENT '状态计算标记',
  `create_time` datetime NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
  `create_by` varchar(64) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci NULL DEFAULT NULL COMMENT '创建人',
  `update_time` datetime NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
  `update_by` varchar(64) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci NULL DEFAULT NULL COMMENT '更新人',
  `tenant_id` varchar(32) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci NULL DEFAULT NULL COMMENT '租户ID',
  `del_flag` varchar(1) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci NULL DEFAULT '0' COMMENT '删除标记',
  PRIMARY KEY (`id`) USING BTREE,
  INDEX `idx_bp_phone`(`phone` ASC) USING BTREE,
  INDEX `idx_bp_status`(`account_status` ASC) USING BTREE,
  INDEX `idx_bp_source`(`register_source` ASC) USING BTREE,
  INDEX `idx_bp_tenant`(`tenant_id` ASC) USING BTREE
) ENGINE = InnoDB AUTO_INCREMENT = 171 CHARACTER SET = utf8mb4 COLLATE = utf8mb4_0900_ai_ci COMMENT = '乘客主表' ROW_FORMAT = DYNAMIC;

-- ----------------------------
-- Records of bus_passenger
-- ----------------------------
INSERT INTO `bus_passenger` VALUES (1, '测试乘客73720', '13975618657', 'wechat_miniapp', 'new_user', 'male', NULL, NULL, 0, 0, 'normal', '2026-04-07 14:25:07', NULL, '2026-04-07 14:25:07', NULL, '1', '0');
INSERT INTO `bus_passenger` VALUES (2, '测试乘客75531', '13958703179', 'alipay_miniapp', 'high_frequency', 'female', NULL, NULL, 1, 1, 'normal', '2026-04-07 14:25:08', NULL, '2026-04-07 14:25:08', NULL, '1', '0');
INSERT INTO `bus_passenger` VALUES (3, '测试乘客75722', '13980039449', 'bus_community', 'general_active', 'unknown', NULL, NULL, 2, 2, 'normal', '2026-04-07 14:25:08', NULL, '2026-04-07 14:25:08', NULL, '1', '0');
INSERT INTO `bus_passenger` VALUES (4, '测试乘客75883', '13901818427', 'wechat_miniapp', 'active', 'male', NULL, NULL, 3, 3, 'normal', '2026-04-07 14:25:08', NULL, '2026-04-07 14:25:08', NULL, '1', '0');
INSERT INTO `bus_passenger` VALUES (5, '测试乘客76104', '13912818178', 'alipay_miniapp', 'dormant', 'female', NULL, NULL, 4, 4, 'normal', '2026-04-07 14:25:08', NULL, '2026-04-07 14:25:08', NULL, '1', '0');
INSERT INTO `bus_passenger` VALUES (6, '测试乘客76515', '13963774853', 'bus_community', 'silent', 'unknown', NULL, NULL, 5, 5, 'normal', '2026-04-07 14:25:08', NULL, '2026-04-07 14:25:08', NULL, '1', '0');
INSERT INTO `bus_passenger` VALUES (7, '测试乘客76656', '13979177119', 'wechat_miniapp', 'new_user', 'male', NULL, NULL, 6, 6, 'normal', '2026-04-07 14:25:08', NULL, '2026-04-07 14:25:08', NULL, '1', '0');
INSERT INTO `bus_passenger` VALUES (8, '测试乘客76847', '13953390624', 'alipay_miniapp', 'high_frequency', 'female', NULL, NULL, 0, 7, 'normal', '2026-04-07 14:25:08', NULL, '2026-04-07 14:25:08', NULL, '1', '0');
INSERT INTO `bus_passenger` VALUES (9, '测试乘客77038', '13922467976', 'bus_community', 'general_active', 'unknown', NULL, NULL, 1, 8, 'normal', '2026-04-07 14:25:08', NULL, '2026-04-07 14:25:08', NULL, '1', '0');
INSERT INTO `bus_passenger` VALUES (10, '测试乘客77199', '13997458233', 'wechat_miniapp', 'active', 'male', NULL, NULL, 2, 9, 'normal', '2026-04-07 14:25:08', NULL, '2026-04-07 14:25:08', NULL, '1', '0');
INSERT INTO `bus_passenger` VALUES (11, '测试乘客774310', '13909161712', 'alipay_miniapp', 'dormant', 'female', NULL, NULL, 3, 10, 'normal', '2026-04-07 14:25:08', NULL, '2026-04-07 14:25:08', NULL, '1', '0');
INSERT INTO `bus_passenger` VALUES (12, '测试乘客775711', '13992201103', 'bus_community', 'silent', 'unknown', NULL, NULL, 4, 11, 'normal', '2026-04-07 14:25:08', NULL, '2026-04-07 14:25:08', NULL, '1', '0');
INSERT INTO `bus_passenger` VALUES (13, '测试乘客777312', '13955770983', 'wechat_miniapp', 'new_user', 'male', NULL, NULL, 5, 12, 'normal', '2026-04-07 14:25:08', NULL, '2026-04-07 14:25:08', NULL, '1', '0');
INSERT INTO `bus_passenger` VALUES (14, '测试乘客778813', '13948306512', 'alipay_miniapp', 'high_frequency', 'female', NULL, NULL, 6, 13, 'normal', '2026-04-07 14:25:08', NULL, '2026-04-07 14:25:08', NULL, '1', '0');
INSERT INTO `bus_passenger` VALUES (15, '测试乘客780514', '13942782482', 'bus_community', 'general_active', 'unknown', NULL, NULL, 0, 14, 'normal', '2026-04-07 14:25:08', NULL, '2026-04-07 14:25:08', NULL, '1', '0');
INSERT INTO `bus_passenger` VALUES (16, '测试乘客782615', '13988698502', 'wechat_miniapp', 'active', 'male', NULL, NULL, 1, 15, 'normal', '2026-04-07 14:25:08', NULL, '2026-04-07 14:25:08', NULL, '1', '0');
INSERT INTO `bus_passenger` VALUES (17, '测试乘客784316', '13985581350', 'alipay_miniapp', 'dormant', 'female', NULL, NULL, 2, 16, 'normal', '2026-04-07 14:25:08', NULL, '2026-04-07 14:25:08', NULL, '1', '0');
INSERT INTO `bus_passenger` VALUES (18, '测试乘客785617', '13932116785', 'bus_community', 'silent', 'unknown', NULL, NULL, 3, 17, 'normal', '2026-04-07 14:25:08', NULL, '2026-04-07 14:25:08', NULL, '1', '0');
INSERT INTO `bus_passenger` VALUES (19, '测试乘客787318', '13985405426', 'wechat_miniapp', 'new_user', 'male', NULL, NULL, 4, 18, 'normal', '2026-04-07 14:25:08', NULL, '2026-04-07 14:25:08', NULL, '1', '0');
INSERT INTO `bus_passenger` VALUES (20, '测试乘客788719', '13924851300', 'alipay_miniapp', 'high_frequency', 'female', NULL, NULL, 5, 19, 'normal', '2026-04-07 14:25:08', NULL, '2026-04-07 14:25:08', NULL, '1', '0');
INSERT INTO `bus_passenger` VALUES (21, '测试乘客69440', '13929574844', 'wechat_miniapp', 'new_user', 'male', NULL, NULL, 0, 0, 'normal', '2026-04-30 17:25:07', NULL, '2026-04-30 17:25:07', NULL, '1', '0');
INSERT INTO `bus_passenger` VALUES (22, '测试乘客70091', '13958511339', 'alipay_miniapp', 'high_frequency', 'female', NULL, NULL, 1, 1, 'normal', '2026-04-30 17:25:07', NULL, '2026-04-30 17:25:07', NULL, '1', '0');
INSERT INTO `bus_passenger` VALUES (23, '测试乘客70222', '13980877636', 'bus_community', 'general_active', 'unknown', NULL, NULL, 2, 2, 'normal', '2026-04-30 17:25:07', NULL, '2026-04-30 17:25:07', NULL, '1', '0');
INSERT INTO `bus_passenger` VALUES (24, '测试乘客70323', '13928766762', 'wechat_miniapp', 'active', 'male', NULL, NULL, 3, 3, 'normal', '2026-04-30 17:25:07', NULL, '2026-04-30 17:25:07', NULL, '1', '0');
INSERT INTO `bus_passenger` VALUES (25, '测试乘客70514', '13905056099', 'alipay_miniapp', 'dormant', 'female', NULL, NULL, 4, 4, 'normal', '2026-04-30 17:25:07', NULL, '2026-04-30 17:25:07', NULL, '1', '0');
INSERT INTO `bus_passenger` VALUES (26, '测试乘客70615', '13924081262', 'bus_community', 'silent', 'unknown', NULL, NULL, 5, 5, 'normal', '2026-04-30 17:25:07', NULL, '2026-04-30 17:25:07', NULL, '1', '0');
INSERT INTO `bus_passenger` VALUES (27, '测试乘客70696', '13997450600', 'wechat_miniapp', 'new_user', 'male', NULL, NULL, 6, 6, 'normal', '2026-04-30 17:25:07', NULL, '2026-04-30 17:25:07', NULL, '1', '0');
INSERT INTO `bus_passenger` VALUES (28, '测试乘客70827', '13910587038', 'alipay_miniapp', 'high_frequency', 'female', NULL, NULL, 0, 7, 'normal', '2026-04-30 17:25:07', NULL, '2026-04-30 17:25:07', NULL, '1', '0');
INSERT INTO `bus_passenger` VALUES (29, '测试乘客70928', '13990116745', 'bus_community', 'general_active', 'unknown', NULL, NULL, 1, 8, 'normal', '2026-04-30 17:25:07', NULL, '2026-04-30 17:25:07', NULL, '1', '0');
INSERT INTO `bus_passenger` VALUES (30, '测试乘客71069', '13912031175', 'wechat_miniapp', 'active', 'male', NULL, NULL, 2, 9, 'normal', '2026-04-30 17:25:07', NULL, '2026-04-30 17:25:07', NULL, '1', '0');
INSERT INTO `bus_passenger` VALUES (31, '测试乘客711810', '13963773310', 'alipay_miniapp', 'dormant', 'female', NULL, NULL, 3, 10, 'normal', '2026-04-30 17:25:07', NULL, '2026-04-30 17:25:07', NULL, '1', '0');
INSERT INTO `bus_passenger` VALUES (32, '测试乘客712911', '13931710490', 'bus_community', 'silent', 'unknown', NULL, NULL, 4, 11, 'normal', '2026-04-30 17:25:07', NULL, '2026-04-30 17:25:07', NULL, '1', '0');
INSERT INTO `bus_passenger` VALUES (33, '测试乘客713912', '13986601157', 'wechat_miniapp', 'new_user', 'male', NULL, NULL, 5, 12, 'normal', '2026-04-30 17:25:07', NULL, '2026-04-30 17:25:07', NULL, '1', '0');
INSERT INTO `bus_passenger` VALUES (34, '测试乘客716513', '13955590755', 'alipay_miniapp', 'high_frequency', 'female', NULL, NULL, 6, 13, 'normal', '2026-04-30 17:25:07', NULL, '2026-04-30 17:25:07', NULL, '1', '0');
INSERT INTO `bus_passenger` VALUES (35, '测试乘客718214', '13909247711', 'bus_community', 'general_active', 'unknown', NULL, NULL, 0, 14, 'normal', '2026-04-30 17:25:07', NULL, '2026-04-30 17:25:07', NULL, '1', '0');
INSERT INTO `bus_passenger` VALUES (36, '测试乘客719215', '13965546057', 'wechat_miniapp', 'active', 'male', NULL, NULL, 1, 15, 'normal', '2026-04-30 17:25:07', NULL, '2026-04-30 17:25:07', NULL, '1', '0');
INSERT INTO `bus_passenger` VALUES (37, '测试乘客720916', '13969986944', 'alipay_miniapp', 'dormant', 'female', NULL, NULL, 2, 16, 'normal', '2026-04-30 17:25:07', NULL, '2026-04-30 17:25:07', NULL, '1', '0');
INSERT INTO `bus_passenger` VALUES (38, '测试乘客722417', '13916318996', 'bus_community', 'silent', 'unknown', NULL, NULL, 3, 17, 'normal', '2026-04-30 17:25:07', NULL, '2026-04-30 17:25:07', NULL, '1', '0');
INSERT INTO `bus_passenger` VALUES (39, '测试乘客723618', '13993481325', 'wechat_miniapp', 'new_user', 'male', NULL, NULL, 4, 18, 'normal', '2026-04-30 17:25:07', NULL, '2026-04-30 17:25:07', NULL, '1', '0');
INSERT INTO `bus_passenger` VALUES (40, '测试乘客724519', '13990489030', 'alipay_miniapp', 'high_frequency', 'female', NULL, NULL, 5, 19, 'normal', '2026-04-30 17:25:07', NULL, '2026-04-30 17:25:07', NULL, '1', '0');
INSERT INTO `bus_passenger` VALUES (41, '测试乘客227700', '13940235889', 'wechat_miniapp', 'new_user', 'male', NULL, NULL, 0, 0, 'normal', '2026-05-06 16:17:03', NULL, '2026-05-06 16:17:03', NULL, '1', '0');
INSERT INTO `bus_passenger` VALUES (42, '测试乘客227921', '13984986692', 'alipay_miniapp', 'high_frequency', 'female', NULL, NULL, 1, 1, 'normal', '2026-05-06 16:17:03', NULL, '2026-05-06 16:17:03', NULL, '1', '0');
INSERT INTO `bus_passenger` VALUES (43, '测试乘客228062', '13907213522', 'bus_community', 'general_active', 'unknown', NULL, NULL, 2, 2, 'normal', '2026-05-06 16:17:03', NULL, '2026-05-06 16:17:03', NULL, '1', '0');
INSERT INTO `bus_passenger` VALUES (44, '测试乘客228183', '13912227925', 'wechat_miniapp', 'active', 'male', NULL, NULL, 3, 3, 'normal', '2026-05-06 16:17:03', NULL, '2026-05-06 16:17:03', NULL, '1', '0');
INSERT INTO `bus_passenger` VALUES (45, '测试乘客228434', '13918424490', 'alipay_miniapp', 'dormant', 'female', NULL, NULL, 4, 4, 'normal', '2026-05-06 16:17:03', NULL, '2026-05-06 16:17:03', NULL, '1', '0');
INSERT INTO `bus_passenger` VALUES (46, '测试乘客228545', '13903657501', 'bus_community', 'silent', 'unknown', NULL, NULL, 5, 5, 'normal', '2026-05-06 16:17:03', NULL, '2026-05-06 16:17:03', NULL, '1', '0');
INSERT INTO `bus_passenger` VALUES (47, '测试乘客228686', '13968226088', 'wechat_miniapp', 'new_user', 'male', NULL, NULL, 6, 6, 'normal', '2026-05-06 16:17:03', NULL, '2026-05-06 16:17:03', NULL, '1', '0');
INSERT INTO `bus_passenger` VALUES (48, '测试乘客228807', '13966341808', 'alipay_miniapp', 'high_frequency', 'female', NULL, NULL, 0, 7, 'normal', '2026-05-06 16:17:03', NULL, '2026-05-06 16:17:03', NULL, '1', '0');
INSERT INTO `bus_passenger` VALUES (49, '测试乘客228908', '13929919403', 'bus_community', 'general_active', 'unknown', NULL, NULL, 1, 8, 'normal', '2026-05-06 16:17:03', NULL, '2026-05-06 16:17:03', NULL, '1', '0');
INSERT INTO `bus_passenger` VALUES (50, '测试乘客229009', '13981301175', 'wechat_miniapp', 'active', 'male', NULL, NULL, 2, 9, 'normal', '2026-05-06 16:17:03', NULL, '2026-05-06 16:17:03', NULL, '1', '0');
INSERT INTO `bus_passenger` VALUES (51, '测试乘客2291110', '13967138645', 'alipay_miniapp', 'dormant', 'female', NULL, NULL, 3, 10, 'normal', '2026-05-06 16:17:03', NULL, '2026-05-06 16:17:03', NULL, '1', '0');
INSERT INTO `bus_passenger` VALUES (52, '测试乘客2292111', '13928656217', 'bus_community', 'silent', 'unknown', NULL, NULL, 4, 11, 'normal', '2026-05-06 16:17:03', NULL, '2026-05-06 16:17:03', NULL, '1', '0');
INSERT INTO `bus_passenger` VALUES (53, '测试乘客2293212', '13932188410', 'wechat_miniapp', 'new_user', 'male', NULL, NULL, 5, 12, 'normal', '2026-05-06 16:17:03', NULL, '2026-05-06 16:17:03', NULL, '1', '0');
INSERT INTO `bus_passenger` VALUES (54, '测试乘客2294313', '13994675486', 'alipay_miniapp', 'high_frequency', 'female', NULL, NULL, 6, 13, 'normal', '2026-05-06 16:17:03', NULL, '2026-05-06 16:17:03', NULL, '1', '0');
INSERT INTO `bus_passenger` VALUES (55, '测试乘客2295514', '13966087462', 'bus_community', 'general_active', 'unknown', NULL, NULL, 0, 14, 'normal', '2026-05-06 16:17:03', NULL, '2026-05-06 16:17:03', NULL, '1', '0');
INSERT INTO `bus_passenger` VALUES (56, '测试乘客2297015', '13983197962', 'wechat_miniapp', 'active', 'male', NULL, NULL, 1, 15, 'normal', '2026-05-06 16:17:03', NULL, '2026-05-06 16:17:03', NULL, '1', '0');
INSERT INTO `bus_passenger` VALUES (57, '测试乘客2298316', '13954986877', 'alipay_miniapp', 'dormant', 'female', NULL, NULL, 2, 16, 'normal', '2026-05-06 16:17:03', NULL, '2026-05-06 16:17:03', NULL, '1', '0');
INSERT INTO `bus_passenger` VALUES (58, '测试乘客2299417', '13933066859', 'bus_community', 'silent', 'unknown', NULL, NULL, 3, 17, 'normal', '2026-05-06 16:17:03', NULL, '2026-05-06 16:17:03', NULL, '1', '0');
INSERT INTO `bus_passenger` VALUES (59, '测试乘客2300418', '13975234260', 'wechat_miniapp', 'new_user', 'male', NULL, NULL, 4, 18, 'normal', '2026-05-06 16:17:03', NULL, '2026-05-06 16:17:03', NULL, '1', '0');
INSERT INTO `bus_passenger` VALUES (60, '测试乘客2301519', '13900438914', 'alipay_miniapp', 'high_frequency', 'female', NULL, NULL, 5, 19, 'normal', '2026-05-06 16:17:03', NULL, '2026-05-06 16:17:03', NULL, '1', '0');
INSERT INTO `bus_passenger` VALUES (61, '测试乘客278980', '13949753576', 'wechat_miniapp', 'new_user', 'male', NULL, NULL, 0, 0, 'normal', '2026-05-18 10:20:28', NULL, '2026-05-18 10:20:28', NULL, '1', '0');
INSERT INTO `bus_passenger` VALUES (62, '测试乘客279131', '13946259715', 'alipay_miniapp', 'high_frequency', 'female', NULL, NULL, 1, 1, 'normal', '2026-05-18 10:20:28', NULL, '2026-05-18 10:20:28', NULL, '1', '0');
INSERT INTO `bus_passenger` VALUES (63, '测试乘客279252', '13984004647', 'bus_community', 'general_active', 'unknown', NULL, NULL, 2, 2, 'normal', '2026-05-18 10:20:28', NULL, '2026-05-18 10:20:28', NULL, '1', '0');
INSERT INTO `bus_passenger` VALUES (64, '测试乘客279363', '13917707752', 'wechat_miniapp', 'active', 'male', NULL, NULL, 3, 3, 'normal', '2026-05-18 10:20:28', NULL, '2026-05-18 10:20:28', NULL, '1', '0');
INSERT INTO `bus_passenger` VALUES (65, '测试乘客279464', '13971041365', 'alipay_miniapp', 'dormant', 'female', NULL, NULL, 4, 4, 'normal', '2026-05-18 10:20:28', NULL, '2026-05-18 10:20:28', NULL, '1', '0');
INSERT INTO `bus_passenger` VALUES (66, '测试乘客279555', '13917036828', 'bus_community', 'silent', 'unknown', NULL, NULL, 5, 5, 'normal', '2026-05-18 10:20:28', NULL, '2026-05-18 10:20:28', NULL, '1', '0');
INSERT INTO `bus_passenger` VALUES (67, '测试乘客279646', '13935119222', 'wechat_miniapp', 'new_user', 'male', NULL, NULL, 6, 6, 'normal', '2026-05-18 10:20:28', NULL, '2026-05-18 10:20:28', NULL, '1', '0');
INSERT INTO `bus_passenger` VALUES (68, '测试乘客279737', '13913637009', 'alipay_miniapp', 'high_frequency', 'female', NULL, NULL, 0, 7, 'normal', '2026-05-18 10:20:28', NULL, '2026-05-18 10:20:28', NULL, '1', '0');
INSERT INTO `bus_passenger` VALUES (69, '测试乘客279848', '13937485508', 'bus_community', 'general_active', 'unknown', NULL, NULL, 1, 8, 'normal', '2026-05-18 10:20:28', NULL, '2026-05-18 10:20:28', NULL, '1', '0');
INSERT INTO `bus_passenger` VALUES (70, '测试乘客279939', '13931746030', 'wechat_miniapp', 'active', 'male', NULL, NULL, 2, 9, 'normal', '2026-05-18 10:20:28', NULL, '2026-05-18 10:20:28', NULL, '1', '0');
INSERT INTO `bus_passenger` VALUES (71, '测试乘客2800310', '13945090778', 'alipay_miniapp', 'dormant', 'female', NULL, NULL, 3, 10, 'normal', '2026-05-18 10:20:28', NULL, '2026-05-18 10:20:28', NULL, '1', '0');
INSERT INTO `bus_passenger` VALUES (72, '测试乘客2801611', '13921048884', 'bus_community', 'silent', 'unknown', NULL, NULL, 4, 11, 'normal', '2026-05-18 10:20:28', NULL, '2026-05-18 10:20:28', NULL, '1', '0');
INSERT INTO `bus_passenger` VALUES (73, '测试乘客2802412', '13944976997', 'wechat_miniapp', 'new_user', 'male', NULL, NULL, 5, 12, 'normal', '2026-05-18 10:20:28', NULL, '2026-05-18 10:20:28', NULL, '1', '0');
INSERT INTO `bus_passenger` VALUES (74, '测试乘客2803313', '13912349478', 'alipay_miniapp', 'high_frequency', 'female', NULL, NULL, 6, 13, 'normal', '2026-05-18 10:20:28', NULL, '2026-05-18 10:20:28', NULL, '1', '0');
INSERT INTO `bus_passenger` VALUES (75, '测试乘客2804214', '13916839441', 'bus_community', 'general_active', 'unknown', NULL, NULL, 0, 14, 'normal', '2026-05-18 10:20:28', NULL, '2026-05-18 10:20:28', NULL, '1', '0');
INSERT INTO `bus_passenger` VALUES (76, '测试乘客2805315', '13970419414', 'wechat_miniapp', 'active', 'male', NULL, NULL, 1, 15, 'normal', '2026-05-18 10:20:28', NULL, '2026-05-18 10:20:28', NULL, '1', '0');
INSERT INTO `bus_passenger` VALUES (77, '测试乘客2806216', '13997588870', 'alipay_miniapp', 'dormant', 'female', NULL, NULL, 2, 16, 'normal', '2026-05-18 10:20:28', NULL, '2026-05-18 10:20:28', NULL, '1', '0');
INSERT INTO `bus_passenger` VALUES (78, '测试乘客2807117', '13966738063', 'bus_community', 'silent', 'unknown', NULL, NULL, 3, 17, 'normal', '2026-05-18 10:20:28', NULL, '2026-05-18 10:20:28', NULL, '1', '0');
INSERT INTO `bus_passenger` VALUES (79, '测试乘客2808118', '13961697487', 'wechat_miniapp', 'new_user', 'male', NULL, NULL, 4, 18, 'normal', '2026-05-18 10:20:28', NULL, '2026-05-18 10:20:28', NULL, '1', '0');
INSERT INTO `bus_passenger` VALUES (80, '测试乘客2809219', '13956198362', 'alipay_miniapp', 'high_frequency', 'female', NULL, NULL, 5, 19, 'normal', '2026-05-18 10:20:28', NULL, '2026-05-18 10:20:28', NULL, '1', '0');
INSERT INTO `bus_passenger` VALUES (81, '测试乘客314020', '13903130069', 'wechat_miniapp', 'new_user', 'male', NULL, NULL, 0, 0, 'normal', '2026-05-18 10:20:31', NULL, '2026-05-18 10:20:31', NULL, '1', '0');
INSERT INTO `bus_passenger` VALUES (82, '测试乘客314141', '13900187214', 'alipay_miniapp', 'high_frequency', 'female', NULL, NULL, 1, 1, 'normal', '2026-05-18 10:20:31', NULL, '2026-05-18 10:20:31', NULL, '1', '0');
INSERT INTO `bus_passenger` VALUES (83, '测试乘客314242', '13991399996', 'bus_community', 'general_active', 'unknown', NULL, NULL, 2, 2, 'normal', '2026-05-18 10:20:31', NULL, '2026-05-18 10:20:31', NULL, '1', '0');
INSERT INTO `bus_passenger` VALUES (84, '测试乘客314343', '13999195037', 'wechat_miniapp', 'active', 'male', NULL, NULL, 3, 3, 'normal', '2026-05-18 10:20:31', NULL, '2026-05-18 10:20:31', NULL, '1', '0');
INSERT INTO `bus_passenger` VALUES (85, '测试乘客314464', '13978361507', 'alipay_miniapp', 'dormant', 'female', NULL, NULL, 4, 4, 'normal', '2026-05-18 10:20:31', NULL, '2026-05-18 10:20:31', NULL, '1', '0');
INSERT INTO `bus_passenger` VALUES (86, '测试乘客314565', '13912968201', 'bus_community', 'silent', 'unknown', NULL, NULL, 5, 5, 'normal', '2026-05-18 10:20:31', NULL, '2026-05-18 10:20:31', NULL, '1', '0');
INSERT INTO `bus_passenger` VALUES (87, '测试乘客314666', '13962641794', 'wechat_miniapp', 'new_user', 'male', NULL, NULL, 6, 6, 'normal', '2026-05-18 10:20:31', NULL, '2026-05-18 10:20:31', NULL, '1', '0');
INSERT INTO `bus_passenger` VALUES (88, '测试乘客314767', '13900579938', 'alipay_miniapp', 'high_frequency', 'female', NULL, NULL, 0, 7, 'normal', '2026-05-18 10:20:31', NULL, '2026-05-18 10:20:31', NULL, '1', '0');
INSERT INTO `bus_passenger` VALUES (89, '测试乘客314858', '13981518115', 'bus_community', 'general_active', 'unknown', NULL, NULL, 1, 8, 'normal', '2026-05-18 10:20:31', NULL, '2026-05-18 10:20:31', NULL, '1', '0');
INSERT INTO `bus_passenger` VALUES (90, '测试乘客314949', '13901985789', 'wechat_miniapp', 'active', 'male', NULL, NULL, 2, 9, 'normal', '2026-05-18 10:20:31', NULL, '2026-05-18 10:20:31', NULL, '1', '0');
INSERT INTO `bus_passenger` VALUES (91, '测试乘客3150310', '13918483320', 'alipay_miniapp', 'dormant', 'female', NULL, NULL, 3, 10, 'normal', '2026-05-18 10:20:32', NULL, '2026-05-18 10:20:32', NULL, '1', '0');
INSERT INTO `bus_passenger` VALUES (92, '测试乘客3151211', '13901304519', 'bus_community', 'silent', 'unknown', NULL, NULL, 4, 11, 'normal', '2026-05-18 10:20:32', NULL, '2026-05-18 10:20:32', NULL, '1', '0');
INSERT INTO `bus_passenger` VALUES (93, '测试乘客3152412', '13977531418', 'wechat_miniapp', 'new_user', 'male', NULL, NULL, 5, 12, 'normal', '2026-05-18 10:20:32', NULL, '2026-05-18 10:20:32', NULL, '1', '0');
INSERT INTO `bus_passenger` VALUES (94, '测试乘客3153313', '13936341625', 'alipay_miniapp', 'high_frequency', 'female', NULL, NULL, 6, 13, 'normal', '2026-05-18 10:20:32', NULL, '2026-05-18 10:20:32', NULL, '1', '0');
INSERT INTO `bus_passenger` VALUES (95, '测试乘客3154214', '13948214171', 'bus_community', 'general_active', 'unknown', NULL, NULL, 0, 14, 'normal', '2026-05-18 10:20:32', NULL, '2026-05-18 10:20:32', NULL, '1', '0');
INSERT INTO `bus_passenger` VALUES (96, '测试乘客3155215', '13955153480', 'wechat_miniapp', 'active', 'male', NULL, NULL, 1, 15, 'normal', '2026-05-18 10:20:32', NULL, '2026-05-18 10:20:32', NULL, '1', '0');
INSERT INTO `bus_passenger` VALUES (97, '测试乘客3156116', '13949626237', 'alipay_miniapp', 'dormant', 'female', NULL, NULL, 2, 16, 'normal', '2026-05-18 10:20:32', NULL, '2026-05-18 10:20:32', NULL, '1', '0');
INSERT INTO `bus_passenger` VALUES (98, '测试乘客3157017', '13906091784', 'bus_community', 'silent', 'unknown', NULL, NULL, 3, 17, 'normal', '2026-05-18 10:20:32', NULL, '2026-05-18 10:20:32', NULL, '1', '0');
INSERT INTO `bus_passenger` VALUES (99, '测试乘客3158018', '13944164551', 'wechat_miniapp', 'new_user', 'male', NULL, NULL, 4, 18, 'normal', '2026-05-18 10:20:32', NULL, '2026-05-18 10:20:32', NULL, '1', '0');
INSERT INTO `bus_passenger` VALUES (100, '测试乘客3158919', '13982998904', 'alipay_miniapp', 'high_frequency', 'female', NULL, NULL, 5, 19, 'normal', '2026-05-18 10:20:32', NULL, '2026-05-18 10:20:32', NULL, '1', '0');
INSERT INTO `bus_passenger` VALUES (101, '测试乘客332460', '13999464556', 'wechat_miniapp', 'new_user', 'male', NULL, NULL, 0, 0, 'normal', '2026-05-18 10:20:33', NULL, '2026-05-18 10:20:33', NULL, '1', '0');
INSERT INTO `bus_passenger` VALUES (102, '测试乘客332611', '13923786328', 'alipay_miniapp', 'high_frequency', 'female', NULL, NULL, 1, 1, 'normal', '2026-05-18 10:20:33', NULL, '2026-05-18 10:20:33', NULL, '1', '0');
INSERT INTO `bus_passenger` VALUES (103, '测试乘客332712', '13999168672', 'bus_community', 'general_active', 'unknown', NULL, NULL, 2, 2, 'normal', '2026-05-18 10:20:33', NULL, '2026-05-18 10:20:33', NULL, '1', '0');
INSERT INTO `bus_passenger` VALUES (104, '测试乘客332803', '13936067046', 'wechat_miniapp', 'active', 'male', NULL, NULL, 3, 3, 'normal', '2026-05-18 10:20:33', NULL, '2026-05-18 10:20:33', NULL, '1', '0');
INSERT INTO `bus_passenger` VALUES (105, '测试乘客332894', '13957913720', 'alipay_miniapp', 'dormant', 'female', NULL, NULL, 4, 4, 'normal', '2026-05-18 10:20:33', NULL, '2026-05-18 10:20:33', NULL, '1', '0');
INSERT INTO `bus_passenger` VALUES (106, '测试乘客333015', '13905466514', 'bus_community', 'silent', 'unknown', NULL, NULL, 5, 5, 'normal', '2026-05-18 10:20:33', NULL, '2026-05-18 10:20:33', NULL, '1', '0');
INSERT INTO `bus_passenger` VALUES (107, '测试乘客333106', '13952007286', 'wechat_miniapp', 'new_user', 'male', NULL, NULL, 6, 6, 'normal', '2026-05-18 10:20:33', NULL, '2026-05-18 10:20:33', NULL, '1', '0');
INSERT INTO `bus_passenger` VALUES (108, '测试乘客333187', '13940729423', 'alipay_miniapp', 'high_frequency', 'female', NULL, NULL, 0, 7, 'normal', '2026-05-18 10:20:33', NULL, '2026-05-18 10:20:33', NULL, '1', '0');
INSERT INTO `bus_passenger` VALUES (109, '测试乘客333278', '13942010656', 'bus_community', 'general_active', 'unknown', NULL, NULL, 1, 8, 'normal', '2026-05-18 10:20:33', NULL, '2026-05-18 10:20:33', NULL, '1', '0');
INSERT INTO `bus_passenger` VALUES (110, '测试乘客333359', '13911540875', 'wechat_miniapp', 'active', 'male', NULL, NULL, 2, 9, 'normal', '2026-05-18 10:20:33', NULL, '2026-05-18 10:20:33', NULL, '1', '0');
INSERT INTO `bus_passenger` VALUES (111, '测试乘客3334410', '13946729997', 'alipay_miniapp', 'dormant', 'female', NULL, NULL, 3, 10, 'normal', '2026-05-18 10:20:33', NULL, '2026-05-18 10:20:33', NULL, '1', '0');
INSERT INTO `bus_passenger` VALUES (112, '测试乘客3335211', '13908049435', 'bus_community', 'silent', 'unknown', NULL, NULL, 4, 11, 'normal', '2026-05-18 10:20:33', NULL, '2026-05-18 10:20:33', NULL, '1', '0');
INSERT INTO `bus_passenger` VALUES (113, '测试乘客3336112', '13907690083', 'wechat_miniapp', 'new_user', 'male', NULL, NULL, 5, 12, 'normal', '2026-05-18 10:20:33', NULL, '2026-05-18 10:20:33', NULL, '1', '0');
INSERT INTO `bus_passenger` VALUES (114, '测试乘客3337013', '13942265750', 'alipay_miniapp', 'high_frequency', 'female', NULL, NULL, 6, 13, 'normal', '2026-05-18 10:20:33', NULL, '2026-05-18 10:20:33', NULL, '1', '0');
INSERT INTO `bus_passenger` VALUES (115, '测试乘客3338014', '13958498490', 'bus_community', 'general_active', 'unknown', NULL, NULL, 0, 14, 'normal', '2026-05-18 10:20:33', NULL, '2026-05-18 10:20:33', NULL, '1', '0');
INSERT INTO `bus_passenger` VALUES (116, '测试乘客3339015', '13903222205', 'wechat_miniapp', 'active', 'male', NULL, NULL, 1, 15, 'normal', '2026-05-18 10:20:33', NULL, '2026-05-18 10:20:33', NULL, '1', '0');
INSERT INTO `bus_passenger` VALUES (117, '测试乘客3340016', '13956939655', 'alipay_miniapp', 'dormant', 'female', NULL, NULL, 2, 16, 'normal', '2026-05-18 10:20:33', NULL, '2026-05-18 10:20:33', NULL, '1', '0');
INSERT INTO `bus_passenger` VALUES (118, '测试乘客3341117', '13978361931', 'bus_community', 'silent', 'unknown', NULL, NULL, 3, 17, 'normal', '2026-05-18 10:20:33', NULL, '2026-05-18 10:20:33', NULL, '1', '0');
INSERT INTO `bus_passenger` VALUES (119, '测试乘客3342318', '13927588487', 'wechat_miniapp', 'new_user', 'male', NULL, NULL, 4, 18, 'normal', '2026-05-18 10:20:33', NULL, '2026-05-18 10:20:33', NULL, '1', '0');
INSERT INTO `bus_passenger` VALUES (120, '测试乘客3345319', '13930027047', 'alipay_miniapp', 'high_frequency', 'female', NULL, NULL, 5, 19, 'normal', '2026-05-18 10:20:33', NULL, '2026-05-18 10:20:33', NULL, '1', '0');
INSERT INTO `bus_passenger` VALUES (121, '天河小陈', '13900010001', 'wechat_miniapp', 'active', 'male', '2026-05-20 08:30:00', '2026-05-27 08:30:00', 5, 0, 'normal', '2026-05-27 10:59:46', NULL, '2026-05-27 10:59:46', NULL, '1', '0');
INSERT INTO `bus_passenger` VALUES (122, '海珠阿May', '13900010002', 'wechat_miniapp', 'high_frequency', 'female', '2026-05-15 09:00:00', '2026-05-27 09:00:00', 7, 0, 'normal', '2026-05-27 10:59:46', NULL, '2026-05-27 10:59:46', NULL, '1', '0');
INSERT INTO `bus_passenger` VALUES (123, '番禺老王', '13900010003', 'alipay_miniapp', 'active', 'male', '2026-05-18 08:45:00', '2026-05-27 08:45:00', 4, 0, 'normal', '2026-05-27 10:59:46', NULL, '2026-05-27 10:59:46', NULL, '1', '0');
INSERT INTO `bus_passenger` VALUES (124, '越秀学生', '13900010004', 'wechat_miniapp', 'active', 'female', '2026-05-10 10:00:00', '2026-05-27 10:00:00', 3, 0, 'normal', '2026-05-27 10:59:46', NULL, '2026-05-27 10:59:46', NULL, '1', '0');
INSERT INTO `bus_passenger` VALUES (125, '荔湾街坊', '13900010005', 'alipay_miniapp', 'general_active', 'male', '2026-05-05 11:00:00', '2026-05-27 11:00:00', 2, 0, 'normal', '2026-05-27 10:59:46', NULL, '2026-05-27 10:59:46', NULL, '1', '0');
INSERT INTO `bus_passenger` VALUES (126, '白云游客', '13900010006', 'wechat_miniapp', 'new_user', 'unknown', NULL, NULL, 0, 0, 'normal', '2026-05-27 10:59:46', NULL, '2026-05-27 10:59:46', NULL, '1', '0');
INSERT INTO `bus_passenger` VALUES (127, '黄埔打工人', '13900010007', 'bus_community', 'dormant', 'male', '2026-05-01 07:30:00', '2026-05-20 07:30:00', 0, 7, 'normal', '2026-05-27 10:59:46', NULL, '2026-05-27 10:59:46', NULL, '1', '0');
INSERT INTO `bus_passenger` VALUES (128, '南沙业主', '13900010008', 'wechat_miniapp', 'silent', 'female', '2026-04-01 14:00:00', '2026-05-15 14:00:00', 0, 12, 'normal', '2026-05-27 10:59:46', NULL, '2026-05-27 10:59:46', NULL, '1', '0');
INSERT INTO `bus_passenger` VALUES (129, '花都小李', '13900010009', 'alipay_miniapp', 'active', 'female', '2026-05-19 07:20:00', '2026-05-27 07:20:00', 6, 0, 'normal', '2026-05-27 10:59:46', NULL, '2026-05-27 10:59:46', NULL, '1', '0');
INSERT INTO `bus_passenger` VALUES (130, '增城小张', '13900010010', 'wechat_miniapp', 'active', 'male', '2026-05-21 13:50:00', '2026-05-27 13:50:00', 4, 0, 'normal', '2026-05-27 10:59:46', NULL, '2026-05-27 10:59:46', NULL, '1', '0');
INSERT INTO `bus_passenger` VALUES (131, '测试乘客989550', '13949533119', 'wechat_miniapp', 'new_user', 'male', NULL, NULL, 0, 0, 'normal', '2026-05-28 11:08:19', NULL, '2026-05-28 11:08:19', NULL, '1', '0');
INSERT INTO `bus_passenger` VALUES (132, '测试乘客989701', '13997383292', 'alipay_miniapp', 'high_frequency', 'female', NULL, NULL, 1, 1, 'normal', '2026-05-28 11:08:19', NULL, '2026-05-28 11:08:19', NULL, '1', '0');
INSERT INTO `bus_passenger` VALUES (133, '测试乘客989802', '13909084786', 'bus_community', 'general_active', 'unknown', NULL, NULL, 2, 2, 'normal', '2026-05-28 11:08:19', NULL, '2026-05-28 11:08:19', NULL, '1', '0');
INSERT INTO `bus_passenger` VALUES (134, '测试乘客989913', '13947503508', 'wechat_miniapp', 'active', 'male', NULL, NULL, 3, 3, 'normal', '2026-05-28 11:08:19', NULL, '2026-05-28 11:08:19', NULL, '1', '0');
INSERT INTO `bus_passenger` VALUES (135, '测试乘客989994', '13955528008', 'alipay_miniapp', 'dormant', 'female', NULL, NULL, 4, 4, 'normal', '2026-05-28 11:08:19', NULL, '2026-05-28 11:08:19', NULL, '1', '0');
INSERT INTO `bus_passenger` VALUES (136, '测试乘客990095', '13917147552', 'bus_community', 'silent', 'unknown', NULL, NULL, 5, 5, 'normal', '2026-05-28 11:08:19', NULL, '2026-05-28 11:08:19', NULL, '1', '0');
INSERT INTO `bus_passenger` VALUES (137, '测试乘客990186', '13947291862', 'wechat_miniapp', 'new_user', 'male', NULL, NULL, 6, 6, 'normal', '2026-05-28 11:08:19', NULL, '2026-05-28 11:08:19', NULL, '1', '0');
INSERT INTO `bus_passenger` VALUES (138, '测试乘客990277', '13980942704', 'alipay_miniapp', 'high_frequency', 'female', NULL, NULL, 0, 7, 'normal', '2026-05-28 11:08:19', NULL, '2026-05-28 11:08:19', NULL, '1', '0');
INSERT INTO `bus_passenger` VALUES (139, '测试乘客990368', '13953013384', 'bus_community', 'general_active', 'unknown', NULL, NULL, 1, 8, 'normal', '2026-05-28 11:08:19', NULL, '2026-05-28 11:08:19', NULL, '1', '0');
INSERT INTO `bus_passenger` VALUES (140, '测试乘客990449', '13969959085', 'wechat_miniapp', 'active', 'male', NULL, NULL, 2, 9, 'normal', '2026-05-28 11:08:19', NULL, '2026-05-28 11:08:19', NULL, '1', '0');
INSERT INTO `bus_passenger` VALUES (141, '测试乘客9905110', '13925615237', 'alipay_miniapp', 'dormant', 'female', NULL, NULL, 3, 10, 'normal', '2026-05-28 11:08:19', NULL, '2026-05-28 11:08:19', NULL, '1', '0');
INSERT INTO `bus_passenger` VALUES (142, '测试乘客9906011', '13941209339', 'bus_community', 'silent', 'unknown', NULL, NULL, 4, 11, 'normal', '2026-05-28 11:08:19', NULL, '2026-05-28 11:08:19', NULL, '1', '0');
INSERT INTO `bus_passenger` VALUES (143, '测试乘客9906712', '13907639444', 'wechat_miniapp', 'new_user', 'male', NULL, NULL, 5, 12, 'normal', '2026-05-28 11:08:19', NULL, '2026-05-28 11:08:19', NULL, '1', '0');
INSERT INTO `bus_passenger` VALUES (144, '测试乘客9907813', '13989257940', 'alipay_miniapp', 'high_frequency', 'female', NULL, NULL, 6, 13, 'normal', '2026-05-28 11:08:19', NULL, '2026-05-28 11:08:19', NULL, '1', '0');
INSERT INTO `bus_passenger` VALUES (145, '测试乘客9909214', '13906705756', 'bus_community', 'general_active', 'unknown', NULL, NULL, 0, 14, 'normal', '2026-05-28 11:08:19', NULL, '2026-05-28 11:08:19', NULL, '1', '0');
INSERT INTO `bus_passenger` VALUES (146, '测试乘客9910115', '13974430111', 'wechat_miniapp', 'active', 'male', NULL, NULL, 1, 15, 'normal', '2026-05-28 11:08:19', NULL, '2026-05-28 11:08:19', NULL, '1', '0');
INSERT INTO `bus_passenger` VALUES (147, '测试乘客9911016', '13933213757', 'alipay_miniapp', 'dormant', 'female', NULL, NULL, 2, 16, 'normal', '2026-05-28 11:08:19', NULL, '2026-05-28 11:08:19', NULL, '1', '0');
INSERT INTO `bus_passenger` VALUES (148, '测试乘客9911917', '13995258578', 'bus_community', 'silent', 'unknown', NULL, NULL, 3, 17, 'normal', '2026-05-28 11:08:19', NULL, '2026-05-28 11:08:19', NULL, '1', '0');
INSERT INTO `bus_passenger` VALUES (149, '测试乘客9912818', '13936177921', 'wechat_miniapp', 'new_user', 'male', NULL, NULL, 4, 18, 'normal', '2026-05-28 11:08:19', NULL, '2026-05-28 11:08:19', NULL, '1', '0');
INSERT INTO `bus_passenger` VALUES (150, '测试乘客9913619', '13918657051', 'alipay_miniapp', 'high_frequency', 'female', NULL, NULL, 5, 19, 'normal', '2026-05-28 11:08:19', NULL, '2026-05-28 11:08:19', NULL, '1', '0');
INSERT INTO `bus_passenger` VALUES (151, '测试乘客180880', '13963211496', 'wechat_miniapp', 'new_user', 'male', NULL, NULL, 0, 0, 'normal', '2026-06-02 09:16:58', NULL, '2026-06-02 09:16:58', NULL, '1', '0');
INSERT INTO `bus_passenger` VALUES (152, '测试乘客181031', '13944648789', 'alipay_miniapp', 'high_frequency', 'female', NULL, NULL, 1, 1, 'normal', '2026-06-02 09:16:58', NULL, '2026-06-02 09:16:58', NULL, '1', '0');
INSERT INTO `bus_passenger` VALUES (153, '测试乘客181122', '13975505874', 'bus_community', 'general_active', 'unknown', NULL, NULL, 2, 2, 'normal', '2026-06-02 09:16:58', NULL, '2026-06-02 09:16:58', NULL, '1', '0');
INSERT INTO `bus_passenger` VALUES (154, '测试乘客181243', '13913378246', 'wechat_miniapp', 'active', 'male', NULL, NULL, 3, 3, 'normal', '2026-06-02 09:16:58', NULL, '2026-06-02 09:16:58', NULL, '1', '0');
INSERT INTO `bus_passenger` VALUES (155, '测试乘客181344', '13990766426', 'alipay_miniapp', 'dormant', 'female', NULL, NULL, 4, 4, 'normal', '2026-06-02 09:16:58', NULL, '2026-06-02 09:16:58', NULL, '1', '0');
INSERT INTO `bus_passenger` VALUES (156, '测试乘客181475', '13967040842', 'bus_community', 'silent', 'unknown', NULL, NULL, 5, 5, 'normal', '2026-06-02 09:16:58', NULL, '2026-06-02 09:16:58', NULL, '1', '0');
INSERT INTO `bus_passenger` VALUES (157, '测试乘客181566', '13995963496', 'wechat_miniapp', 'new_user', 'male', NULL, NULL, 6, 6, 'normal', '2026-06-02 09:16:58', NULL, '2026-06-02 09:16:58', NULL, '1', '0');
INSERT INTO `bus_passenger` VALUES (158, '测试乘客181677', '13977810116', 'alipay_miniapp', 'high_frequency', 'female', NULL, NULL, 0, 7, 'normal', '2026-06-02 09:16:58', NULL, '2026-06-02 09:16:58', NULL, '1', '0');
INSERT INTO `bus_passenger` VALUES (159, '测试乘客181788', '13975225256', 'bus_community', 'general_active', 'unknown', NULL, NULL, 1, 8, 'normal', '2026-06-02 09:16:58', NULL, '2026-06-02 09:16:58', NULL, '1', '0');
INSERT INTO `bus_passenger` VALUES (160, '测试乘客181879', '13966338404', 'wechat_miniapp', 'active', 'male', NULL, NULL, 2, 9, 'normal', '2026-06-02 09:16:58', NULL, '2026-06-02 09:16:58', NULL, '1', '0');
INSERT INTO `bus_passenger` VALUES (161, '测试乘客1819510', '13928590822', 'alipay_miniapp', 'dormant', 'female', NULL, NULL, 3, 10, 'normal', '2026-06-02 09:16:58', NULL, '2026-06-02 09:16:58', NULL, '1', '0');
INSERT INTO `bus_passenger` VALUES (162, '测试乘客1820311', '13966125506', 'bus_community', 'silent', 'unknown', NULL, NULL, 4, 11, 'normal', '2026-06-02 09:16:58', NULL, '2026-06-02 09:16:58', NULL, '1', '0');
INSERT INTO `bus_passenger` VALUES (163, '测试乘客1821112', '13996215375', 'wechat_miniapp', 'new_user', 'male', NULL, NULL, 5, 12, 'normal', '2026-06-02 09:16:58', NULL, '2026-06-02 09:16:58', NULL, '1', '0');
INSERT INTO `bus_passenger` VALUES (164, '测试乘客1822013', '13933683947', 'alipay_miniapp', 'high_frequency', 'female', NULL, NULL, 6, 13, 'normal', '2026-06-02 09:16:58', NULL, '2026-06-02 09:16:58', NULL, '1', '0');
INSERT INTO `bus_passenger` VALUES (165, '测试乘客1822914', '13978041602', 'bus_community', 'general_active', 'unknown', NULL, NULL, 0, 14, 'normal', '2026-06-02 09:16:58', NULL, '2026-06-02 09:16:58', NULL, '1', '0');
INSERT INTO `bus_passenger` VALUES (166, '测试乘客1823715', '13998102983', 'wechat_miniapp', 'active', 'male', NULL, NULL, 1, 15, 'normal', '2026-06-02 09:16:58', NULL, '2026-06-02 09:16:58', NULL, '1', '0');
INSERT INTO `bus_passenger` VALUES (167, '测试乘客1824516', '13941741597', 'alipay_miniapp', 'dormant', 'female', NULL, NULL, 2, 16, 'normal', '2026-06-02 09:16:58', NULL, '2026-06-02 09:16:58', NULL, '1', '0');
INSERT INTO `bus_passenger` VALUES (168, '测试乘客1825317', '13990893272', 'bus_community', 'silent', 'unknown', NULL, NULL, 3, 17, 'normal', '2026-06-02 09:16:58', NULL, '2026-06-02 09:16:58', NULL, '1', '0');
INSERT INTO `bus_passenger` VALUES (169, '测试乘客1826418', '13953842410', 'wechat_miniapp', 'new_user', 'male', NULL, NULL, 4, 18, 'normal', '2026-06-02 09:16:58', NULL, '2026-06-02 09:16:58', NULL, '1', '0');
INSERT INTO `bus_passenger` VALUES (170, '测试乘客1827219', '13998109491', 'alipay_miniapp', 'high_frequency', 'female', NULL, NULL, 5, 19, 'normal', '2026-06-02 09:16:58', NULL, '2026-06-02 09:16:58', NULL, '1', '0');

-- ----------------------------
-- Table structure for bus_passenger_address
-- ----------------------------
DROP TABLE IF EXISTS `bus_passenger_address`;
CREATE TABLE `bus_passenger_address`  (
  `id` bigint NOT NULL AUTO_INCREMENT COMMENT '主键',
  `passenger_id` bigint NOT NULL COMMENT '乘客ID',
  `label` varchar(50) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci NULL DEFAULT NULL COMMENT '地址标签:家/公司等',
  `address` varchar(255) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci NOT NULL COMMENT '地址文本',
  `longitude` decimal(10, 6) NULL DEFAULT NULL COMMENT '经度',
  `latitude` decimal(10, 6) NULL DEFAULT NULL COMMENT '纬度',
  `is_default` tinyint NULL DEFAULT 0 COMMENT '是否默认地址',
  `create_time` datetime NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
  `update_time` datetime NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
  `tenant_id` varchar(32) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci NULL DEFAULT NULL COMMENT '租户ID',
  PRIMARY KEY (`id`) USING BTREE,
  INDEX `idx_bpa_passenger`(`passenger_id` ASC) USING BTREE,
  INDEX `idx_bpa_tenant`(`tenant_id` ASC) USING BTREE
) ENGINE = InnoDB AUTO_INCREMENT = 11 CHARACTER SET = utf8mb4 COLLATE = utf8mb4_0900_ai_ci COMMENT = '乘客地址簿' ROW_FORMAT = DYNAMIC;

-- ----------------------------
-- Records of bus_passenger_address
-- ----------------------------
INSERT INTO `bus_passenger_address` VALUES (1, 121, '家', '天河区体育西路50号', 113.321500, 23.126800, 1, '2026-05-27 10:59:52', '2026-05-27 10:59:52', '1');
INSERT INTO `bus_passenger_address` VALUES (2, 121, '公司', '天河区珠江新城华夏路10号', 113.322000, 23.127000, 0, '2026-05-27 10:59:52', '2026-05-27 10:59:52', '1');
INSERT INTO `bus_passenger_address` VALUES (3, 122, '家', '海珠区广州塔路1号', 113.325000, 23.109000, 1, '2026-05-27 10:59:52', '2026-05-27 10:59:52', '1');
INSERT INTO `bus_passenger_address` VALUES (4, 122, '公司', '海珠区新港中路100号', 113.317500, 23.100500, 0, '2026-05-27 10:59:52', '2026-05-27 10:59:52', '1');
INSERT INTO `bus_passenger_address` VALUES (5, 123, '家', '番禺区番禺广场路1号', 113.365000, 22.945000, 1, '2026-05-27 10:59:52', '2026-05-27 10:59:52', '1');
INSERT INTO `bus_passenger_address` VALUES (6, 123, '学校', '番禺区大学城外环西路230号', 113.385000, 23.058000, 0, '2026-05-27 10:59:52', '2026-05-27 10:59:52', '1');
INSERT INTO `bus_passenger_address` VALUES (7, 124, '家', '越秀区中山五路10号', 113.267000, 23.128000, 1, '2026-05-27 10:59:52', '2026-05-27 10:59:52', '1');
INSERT INTO `bus_passenger_address` VALUES (8, 124, '公司', '越秀区北京路步行街100号', 113.272000, 23.122000, 0, '2026-05-27 10:59:52', '2026-05-27 10:59:52', '1');
INSERT INTO `bus_passenger_address` VALUES (9, 125, '家', '荔湾区中山七路20号', 113.240000, 23.124000, 1, '2026-05-27 10:59:52', '2026-05-27 10:59:52', '1');
INSERT INTO `bus_passenger_address` VALUES (10, 125, '公司', '荔湾区长寿西路30号', 113.242000, 23.117000, 0, '2026-05-27 10:59:52', '2026-05-27 10:59:52', '1');

-- ----------------------------
-- Table structure for bus_passenger_favorite_route
-- ----------------------------
DROP TABLE IF EXISTS `bus_passenger_favorite_route`;
CREATE TABLE `bus_passenger_favorite_route`  (
  `id` bigint NOT NULL AUTO_INCREMENT COMMENT '主键',
  `passenger_id` bigint NOT NULL COMMENT '乘客ID',
  `route_name` varchar(128) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci NOT NULL COMMENT '常用线路名称',
  `origin_name` varchar(128) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci NULL DEFAULT NULL COMMENT '起点',
  `destination_name` varchar(128) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci NULL DEFAULT NULL COMMENT '终点',
  `use_count` int NULL DEFAULT 0 COMMENT '使用次数',
  `last_use_time` datetime NULL DEFAULT NULL COMMENT '最近使用时间',
  `create_time` datetime NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
  `update_time` datetime NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
  `tenant_id` varchar(32) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci NULL DEFAULT NULL COMMENT '租户ID',
  PRIMARY KEY (`id`) USING BTREE,
  INDEX `idx_bpfr_passenger`(`passenger_id` ASC) USING BTREE,
  INDEX `idx_bpfr_tenant`(`tenant_id` ASC) USING BTREE
) ENGINE = InnoDB AUTO_INCREMENT = 11 CHARACTER SET = utf8mb4 COLLATE = utf8mb4_0900_ai_ci COMMENT = '乘客常用线路' ROW_FORMAT = DYNAMIC;

-- ----------------------------
-- Records of bus_passenger_favorite_route
-- ----------------------------
INSERT INTO `bus_passenger_favorite_route` VALUES (1, 121, '天河穿梭线', '体育西路站', '珠江新城站', 12, '2026-05-27 08:30:00', '2026-05-27 10:59:56', '2026-05-27 10:59:56', '1');
INSERT INTO `bus_passenger_favorite_route` VALUES (2, 121, '花都机场线', '花都广场站', '机场南站', 3, '2026-05-26 07:00:00', '2026-05-27 10:59:56', '2026-05-27 10:59:56', '1');
INSERT INTO `bus_passenger_favorite_route` VALUES (3, 122, '海珠滨江线', '广州塔站', '客村站', 8, '2026-05-27 08:45:00', '2026-05-27 10:59:56', '2026-05-27 10:59:56', '1');
INSERT INTO `bus_passenger_favorite_route` VALUES (4, 122, '越秀经典线', '公园前站', '北京路站', 5, '2026-05-26 11:00:00', '2026-05-27 10:59:56', '2026-05-27 10:59:56', '1');
INSERT INTO `bus_passenger_favorite_route` VALUES (5, 123, '大学城专线', '大学城北站', '番禺广场站', 15, '2026-05-27 14:00:00', '2026-05-27 10:59:56', '2026-05-27 10:59:56', '1');
INSERT INTO `bus_passenger_favorite_route` VALUES (6, 123, '番禺区内线', '番禺广场站', '市桥站', 6, '2026-05-25 10:00:00', '2026-05-27 10:59:56', '2026-05-27 10:59:56', '1');
INSERT INTO `bus_passenger_favorite_route` VALUES (7, 124, '越秀经典线', '公园前站', '北京路站', 10, '2026-05-27 11:00:00', '2026-05-27 10:59:56', '2026-05-27 10:59:56', '1');
INSERT INTO `bus_passenger_favorite_route` VALUES (8, 124, '荔湾风情线', '陈家祠站', '长寿路站', 4, '2026-05-24 09:00:00', '2026-05-27 10:59:56', '2026-05-27 10:59:56', '1');
INSERT INTO `bus_passenger_favorite_route` VALUES (9, 125, '荔湾风情线', '陈家祠站', '长寿路站', 7, '2026-05-27 11:30:00', '2026-05-27 10:59:56', '2026-05-27 10:59:56', '1');
INSERT INTO `bus_passenger_favorite_route` VALUES (10, 125, '海珠滨江线', '广州塔站', '客村站', 3, '2026-05-23 10:00:00', '2026-05-27 10:59:56', '2026-05-27 10:59:56', '1');

-- ----------------------------
-- Table structure for bus_ride_group
-- ----------------------------
DROP TABLE IF EXISTS `bus_ride_group`;
CREATE TABLE `bus_ride_group`  (
  `id` bigint NOT NULL AUTO_INCREMENT COMMENT '主键',
  `group_no` varchar(64) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci NOT NULL COMMENT '分组编号',
  `area_id` bigint NULL DEFAULT NULL COMMENT '运营区域ID',
  `planned_departure_time` datetime NULL DEFAULT NULL COMMENT '计划出发时间（组内中位期望时间）',
  `total_passenger_count` int NOT NULL DEFAULT 0 COMMENT '组内总乘客人数',
  `request_count` int NOT NULL DEFAULT 0 COMMENT '组内需求条数',
  `center_origin_lng` double NULL DEFAULT NULL COMMENT '出发中心经度',
  `center_origin_lat` double NULL DEFAULT NULL COMMENT '出发中心纬度',
  `center_dest_lng` double NULL DEFAULT NULL COMMENT '目的中心经度',
  `center_dest_lat` double NULL DEFAULT NULL COMMENT '目的中心纬度',
  `direction_bearing` double NULL DEFAULT NULL COMMENT '平均方向角(度)',
  `waypoints_json` text CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci NULL COMMENT '有序上下车点JSON',
  `status` varchar(20) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci NOT NULL DEFAULT 'FORMING' COMMENT '状态:FORMING/SEALED/DISPATCHED/CANCELLED',
  `dispatch_task_id` bigint NULL DEFAULT NULL COMMENT '关联调度任务ID',
  `create_time` datetime NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
  `update_time` datetime NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
  `tenant_id` varchar(32) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci NULL DEFAULT NULL COMMENT '租户ID',
  `del_flag` varchar(1) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci NULL DEFAULT '0' COMMENT '删除标记',
  PRIMARY KEY (`id`) USING BTREE,
  UNIQUE INDEX `uk_brg_group_no`(`group_no` ASC) USING BTREE,
  INDEX `idx_brg_status`(`status` ASC) USING BTREE,
  INDEX `idx_brg_area`(`area_id` ASC) USING BTREE,
  INDEX `idx_brg_tenant`(`tenant_id` ASC) USING BTREE
) ENGINE = InnoDB AUTO_INCREMENT = 18 CHARACTER SET = utf8mb4 COLLATE = utf8mb4_0900_ai_ci COMMENT = '组客分组表' ROW_FORMAT = DYNAMIC;

-- ----------------------------
-- Records of bus_ride_group
-- ----------------------------
INSERT INTO `bus_ride_group` VALUES (5, 'GR20260516197020', 10, '2026-05-16 20:45:00', 4, 3, 113.32816666666666, 23.140266666666665, 113.33203333333334, 23.143633333333337, 41.3881081267761, '[{\"type\":\"PICKUP\",\"requestId\":\"60\",\"lng\":113.328,\"lat\":23.142,\"address\":\"林和西地铁站\",\"passengerCount\":1,\"seq\":1},{\"type\":\"DROPOFF\",\"requestId\":\"60\",\"lng\":113.3285,\"lat\":23.143,\"address\":\"中信广场\",\"passengerCount\":1,\"seq\":2},{\"type\":\"PICKUP\",\"requestId\":\"61\",\"lng\":113.335,\"lat\":23.152,\"address\":\"沙河顶地铁站\",\"passengerCount\":2,\"seq\":3},{\"type\":\"DROPOFF\",\"requestId\":\"61\",\"lng\":113.34,\"lat\":23.155,\"address\":\"沙河服装城\",\"passengerCount\":2,\"seq\":4},{\"type\":\"PICKUP\",\"requestId\":\"53\",\"lng\":113.3215,\"lat\":23.1268,\"address\":\"体育西路地铁站A口\",\"passengerCount\":1,\"seq\":5},{\"type\":\"DROPOFF\",\"requestId\":\"53\",\"lng\":113.3276,\"lat\":23.1329,\"address\":\"天河城购物中心\",\"passengerCount\":1,\"seq\":6}]', 'DISPATCHED', 37, '2026-05-16 21:33:39', '2026-05-16 21:33:40', '1', '0');
INSERT INTO `bus_ride_group` VALUES (6, 'GR20260525815803', 10, '2026-05-16 20:45:00', 4, 3, 113.32816666666666, 23.140266666666665, 113.33203333333334, 23.143633333333337, 41.3881081267761, '[{\"type\":\"PICKUP\",\"requestId\":\"60\",\"lng\":113.328,\"lat\":23.142,\"address\":\"林和西地铁站\",\"passengerCount\":1,\"seq\":1},{\"type\":\"DROPOFF\",\"requestId\":\"60\",\"lng\":113.3285,\"lat\":23.143,\"address\":\"中信广场\",\"passengerCount\":1,\"seq\":2},{\"type\":\"PICKUP\",\"requestId\":\"61\",\"lng\":113.335,\"lat\":23.152,\"address\":\"沙河顶地铁站\",\"passengerCount\":2,\"seq\":3},{\"type\":\"DROPOFF\",\"requestId\":\"61\",\"lng\":113.34,\"lat\":23.155,\"address\":\"沙河服装城\",\"passengerCount\":2,\"seq\":4},{\"type\":\"PICKUP\",\"requestId\":\"53\",\"lng\":113.3215,\"lat\":23.1268,\"address\":\"体育西路地铁站A口\",\"passengerCount\":1,\"seq\":5},{\"type\":\"DROPOFF\",\"requestId\":\"53\",\"lng\":113.3276,\"lat\":23.1329,\"address\":\"天河城购物中心\",\"passengerCount\":1,\"seq\":6}]', 'FORMING', NULL, '2026-05-25 15:00:07', '2026-05-25 15:00:07', '1', '0');
INSERT INTO `bus_ride_group` VALUES (7, 'GR20260527001', 201, '2026-05-27 08:30:00', 3, 2, 113.3215, 23.1268, 113.322, 23.127, NULL, NULL, 'DISPATCHED', NULL, '2026-05-27 10:59:09', '2026-05-27 10:59:09', '1', '0');
INSERT INTO `bus_ride_group` VALUES (8, 'GR20260527002', 202, '2026-05-27 09:00:00', 4, 2, 113.325, 23.109, 113.3175, 23.1005, NULL, NULL, 'DISPATCHED', NULL, '2026-05-27 10:59:09', '2026-05-27 10:59:09', '1', '0');
INSERT INTO `bus_ride_group` VALUES (9, 'GR20260527003', 204, '2026-05-27 11:00:00', 1, 1, 113.267, 23.128, 113.272, 23.122, NULL, NULL, 'DISPATCHED', NULL, '2026-05-27 10:59:09', '2026-05-27 10:59:09', '1', '0');
INSERT INTO `bus_ride_group` VALUES (10, 'GR20260527004', 205, '2026-05-27 11:30:00', 2, 1, 113.24, 23.124, 113.242, 23.117, NULL, NULL, 'FORMING', NULL, '2026-05-27 10:59:09', '2026-05-27 10:59:09', '1', '0');
INSERT INTO `bus_ride_group` VALUES (11, 'GR20260527005', 203, '2026-05-27 14:00:00', 4, 1, 113.365, 22.945, 113.385, 23.058, NULL, NULL, 'DISPATCHED', NULL, '2026-05-27 10:59:09', '2026-05-27 10:59:09', '1', '0');
INSERT INTO `bus_ride_group` VALUES (12, 'GR20260528001', 201, '2026-05-28 08:30:00', 2, 1, 113.3215, 23.1268, 113.322, 23.127, NULL, NULL, 'FORMING', NULL, '2026-05-27 10:59:09', '2026-05-27 10:59:09', '1', '0');
INSERT INTO `bus_ride_group` VALUES (13, 'GR20260528002', 201, '2026-05-28 17:30:00', 5, 3, 113.3215, 23.1268, 113.322, 23.127, NULL, NULL, 'FORMING', NULL, '2026-05-27 10:59:09', '2026-05-27 10:59:09', '1', '0');
INSERT INTO `bus_ride_group` VALUES (14, 'GR20260529001', 210, '2026-05-29 07:00:00', 3, 2, 113.21, 23.41, 113.205, 23.405, NULL, NULL, 'FORMING', NULL, '2026-05-27 10:59:09', '2026-05-27 10:59:09', '1', '0');
INSERT INTO `bus_ride_group` VALUES (15, 'GR20260529002', 204, '2026-05-29 09:00:00', 2, 2, 113.267, 23.128, 113.272, 23.122, NULL, NULL, 'SEALED', NULL, '2026-05-27 10:59:09', '2026-05-27 10:59:09', '1', '0');
INSERT INTO `bus_ride_group` VALUES (16, 'GR20260530001', 205, '2026-05-30 08:30:00', 1, 1, 113.24, 23.124, 113.242, 23.117, NULL, NULL, 'CANCELLED', NULL, '2026-05-27 10:59:09', '2026-05-27 10:59:09', '1', '0');
INSERT INTO `bus_ride_group` VALUES (17, 'GR20260601286168', NULL, NULL, 2, 2, 113.329806, 23.132025, 113.32979, 23.132016, 238.54681157349643, '[{\"type\":\"PICKUP\",\"requestId\":\"91\",\"lng\":113.329806,\"lat\":23.132025,\"address\":\"创展中心东座公交站\",\"passengerCount\":1,\"seq\":1},{\"type\":\"PICKUP\",\"requestId\":\"92\",\"lng\":113.329806,\"lat\":23.132025,\"address\":\"创展中心东座公交站\",\"passengerCount\":1,\"seq\":2},{\"type\":\"DROPOFF\",\"requestId\":\"91\",\"lng\":113.32979,\"lat\":23.132016,\"address\":\"创展中心西座公交站\",\"passengerCount\":1,\"seq\":3},{\"type\":\"DROPOFF\",\"requestId\":\"92\",\"lng\":113.32979,\"lat\":23.132016,\"address\":\"创展中心西座公交站\",\"passengerCount\":1,\"seq\":4}]', 'FORMING', NULL, '2026-06-01 18:30:44', '2026-06-01 18:30:44', '1', '0');

-- ----------------------------
-- Table structure for bus_ride_request
-- ----------------------------
DROP TABLE IF EXISTS `bus_ride_request`;
CREATE TABLE `bus_ride_request`  (
  `id` bigint NOT NULL AUTO_INCREMENT COMMENT '主键',
  `passenger_id` varchar(64) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci NULL DEFAULT NULL COMMENT '乘客ID',
  `passenger_phone` varchar(32) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci NULL DEFAULT NULL COMMENT '乘客手机号',
  `order_id` varchar(64) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci NOT NULL COMMENT '关联订单ID',
  `order_no` varchar(64) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci NULL DEFAULT NULL COMMENT '订单编号',
  `origin_lng` double NULL DEFAULT NULL COMMENT '出发经度',
  `origin_lat` double NULL DEFAULT NULL COMMENT '出发纬度',
  `origin_address` varchar(255) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci NULL DEFAULT NULL COMMENT '出发地址/站点名',
  `dest_lng` double NULL DEFAULT NULL COMMENT '目的经度',
  `dest_lat` double NULL DEFAULT NULL COMMENT '目的纬度',
  `dest_address` varchar(255) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci NULL DEFAULT NULL COMMENT '目的地址/站点名',
  `passenger_count` int NOT NULL DEFAULT 1 COMMENT '乘客人数',
  `request_time` datetime NOT NULL COMMENT '需求发起时间',
  `expected_departure_time` datetime NULL DEFAULT NULL COMMENT '期望出发时间',
  `expire_time` datetime NULL DEFAULT NULL COMMENT '需求过期时间',
  `area_id` bigint NULL DEFAULT NULL COMMENT '所属运营区域ID',
  `group_id` bigint NULL DEFAULT NULL COMMENT '组客分组ID（组客后关联）',
  `dispatch_task_id` bigint NULL DEFAULT NULL COMMENT '关联调度任务ID（匹配后关联）',
  `status` varchar(20) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci NOT NULL DEFAULT 'WAITING' COMMENT '状态:WAITING/GROUPED/MATCHED/EXPIRED/CANCELLED',
  `reject_count` int NULL DEFAULT 0 COMMENT '被拒绝改派次数',
  `remark` varchar(500) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci NULL DEFAULT NULL COMMENT '备注',
  `create_time` datetime NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
  `create_by` varchar(64) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci NULL DEFAULT NULL COMMENT '创建人',
  `update_time` datetime NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
  `update_by` varchar(64) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci NULL DEFAULT NULL COMMENT '更新人',
  `tenant_id` varchar(32) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci NULL DEFAULT NULL COMMENT '租户ID',
  `del_flag` varchar(1) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci NULL DEFAULT '0' COMMENT '删除标记',
  PRIMARY KEY (`id`) USING BTREE,
  INDEX `idx_brr_order`(`order_id` ASC) USING BTREE,
  INDEX `idx_brr_status`(`status` ASC) USING BTREE,
  INDEX `idx_brr_passenger`(`passenger_id` ASC) USING BTREE,
  INDEX `idx_brr_area`(`area_id` ASC) USING BTREE,
  INDEX `idx_brr_group`(`group_id` ASC) USING BTREE,
  INDEX `idx_brr_expire`(`expire_time` ASC) USING BTREE,
  INDEX `idx_brr_tenant`(`tenant_id` ASC) USING BTREE
) ENGINE = InnoDB AUTO_INCREMENT = 96 CHARACTER SET = utf8mb4 COLLATE = utf8mb4_0900_ai_ci COMMENT = '约车需求池' ROW_FORMAT = DYNAMIC;

-- ----------------------------
-- Records of bus_ride_request
-- ----------------------------
INSERT INTO `bus_ride_request` VALUES (1, '2053666005677953025', NULL, '59a3dd42b5fe4e879aed5a763f447e9e', 'ORD_20260518094215_604928', 113.32848744306068, 23.131895838544462, '创展中心西站', 113.33062095282935, 23.131705090250005, '创展中心东站', 1, '2026-05-18 09:42:34', '2026-05-25 11:53:48', '2026-05-25 23:12:34', NULL, NULL, NULL, 'EXPIRED', 0, NULL, '2026-05-18 09:42:34', '13560004373', '2026-05-29 10:29:03', NULL, '1', '0');
INSERT INTO `bus_ride_request` VALUES (53, 'P_Near001', '13912340001', 'NEAR_ORD_001', 'NEAR20260516001', 113.3215, 23.1268, '体育西路地铁站A口', 113.3276, 23.1329, '天河城购物中心', 1, '2026-05-16 20:30:00', '2026-05-16 20:45:00', '2026-05-25 23:12:34', 10, 6, 37, 'GROUPED', 0, '车辆附近，急需用车', '2026-05-16 20:30:00', 'user001', '2026-05-25 15:00:07', 'user001', '1', '0');
INSERT INTO `bus_ride_request` VALUES (54, 'P_Near002', '13912340002', 'NEAR_ORD_002', 'NEAR20260516002', 113.324, 23.1245, '珠江新城地铁站', 113.325, 23.1085, '广州塔', 2, '2026-05-16 20:25:00', '2026-05-16 20:40:00', '2026-05-25 23:12:34', 10, NULL, 41, 'EXPIRED', 0, '往车辆位置西南方向', '2026-05-16 20:25:00', 'user002', '2026-05-29 10:29:03', 'user002', '1', '0');
INSERT INTO `bus_ride_request` VALUES (55, 'P_Near003', '13912340003', 'NEAR_ORD_003', 'NEAR20260516003', 113.3302, 23.1289, '天河南一路', 113.338, 23.134, '石牌桥', 1, '2026-05-16 20:35:00', '2026-05-16 20:50:00', '2026-05-25 23:12:34', 10, 3, 43, 'EXPIRED', 0, '车辆东北方向', '2026-05-16 20:35:00', 'user003', '2026-05-29 10:29:03', 'user003', '1', '0');
INSERT INTO `bus_ride_request` VALUES (56, 'P_Near004', '13912340004', 'NEAR_ORD_004', 'NEAR20260516004', 113.3382, 23.12, '猎德地铁站', 113.332, 23.126, '冼村', 3, '2026-05-16 20:20:00', '2026-05-16 20:35:00', '2026-05-25 23:12:34', 10, NULL, 40, 'EXPIRED', 0, '已组客，等待匹配', '2026-05-16 20:20:00', 'user004', '2026-05-29 10:29:03', 'system', '1', '0');
INSERT INTO `bus_ride_request` VALUES (57, 'P_Near005', '13912340005', 'NEAR_ORD_005', 'NEAR20260516005', 113.3478, 23.145, '华师地铁站', 113.342, 23.137, '岗顶', 1, '2026-05-16 20:40:00', '2026-05-16 20:55:00', '2026-05-25 23:12:34', 10, NULL, 44, 'EXPIRED', 0, '车辆东北方向约2km', '2026-05-16 20:40:00', 'user005', '2026-05-29 10:29:03', 'user005', '1', '0');
INSERT INTO `bus_ride_request` VALUES (58, 'P_Near006', '13912340006', 'NEAR_ORD_006', 'NEAR20260516006', 113.316, 23.12, '五羊邨', 113.3245, 23.1317, '天河体育中心', 1, '2026-05-16 19:50:00', '2026-05-16 20:10:00', '2026-05-25 23:12:34', 10, 301, 39, 'EXPIRED', 0, '已匹配车辆，行程进行中', '2026-05-16 19:50:00', 'user006', '2026-05-29 10:29:03', 'system', '1', '0');
INSERT INTO `bus_ride_request` VALUES (59, 'P_Near007', '13912340007', 'NEAR_ORD_007', 'NEAR20260516007', 113.312, 23.13, '杨箕地铁站', 113.325, 23.144, '广州动物园', 2, '2026-05-16 19:00:00', '2026-05-16 19:30:00', '2026-05-25 23:12:34', 10, NULL, 38, 'EXPIRED', 0, '乘客未支付，需求已过期', '2026-05-16 19:00:00', 'user007', '2026-05-29 10:29:03', 'system', '1', '0');
INSERT INTO `bus_ride_request` VALUES (60, 'P_Near008', '13912340008', 'NEAR_ORD_008', 'NEAR20260516008', 113.328, 23.142, '林和西地铁站', 113.3285, 23.143, '中信广场', 1, '2026-05-16 20:15:00', '2026-05-16 20:30:00', '2026-05-25 23:12:34', 10, 6, 37, 'GROUPED', 0, '用户临时取消', '2026-05-16 20:15:00', 'user008', '2026-05-25 15:00:07', 'user008', '1', '0');
INSERT INTO `bus_ride_request` VALUES (61, 'P_Near009', '13912340009', 'NEAR_ORD_009', 'NEAR20260516009', 113.335, 23.152, '沙河顶地铁站', 113.34, 23.155, '沙河服装城', 2, '2026-05-16 20:28:00', '2026-05-16 20:45:00', '2026-05-25 23:12:34', 10, 6, 37, 'GROUPED', 0, '已组客，待调度匹配', '2026-05-16 20:28:00', 'user009', '2026-05-25 15:00:07', 'system', '1', '0');
INSERT INTO `bus_ride_request` VALUES (62, 'P_Near010', '13912340010', 'NEAR_ORD_010', 'NEAR20260516010', 113.331, 23.1225, '黄埔大道西', 113.342, 23.119, '跑马场', 1, '2026-05-16 20:32:00', '2026-05-16 20:48:00', '2026-05-25 23:12:34', 10, NULL, 42, 'EXPIRED', 0, '车辆南侧约1.5km', '2026-05-16 20:32:00', 'user010', '2026-05-29 10:29:03', 'user010', '1', '0');
INSERT INTO `bus_ride_request` VALUES (73, '2053666005677953025', NULL, '77f082300d004983b3f74dcd4d4d3262', 'ORD_20260528090948_111936', 113.331482, 23.133003, '石牌桥地铁站口站', 113.331482, 23.133003, '石牌桥A口公交站', 1, '2026-05-28 09:10:00', NULL, '2026-05-28 09:40:00', NULL, NULL, NULL, 'EXPIRED', 0, NULL, '2026-05-28 09:10:00', '13560004373', '2026-05-29 10:29:03', NULL, '1', '0');
INSERT INTO `bus_ride_request` VALUES (74, '2053666005677953025', NULL, '35a26b307f36465dbf3d0ab26382fe30', 'ORD_20260528150740_502976', 113.329777, 23.131938, '天河南一路', 113.326576, 23.148611, '广州东站', 2, '2026-05-28 15:07:42', NULL, '2026-05-28 15:37:42', NULL, NULL, NULL, 'EXPIRED', 0, NULL, '2026-05-28 15:07:42', '13560004373', '2026-05-29 10:29:03', NULL, '1', '0');
INSERT INTO `bus_ride_request` VALUES (75, '2059902964167528449', NULL, '1e9b16a7633c41de953bc5544d0d6118', 'ORD_20260528154231_285440', 113.331482, 23.133003, '石牌桥地铁站口站', 113.331482, 23.133003, '石牌桥A口公交站', 1, '2026-05-28 15:42:35', NULL, '2026-05-28 16:12:35', NULL, NULL, NULL, 'EXPIRED', 0, NULL, '2026-05-28 15:42:35', '13560004373', '2026-05-29 10:29:03', NULL, '1', '0');
INSERT INTO `bus_ride_request` VALUES (76, '2059902964167528449', NULL, '0082a39631c4484689c987516ae38887', 'ORD_20260528154614_816576', 113.331482, 23.133003, '石牌桥地铁站口站', 113.331482, 23.133003, '石牌桥A口公交站', 1, '2026-05-28 15:46:16', NULL, '2026-05-28 16:16:16', NULL, NULL, NULL, 'EXPIRED', 0, NULL, '2026-05-28 15:46:16', '13560004373', '2026-05-29 10:29:03', NULL, '1', '0');
INSERT INTO `bus_ride_request` VALUES (77, '2059892109837258754', NULL, '1f641c34605749b8a55e8bc6349665e0', 'ORD_20260528171807_195776', 113.3245, 23.1067, '广州塔站', 113.314474, 23.150741, '沙河', 1, '2026-05-28 17:18:11', NULL, '2026-05-28 17:48:11', NULL, NULL, 56, 'MATCHED', 0, NULL, '2026-05-28 17:18:11', '13560004373', '2026-05-28 17:18:40', NULL, '1', '0');
INSERT INTO `bus_ride_request` VALUES (78, '2059902964167528449', NULL, '139f11dec5df439398070737451dcd23', 'ORD_20260528175725_268928', 113.314474, 23.150741, '沙河', 113.326576, 23.148611, '广州东站', 1, '2026-05-28 17:57:27', NULL, '2026-05-28 18:27:27', NULL, NULL, 64, 'MATCHED', 0, NULL, '2026-05-28 17:57:27', '13560004373', '2026-05-28 17:59:05', NULL, '1', '0');
INSERT INTO `bus_ride_request` VALUES (79, '2059902964167528449', NULL, '45ba93a1d6194c05a28f69d6c328196a', 'ORD_20260528180232_085632', 113.314474, 23.150741, '沙河', 113.326576, 23.148611, '广州东站', 1, '2026-05-28 18:02:34', NULL, '2026-05-28 18:32:34', NULL, NULL, 65, 'MATCHED', 0, NULL, '2026-05-28 18:02:34', '13560004373', '2026-05-28 18:02:50', NULL, '1', '0');
INSERT INTO `bus_ride_request` VALUES (80, '2059902964167528449', NULL, '277d695ec19c44319f31e556e406e470', 'ORD_20260529093004_001088', 113.331482, 23.133003, '石牌桥地铁站口站', 113.331482, 23.133003, '石牌桥A口公交站', 1, '2026-05-29 09:30:06', NULL, '2026-05-29 10:00:06', NULL, NULL, NULL, 'EXPIRED', 0, NULL, '2026-05-29 09:30:06', '13560004373', '2026-05-29 10:29:03', NULL, '1', '0');
INSERT INTO `bus_ride_request` VALUES (81, '2053666005677953025', NULL, '8bd375f3c276463186759801e22ec4f8', 'ORD_20260529093123_506304', 113.331482, 23.133003, '石牌桥地铁站口站', 113.331482, 23.133003, '石牌桥A口公交站', 2, '2026-05-29 09:31:26', NULL, '2026-05-29 10:01:26', NULL, NULL, NULL, 'EXPIRED', 0, NULL, '2026-05-29 09:31:26', '13560004373', '2026-05-29 10:29:03', NULL, '1', '0');
INSERT INTO `bus_ride_request` VALUES (82, '2060174941524512769', NULL, '23a28db9a73448918ea39ea5c9c2cc80', 'ORD_20260529094322_941248', 113.326576, 23.148611, '广州东站', 113.314474, 23.150741, '沙河', 2, '2026-05-29 09:43:27', NULL, '2026-05-29 10:13:27', NULL, NULL, NULL, 'EXPIRED', 0, NULL, '2026-05-29 09:43:27', '13560004373', '2026-05-29 10:29:03', NULL, '1', '0');
INSERT INTO `bus_ride_request` VALUES (83, '2059902964167528449', NULL, '8cd9743567404874b060d3033290ac8d', 'ORD_20260529102858_880896', 113.331482, 23.133003, '石牌桥地铁站口站', 113.331482, 23.133003, '石牌桥A口公交站', 1, '2026-05-29 10:29:00', NULL, '2026-05-29 10:59:00', NULL, NULL, 66, 'MATCHED', 0, NULL, '2026-05-29 10:29:00', '13560004373', '2026-05-29 10:29:16', NULL, '1', '0');
INSERT INTO `bus_ride_request` VALUES (84, '2059902964167528449', NULL, '4a4034cb56ee42419de0774c29bf425f', 'ORD_20260529184206_666560', 113.314474, 23.150741, '沙河', 113.326576, 23.148611, '广州东站', 1, '2026-05-29 18:42:07', NULL, '2026-05-29 19:12:07', NULL, NULL, NULL, 'EXPIRED', 0, NULL, '2026-05-29 18:42:07', '13560004373', '2026-05-30 15:20:44', NULL, '1', '0');
INSERT INTO `bus_ride_request` VALUES (85, '2059902964167528449', NULL, '36f926d087754ff789f126747863d826', 'ORD_20260529184919_060096', 113.331482, 23.133003, '石牌桥地铁站口站', 113.331482, 23.133003, '石牌桥A口公交站', 1, '2026-05-29 18:49:24', NULL, '2026-05-29 19:19:24', NULL, NULL, NULL, 'EXPIRED', 0, NULL, '2026-05-29 18:49:24', '13560004373', '2026-05-30 15:20:44', NULL, '1', '0');
INSERT INTO `bus_ride_request` VALUES (86, '2059902964167528449', NULL, '585b3e1050844e24b0ff09dc45da1c5b', 'ORD_20260530105548_574848', 113.267, 23.128, '公园前站', 113.272, 23.122, '北京路站', 1, '2026-05-30 10:56:00', NULL, '2026-05-30 11:26:00', NULL, NULL, 67, 'MATCHED', 0, NULL, '2026-05-30 10:56:00', '13560004373', '2026-05-30 10:57:44', NULL, '1', '0');
INSERT INTO `bus_ride_request` VALUES (87, '2059902964167528449', NULL, '00941a0909924b40809e0b0ffde35323', 'ORD_20260530143555_709056', 113.267, 23.128, '公园前站', 113.272, 23.122, '北京路站', 1, '2026-05-30 14:35:57', NULL, '2026-05-30 15:05:57', NULL, NULL, NULL, 'EXPIRED', 0, NULL, '2026-05-30 14:35:57', '13560004373', '2026-05-30 15:20:44', NULL, '1', '0');
INSERT INTO `bus_ride_request` VALUES (88, '2053666005677953025', NULL, '778d8f49dad743428388346dffa60748', 'ORD_20260601153413_325632', 113.331482, 23.133003, '石牌桥地铁站口站', 113.331482, 23.133003, '石牌桥A口公交站', 1, '2026-06-01 15:34:25', NULL, '2026-06-01 16:04:25', NULL, NULL, NULL, 'WAITING', 0, NULL, '2026-06-01 15:34:25', '13560004373', '2026-06-01 15:34:25', NULL, '1', '0');
INSERT INTO `bus_ride_request` VALUES (89, '2053666005677953025', NULL, '70172de873f742a89940b130f098e7b4', 'ORD_20260601153544_931264', 113.331482, 23.133003, '石牌桥地铁站口站', 113.331482, 23.133003, '石牌桥A口公交站', 1, '2026-06-01 15:35:46', NULL, '2026-06-01 16:05:46', NULL, NULL, NULL, 'WAITING', 0, NULL, '2026-06-01 15:35:46', '13560004373', '2026-06-01 15:35:46', NULL, '1', '0');
INSERT INTO `bus_ride_request` VALUES (90, '2061296189767847937', NULL, '49ee96c52c624e3ebe7f427d635d2d78', 'ORD_20260601170930_935296', 113.314474, 23.150741, '沙河', 113.326576, 23.148611, '广州东站', 1, '2026-06-01 17:09:32', NULL, '2026-06-01 17:39:32', NULL, NULL, NULL, 'WAITING', 0, NULL, '2026-06-01 17:09:32', '13560004373', '2026-06-01 17:09:32', NULL, '1', '0');
INSERT INTO `bus_ride_request` VALUES (91, '2061296189767847937', NULL, '37877331c0684fcdbfbe0babec5fb44f', 'ORD_20260601182837_099136', 113.329806, 23.132025, '创展中心东座公交站', 113.32979, 23.132016, '创展中心西座公交站', 1, '2026-06-01 18:28:38', NULL, '2026-06-01 18:58:38', NULL, 17, NULL, 'GROUPED', 0, NULL, '2026-06-01 18:28:38', '13560004373', '2026-06-01 18:30:44', NULL, '1', '0');
INSERT INTO `bus_ride_request` VALUES (92, '2061296189767847937', NULL, '08bd1d827b794ca19c5139e7e80e1e9a', 'ORD_20260601183009_683584', 113.329806, 23.132025, '创展中心东座公交站', 113.32979, 23.132016, '创展中心西座公交站', 1, '2026-06-01 18:30:10', NULL, '2026-06-01 19:00:10', NULL, 17, NULL, 'GROUPED', 0, NULL, '2026-06-01 18:30:10', '13560004373', '2026-06-01 18:30:44', NULL, '1', '0');
INSERT INTO `bus_ride_request` VALUES (93, '2061296189767847937', NULL, '761d129cfd91409cac30a287b1c501fa', 'ORD_20260601183603_094656', 113.331482, 23.133003, '石牌桥地铁站口站', 113.32979, 23.132016, '创展中心西座公交站', 1, '2026-06-01 18:36:06', NULL, '2026-06-01 19:06:06', NULL, NULL, NULL, 'WAITING', 0, NULL, '2026-06-01 18:36:06', '13560004373', '2026-06-01 18:36:06', NULL, '1', '0');
INSERT INTO `bus_ride_request` VALUES (94, '2061296189767847937', NULL, '5fabc01d22c14e308f4da7bafff2f651', 'ORD_20260601184100_707392', 113.331482, 23.133003, '石牌桥地铁站口站', 113.329806, 23.132025, '创展中心东座公交站', 1, '2026-06-01 18:41:02', NULL, '2026-06-01 19:11:02', NULL, NULL, NULL, 'WAITING', 0, NULL, '2026-06-01 18:41:02', '13560004373', '2026-06-01 18:41:02', NULL, '1', '0');
INSERT INTO `bus_ride_request` VALUES (95, '2061647851355279361', NULL, 'cda653a49cca451cbce27bd0eb1073b1', 'ORD_20260602111622_013056', 113.331482, 23.133003, '石牌桥地铁站口站', 113.32979, 23.132016, '创展中心西座公交站', 1, '2026-06-02 11:16:25', NULL, '2026-06-02 11:46:25', NULL, NULL, NULL, 'WAITING', 0, NULL, '2026-06-02 11:16:25', '13560004373', '2026-06-02 11:16:25', NULL, '1', '0');

-- ----------------------------
-- Table structure for bus_route
-- ----------------------------
DROP TABLE IF EXISTS `bus_route`;
CREATE TABLE `bus_route`  (
  `id` bigint NOT NULL AUTO_INCREMENT COMMENT '主键ID',
  `route_id` varchar(32) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL COMMENT '线路ID（唯一）',
  `route_name` varchar(100) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL COMMENT '线路名称',
  `route_type` varchar(16) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NULL DEFAULT NULL COMMENT '线路类型',
  `org_code` varchar(32) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NULL DEFAULT NULL COMMENT '机构编码',
  `org_name` varchar(100) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NULL DEFAULT NULL COMMENT '机构名称',
  `area_code` varchar(32) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NULL DEFAULT NULL COMMENT '运营区域编码',
  `area_name` varchar(100) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NULL DEFAULT NULL COMMENT '运营区域名称',
  `station_count` int NULL DEFAULT 0 COMMENT '站点数量',
  `status` char(1) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NULL DEFAULT '0' COMMENT '状态：0-禁用，1-启用',
  `allow_standing` char(1) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NULL DEFAULT '0' COMMENT '是否允许站票：0-不允许，1-允许',
  `total_duration` int NULL DEFAULT 0 COMMENT '总时长（分钟）',
  `dept_id` bigint NULL DEFAULT NULL COMMENT '部门ID（数据权限）',
  `create_time` datetime NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
  `create_by` varchar(64) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NULL DEFAULT NULL COMMENT '创建人',
  `update_time` datetime NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
  `update_by` varchar(64) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NULL DEFAULT NULL COMMENT '更新人',
  `audit_time` datetime NULL DEFAULT NULL COMMENT '审核时间',
  `audit_by` varchar(64) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NULL DEFAULT NULL COMMENT '审核人',
  `tenant_id` bigint NULL DEFAULT NULL COMMENT '租户ID',
  PRIMARY KEY (`id`) USING BTREE,
  UNIQUE INDEX `uk_route_id`(`route_id` ASC) USING BTREE,
  INDEX `idx_route_name`(`route_name` ASC) USING BTREE,
  INDEX `idx_org_code`(`org_code` ASC) USING BTREE,
  INDEX `idx_area_code`(`area_code` ASC) USING BTREE,
  INDEX `idx_status`(`status` ASC) USING BTREE,
  INDEX `idx_create_time`(`create_time` ASC) USING BTREE
) ENGINE = InnoDB AUTO_INCREMENT = 3017 CHARACTER SET = utf8mb4 COLLATE = utf8mb4_unicode_ci COMMENT = '线路主表' ROW_FORMAT = DYNAMIC;

-- ----------------------------
-- Records of bus_route
-- ----------------------------
INSERT INTO `bus_route` VALUES (3, 'BUS001', '常规公交101路', NULL, '1', '智慧公交服务平台', 'GZ-LW-001', '荔湾区', 2, '1', '1', 5, NULL, '2026-03-29 15:02:25', 'admin', '2026-05-14 16:31:00', 'admin', '2026-04-30 15:42:07', 'admin', 1);
INSERT INTO `bus_route` VALUES (7, 'Test001', '测试线路', 'custom', '1', '智慧公交服务平台', NULL, NULL, 2, '1', '0', 0, NULL, '2026-04-08 10:25:19', 'admin', '2026-05-14 16:31:00', 'admin', '2026-04-30 15:42:07', 'admin', 1);
INSERT INTO `bus_route` VALUES (8, 'xx01', 'A线', 'custom', '1', '智慧公交服务平台', NULL, NULL, 2, '1', '1', 0, NULL, '2026-04-24 16:01:02', 'admin', '2026-05-19 11:42:09', 'admin', '2026-04-30 15:42:29', 'admin', 1);
INSERT INTO `bus_route` VALUES (13, 'A990', '990', 'normal', '1', '智慧公交服务平台', '0001', '天河区', 3, '1', '1', 0, NULL, '2026-05-13 14:14:14', 'admin', '2026-05-21 15:35:45', 'admin', '2026-04-30 15:42:29', 'admin', 1);
INSERT INTO `bus_route` VALUES (18, '101', '101路', 'custom', '1', '智慧公交服务平台', '0001', '天河区', 5, '1', '0', 0, NULL, '2026-05-20 16:34:01', 'admin', '2026-05-26 11:04:38', 'admin', '2026-05-21 15:37:19', 'admin', 1);
INSERT INTO `bus_route` VALUES (19, '234gfdg', '发顺丰', 'normal', '1', '智慧公交服务平台', '20260513', '创展中心区域', 2, '1', '0', 0, NULL, '2026-05-26 11:03:20', 'admin', '2026-05-26 11:03:55', 'admin', NULL, NULL, 1);
INSERT INTO `bus_route` VALUES (3001, 'R_GZ_201', '天河穿梭线 体育西-珠江新城', 'regular', 'ORG_001', '广州公交集团', 'GZ_TH_CORE', '天河核心区', 2, '1', '1', 15, NULL, '2026-05-27 10:57:27', 'system', '2026-05-27 10:57:27', NULL, NULL, NULL, 1);
INSERT INTO `bus_route` VALUES (3002, 'R_GZ_202', '海珠滨江线 广州塔-客村', 'regular', 'ORG_001', '广州公交集团', 'GZ_HZ_BIN', '海珠滨江带', 2, '1', '1', 12, NULL, '2026-05-27 10:57:27', 'system', '2026-05-27 10:57:27', NULL, NULL, NULL, 1);
INSERT INTO `bus_route` VALUES (3003, 'R_GZ_203', '大学城专线 大学城北-番禺广场', 'regular', 'ORG_001', '广州公交集团', 'GZ_PY_DXC', '番禺大学城', 2, '1', '0', 25, NULL, '2026-05-27 10:57:27', 'system', '2026-05-27 10:57:27', NULL, NULL, NULL, 1);
INSERT INTO `bus_route` VALUES (3004, 'R_GZ_204', '越秀经典线 公园前-北京路', 'regular', 'ORG_001', '广州公交集团', 'GZ_YX_OLD', '越秀老城区', 2, '1', '1', 10, NULL, '2026-05-27 10:57:27', 'system', '2026-05-27 10:57:27', NULL, NULL, NULL, 1);
INSERT INTO `bus_route` VALUES (3005, 'R_GZ_205', '荔湾风情线 陈家祠-长寿路', 'regular', 'ORG_001', '广州公交集团', 'GZ_LW_XG', '荔湾老西关', 2, '1', '1', 8, NULL, '2026-05-27 10:57:27', 'system', '2026-05-27 10:57:27', NULL, NULL, NULL, 1);
INSERT INTO `bus_route` VALUES (3006, 'R_GZ_206', '白云山专线 白云公园-白云山西门', 'regular', 'ORG_001', '广州公交集团', 'GZ_BY_SCENIC', '白云山风景区', 2, '0', '0', 20, NULL, '2026-05-27 10:57:27', 'system', '2026-05-27 10:57:27', NULL, NULL, NULL, 1);
INSERT INTO `bus_route` VALUES (3007, 'R_GZ_207', '黄埔产业线 香雪-萝岗', 'regular', 'ORG_001', '广州公交集团', 'GZ_HP_DEV', '黄埔开发区', 2, '0', '1', 18, NULL, '2026-05-27 10:57:27', 'system', '2026-05-27 10:57:27', NULL, NULL, NULL, 1);
INSERT INTO `bus_route` VALUES (3008, 'R_GZ_208', '南沙快线 蕉门-南沙客运港', 'regular', 'ORG_001', '广州公交集团', 'GZ_NS_FTA', '南沙自贸区', 2, '0', '0', 35, NULL, '2026-05-27 10:57:27', 'system', '2026-05-27 10:57:27', NULL, NULL, NULL, 1);
INSERT INTO `bus_route` VALUES (3009, 'R_GZ_209', '增城专线 新塘-白江', 'regular', 'ORG_001', '广州公交集团', 'GZ_ZC_XT', '增城新塘', 2, '0', '1', 15, NULL, '2026-05-27 10:57:27', 'system', '2026-05-27 10:57:27', NULL, NULL, NULL, 1);
INSERT INTO `bus_route` VALUES (3010, 'R_GZ_210', '花都机场线 机场南-花都广场', 'regular', 'ORG_001', '广州公交集团', 'GZ_HD_AIR', '花都空港区', 2, '1', '0', 22, NULL, '2026-05-27 10:57:27', 'system', '2026-05-27 10:57:27', NULL, NULL, NULL, 1);
INSERT INTO `bus_route` VALUES (3011, 'A0529', '0529线路', 'custom', '1', '智慧公交服务平台', '15', '天河体育中心', 5, '1', '1', 34, 1, '2026-05-29 10:16:29', 'admin', '2026-05-29 10:22:02', 'felix', '2026-05-29 10:16:48', 'admin', 1);
INSERT INTO `bus_route` VALUES (3012, 'line1', '线路1', 'normal', '1', '智慧公交服务平台', 'part1', '数据中心区域', 3, '0', '0', 0, 2059155512602853378, '2026-05-30 16:13:50', 'alex01', '2026-05-30 16:14:19', 'alex01', '2026-05-30 16:14:12', 'alex01', 1);
INSERT INTO `bus_route` VALUES (3013, 'line2', '线路2', 'normal', '1', '智慧公交服务平台', 'part1', '数据中心区域', 3, '0', '0', 0, 2059155512602853378, '2026-05-30 16:28:04', 'alex01', '2026-05-30 16:28:04', 'alex01', NULL, NULL, 1);
INSERT INTO `bus_route` VALUES (3014, 'RT000001', 'H测试线路', 'normal', '00008888', '广州巴士集团有限公司', '123456789_COPY', '天河南二路街道', 2, '1', '0', 0, 2059155512602853378, '2026-06-01 16:58:43', 'felix', '2026-06-01 16:58:55', 'felix', '2026-06-01 16:58:48', 'felix', 1);
INSERT INTO `bus_route` VALUES (3015, 'RT000002', 'H233', 'custom', '00008888', '广州巴士集团有限公司', '123456789_COPY', '天河南二路街道', 2, '1', '0', 0, 2059155512602853378, '2026-06-01 17:04:45', 'felix', '2026-06-01 17:04:45', 'felix', NULL, NULL, 1);
INSERT INTO `bus_route` VALUES (3016, 'RT000003', '测A13456', 'custom', '00008888', '广州巴士集团有限公司', 'AR000003', '汉溪长隆', 2, '1', '1', 0, 2059155512602853378, '2026-06-01 17:47:45', 'felix', '2026-06-01 17:47:53', 'felix', '2026-06-01 17:47:49', 'felix', 1);

-- ----------------------------
-- Table structure for bus_route_station
-- ----------------------------
DROP TABLE IF EXISTS `bus_route_station`;
CREATE TABLE `bus_route_station`  (
  `id` bigint NOT NULL AUTO_INCREMENT COMMENT '主键ID',
  `route_id` varchar(32) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL COMMENT '线路ID',
  `station_id` bigint NOT NULL COMMENT '站点ID',
  `station_name` varchar(100) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NULL DEFAULT NULL COMMENT '站点名称（冗余）',
  `station_address` varchar(200) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NULL DEFAULT NULL COMMENT '站点地址（冗余）',
  `longitude` decimal(10, 7) NULL DEFAULT NULL COMMENT '经度（冗余）',
  `latitude` decimal(10, 7) NULL DEFAULT NULL COMMENT '纬度（冗余）',
  `sequence` int NOT NULL DEFAULT 0 COMMENT '站点顺序',
  `duration_to_next` int NULL DEFAULT 0 COMMENT '到下一站时长（分钟）',
  `create_time` datetime NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
  `create_by` varchar(64) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NULL DEFAULT NULL COMMENT '创建人',
  `update_time` datetime NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
  `update_by` varchar(64) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NULL DEFAULT NULL COMMENT '更新人',
  `tenant_id` bigint NULL DEFAULT NULL COMMENT '租户ID',
  PRIMARY KEY (`id`) USING BTREE,
  UNIQUE INDEX `uk_route_station`(`route_id` ASC, `station_id` ASC) USING BTREE,
  INDEX `idx_route_id`(`route_id` ASC) USING BTREE,
  INDEX `idx_station_id`(`station_id` ASC) USING BTREE,
  INDEX `idx_sequence`(`sequence` ASC) USING BTREE
) ENGINE = InnoDB AUTO_INCREMENT = 137 CHARACTER SET = utf8mb4 COLLATE = utf8mb4_unicode_ci COMMENT = '线路站点关联表' ROW_FORMAT = DYNAMIC;

-- ----------------------------
-- Records of bus_route_station
-- ----------------------------
INSERT INTO `bus_route_station` VALUES (33, 'BUS001', 7, '中山八路2', '中山八路公交站2', 113.2352400, 23.1255530, 1, 5, '2026-04-07 13:27:16', 'admin', '2026-04-07 13:28:57', NULL, 1);
INSERT INTO `bus_route_station` VALUES (34, 'BUS001', 6, '中山八路公交站', '中山八路公交站', 113.2352400, 23.1255700, 2, 0, '2026-04-07 13:27:16', 'admin', '2026-04-07 13:28:57', NULL, 1);
INSERT INTO `bus_route_station` VALUES (62, 'Test001', 7, '中山八路2', '中山八路公交站2', 113.2352400, 23.1255530, 1, 0, '2026-04-30 17:55:52', 'admin', '2026-04-30 17:55:48', NULL, 1);
INSERT INTO `bus_route_station` VALUES (63, 'Test001', 6, '中山八路公交站', '中山八路公交站', 113.2352400, 23.1255700, 2, 0, '2026-04-30 17:55:52', 'admin', '2026-04-30 17:55:48', NULL, 1);
INSERT INTO `bus_route_station` VALUES (66, 'xx01', 9, '创展中心', 'e', 111.1317240, 21.9645880, 1, 0, '2026-04-30 17:56:27', 'admin', '2026-04-30 17:56:23', NULL, 1);
INSERT INTO `bus_route_station` VALUES (67, 'xx01', 7, '中山八路2', '中山八路公交站2', 113.2352400, 23.1255530, 2, 0, '2026-04-30 17:56:27', 'admin', '2026-04-30 17:56:23', NULL, 1);
INSERT INTO `bus_route_station` VALUES (74, 'A990', 10, '体育中心站', '天河区体育中心', 161.4610000, 26.1603000, 1, 0, '2026-05-13 14:14:14', 'admin', '2026-05-13 14:14:12', NULL, 1);
INSERT INTO `bus_route_station` VALUES (75, 'A990', 9, '创展中心', 'e', 111.1317240, 21.9645880, 2, 0, '2026-05-13 14:14:14', 'admin', '2026-05-13 14:14:12', NULL, 1);
INSERT INTO `bus_route_station` VALUES (76, 'A990', 6, '中山八路公交站', '中山八路公交站', 113.2352400, 23.1255700, 3, 0, '2026-05-13 14:14:14', 'admin', '2026-05-13 14:14:12', NULL, 1);
INSERT INTO `bus_route_station` VALUES (101, '101', 16, '体育中心地铁站', '体育中心地铁站A出口左前方50米', 113.5314830, 23.1514600, 1, 0, '2026-05-21 15:36:55', 'admin', '2026-05-21 15:36:51', NULL, 1);
INSERT INTO `bus_route_station` VALUES (102, '101', 18, '岗顶站', '岗顶', 113.5514850, 23.1617046, 2, 0, '2026-05-21 15:36:55', 'admin', '2026-05-21 15:36:51', NULL, 1);
INSERT INTO `bus_route_station` VALUES (103, '101', 19, '上社站', '上社', 113.7548600, 23.1814612, 3, 0, '2026-05-21 15:36:55', 'admin', '2026-05-21 15:36:51', NULL, 1);
INSERT INTO `bus_route_station` VALUES (104, '101', 17, '冼村站', '冼村站地铁站B出口前方10米', 113.6314840, 23.1858463, 4, 0, '2026-05-21 15:36:55', 'admin', '2026-05-21 15:36:51', NULL, 1);
INSERT INTO `bus_route_station` VALUES (105, '101', 13, '石牌桥地铁站口站', '石牌桥地铁站A出口左前方20米', 113.3314820, 23.1330030, 5, 0, '2026-05-21 15:36:55', 'admin', '2026-05-21 15:36:51', NULL, 1);
INSERT INTO `bus_route_station` VALUES (108, '234gfdg', 21, '广州南站公交站', '广州市番禺区石壁街道石壁村广州南站公交站', 113.8964151, 23.4616111, 1, 0, '2026-05-26 11:03:55', 'admin', '2026-05-26 11:03:48', NULL, 1);
INSERT INTO `bus_route_station` VALUES (109, '234gfdg', 13, '石牌桥地铁站口站', '石牌桥地铁站A出口左前方20米', 113.3314820, 23.1330030, 2, 0, '2026-05-26 11:03:55', 'admin', '2026-05-26 11:03:48', NULL, 1);
INSERT INTO `bus_route_station` VALUES (110, 'R_GZ_201', 2001, '体育西路站', NULL, 113.3215000, 23.1268000, 1, 8, '2026-05-27 10:57:33', NULL, '2026-05-27 10:57:33', NULL, 1);
INSERT INTO `bus_route_station` VALUES (111, 'R_GZ_201', 2002, '珠江新城站', NULL, 113.3220000, 23.1270000, 2, 0, '2026-05-27 10:57:33', NULL, '2026-05-27 10:57:33', NULL, 1);
INSERT INTO `bus_route_station` VALUES (112, 'R_GZ_202', 2003, '广州塔站', NULL, 113.3250000, 23.1090000, 1, 7, '2026-05-27 10:57:33', NULL, '2026-05-27 10:57:33', NULL, 1);
INSERT INTO `bus_route_station` VALUES (113, 'R_GZ_202', 2004, '客村站', NULL, 113.3175000, 23.1005000, 2, 0, '2026-05-27 10:57:33', NULL, '2026-05-27 10:57:33', NULL, 1);
INSERT INTO `bus_route_station` VALUES (114, 'R_GZ_203', 2005, '大学城北站', NULL, 113.3850000, 23.0580000, 1, 15, '2026-05-27 10:57:33', NULL, '2026-05-27 10:57:33', NULL, 1);
INSERT INTO `bus_route_station` VALUES (115, 'R_GZ_203', 2006, '番禺广场站', NULL, 113.3650000, 22.9450000, 2, 0, '2026-05-27 10:57:33', NULL, '2026-05-27 10:57:33', NULL, 1);
INSERT INTO `bus_route_station` VALUES (116, 'R_GZ_204', 2007, '公园前站', NULL, 113.2670000, 23.1280000, 1, 5, '2026-05-27 10:57:33', NULL, '2026-05-27 10:57:33', NULL, 1);
INSERT INTO `bus_route_station` VALUES (117, 'R_GZ_204', 2008, '北京路站', NULL, 113.2720000, 23.1220000, 2, 0, '2026-05-27 10:57:33', NULL, '2026-05-27 10:57:33', NULL, 1);
INSERT INTO `bus_route_station` VALUES (118, 'R_GZ_205', 2009, '陈家祠站', NULL, 113.2400000, 23.1240000, 1, 4, '2026-05-27 10:57:33', NULL, '2026-05-27 10:57:33', NULL, 1);
INSERT INTO `bus_route_station` VALUES (119, 'R_GZ_205', 2010, '长寿路站', NULL, 113.2420000, 23.1170000, 2, 0, '2026-05-27 10:57:33', NULL, '2026-05-27 10:57:33', NULL, 1);
INSERT INTO `bus_route_station` VALUES (120, 'A0529', 2007, '公园前站', '越秀区中山五路公园前地铁站', 113.2670000, 23.1280000, 1, 10, '2026-05-29 10:16:29', 'admin', '2026-05-29 10:16:21', NULL, 1);
INSERT INTO `bus_route_station` VALUES (121, 'A0529', 2010, '长寿路站', '荔湾区长寿路地铁站B口', 113.2420000, 23.1170000, 2, 9, '2026-05-29 10:16:29', 'admin', '2026-05-29 10:16:21', NULL, 1);
INSERT INTO `bus_route_station` VALUES (122, 'A0529', 2009, '陈家祠站', '荔湾区中山七路陈家祠地铁站', 113.2400000, 23.1240000, 3, 8, '2026-05-29 10:16:29', 'admin', '2026-05-29 10:16:21', NULL, 1);
INSERT INTO `bus_route_station` VALUES (123, 'A0529', 2008, '北京路站', '越秀区北京路步行街', 113.2720000, 23.1220000, 4, 7, '2026-05-29 10:16:29', 'admin', '2026-05-29 10:16:21', NULL, 1);
INSERT INTO `bus_route_station` VALUES (124, 'A0529', 2006, '番禺广场站', '番禺区番禺广场地铁站A口', 113.3650000, 22.9450000, 5, 0, '2026-05-29 10:16:29', 'admin', '2026-05-29 10:16:21', NULL, 1);
INSERT INTO `bus_route_station` VALUES (125, 'line1', 2021, '白云大厦', '数据中心', 113.2852090, 23.1203070, 1, 0, '2026-05-30 16:13:50', 'alex01', '2026-05-30 16:13:42', NULL, 1);
INSERT INTO `bus_route_station` VALUES (126, 'line1', 2020, '白云大厦', '白云大厦', 113.2852090, 23.1203070, 2, 0, '2026-05-30 16:13:50', 'alex01', '2026-05-30 16:13:42', NULL, 1);
INSERT INTO `bus_route_station` VALUES (127, 'line1', 2016, '广州火车站（草暖公园）总站', '环市西路158号', 113.2630000, 23.1485000, 3, 0, '2026-05-30 16:13:50', 'alex01', '2026-05-30 16:13:42', NULL, 1);
INSERT INTO `bus_route_station` VALUES (128, 'line2', 2021, '白云大厦', '数据中心', 113.2852090, 23.1203070, 1, 0, '2026-05-30 16:28:04', 'alex01', '2026-05-30 16:27:55', NULL, 1);
INSERT INTO `bus_route_station` VALUES (129, 'line2', 2020, '白云大厦', '白云大厦', 113.2852090, 23.1203070, 2, 0, '2026-05-30 16:28:04', 'alex01', '2026-05-30 16:27:55', NULL, 1);
INSERT INTO `bus_route_station` VALUES (130, 'line2', 2016, '广州火车站（草暖公园）总站', '环市西路158号', 113.2630000, 23.1485000, 3, 0, '2026-05-30 16:28:04', 'alex01', '2026-05-30 16:27:55', NULL, 1);
INSERT INTO `bus_route_station` VALUES (131, 'RT000001', 2012, '天河南一路', '天河南二路', 113.3297770, 23.1319380, 1, 0, '2026-06-01 16:58:43', 'felix', '2026-06-01 16:58:34', NULL, 1);
INSERT INTO `bus_route_station` VALUES (132, 'RT000001', 2013, '沙河', '沙河公交总站', 113.3144740, 23.1507410, 2, 0, '2026-06-01 16:58:43', 'felix', '2026-06-01 16:58:34', NULL, 1);
INSERT INTO `bus_route_station` VALUES (133, 'RT000002', 2013, '沙河', '沙河公交总站', 113.3144740, 23.1507410, 1, 0, '2026-06-01 17:04:45', 'felix', '2026-06-01 17:04:36', NULL, 1);
INSERT INTO `bus_route_station` VALUES (134, 'RT000002', 2012, '天河南一路', '天河南二路', 113.3297770, 23.1319380, 2, 0, '2026-06-01 17:04:45', 'felix', '2026-06-01 17:04:36', NULL, 1);
INSERT INTO `bus_route_station` VALUES (135, 'RT000003', 2024, '南村万博', '南村万博', 113.3470030, 23.0044250, 1, 0, '2026-06-01 17:47:45', 'felix', '2026-06-01 17:47:36', NULL, 1);
INSERT INTO `bus_route_station` VALUES (136, 'RT000003', 2023, '汉溪长隆', '汉溪长隆', 113.3298500, 22.9941830, 2, 0, '2026-06-01 17:47:45', 'felix', '2026-06-01 17:47:36', NULL, 1);

-- ----------------------------
-- Table structure for bus_schedule
-- ----------------------------
DROP TABLE IF EXISTS `bus_schedule`;
CREATE TABLE `bus_schedule`  (
  `id` bigint NOT NULL AUTO_INCREMENT COMMENT '主键',
  `driver_id` bigint NOT NULL COMMENT '司机ID',
  `driver_name` varchar(50) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci NOT NULL COMMENT '司机姓名',
  `driver_code` varchar(20) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci NULL DEFAULT NULL COMMENT '司机工号',
  `phone` varchar(20) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci NULL DEFAULT NULL COMMENT '手机号',
  `schedule_date` date NOT NULL COMMENT '排班日期',
  `status` varchar(10) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci NULL DEFAULT '0' COMMENT '状态：0-有效，1-无效',
  `shift_type` varchar(32) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci NOT NULL DEFAULT 'dynamic_bus' COMMENT '班次类型：dynamic_bus/custom_bus/rest/leave',
  `actual_check_in` datetime NULL DEFAULT NULL COMMENT '实际签到时间',
  `actual_check_out` datetime NULL DEFAULT NULL COMMENT '实际签退时间',
  `work_minutes` int NOT NULL DEFAULT 0 COMMENT '当日出勤分钟数',
  `completed_order_count` int NOT NULL DEFAULT 0 COMMENT '当日完成订单数',
  `attendance_status` varchar(32) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci NULL DEFAULT NULL COMMENT '考勤状态：normal/late/early_leave/absent/leave/rest/on_shift',
  `attendance_remark` varchar(255) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci NULL DEFAULT NULL COMMENT '考勤备注',
  `dept_id` bigint NULL DEFAULT NULL COMMENT '部门ID（数据权限）',
  `create_time` datetime NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
  `create_by` varchar(64) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci NULL DEFAULT NULL COMMENT '创建人',
  `update_time` datetime NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
  `update_by` varchar(64) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci NULL DEFAULT NULL COMMENT '更新人',
  `tenant_id` varchar(32) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci NULL DEFAULT NULL COMMENT '租户ID',
  `del_flag` varchar(1) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci NULL DEFAULT '0' COMMENT '删除标记',
  PRIMARY KEY (`id`) USING BTREE,
  INDEX `idx_bs_driver_date`(`driver_id` ASC, `schedule_date` ASC) USING BTREE,
  INDEX `idx_bs_phone`(`phone` ASC) USING BTREE,
  INDEX `idx_bs_status`(`status` ASC) USING BTREE,
  INDEX `idx_bs_tenant`(`tenant_id` ASC) USING BTREE
) ENGINE = InnoDB AUTO_INCREMENT = 121 CHARACTER SET = utf8mb4 COLLATE = utf8mb4_0900_ai_ci COMMENT = '排班主表' ROW_FORMAT = DYNAMIC;

-- ----------------------------
-- Records of bus_schedule
-- ----------------------------
INSERT INTO `bus_schedule` VALUES (1, 1, '郑育明', '6800D165', '13602441228', '2026-04-06', '0', 'dynamic_bus', NULL, NULL, 0, 0, NULL, NULL, NULL, '2026-04-06 22:10:27', 'admin', '2026-04-06 22:12:08', NULL, '1', '0');
INSERT INTO `bus_schedule` VALUES (2, 3, '李娜', '6800D167', '13900139000', '2026-04-08', '0', 'dynamic_bus', NULL, NULL, 0, 0, NULL, NULL, NULL, '2026-04-08 10:45:16', 'admin', '2026-04-08 10:47:02', NULL, '1', '0');
INSERT INTO `bus_schedule` VALUES (3, 2, '张伟', '6800D166', '13800138000', '2026-04-08', '0', 'dynamic_bus', NULL, NULL, 0, 0, NULL, NULL, NULL, '2026-04-08 10:45:16', 'admin', '2026-04-08 10:47:02', NULL, '1', '0');
INSERT INTO `bus_schedule` VALUES (4, 1, '郑育明', '6800D165', '13602441228', '2026-04-24', '0', 'dynamic_bus', NULL, NULL, 0, 0, NULL, NULL, NULL, '2026-04-24 16:06:16', 'admin', '2026-04-24 16:06:15', NULL, '1', '0');
INSERT INTO `bus_schedule` VALUES (5, 1, '郑育明', '6800D165', '13602441228', '2026-04-25', '0', 'dynamic_bus', NULL, NULL, 0, 0, NULL, NULL, NULL, '2026-04-24 16:06:16', 'admin', '2026-04-24 16:06:15', NULL, '1', '0');
INSERT INTO `bus_schedule` VALUES (6, 1, '郑育明', '6800D165', '13602441228', '2026-04-26', '0', 'dynamic_bus', NULL, NULL, 0, 0, NULL, NULL, NULL, '2026-04-24 16:06:16', 'admin', '2026-04-24 16:06:15', NULL, '1', '0');
INSERT INTO `bus_schedule` VALUES (7, 1, '郑育明', '6800D165', '13602441228', '2026-04-27', '0', 'dynamic_bus', NULL, NULL, 0, 0, NULL, NULL, NULL, '2026-04-24 16:06:16', 'admin', '2026-04-24 16:06:15', NULL, '1', '0');
INSERT INTO `bus_schedule` VALUES (8, 2, '张伟', '6800D166', '13800138000', '2026-04-30', '0', 'dynamic_bus', NULL, NULL, 0, 0, NULL, NULL, NULL, '2026-04-30 17:16:41', 'admin', '2026-04-30 17:16:37', NULL, '1', '0');
INSERT INTO `bus_schedule` VALUES (9, 2, '张伟', '6800D166', '13800138000', '2026-05-01', '0', 'dynamic_bus', NULL, NULL, 0, 0, NULL, NULL, NULL, '2026-04-30 17:16:41', 'admin', '2026-04-30 17:16:37', NULL, '1', '0');
INSERT INTO `bus_schedule` VALUES (10, 2, '张伟', '6800D166', '13800138000', '2026-05-02', '0', 'dynamic_bus', NULL, NULL, 0, 0, NULL, NULL, NULL, '2026-04-30 17:16:41', 'admin', '2026-04-30 17:16:37', NULL, '1', '0');
INSERT INTO `bus_schedule` VALUES (11, 2, '张伟', '6800D166', '13800138000', '2026-05-03', '0', 'dynamic_bus', NULL, NULL, 0, 0, NULL, NULL, NULL, '2026-04-30 17:16:41', 'admin', '2026-04-30 17:16:37', NULL, '1', '0');
INSERT INTO `bus_schedule` VALUES (12, 2, '张伟', '6800D166', '13800138000', '2026-05-04', '0', 'dynamic_bus', NULL, NULL, 0, 0, NULL, NULL, NULL, '2026-04-30 17:16:41', 'admin', '2026-04-30 17:16:37', NULL, '1', '0');
INSERT INTO `bus_schedule` VALUES (13, 2, '张伟', '6800D166', '13800138000', '2026-05-05', '0', 'dynamic_bus', NULL, NULL, 0, 0, NULL, NULL, NULL, '2026-04-30 17:16:41', 'admin', '2026-04-30 17:16:37', NULL, '1', '0');
INSERT INTO `bus_schedule` VALUES (14, 1, '郑育明', '6800D165', '13602441228', '2026-05-06', '0', 'dynamic_bus', NULL, NULL, 0, 0, NULL, NULL, NULL, '2026-05-06 14:25:00', 'admin', '2026-05-06 14:24:53', NULL, '1', '0');
INSERT INTO `bus_schedule` VALUES (15, 2, '张伟', '6800D166', '13800138000', '2026-05-06', '0', 'dynamic_bus', NULL, NULL, 0, 0, NULL, NULL, NULL, '2026-05-06 14:25:00', 'admin', '2026-05-06 14:24:53', NULL, '1', '0');
INSERT INTO `bus_schedule` VALUES (16, 3, '李娜', '6800D167', '13900139000', '2026-05-06', '0', 'dynamic_bus', NULL, NULL, 0, 0, NULL, NULL, NULL, '2026-05-06 14:25:00', 'admin', '2026-05-06 14:24:53', NULL, '1', '0');
INSERT INTO `bus_schedule` VALUES (17, 1, '郑育明', '6800D165', '13602441228', '2026-05-11', '0', 'dynamic_bus', NULL, NULL, 0, 0, NULL, NULL, NULL, '2026-05-11 15:01:21', 'admin', '2026-05-11 15:01:12', NULL, '1', '0');
INSERT INTO `bus_schedule` VALUES (18, 1, '郑育明', '6800D165', '13602441228', '2026-05-12', '0', 'dynamic_bus', NULL, NULL, 0, 0, NULL, NULL, NULL, '2026-05-11 15:01:21', 'admin', '2026-05-11 15:01:12', NULL, '1', '0');
INSERT INTO `bus_schedule` VALUES (19, 1, '郑育明', '6800D165', '13602441228', '2026-05-13', '0', 'dynamic_bus', NULL, NULL, 0, 0, NULL, NULL, NULL, '2026-05-11 15:01:21', 'admin', '2026-05-11 15:01:12', NULL, '1', '0');
INSERT INTO `bus_schedule` VALUES (20, 1, '郑育明', '6800D165', '13602441228', '2026-05-14', '0', 'dynamic_bus', NULL, NULL, 0, 0, NULL, NULL, NULL, '2026-05-11 15:01:21', 'admin', '2026-05-11 15:01:12', NULL, '1', '0');
INSERT INTO `bus_schedule` VALUES (21, 2, '张伟', '6800D166', '13800138000', '2026-05-13', '0', 'dynamic_bus', NULL, NULL, 0, 0, NULL, NULL, NULL, '2026-05-13 14:32:22', 'admin', '2026-05-13 14:32:20', NULL, '1', '0');
INSERT INTO `bus_schedule` VALUES (22, 2, '张伟', '6800D166', '13800138000', '2026-05-14', '0', 'dynamic_bus', NULL, NULL, 0, 0, NULL, NULL, NULL, '2026-05-14 10:50:42', 'admin', '2026-05-14 10:50:40', NULL, '1', '0');
INSERT INTO `bus_schedule` VALUES (23, 2, '张伟', '6800D166', '13800138000', '2026-05-15', '0', 'dynamic_bus', NULL, NULL, 0, 0, NULL, NULL, NULL, '2026-05-15 10:06:37', 'admin', '2026-05-15 10:06:35', NULL, '1', '0');
INSERT INTO `bus_schedule` VALUES (24, 5, '测试司机', 'DRV260513', '13432496353', '2026-05-18', '0', 'dynamic_bus', '2026-05-18 11:20:44', NULL, 0, 0, 'late', '签到迟到', NULL, '2026-05-18 10:44:42', 'admin', '2026-05-18 11:20:45', '13432496353', '1', '0');
INSERT INTO `bus_schedule` VALUES (25, 5, '测试司机', 'DRV260513', '13432496353', '2026-05-18', '0', 'dynamic_bus', NULL, NULL, 0, 0, NULL, NULL, NULL, '2026-05-18 14:49:44', 'admin', '2026-05-18 14:49:40', NULL, '1', '0');
INSERT INTO `bus_schedule` VALUES (26, 1, '郑育明', '00230909', '13432496353', '2026-05-18', '0', 'dynamic_bus', '2026-05-18 18:10:12', NULL, 0, 0, 'late', '签到迟到', NULL, '2026-05-18 14:53:49', 'admin', '2026-05-18 18:10:13', '13432496353', '1', '0');
INSERT INTO `bus_schedule` VALUES (27, 1, '郑育明', '00230909', '13432496353', '2026-05-20', '0', 'dynamic_bus', NULL, NULL, 0, 0, NULL, NULL, NULL, '2026-05-20 16:32:56', 'admin', '2026-05-21 15:08:18', 'admin', '1', '0');
INSERT INTO `bus_schedule` VALUES (30, 2, '张伟', '6800D166', '13800138000', '2026-05-21', '0', 'dynamic_bus', NULL, NULL, 0, 0, NULL, NULL, NULL, '2026-05-21 13:01:22', 'admin', '2026-05-21 13:01:17', NULL, '1', '0');
INSERT INTO `bus_schedule` VALUES (31, 1, '郑育明', '00230909', '13432496353', '2026-05-21', '0', 'dynamic_bus', NULL, NULL, 0, 0, NULL, NULL, NULL, '2026-05-21 14:50:14', 'admin', '2026-05-21 15:07:55', 'admin', '1', '0');
INSERT INTO `bus_schedule` VALUES (32, 3, '李娜', '6800D167', '13900139000', '2026-05-22', '0', 'dynamic_bus', NULL, NULL, 0, 0, NULL, NULL, NULL, '2026-05-21 15:06:40', 'admin', '2026-05-21 15:07:23', NULL, '1', '1');
INSERT INTO `bus_schedule` VALUES (33, 1, '郑育明', '00230909', '13432496353', '2026-05-22', '0', 'dynamic_bus', NULL, NULL, 0, 0, NULL, NULL, NULL, '2026-05-22 09:25:42', 'admin', '2026-05-22 09:25:37', NULL, '1', '0');
INSERT INTO `bus_schedule` VALUES (34, 1, '郑育明', '00230909', '13432496353', '2026-05-23', '0', 'dynamic_bus', NULL, NULL, 0, 0, NULL, NULL, NULL, '2026-05-22 09:25:42', 'admin', '2026-05-22 09:25:37', NULL, '1', '0');
INSERT INTO `bus_schedule` VALUES (35, 1, '郑育明', '00230909', '13432496353', '2026-05-24', '0', 'dynamic_bus', NULL, NULL, 0, 0, NULL, NULL, NULL, '2026-05-22 09:25:42', 'admin', '2026-05-22 09:25:37', NULL, '1', '0');
INSERT INTO `bus_schedule` VALUES (36, 1, '郑育明', '00230909', '13432496353', '2026-05-25', '0', 'dynamic_bus', '2026-05-25 09:58:44', NULL, 0, 0, 'late', '签到迟到', NULL, '2026-05-22 09:25:42', 'admin', '2026-05-25 09:58:45', '13432496353', '1', '0');
INSERT INTO `bus_schedule` VALUES (37, 1, '郑育明', '00230909', '13432496353', '2026-05-26', '0', 'dynamic_bus', '2026-05-26 10:24:04', NULL, 0, 0, 'late', '签到迟到', NULL, '2026-05-22 09:25:42', 'admin', '2026-05-26 10:24:05', '13432496353', '1', '0');
INSERT INTO `bus_schedule` VALUES (38, 1, '郑育明', '00230909', '13432496353', '2026-05-27', '0', 'dynamic_bus', NULL, NULL, 0, 0, NULL, NULL, NULL, '2026-05-22 09:25:42', 'admin', '2026-05-22 09:25:37', NULL, '1', '0');
INSERT INTO `bus_schedule` VALUES (39, 1, '郑育明', '00230909', '13432496353', '2026-05-28', '0', 'dynamic_bus', '2026-05-28 17:06:16', '2026-05-28 17:06:37', 0, 0, 'early_leave', '早退', NULL, '2026-05-22 09:25:42', 'admin', '2026-05-28 17:06:39', '13432496353', '1', '0');
INSERT INTO `bus_schedule` VALUES (40, 1, '郑育明', '00230909', '13432496353', '2026-05-29', '0', 'dynamic_bus', '2026-05-29 15:31:46', NULL, 0, 0, 'late', '签到迟到', NULL, '2026-05-22 09:25:42', 'admin', '2026-05-29 15:31:48', '13432496353', '1', '0');
INSERT INTO `bus_schedule` VALUES (41, 4, '范工', 'DRV260522', '13802402145', '2026-05-22', '0', 'dynamic_bus', '2026-05-22 15:24:54', NULL, 0, 0, 'late', '签到迟到', NULL, '2026-05-22 14:12:57', 'admin', '2026-05-22 15:24:55', '13802402145', '1', '0');
INSERT INTO `bus_schedule` VALUES (42, 5, '刘罗瑞', 'DRV260513', '13652944754', '2026-05-22', '0', 'dynamic_bus', '2026-05-22 16:48:59', NULL, 0, 0, 'late', '签到迟到', NULL, '2026-05-22 16:48:58', 'admin', '2026-05-22 16:49:01', '13652944754', '1', '0');
INSERT INTO `bus_schedule` VALUES (43, 4, '范工', 'DRV260522', '13802402145', '2026-05-25', '0', 'dynamic_bus', NULL, NULL, 0, 0, NULL, NULL, NULL, '2026-05-25 14:53:30', 'admin', '2026-05-25 14:53:23', NULL, '1', '0');
INSERT INTO `bus_schedule` VALUES (44, 5, '刘罗瑞', 'DRV260513', '13652944754', '2026-05-25', '0', 'dynamic_bus', '2026-05-25 16:28:04', NULL, 0, 0, 'late', '签到迟到', NULL, '2026-05-25 16:27:59', 'admin', '2026-05-26 10:59:32', 'admin', '1', '0');
INSERT INTO `bus_schedule` VALUES (45, 5, '刘罗瑞', 'DRV260513', '13652944754', '2026-05-27', '0', 'dynamic_bus', '2026-05-27 09:36:39', '2026-05-27 09:38:57', 2, 0, 'early_leave', '早退', NULL, '2026-05-27 09:34:17', 'admin', '2026-05-27 10:24:41', 'admin', '1', '0');
INSERT INTO `bus_schedule` VALUES (101, 2001, '陈伟强', 'GZ02001', '13800020001', '2026-05-27', '0', 'dynamic_bus', NULL, NULL, 480, 8, 'normal', NULL, NULL, '2026-05-27 10:58:38', NULL, '2026-05-27 10:58:38', NULL, '1', '0');
INSERT INTO `bus_schedule` VALUES (102, 2002, '李俊杰', 'GZ02002', '13800020002', '2026-05-27', '0', 'dynamic_bus', NULL, NULL, 480, 7, 'normal', NULL, NULL, '2026-05-27 10:58:38', NULL, '2026-05-27 10:58:38', NULL, '1', '0');
INSERT INTO `bus_schedule` VALUES (103, 2003, '王美芳', 'GZ02003', '13800020003', '2026-05-27', '0', 'custom_bus', NULL, NULL, 360, 5, 'normal', NULL, NULL, '2026-05-27 10:58:38', NULL, '2026-05-27 10:58:38', NULL, '1', '0');
INSERT INTO `bus_schedule` VALUES (104, 2004, '张建平', 'GZ02004', '13800020004', '2026-05-27', '0', 'dynamic_bus', NULL, NULL, 420, 6, 'late', NULL, NULL, '2026-05-27 10:58:38', NULL, '2026-05-27 10:58:38', NULL, '1', '0');
INSERT INTO `bus_schedule` VALUES (105, 2005, '刘淑华', 'GZ02005', '13800020005', '2026-05-27', '0', 'dynamic_bus', NULL, NULL, 300, 3, 'normal', NULL, NULL, '2026-05-27 10:58:38', NULL, '2026-05-27 10:58:38', NULL, '1', '0');
INSERT INTO `bus_schedule` VALUES (106, 2006, '黄志强', 'GZ02006', '13800020006', '2026-05-28', '0', 'dynamic_bus', NULL, NULL, 480, 0, 'normal', NULL, NULL, '2026-05-27 10:58:38', NULL, '2026-05-27 10:58:38', NULL, '1', '0');
INSERT INTO `bus_schedule` VALUES (107, 2007, '吴敏仪', 'GZ02007', '13800020007', '2026-05-28', '0', 'custom_bus', NULL, NULL, 420, 0, 'normal', NULL, NULL, '2026-05-27 10:58:38', NULL, '2026-05-27 10:58:38', NULL, '1', '0');
INSERT INTO `bus_schedule` VALUES (108, 2008, '林振华', 'GZ02008', '13800020008', '2026-05-28', '0', 'dynamic_bus', NULL, NULL, 480, 0, 'normal', NULL, NULL, '2026-05-27 10:58:38', NULL, '2026-05-27 10:58:38', NULL, '1', '0');
INSERT INTO `bus_schedule` VALUES (109, 2009, '郭志勇', 'GZ02009', '13800020009', '2026-05-29', '0', 'dynamic_bus', NULL, NULL, 480, 0, 'normal', NULL, NULL, '2026-05-27 10:58:38', NULL, '2026-05-27 10:58:38', NULL, '1', '0');
INSERT INTO `bus_schedule` VALUES (110, 2010, '梁淑芬', 'GZ02010', '13800020010', '2026-05-29', '0', 'dynamic_bus', NULL, NULL, 0, 0, 'absent', NULL, NULL, '2026-05-27 10:58:38', NULL, '2026-05-27 10:58:38', NULL, '1', '0');
INSERT INTO `bus_schedule` VALUES (111, 2009, '郭志勇', 'GZ02009', '13042071722', '2026-05-28', '0', 'dynamic_bus', '2026-05-28 17:54:19', NULL, 0, 0, 'late', '签到迟到', 1, '2026-05-28 15:33:59', 'admin', '2026-05-28 17:54:21', '13042071722', '1', '0');
INSERT INTO `bus_schedule` VALUES (112, 2009, '郭志勇', 'GZ02009', '13042071722', '2026-05-29', '0', 'dynamic_bus', '2026-05-29 09:34:22', NULL, 0, 0, 'late', '签到迟到', 1, '2026-05-29 09:23:58', 'admin', '2026-05-29 09:34:24', '13042071722', '1', '0');
INSERT INTO `bus_schedule` VALUES (113, 2011, '鸿聪测试', '00018888', '13533746722', '2026-05-29', '0', 'dynamic_bus', NULL, NULL, 0, 0, NULL, NULL, 2059155512602853378, '2026-05-29 16:45:23', 'felix', '2026-05-29 16:45:15', NULL, '1', '0');
INSERT INTO `bus_schedule` VALUES (114, 2012, '刘测试', '00028888', '19102053473', '2026-05-29', '0', 'dynamic_bus', '2026-05-29 18:48:37', NULL, 0, 0, 'late', '签到迟到', 1, '2026-05-29 18:35:53', 'admin', '2026-05-29 18:48:39', '19102053473', '1', '0');
INSERT INTO `bus_schedule` VALUES (115, 2012, '刘测试', '00028888', '19102053473', '2026-05-30', '0', 'dynamic_bus', '2026-05-30 10:26:46', NULL, 0, 0, 'late', '签到迟到', 1, '2026-05-30 10:26:29', 'admin', '2026-05-30 10:26:48', '19102053473', '1', '0');
INSERT INTO `bus_schedule` VALUES (116, 2012, '刘测试', '00028888', '19102053473', '2026-05-31', '0', 'dynamic_bus', '2026-05-31 09:50:25', '2026-05-31 09:58:55', 8, 0, 'early_leave', '早退', 1, '2026-05-31 09:50:23', 'admin', '2026-05-31 09:58:57', '19102053473', '1', '0');
INSERT INTO `bus_schedule` VALUES (117, 2011, '鸿聪测试', '00018888', '13533746722', '2026-06-01', '0', 'dynamic_bus', NULL, NULL, 0, 0, NULL, NULL, 2059155512602853378, '2026-06-01 09:16:29', 'felix', '2026-06-01 09:16:20', NULL, '1', '0');
INSERT INTO `bus_schedule` VALUES (118, 2012, '刘测试', '00028888', '19102053473', '2026-06-01', '0', 'dynamic_bus', '2026-06-01 14:35:12', NULL, 0, 0, 'late', '签到迟到', 2061273631362301953, '2026-06-01 14:06:35', 'admin', '2026-06-01 14:35:15', '19102053473', '1', '0');
INSERT INTO `bus_schedule` VALUES (119, 2014, '鸿聪测试', '00018886', '13533746715', '2026-06-01', '0', 'dynamic_bus', '2026-06-01 15:34:09', NULL, 0, 0, 'late', '签到迟到', 2059155512602853378, '2026-06-01 14:59:45', 'felix', '2026-06-01 15:34:11', '13533746715', '1', '0');
INSERT INTO `bus_schedule` VALUES (120, 2015, '杨测试', '88885566', '13417037248', '2026-06-02', '0', 'dynamic_bus', '2026-06-02 10:12:04', NULL, 0, 0, 'late', '签到迟到', 2061273631362301953, '2026-06-02 09:49:01', 'admin', '2026-06-02 10:12:07', '13417037248', '1', '0');

-- ----------------------------
-- Table structure for bus_schedule_route
-- ----------------------------
DROP TABLE IF EXISTS `bus_schedule_route`;
CREATE TABLE `bus_schedule_route`  (
  `id` bigint NOT NULL AUTO_INCREMENT COMMENT '主键',
  `schedule_id` bigint NOT NULL COMMENT '排班ID',
  `route_id` bigint NULL DEFAULT NULL COMMENT '线路ID',
  `route_name` varchar(100) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci NULL DEFAULT NULL COMMENT '线路名称',
  `route_type` varchar(20) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci NULL DEFAULT NULL COMMENT '线路类型',
  `start_station` varchar(100) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci NULL DEFAULT NULL COMMENT '起点站',
  `end_station` varchar(100) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci NULL DEFAULT NULL COMMENT '终点站',
  `create_time` datetime NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
  `create_by` varchar(64) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci NULL DEFAULT NULL COMMENT '创建人',
  `update_time` datetime NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
  `update_by` varchar(64) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci NULL DEFAULT NULL COMMENT '更新人',
  `tenant_id` varchar(32) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci NULL DEFAULT NULL COMMENT '租户ID',
  `del_flag` varchar(1) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci NULL DEFAULT '0' COMMENT '删除标记',
  PRIMARY KEY (`id`) USING BTREE,
  INDEX `idx_bsr_schedule`(`schedule_id` ASC) USING BTREE
) ENGINE = InnoDB AUTO_INCREMENT = 11 CHARACTER SET = utf8mb4 COLLATE = utf8mb4_0900_ai_ci COMMENT = '排班关联线路表' ROW_FORMAT = DYNAMIC;

-- ----------------------------
-- Records of bus_schedule_route
-- ----------------------------
INSERT INTO `bus_schedule_route` VALUES (1, 101, 3001, '天河穿梭线 体育西-珠江新城', 'regular', '体育西路站', '珠江新城站', '2026-05-27 11:00:16', NULL, '2026-05-27 11:00:16', NULL, '1', '0');
INSERT INTO `bus_schedule_route` VALUES (2, 102, 3002, '海珠滨江线 广州塔-客村', 'regular', '广州塔站', '客村站', '2026-05-27 11:00:16', NULL, '2026-05-27 11:00:16', NULL, '1', '0');
INSERT INTO `bus_schedule_route` VALUES (3, 103, 3004, '越秀经典线 公园前-北京路', 'regular', '公园前站', '北京路站', '2026-05-27 11:00:16', NULL, '2026-05-27 11:00:16', NULL, '1', '0');
INSERT INTO `bus_schedule_route` VALUES (4, 104, 3005, '荔湾风情线 陈家祠-长寿路', 'regular', '陈家祠站', '长寿路站', '2026-05-27 11:00:16', NULL, '2026-05-27 11:00:16', NULL, '1', '0');
INSERT INTO `bus_schedule_route` VALUES (5, 105, 3003, '大学城专线 大学城北-番禺广场', 'regular', '大学城北站', '番禺广场站', '2026-05-27 11:00:16', NULL, '2026-05-27 11:00:16', NULL, '1', '0');
INSERT INTO `bus_schedule_route` VALUES (6, 106, 3001, '天河穿梭线 体育西-珠江新城', 'regular', '体育西路站', '珠江新城站', '2026-05-27 11:00:16', NULL, '2026-05-27 11:00:16', NULL, '1', '0');
INSERT INTO `bus_schedule_route` VALUES (7, 107, 3004, '越秀经典线 公园前-北京路', 'regular', '公园前站', '北京路站', '2026-05-27 11:00:16', NULL, '2026-05-27 11:00:16', NULL, '1', '0');
INSERT INTO `bus_schedule_route` VALUES (8, 108, 3003, '大学城专线 大学城北-番禺广场', 'regular', '大学城北站', '番禺广场站', '2026-05-27 11:00:16', NULL, '2026-05-27 11:00:16', NULL, '1', '0');
INSERT INTO `bus_schedule_route` VALUES (9, 109, 3010, '花都机场线 机场南-花都广场', 'regular', '机场南站', '花都广场站', '2026-05-27 11:00:16', NULL, '2026-05-27 11:00:16', NULL, '1', '0');
INSERT INTO `bus_schedule_route` VALUES (10, 110, 3005, '荔湾风情线 陈家祠-长寿路', 'regular', '陈家祠站', '长寿路站', '2026-05-27 11:00:16', NULL, '2026-05-27 11:00:16', NULL, '1', '0');

-- ----------------------------
-- Table structure for bus_schedule_time_slot
-- ----------------------------
DROP TABLE IF EXISTS `bus_schedule_time_slot`;
CREATE TABLE `bus_schedule_time_slot`  (
  `id` bigint NOT NULL AUTO_INCREMENT COMMENT '主键',
  `schedule_id` bigint NOT NULL COMMENT '排班ID',
  `start_time` varchar(5) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci NOT NULL COMMENT '开始时间 HH:mm',
  `end_time` varchar(5) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci NOT NULL COMMENT '结束时间 HH:mm',
  `create_time` datetime NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
  `create_by` varchar(64) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci NULL DEFAULT NULL COMMENT '创建人',
  `update_time` datetime NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
  `update_by` varchar(64) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci NULL DEFAULT NULL COMMENT '更新人',
  `tenant_id` varchar(32) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci NULL DEFAULT NULL COMMENT '租户ID',
  `del_flag` varchar(1) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci NULL DEFAULT '0' COMMENT '删除标记',
  PRIMARY KEY (`id`) USING BTREE,
  INDEX `idx_bsts_schedule`(`schedule_id` ASC) USING BTREE,
  INDEX `idx_bsts_tenant`(`tenant_id` ASC) USING BTREE
) ENGINE = InnoDB AUTO_INCREMENT = 83 CHARACTER SET = utf8mb4 COLLATE = utf8mb4_0900_ai_ci COMMENT = '排班时间段表' ROW_FORMAT = DYNAMIC;

-- ----------------------------
-- Records of bus_schedule_time_slot
-- ----------------------------
INSERT INTO `bus_schedule_time_slot` VALUES (1, 1, '22:09', '23:09', '2026-04-06 22:10:27', 'admin', '2026-04-06 22:12:08', NULL, '1', '0');
INSERT INTO `bus_schedule_time_slot` VALUES (2, 2, '10:45', '12:45', '2026-04-08 10:45:16', 'admin', '2026-04-08 10:47:02', NULL, '1', '0');
INSERT INTO `bus_schedule_time_slot` VALUES (3, 3, '10:45', '12:45', '2026-04-08 10:45:16', 'admin', '2026-04-08 10:47:02', NULL, '1', '0');
INSERT INTO `bus_schedule_time_slot` VALUES (4, 4, '16:06', '22:06', '2026-04-24 16:06:16', 'admin', '2026-04-24 16:06:15', NULL, '1', '0');
INSERT INTO `bus_schedule_time_slot` VALUES (5, 5, '16:06', '22:06', '2026-04-24 16:06:16', 'admin', '2026-04-24 16:06:15', NULL, '1', '0');
INSERT INTO `bus_schedule_time_slot` VALUES (6, 6, '16:06', '22:06', '2026-04-24 16:06:16', 'admin', '2026-04-24 16:06:15', NULL, '1', '0');
INSERT INTO `bus_schedule_time_slot` VALUES (7, 7, '16:06', '22:06', '2026-04-24 16:06:16', 'admin', '2026-04-24 16:06:15', NULL, '1', '0');
INSERT INTO `bus_schedule_time_slot` VALUES (8, 8, '09:00', '18:00', '2026-04-30 17:16:41', 'admin', '2026-04-30 17:16:37', NULL, '1', '0');
INSERT INTO `bus_schedule_time_slot` VALUES (9, 9, '09:00', '18:00', '2026-04-30 17:16:41', 'admin', '2026-04-30 17:16:37', NULL, '1', '0');
INSERT INTO `bus_schedule_time_slot` VALUES (10, 10, '09:00', '18:00', '2026-04-30 17:16:41', 'admin', '2026-04-30 17:16:37', NULL, '1', '0');
INSERT INTO `bus_schedule_time_slot` VALUES (11, 11, '09:00', '18:00', '2026-04-30 17:16:41', 'admin', '2026-04-30 17:16:37', NULL, '1', '0');
INSERT INTO `bus_schedule_time_slot` VALUES (12, 12, '09:00', '18:00', '2026-04-30 17:16:41', 'admin', '2026-04-30 17:16:37', NULL, '1', '0');
INSERT INTO `bus_schedule_time_slot` VALUES (13, 13, '09:00', '18:00', '2026-04-30 17:16:41', 'admin', '2026-04-30 17:16:37', NULL, '1', '0');
INSERT INTO `bus_schedule_time_slot` VALUES (14, 14, '14:25', '16:25', '2026-05-06 14:25:00', 'admin', '2026-05-06 14:24:53', NULL, '1', '0');
INSERT INTO `bus_schedule_time_slot` VALUES (15, 15, '14:25', '16:25', '2026-05-06 14:25:00', 'admin', '2026-05-06 14:24:53', NULL, '1', '0');
INSERT INTO `bus_schedule_time_slot` VALUES (16, 16, '14:25', '16:25', '2026-05-06 14:25:00', 'admin', '2026-05-06 14:24:53', NULL, '1', '0');
INSERT INTO `bus_schedule_time_slot` VALUES (17, 17, '15:01', '23:06', '2026-05-11 15:01:21', 'admin', '2026-05-11 15:01:12', NULL, '1', '0');
INSERT INTO `bus_schedule_time_slot` VALUES (18, 18, '15:01', '23:06', '2026-05-11 15:01:21', 'admin', '2026-05-11 15:01:12', NULL, '1', '0');
INSERT INTO `bus_schedule_time_slot` VALUES (19, 19, '15:01', '23:06', '2026-05-11 15:01:21', 'admin', '2026-05-11 15:01:12', NULL, '1', '0');
INSERT INTO `bus_schedule_time_slot` VALUES (20, 20, '15:01', '23:06', '2026-05-11 15:01:21', 'admin', '2026-05-11 15:01:12', NULL, '1', '0');
INSERT INTO `bus_schedule_time_slot` VALUES (21, 21, '10:30', '20:30', '2026-05-13 14:32:22', 'admin', '2026-05-13 14:32:20', NULL, '1', '0');
INSERT INTO `bus_schedule_time_slot` VALUES (22, 22, '10:50', '22:50', '2026-05-14 10:50:42', 'admin', '2026-05-14 10:50:40', NULL, '1', '0');
INSERT INTO `bus_schedule_time_slot` VALUES (23, 23, '10:00', '19:00', '2026-05-15 10:06:37', 'admin', '2026-05-15 10:06:35', NULL, '1', '0');
INSERT INTO `bus_schedule_time_slot` VALUES (24, 24, '10:39', '11:39', '2026-05-18 10:44:42', 'admin', '2026-05-18 10:44:38', NULL, '1', '0');
INSERT INTO `bus_schedule_time_slot` VALUES (25, 25, '14:49', '22:49', '2026-05-18 14:49:44', 'admin', '2026-05-18 14:49:40', NULL, '1', '0');
INSERT INTO `bus_schedule_time_slot` VALUES (26, 26, '14:49', '22:49', '2026-05-18 14:53:49', 'admin', '2026-05-18 14:53:46', NULL, '1', '0');
INSERT INTO `bus_schedule_time_slot` VALUES (27, 27, '16:34', '20:34', '2026-05-20 16:32:56', 'admin', '2026-05-21 15:08:13', NULL, '1', '1');
INSERT INTO `bus_schedule_time_slot` VALUES (28, 28, '09:34', '12:00', '2026-05-21 09:33:33', 'admin', '2026-05-21 09:33:29', NULL, '1', '0');
INSERT INTO `bus_schedule_time_slot` VALUES (29, 28, '13:30', '17:30', '2026-05-21 09:33:33', 'admin', '2026-05-21 09:33:29', NULL, '1', '0');
INSERT INTO `bus_schedule_time_slot` VALUES (30, 29, '10:30', '21:30', '2026-05-21 09:33:38', 'admin', '2026-05-21 09:33:33', NULL, '1', '0');
INSERT INTO `bus_schedule_time_slot` VALUES (31, 30, '14:00', '17:30', '2026-05-21 13:01:22', 'admin', '2026-05-21 13:01:17', NULL, '1', '0');
INSERT INTO `bus_schedule_time_slot` VALUES (32, 31, '14:51', '15:30', '2026-05-21 14:50:14', 'admin', '2026-05-21 15:07:50', NULL, '1', '1');
INSERT INTO `bus_schedule_time_slot` VALUES (33, 32, '08:00', '18:00', '2026-05-21 15:06:40', 'admin', '2026-05-21 15:07:23', NULL, '1', '1');
INSERT INTO `bus_schedule_time_slot` VALUES (34, 31, '14:51', '15:30', '2026-05-21 15:07:55', 'admin', '2026-05-21 15:07:50', NULL, '1', '0');
INSERT INTO `bus_schedule_time_slot` VALUES (35, 31, '15:30', '23:00', '2026-05-21 15:07:55', 'admin', '2026-05-21 15:07:50', NULL, '1', '0');
INSERT INTO `bus_schedule_time_slot` VALUES (36, 27, '16:34', '20:34', '2026-05-21 15:08:18', 'admin', '2026-05-21 15:08:13', NULL, '1', '0');
INSERT INTO `bus_schedule_time_slot` VALUES (37, 27, '17:00', '23:00', '2026-05-21 15:08:18', 'admin', '2026-05-21 15:08:13', NULL, '1', '0');
INSERT INTO `bus_schedule_time_slot` VALUES (38, 33, '09:00', '11:30', '2026-05-22 09:25:42', 'admin', '2026-05-22 09:25:37', NULL, '1', '0');
INSERT INTO `bus_schedule_time_slot` VALUES (39, 33, '14:00', '17:30', '2026-05-22 09:25:42', 'admin', '2026-05-22 09:25:37', NULL, '1', '0');
INSERT INTO `bus_schedule_time_slot` VALUES (40, 34, '09:00', '11:30', '2026-05-22 09:25:42', 'admin', '2026-05-22 09:25:37', NULL, '1', '0');
INSERT INTO `bus_schedule_time_slot` VALUES (41, 34, '14:00', '17:30', '2026-05-22 09:25:42', 'admin', '2026-05-22 09:25:37', NULL, '1', '0');
INSERT INTO `bus_schedule_time_slot` VALUES (42, 35, '09:00', '11:30', '2026-05-22 09:25:42', 'admin', '2026-05-22 09:25:37', NULL, '1', '0');
INSERT INTO `bus_schedule_time_slot` VALUES (43, 35, '14:00', '17:30', '2026-05-22 09:25:42', 'admin', '2026-05-22 09:25:37', NULL, '1', '0');
INSERT INTO `bus_schedule_time_slot` VALUES (44, 36, '09:00', '11:30', '2026-05-22 09:25:42', 'admin', '2026-05-22 09:25:37', NULL, '1', '0');
INSERT INTO `bus_schedule_time_slot` VALUES (45, 36, '14:00', '17:30', '2026-05-22 09:25:42', 'admin', '2026-05-22 09:25:37', NULL, '1', '0');
INSERT INTO `bus_schedule_time_slot` VALUES (46, 37, '09:00', '11:30', '2026-05-22 09:25:42', 'admin', '2026-05-22 09:25:37', NULL, '1', '0');
INSERT INTO `bus_schedule_time_slot` VALUES (47, 37, '14:00', '17:30', '2026-05-22 09:25:42', 'admin', '2026-05-22 09:25:37', NULL, '1', '0');
INSERT INTO `bus_schedule_time_slot` VALUES (48, 38, '09:00', '11:30', '2026-05-22 09:25:42', 'admin', '2026-05-22 09:25:37', NULL, '1', '0');
INSERT INTO `bus_schedule_time_slot` VALUES (49, 38, '14:00', '17:30', '2026-05-22 09:25:42', 'admin', '2026-05-22 09:25:37', NULL, '1', '0');
INSERT INTO `bus_schedule_time_slot` VALUES (50, 39, '09:00', '11:30', '2026-05-22 09:25:42', 'admin', '2026-05-22 09:25:37', NULL, '1', '0');
INSERT INTO `bus_schedule_time_slot` VALUES (51, 39, '14:00', '17:30', '2026-05-22 09:25:42', 'admin', '2026-05-22 09:25:37', NULL, '1', '0');
INSERT INTO `bus_schedule_time_slot` VALUES (52, 40, '09:00', '11:30', '2026-05-22 09:25:42', 'admin', '2026-05-22 09:25:37', NULL, '1', '0');
INSERT INTO `bus_schedule_time_slot` VALUES (53, 40, '14:00', '17:30', '2026-05-22 09:25:42', 'admin', '2026-05-22 09:25:37', NULL, '1', '0');
INSERT INTO `bus_schedule_time_slot` VALUES (54, 41, '14:12', '23:12', '2026-05-22 14:12:57', 'admin', '2026-05-22 14:12:52', NULL, '1', '0');
INSERT INTO `bus_schedule_time_slot` VALUES (55, 42, '14:12', '23:12', '2026-05-22 16:48:58', 'admin', '2026-05-22 16:48:53', NULL, '1', '0');
INSERT INTO `bus_schedule_time_slot` VALUES (56, 43, '14:53', '23:53', '2026-05-25 14:53:30', 'admin', '2026-05-25 14:53:23', NULL, '1', '0');
INSERT INTO `bus_schedule_time_slot` VALUES (57, 44, '16:27', '23:27', '2026-05-25 16:27:59', 'admin', '2026-05-25 17:08:46', NULL, '1', '1');
INSERT INTO `bus_schedule_time_slot` VALUES (58, 44, '16:27', '16:30', '2026-05-25 17:08:53', 'admin', '2026-05-26 10:59:18', NULL, '1', '1');
INSERT INTO `bus_schedule_time_slot` VALUES (59, 44, '16:27', '16:30', '2026-05-26 10:59:25', 'admin', '2026-05-26 10:59:25', NULL, '1', '1');
INSERT INTO `bus_schedule_time_slot` VALUES (60, 44, '16:27', '16:30', '2026-05-26 10:59:32', 'admin', '2026-05-26 10:59:25', NULL, '1', '0');
INSERT INTO `bus_schedule_time_slot` VALUES (61, 45, '09:00', '18:00', '2026-05-27 09:34:17', 'admin', '2026-05-27 10:24:34', NULL, '1', '1');
INSERT INTO `bus_schedule_time_slot` VALUES (62, 45, '09:00', '10:00', '2026-05-27 10:24:41', 'admin', '2026-05-27 10:24:34', NULL, '1', '0');
INSERT INTO `bus_schedule_time_slot` VALUES (63, 101, '07:00', '11:00', '2026-05-27 11:00:21', NULL, '2026-05-27 11:00:21', NULL, '1', '0');
INSERT INTO `bus_schedule_time_slot` VALUES (64, 101, '13:00', '17:00', '2026-05-27 11:00:21', NULL, '2026-05-27 11:00:21', NULL, '1', '0');
INSERT INTO `bus_schedule_time_slot` VALUES (65, 102, '07:30', '11:30', '2026-05-27 11:00:21', NULL, '2026-05-27 11:00:21', NULL, '1', '0');
INSERT INTO `bus_schedule_time_slot` VALUES (66, 102, '13:30', '17:30', '2026-05-27 11:00:21', NULL, '2026-05-27 11:00:21', NULL, '1', '0');
INSERT INTO `bus_schedule_time_slot` VALUES (67, 103, '08:00', '12:00', '2026-05-27 11:00:21', NULL, '2026-05-27 11:00:21', NULL, '1', '0');
INSERT INTO `bus_schedule_time_slot` VALUES (68, 103, '14:00', '18:00', '2026-05-27 11:00:21', NULL, '2026-05-27 11:00:21', NULL, '1', '0');
INSERT INTO `bus_schedule_time_slot` VALUES (69, 104, '09:00', '13:00', '2026-05-27 11:00:21', NULL, '2026-05-27 11:00:21', NULL, '1', '0');
INSERT INTO `bus_schedule_time_slot` VALUES (70, 104, '14:00', '18:00', '2026-05-27 11:00:21', NULL, '2026-05-27 11:00:21', NULL, '1', '0');
INSERT INTO `bus_schedule_time_slot` VALUES (71, 105, '08:00', '12:00', '2026-05-27 11:00:21', NULL, '2026-05-27 11:00:21', NULL, '1', '0');
INSERT INTO `bus_schedule_time_slot` VALUES (72, 106, '07:00', '11:00', '2026-05-27 11:00:21', NULL, '2026-05-27 11:00:21', NULL, '1', '0');
INSERT INTO `bus_schedule_time_slot` VALUES (73, 111, '15:30', '23:33', '2026-05-28 15:33:59', 'admin', '2026-05-28 15:33:52', NULL, '1', '0');
INSERT INTO `bus_schedule_time_slot` VALUES (74, 112, '09:21', '23:23', '2026-05-29 09:23:58', 'admin', '2026-05-29 09:23:50', NULL, '1', '0');
INSERT INTO `bus_schedule_time_slot` VALUES (75, 113, '16:46', '18:46', '2026-05-29 16:45:23', 'felix', '2026-05-29 16:45:15', NULL, '1', '0');
INSERT INTO `bus_schedule_time_slot` VALUES (76, 114, '18:00', '20:00', '2026-05-29 18:35:53', 'admin', '2026-05-29 18:35:45', NULL, '1', '0');
INSERT INTO `bus_schedule_time_slot` VALUES (77, 115, '09:26', '22:26', '2026-05-30 10:26:29', 'admin', '2026-05-30 10:26:20', NULL, '1', '0');
INSERT INTO `bus_schedule_time_slot` VALUES (78, 116, '09:50', '23:50', '2026-05-31 09:50:23', 'admin', '2026-05-31 09:50:14', NULL, '1', '0');
INSERT INTO `bus_schedule_time_slot` VALUES (79, 117, '09:17', '19:17', '2026-06-01 09:16:29', 'felix', '2026-06-01 09:16:20', NULL, '1', '0');
INSERT INTO `bus_schedule_time_slot` VALUES (80, 118, '14:06', '23:06', '2026-06-01 14:06:35', 'admin', '2026-06-01 14:06:26', NULL, '1', '0');
INSERT INTO `bus_schedule_time_slot` VALUES (81, 119, '15:01', '18:01', '2026-06-01 14:59:45', 'felix', '2026-06-01 14:59:35', NULL, '1', '0');
INSERT INTO `bus_schedule_time_slot` VALUES (82, 120, '09:48', '09:55', '2026-06-02 09:49:01', 'admin', '2026-06-02 09:48:52', NULL, '1', '0');

-- ----------------------------
-- Table structure for bus_schedule_vehicle
-- ----------------------------
DROP TABLE IF EXISTS `bus_schedule_vehicle`;
CREATE TABLE `bus_schedule_vehicle`  (
  `id` bigint NOT NULL AUTO_INCREMENT COMMENT '主键',
  `schedule_id` bigint NOT NULL COMMENT '排班ID',
  `vehicle_id` bigint NULL DEFAULT NULL COMMENT '车辆ID',
  `vehicle_number` varchar(20) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci NULL DEFAULT NULL COMMENT '车牌号/车辆编号',
  `vehicle_type` varchar(20) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci NULL DEFAULT NULL COMMENT '车辆类型',
  `seat_count` int NULL DEFAULT 0 COMMENT '座位数',
  `bind_status` varchar(10) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci NULL DEFAULT '0' COMMENT '绑定状态：0-未绑定，1-已绑定',
  `create_time` datetime NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
  `create_by` varchar(64) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci NULL DEFAULT NULL COMMENT '创建人',
  `update_time` datetime NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
  `update_by` varchar(64) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci NULL DEFAULT NULL COMMENT '更新人',
  `tenant_id` varchar(32) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci NULL DEFAULT NULL COMMENT '租户ID',
  `del_flag` varchar(1) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci NULL DEFAULT '0' COMMENT '删除标记',
  PRIMARY KEY (`id`) USING BTREE,
  INDEX `idx_bsv_schedule`(`schedule_id` ASC) USING BTREE
) ENGINE = InnoDB AUTO_INCREMENT = 11 CHARACTER SET = utf8mb4 COLLATE = utf8mb4_0900_ai_ci COMMENT = '排班关联车辆表' ROW_FORMAT = DYNAMIC;

-- ----------------------------
-- Records of bus_schedule_vehicle
-- ----------------------------
INSERT INTO `bus_schedule_vehicle` VALUES (1, 101, 4001, '粤A00001D', '0', 45, '1', '2026-05-27 11:00:26', NULL, '2026-05-27 11:00:26', NULL, '1', '0');
INSERT INTO `bus_schedule_vehicle` VALUES (2, 102, 4002, '粤A00002D', '0', 45, '1', '2026-05-27 11:00:26', NULL, '2026-05-27 11:00:26', NULL, '1', '0');
INSERT INTO `bus_schedule_vehicle` VALUES (3, 103, 4004, '粤A00004D', '1', 30, '1', '2026-05-27 11:00:26', NULL, '2026-05-27 11:00:26', NULL, '1', '0');
INSERT INTO `bus_schedule_vehicle` VALUES (4, 104, 4005, '粤A00005D', '1', 30, '1', '2026-05-27 11:00:26', NULL, '2026-05-27 11:00:26', NULL, '1', '0');
INSERT INTO `bus_schedule_vehicle` VALUES (5, 105, 4008, '粤A00008D', '0', 45, '1', '2026-05-27 11:00:26', NULL, '2026-05-27 11:00:26', NULL, '1', '0');
INSERT INTO `bus_schedule_vehicle` VALUES (6, 106, 4001, '粤A00001D', '0', 45, '1', '2026-05-27 11:00:26', NULL, '2026-05-27 11:00:26', NULL, '1', '0');
INSERT INTO `bus_schedule_vehicle` VALUES (7, 107, 4004, '粤A00004D', '1', 30, '0', '2026-05-27 11:00:26', NULL, '2026-05-27 11:00:26', NULL, '1', '0');
INSERT INTO `bus_schedule_vehicle` VALUES (8, 108, 4008, '粤A00008D', '0', 45, '0', '2026-05-27 11:00:26', NULL, '2026-05-27 11:00:26', NULL, '1', '0');
INSERT INTO `bus_schedule_vehicle` VALUES (9, 109, 4009, '粤A00009D', '3', 60, '1', '2026-05-27 11:00:26', NULL, '2026-05-27 11:00:26', NULL, '1', '0');
INSERT INTO `bus_schedule_vehicle` VALUES (10, 110, 4006, '粤A00006D', '2', 20, '0', '2026-05-27 11:00:26', NULL, '2026-05-27 11:00:26', NULL, '1', '0');

-- ----------------------------
-- Table structure for bus_sequence
-- ----------------------------
DROP TABLE IF EXISTS `bus_sequence`;
CREATE TABLE `bus_sequence`  (
  `id` bigint NOT NULL,
  `value` bigint NULL DEFAULT NULL,
  `name` varchar(255) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NULL DEFAULT NULL,
  PRIMARY KEY (`id`) USING BTREE,
  UNIQUE INDEX `name`(`name` ASC) USING BTREE
) ENGINE = InnoDB CHARACTER SET = utf8mb4 COLLATE = utf8mb4_unicode_ci COMMENT = '序列号区间管理表' ROW_FORMAT = DYNAMIC;

-- ----------------------------
-- Records of bus_sequence
-- ----------------------------
INSERT INTO `bus_sequence` VALUES (-1588016638676796492, 180, 'station_code_1');
INSERT INTO `bus_sequence` VALUES (382809850553885448, 10, 'route_id_1');
INSERT INTO `bus_sequence` VALUES (2204010526739046277, 10, 'area_code_1');

-- ----------------------------
-- Table structure for bus_short_break_config
-- ----------------------------
DROP TABLE IF EXISTS `bus_short_break_config`;
CREATE TABLE `bus_short_break_config`  (
  `id` bigint NOT NULL AUTO_INCREMENT COMMENT '主键',
  `area_id` bigint NOT NULL COMMENT '运营区域ID（关联 bus_area.id）',
  `area_name` varchar(100) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci NULL DEFAULT NULL COMMENT '运营区域名称（冗余展示）',
  `daily_max_count` int NOT NULL COMMENT '每人每天小休总次数上限',
  `duration_minutes` int NOT NULL COMMENT '每次小休固定时长(分钟)',
  `dept_id` bigint NULL DEFAULT NULL COMMENT '部门ID（数据权限）',
  `create_time` datetime NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
  `create_by` varchar(64) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci NULL DEFAULT NULL COMMENT '创建人',
  `update_time` datetime NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
  `update_by` varchar(64) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci NULL DEFAULT NULL COMMENT '更新人',
  `tenant_id` varchar(32) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci NULL DEFAULT NULL COMMENT '租户ID',
  `del_flag` varchar(1) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci NULL DEFAULT '0' COMMENT '删除标记：0-未删除，1-已删除',
  PRIMARY KEY (`id`) USING BTREE,
  INDEX `idx_bsbc_tenant_area`(`tenant_id` ASC, `area_id` ASC, `del_flag` ASC) USING BTREE,
  INDEX `idx_bsbc_area`(`area_id` ASC) USING BTREE,
  INDEX `idx_bsbc_tenant`(`tenant_id` ASC) USING BTREE
) ENGINE = InnoDB AUTO_INCREMENT = 3 CHARACTER SET = utf8mb4 COLLATE = utf8mb4_0900_ai_ci COMMENT = '司机小休规则（按区域）' ROW_FORMAT = DYNAMIC;

-- ----------------------------
-- Records of bus_short_break_config
-- ----------------------------
INSERT INTO `bus_short_break_config` VALUES (1, 7, '荔湾区', 3, 15, NULL, '2026-04-07 14:00:21', NULL, '2026-04-07 14:00:21', NULL, '1', '0');
INSERT INTO `bus_short_break_config` VALUES (2, 8, '越秀区', 3, 15, NULL, '2026-04-08 10:50:15', NULL, '2026-04-08 10:50:15', NULL, '1', '0');

-- ----------------------------
-- Table structure for bus_short_break_slot
-- ----------------------------
DROP TABLE IF EXISTS `bus_short_break_slot`;
CREATE TABLE `bus_short_break_slot`  (
  `id` bigint NOT NULL AUTO_INCREMENT COMMENT '主键',
  `config_id` bigint NOT NULL COMMENT '规则主表ID',
  `start_time` varchar(5) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci NOT NULL COMMENT '开始时间(HH:mm)',
  `end_time` varchar(5) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci NOT NULL COMMENT '结束时间(HH:mm，可与下一时段邻接，半开区间右端点)',
  `period_max_count` int NOT NULL COMMENT '该时段内允许发起小休次数上限',
  `dept_id` bigint NULL DEFAULT NULL COMMENT '部门ID（数据权限）',
  `create_time` datetime NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
  `create_by` varchar(64) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci NULL DEFAULT NULL COMMENT '创建人',
  `update_time` datetime NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
  `update_by` varchar(64) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci NULL DEFAULT NULL COMMENT '更新人',
  `tenant_id` varchar(32) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci NULL DEFAULT NULL COMMENT '租户ID',
  PRIMARY KEY (`id`) USING BTREE,
  INDEX `idx_bsbs_config`(`config_id` ASC) USING BTREE,
  INDEX `idx_bsbs_tenant`(`tenant_id` ASC) USING BTREE
) ENGINE = InnoDB AUTO_INCREMENT = 13 CHARACTER SET = utf8mb4 COLLATE = utf8mb4_0900_ai_ci COMMENT = '司机小休时段配置' ROW_FORMAT = DYNAMIC;

-- ----------------------------
-- Records of bus_short_break_slot
-- ----------------------------
INSERT INTO `bus_short_break_slot` VALUES (1, 1, '00:00', '07:00', 1, NULL, '2026-04-07 14:00:21', NULL, '2026-04-07 14:00:21', NULL, '1');
INSERT INTO `bus_short_break_slot` VALUES (2, 1, '07:00', '09:00', 1, NULL, '2026-04-07 14:00:21', NULL, '2026-04-07 14:00:21', NULL, '1');
INSERT INTO `bus_short_break_slot` VALUES (3, 1, '09:00', '17:00', 2, NULL, '2026-04-07 14:00:21', NULL, '2026-04-07 14:00:21', NULL, '1');
INSERT INTO `bus_short_break_slot` VALUES (4, 1, '17:00', '19:00', 1, NULL, '2026-04-07 14:00:21', NULL, '2026-04-07 14:00:21', NULL, '1');
INSERT INTO `bus_short_break_slot` VALUES (5, 1, '19:00', '23:00', 2, NULL, '2026-04-07 14:00:21', NULL, '2026-04-07 14:00:21', NULL, '1');
INSERT INTO `bus_short_break_slot` VALUES (6, 1, '23:00', '24:00', 1, NULL, '2026-04-07 14:00:21', NULL, '2026-04-07 14:00:21', NULL, '1');
INSERT INTO `bus_short_break_slot` VALUES (7, 2, '00:00', '07:00', 4, NULL, '2026-04-08 10:50:15', NULL, '2026-04-08 10:50:15', NULL, '1');
INSERT INTO `bus_short_break_slot` VALUES (8, 2, '07:00', '09:00', 1, NULL, '2026-04-08 10:50:15', NULL, '2026-04-08 10:50:15', NULL, '1');
INSERT INTO `bus_short_break_slot` VALUES (9, 2, '09:00', '17:00', 2, NULL, '2026-04-08 10:50:15', NULL, '2026-04-08 10:50:15', NULL, '1');
INSERT INTO `bus_short_break_slot` VALUES (10, 2, '17:00', '19:00', 1, NULL, '2026-04-08 10:50:15', NULL, '2026-04-08 10:50:15', NULL, '1');
INSERT INTO `bus_short_break_slot` VALUES (11, 2, '19:00', '23:00', 2, NULL, '2026-04-08 10:50:15', NULL, '2026-04-08 10:50:15', NULL, '1');
INSERT INTO `bus_short_break_slot` VALUES (12, 2, '23:00', '24:00', 1, NULL, '2026-04-08 10:50:15', NULL, '2026-04-08 10:50:15', NULL, '1');

-- ----------------------------
-- Table structure for bus_station
-- ----------------------------
DROP TABLE IF EXISTS `bus_station`;
CREATE TABLE `bus_station`  (
  `id` bigint NOT NULL AUTO_INCREMENT COMMENT '站点ID',
  `station_name` varchar(50) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci NOT NULL COMMENT '站点名称',
  `station_code` varchar(20) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci NOT NULL COMMENT '站点编码',
  `station_type` varchar(10) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci NOT NULL COMMENT '站点类型：0-普通公交站，1-总站，2-虚拟站，3-停车场，4-临停点',
  `station_direction` varchar(10) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci NOT NULL COMMENT '站点方向：东、西、南、北',
  `direction_angle` int NULL DEFAULT NULL COMMENT '方向角',
  `longitude` double NOT NULL COMMENT '经度',
  `latitude` double NOT NULL COMMENT '纬度',
  `station_address` varchar(200) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci NOT NULL COMMENT '站点地址',
  `areas` varchar(100) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci NOT NULL COMMENT '所属区域',
  `status` varchar(10) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci NOT NULL COMMENT '状态：0-启用，1-停用',
  `dept_id` bigint NULL DEFAULT NULL COMMENT '部门ID（数据权限）',
  `create_time` datetime NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
  `create_by` varchar(50) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci NULL DEFAULT NULL COMMENT '创建人',
  `update_time` datetime NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
  `update_by` varchar(50) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci NULL DEFAULT NULL COMMENT '更新人',
  `audit_user` varchar(64) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci NULL DEFAULT NULL COMMENT '审核人',
  `audit_time` datetime NULL DEFAULT NULL COMMENT '审核时间',
  `audit_status` varchar(20) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci NULL DEFAULT 'approved' COMMENT '审核状态：pending-待审核，approved-审核通过，rejected-审核驳回',
  `audit_message` varchar(500) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci NULL DEFAULT NULL COMMENT '审核意见',
  `tenant_id` varchar(20) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci NULL DEFAULT '000000' COMMENT '租户ID',
  PRIMARY KEY (`id`) USING BTREE,
  UNIQUE INDEX `uk_station_code`(`station_code` ASC) USING BTREE,
  INDEX `idx_station_name`(`station_name` ASC) USING BTREE,
  INDEX `idx_station_type`(`station_type` ASC) USING BTREE,
  INDEX `idx_status`(`status` ASC) USING BTREE,
  INDEX `idx_areas`(`areas` ASC) USING BTREE
) ENGINE = InnoDB AUTO_INCREMENT = 2030 CHARACTER SET = utf8mb4 COLLATE = utf8mb4_0900_ai_ci COMMENT = '公交站点表' ROW_FORMAT = DYNAMIC;

-- ----------------------------
-- Records of bus_station
-- ----------------------------
INSERT INTO `bus_station` VALUES (6, '中山八路公交站', 'ST000014', '0', '西', NULL, 113.23524, 23.12557, '中山八路公交站', '7', '0', NULL, '2026-04-07 11:17:06', 'admin', '2026-04-07 11:18:47', NULL, NULL, NULL, 'approved', NULL, '1');
INSERT INTO `bus_station` VALUES (13, '石牌桥地铁站口站', 'ST000071', '2', '东', 12, 113.331482, 23.133003, '石牌桥地铁站A出口左前方20米', '10', '0', NULL, '2026-05-18 15:42:57', 'admin', '2026-05-21 15:26:18', 'admin', NULL, NULL, 'approved', NULL, '1');
INSERT INTO `bus_station` VALUES (16, '体育中心地铁站', 'ST000002', '3', '东', 31, 113.531483, 23.15146003, '体育中心地铁站A出口左前方50米', '天河区', '0', NULL, '2026-05-20 16:23:35', 'admin', '2026-05-25 17:14:30', 'admin', NULL, NULL, 'approved', NULL, '1');
INSERT INTO `bus_station` VALUES (17, '冼村站', 'ST000003', '0', '西', 32, 113.631484, 23.18584634462, '冼村站地铁站B出口前方10米', '天河区', '0', NULL, '2026-05-20 16:23:35', 'admin', '2026-05-20 16:23:30', NULL, NULL, NULL, 'approved', NULL, '1');
INSERT INTO `bus_station` VALUES (19, '上社站', 'ST000005', '2', '西', 34, 113.75486, 23.1814611514, '上社', '天河区', '0', NULL, '2026-05-20 16:23:35', 'admin', '2026-05-21 17:24:23', 'admin', NULL, NULL, 'approved', NULL, '1');
INSERT INTO `bus_station` VALUES (20, '石牌桥A口公交站', 'ST000086', '0', '东', NULL, 113.331482, 23.133003, '石牌桥A口公交站', '10', '0', NULL, '2026-05-21 17:22:20', 'admin', '2026-05-21 17:22:15', NULL, NULL, NULL, 'approved', NULL, '1');
INSERT INTO `bus_station` VALUES (21, '广州南站公交站', 'ST000085', '1', '东', NULL, 113.89641511, 23.4616111, '广州市番禺区石壁街道石壁村广州南站公交站', '9', '1', NULL, '2026-05-22 11:37:39', 'admin', '2026-05-26 10:43:16', 'admin', NULL, NULL, 'approved', NULL, '1');
INSERT INTO `bus_station` VALUES (2001, '体育西路站', 'ST_GZ_201', '0', '西', NULL, 113.3215, 23.1268, '天河区体育西路地铁站A口', '201', '0', NULL, '2026-05-27 10:57:21', NULL, '2026-05-27 10:57:21', NULL, NULL, NULL, 'approved', NULL, '1');
INSERT INTO `bus_station` VALUES (2002, '珠江新城站', 'ST_GZ_202', '0', '南', NULL, 113.322, 23.127, '天河区珠江新城地铁站B1口', '201', '0', NULL, '2026-05-27 10:57:21', NULL, '2026-05-27 10:57:21', NULL, NULL, NULL, 'approved', NULL, '1');
INSERT INTO `bus_station` VALUES (2003, '广州塔站', 'ST_GZ_203', '0', '北', NULL, 113.325, 23.109, '海珠区阅江西路广州塔西侧', '202', '0', NULL, '2026-05-27 10:57:21', NULL, '2026-05-27 10:57:21', NULL, NULL, NULL, 'approved', NULL, '1');
INSERT INTO `bus_station` VALUES (2004, '客村站', 'ST_GZ_204', '0', '东', NULL, 113.3175, 23.1005, '海珠区新港中路客村地铁站D口', '202', '0', NULL, '2026-05-27 10:57:21', NULL, '2026-05-27 10:57:21', NULL, NULL, NULL, 'approved', NULL, '1');
INSERT INTO `bus_station` VALUES (2005, '大学城北站', 'ST_GZ_205', '0', '东', NULL, 113.385, 23.058, '番禺区大学城北地铁站C口', '203', '0', NULL, '2026-05-27 10:57:21', NULL, '2026-05-27 10:57:21', NULL, NULL, NULL, 'approved', NULL, '1');
INSERT INTO `bus_station` VALUES (2006, '番禺广场站', 'ST_GZ_206', '0', '西', NULL, 113.365, 22.945, '番禺区番禺广场地铁站A口', '203', '0', NULL, '2026-05-27 10:57:21', NULL, '2026-05-27 10:57:21', NULL, NULL, NULL, 'approved', NULL, '1');
INSERT INTO `bus_station` VALUES (2007, '公园前站', 'ST_GZ_207', '0', '北', NULL, 113.267, 23.128, '越秀区中山五路公园前地铁站', '204', '0', NULL, '2026-05-27 10:57:21', NULL, '2026-05-27 10:57:21', NULL, NULL, NULL, 'approved', NULL, '1');
INSERT INTO `bus_station` VALUES (2008, '北京路站', 'ST_GZ_208', '0', '南', NULL, 113.272, 23.122, '越秀区北京路步行街', '204', '0', NULL, '2026-05-27 10:57:21', NULL, '2026-05-27 10:57:21', NULL, NULL, NULL, 'approved', NULL, '1');
INSERT INTO `bus_station` VALUES (2009, '陈家祠站', 'ST_GZ_209', '0', '西', NULL, 113.24, 23.124, '荔湾区中山七路陈家祠地铁站', '205', '0', NULL, '2026-05-27 10:57:21', NULL, '2026-05-27 10:57:21', NULL, NULL, NULL, 'approved', NULL, '1');
INSERT INTO `bus_station` VALUES (2010, '长寿路站', 'ST_GZ_210', '0', '东', NULL, 113.242, 23.117, '荔湾区长寿路地铁站B口', '205', '0', NULL, '2026-05-27 10:57:21', NULL, '2026-05-27 10:57:21', NULL, NULL, NULL, 'approved', NULL, '1');
INSERT INTO `bus_station` VALUES (2012, '天河南一路', 'ST000133', '3', '东', 3, 113.329777, 23.131938, '天河南二路', '211,212,14', '0', 1, '2026-05-28 14:17:54', 'admin', '2026-05-28 17:14:29', 'admin', NULL, NULL, 'approved', NULL, '1');
INSERT INTO `bus_station` VALUES (2013, '沙河', 'ST000134', '1', '西', 4, 113.314474, 23.150741, '沙河公交总站', '212,14', '0', 1, '2026-05-28 14:18:48', 'admin', '2026-05-28 14:26:58', 'admin', NULL, NULL, 'approved', NULL, '1');
INSERT INTO `bus_station` VALUES (2014, '广州东站', 'ST000135', '1', '西', 1, 113.326576, 23.148611, '广州东站', '14,212', '0', 1, '2026-05-28 14:28:27', 'admin', '2026-05-28 14:28:45', 'admin', NULL, NULL, 'approved', NULL, '1');
INSERT INTO `bus_station` VALUES (2015, '广州东站1', 'ST000138', '1', '西', NULL, 113.324854, 23.150983, '广州东站1', '212', '0', 2059155512602853378, '2026-05-28 16:03:33', 'felix', '2026-05-28 16:03:25', NULL, NULL, NULL, 'approved', NULL, '1');
INSERT INTO `bus_station` VALUES (2016, '广州火车站（草暖公园）总站', 'ST000139', '1', '南', 180, 113.263, 23.1485, '环市西路158号', '越秀区', '0', 2059155512602853378, '2026-05-28 16:21:58', 'felix', '2026-05-28 16:21:50', NULL, NULL, NULL, 'approved', NULL, '1');
INSERT INTO `bus_station` VALUES (2017, '体育中心站', 'ST000140', '3', '北', 0, 113.325, 23.1368, '天河路299号', '天河区', '0', 2059155512602853378, '2026-05-28 16:21:58', 'felix', '2026-05-28 17:37:26', 'admin', NULL, NULL, 'approved', NULL, '1');
INSERT INTO `bus_station` VALUES (2018, '珠江新城站', 'ST000141', '3', '东', 90, 113.327, 23.117, '花城大道85号', '天河区', '0', 2059155512602853378, '2026-05-28 16:21:58', 'felix', '2026-05-28 17:37:19', 'admin', NULL, NULL, 'approved', NULL, '1');
INSERT INTO `bus_station` VALUES (2019, '广州塔站', 'ST000142', '3', '南', 180, 113.3245, 23.1067, '阅江西路222号', '14', '0', 2059155512602853378, '2026-05-28 16:21:58', 'felix', '2026-05-28 17:37:11', 'admin', NULL, NULL, 'approved', NULL, '1');
INSERT INTO `bus_station` VALUES (2020, '白云大厦', 'ST000146', '1', '东', NULL, 113.285209, 23.120307, '白云大厦', '218', '0', 2059155603103350785, '2026-05-28 17:36:46', 'felixx', '2026-05-28 17:36:38', NULL, NULL, NULL, 'approved', NULL, '1');
INSERT INTO `bus_station` VALUES (2021, '白云大厦', 'ST000154', '0', '东', NULL, 113.285209, 23.120307, '数据中心', '219', '0', 2059155512602853378, '2026-05-30 15:23:37', 'alex01', '2026-05-30 15:23:54', 'alex01', NULL, NULL, 'approved', NULL, '1');
INSERT INTO `bus_station` VALUES (2022, '白云路站', 'ST000171', '0', '东', NULL, 113.284884, 23.119539, '白云路', '223', '1', 2059155512602853378, '2026-06-01 10:56:16', 'alex01', '2026-06-01 11:04:00', 'alex04', 'alex04', '2026-06-01 11:04:00', 'approved', '权威', '1');
INSERT INTO `bus_station` VALUES (2023, '汉溪长隆', 'ST000172', '1', '东', 1, 113.32985, 22.994183, '汉溪长隆', '225', '0', 2059155512602853378, '2026-06-01 17:19:09', 'felix', '2026-06-01 17:41:20', 'felix', 'felix', '2026-06-01 17:19:57', 'approved', '1', '1');
INSERT INTO `bus_station` VALUES (2024, '南村万博', 'ST000173', '1', '西', 3, 113.347003, 23.004425, '南村万博', '225', '0', 2059155512602853378, '2026-06-01 17:19:48', 'felix', '2026-06-01 17:41:17', 'felix', 'felix', '2026-06-01 17:19:54', 'approved', '1', '1');
INSERT INTO `bus_station` VALUES (2025, '体育中心站', 'ST000174', '1', '东', NULL, 113.324087, 23.134246, '体育中心站', '226', '0', 2059155512602853378, '2026-06-01 18:02:21', 'felix', '2026-06-01 18:03:23', 'felix', 'felix', '2026-06-01 18:03:12', 'approved', '123214', '1');
INSERT INTO `bus_station` VALUES (2026, '石牌桥地铁站', 'ST000175', '1', '东', NULL, 113.332123, 23.133141, '石牌桥地铁站', '226', '0', 2059155512602853378, '2026-06-01 18:03:01', 'felix', '2026-06-01 18:23:19', 'admin', 'felix', '2026-06-01 18:03:08', 'approved', '1231', '1');
INSERT INTO `bus_station` VALUES (2027, '创展中心东座公交站', 'ST000176', '0', '东', NULL, 113.329806, 23.132025, '广州市天河区天河南二路创展中心', '13', '0', 2061273631362301953, '2026-06-01 18:25:54', 'admin', '2026-06-01 18:28:20', 'admin', 'admin', '2026-06-01 18:28:14', 'approved', '1', '1');
INSERT INTO `bus_station` VALUES (2028, '创展中心西座公交站', 'ST000177', '0', '西', NULL, 113.32979, 23.132016, '广州市天河区天河南二路创展中心西座', '13', '0', 2061273631362301953, '2026-06-01 18:27:58', 'admin', '2026-06-01 18:28:17', 'admin', 'admin', '2026-06-01 18:28:08', 'approved', '1', '1');
INSERT INTO `bus_station` VALUES (2029, '富海大厦', 'ST000178', '0', '西', NULL, 113.332863, 23.136389, '富海大厦', '227', '1', 2061273631362301953, '2026-06-02 10:15:32', 'admin', '2026-06-02 10:15:23', NULL, NULL, NULL, 'pending', NULL, '1');

-- ----------------------------
-- Table structure for bus_vehicle
-- ----------------------------
DROP TABLE IF EXISTS `bus_vehicle`;
CREATE TABLE `bus_vehicle`  (
  `id` bigint NOT NULL AUTO_INCREMENT COMMENT '车辆ID',
  `plate_number` varchar(10) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci NOT NULL COMMENT '车牌号',
  `vehicle_type` varchar(10) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci NOT NULL COMMENT '车辆类型：0-大型客车，1-中型客车，2-小型客车，3-双层巴士，4-铰接客车',
  `seat_count` int NOT NULL COMMENT '座位数',
  `max_load_count` int NOT NULL COMMENT '核载人数',
  `vehicle_color` varchar(20) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci NOT NULL COMMENT '车辆颜色',
  `vehicle_length` decimal(5, 2) NOT NULL COMMENT '车辆长度(米)',
  `vehicle_model` varchar(50) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci NULL DEFAULT NULL COMMENT '车辆型号',
  `manufacturer` varchar(100) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci NULL DEFAULT NULL COMMENT '生产厂家',
  `manufacture_date` datetime NULL DEFAULT NULL COMMENT '出厂日期',
  `registration_date` datetime NULL DEFAULT NULL COMMENT '注册日期',
  `enterprise_id` bigint NULL DEFAULT NULL COMMENT '所属企业ID',
  `operation_status` varchar(20) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci NOT NULL DEFAULT 'offline' COMMENT '运营状态：online-在线，offline-离线，maintenance-维修，idle-闲置',
  `operation_mode` varchar(32) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci NULL DEFAULT NULL COMMENT '运营模式：dynamic_bus/custom_bus/regular',
  `tablet_device_number` varchar(50) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci NULL DEFAULT NULL COMMENT '平板设备号',
  `terminal_device_number` varchar(50) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci NULL DEFAULT NULL COMMENT '电子收费终端号',
  `psam_card_number` varchar(50) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci NULL DEFAULT NULL COMMENT 'PSAM卡号',
  `current_driver_id` bigint NULL DEFAULT NULL COMMENT '当前绑定司机ID',
  `insurance_expiry_date` datetime NULL DEFAULT NULL COMMENT '保险到期日',
  `annual_inspection_date` datetime NULL DEFAULT NULL COMMENT '年检日期',
  `remark` varchar(500) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci NULL DEFAULT NULL COMMENT '备注',
  `dept_id` bigint NULL DEFAULT NULL COMMENT '部门ID（数据权限）',
  `create_time` datetime NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
  `create_by` varchar(50) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci NULL DEFAULT NULL COMMENT '创建人',
  `update_time` datetime NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
  `update_by` varchar(50) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci NULL DEFAULT NULL COMMENT '更新人',
  `del_flag` varchar(1) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci NULL DEFAULT '0' COMMENT '删除标记',
  `tenant_id` varchar(20) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci NULL DEFAULT '000000' COMMENT '租户ID',
  PRIMARY KEY (`id`) USING BTREE,
  UNIQUE INDEX `uk_plate_number`(`plate_number` ASC) USING BTREE,
  UNIQUE INDEX `uk_tablet_device`(`tablet_device_number` ASC) USING BTREE,
  INDEX `idx_vehicle_type`(`vehicle_type` ASC) USING BTREE,
  INDEX `idx_enterprise_id`(`enterprise_id` ASC) USING BTREE,
  INDEX `idx_operation_status`(`operation_status` ASC) USING BTREE,
  INDEX `idx_current_driver_id`(`current_driver_id` ASC) USING BTREE,
  INDEX `idx_create_time`(`create_time` ASC) USING BTREE
) ENGINE = InnoDB AUTO_INCREMENT = 4015 CHARACTER SET = utf8mb4 COLLATE = utf8mb4_0900_ai_ci COMMENT = '公交车辆表' ROW_FORMAT = DYNAMIC;

-- ----------------------------
-- Records of bus_vehicle
-- ----------------------------
INSERT INTO `bus_vehicle` VALUES (1, '京A12345', '0', 45, 50, 'white', 12.50, 'YBL6120', '宇通客车', '2023-01-15 00:00:00', '2023-02-01 00:00:00', 1, 'dynamic_bus', 'dynamic_bus', 'TABLET001', '038100001', '010099991929', NULL, '2024-12-31 00:00:00', '2024-06-30 00:00:00', '车辆状况良好', NULL, '2026-03-29 14:58:40', 'admin', '2026-05-29 09:39:32', 'system', '0', '1');
INSERT INTO `bus_vehicle` VALUES (2, '京B67890', '0', 45, 50, 'red', 12.50, 'YBL6120', '宇通客车', '2023-03-20 00:00:00', '2023-04-01 00:00:00', 1, 'regular', 'regular', 'TABLET002', '031100075', '99993997', NULL, '2024-12-31 00:00:00', '2024-06-30 00:00:00', '车辆状况良好', NULL, '2026-03-29 14:58:40', 'admin', '2026-06-01 17:51:21', 'system', '0', '1');
INSERT INTO `bus_vehicle` VALUES (4, '京D98765', '2', 20, 25, 'green', 7.50, 'KLQ6800', '金龙客车', '2023-07-15 00:00:00', '2023-08-01 00:00:00', 2, 'offline', 'offline', '031100075', '031100075', '99993997', 5, '2024-12-31 00:00:00', '2024-06-30 00:00:00', '车辆闲置', NULL, '2026-03-29 14:58:40', 'admin', '2026-05-29 18:30:07', '13652944754', '0', '1');
INSERT INTO `bus_vehicle` VALUES (8, '粤A147230', '3', 30, 30, 'green', 8.00, NULL, NULL, NULL, NULL, 1, 'online', NULL, NULL, NULL, NULL, 4, NULL, NULL, NULL, NULL, '2026-05-19 11:54:08', 'admin', '2026-05-22 15:24:28', '13802402145', '0', '1');
INSERT INTO `bus_vehicle` VALUES (4001, '粤A00001D', '0', 45, 50, '红色', 12.00, 'XMQ6127', '厦门金龙', NULL, NULL, NULL, 'online', 'regular', NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, '2026-05-27 10:57:38', NULL, '2026-05-27 10:57:38', NULL, '0', '1');
INSERT INTO `bus_vehicle` VALUES (4002, '粤A00002D', '0', 45, 50, '蓝色', 12.00, 'XMQ6127', '厦门金龙', NULL, NULL, NULL, 'online', 'regular', NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, '2026-05-27 10:57:38', NULL, '2026-05-27 10:57:38', NULL, '0', '1');
INSERT INTO `bus_vehicle` VALUES (4003, '粤A00003D', '0', 45, 50, '绿色', 12.00, 'ZK6120', '宇通客车', NULL, NULL, NULL, 'online', 'regular', NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, '2026-05-27 10:57:38', NULL, '2026-05-27 10:57:38', NULL, '0', '1');
INSERT INTO `bus_vehicle` VALUES (4004, '粤A00004D', '1', 30, 35, '白色', 10.50, 'ZK6119', '宇通客车', NULL, NULL, NULL, 'online', 'custom', NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, '2026-05-27 10:57:38', NULL, '2026-05-27 10:57:38', NULL, '0', '1');
INSERT INTO `bus_vehicle` VALUES (4005, '粤A00005D', '1', 30, 35, '银色', 10.50, 'KLQ6110', '金龙客车', NULL, NULL, NULL, 'online', 'custom', NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, '2026-05-27 10:57:38', NULL, '2026-05-27 10:57:38', NULL, '0', '1');
INSERT INTO `bus_vehicle` VALUES (4006, '粤A00006D', '2', 20, 25, '黄色', 8.50, 'KLQ6850', '金龙客车', NULL, NULL, NULL, 'offline', 'dynamic_bus', NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, '2026-05-27 10:57:38', NULL, '2026-05-27 10:57:38', NULL, '0', '1');
INSERT INTO `bus_vehicle` VALUES (4007, '粤A00007D', '2', 20, 25, '橙色', 8.50, 'XML6857', '厦门金龙', NULL, NULL, NULL, 'maintenance', 'dynamic_bus', NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, '2026-05-27 10:57:38', NULL, '2026-05-27 10:57:38', NULL, '0', '1');
INSERT INTO `bus_vehicle` VALUES (4008, '粤A00008D', '0', 45, 50, '紫色', 12.00, 'XMQ6127', '厦门金龙', NULL, NULL, 1, 'idle', 'regular', NULL, '', '', NULL, NULL, NULL, NULL, 2059155680572145665, '2026-05-27 10:57:38', NULL, '2026-06-01 11:10:03', 'admin', '0', '1');
INSERT INTO `bus_vehicle` VALUES (4009, '粤A00009D', '3', 60, 65, '金色', 13.50, 'JNP6137', '青年客车', NULL, NULL, 1, 'offline', 'offline', NULL, '031100075', '99993997', NULL, NULL, NULL, NULL, NULL, '2026-05-27 10:57:38', NULL, '2026-06-01 17:53:39', 'felix', '0', '1');
INSERT INTO `bus_vehicle` VALUES (4010, '粤A00010D', '0', 45, 50, '棕色', 12.00, 'ZK6120', '宇通客车', NULL, NULL, 1, 'offline', 'offline', NULL, NULL, NULL, 2012, NULL, NULL, NULL, 1, '2026-05-27 10:57:38', NULL, '2026-06-01 14:43:38', '19102053473', '0', '1');
INSERT INTO `bus_vehicle` VALUES (4011, '粤A123456', '2', 5, 5, 'white', 10.00, NULL, NULL, NULL, NULL, 2059560868248223746, 'online', NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, 2059560868424384513, '2026-05-28 15:26:37', 'captain', '2026-05-28 15:26:29', NULL, '0', '2059560868248223746');
INSERT INTO `bus_vehicle` VALUES (4012, '粤A88888D', '0', 5, 5, 'white', 11.00, NULL, NULL, NULL, NULL, 1, 'offline', 'offline', 'pingban001', '0311088888', '010099994123', 2009, NULL, NULL, NULL, 1, '2026-05-28 15:44:29', 'admin', '2026-05-29 09:54:52', '13042071722', '0', '1');
INSERT INTO `bus_vehicle` VALUES (4013, '粤A88999D', '0', 4, 4, 'white', 4.00, NULL, NULL, NULL, NULL, 1, 'offline', NULL, '', NULL, NULL, 2015, NULL, NULL, NULL, 2059155512602853378, '2026-05-29 18:32:32', 'alex01', '2026-06-02 09:38:00', 'admin', '0', '1');
INSERT INTO `bus_vehicle` VALUES (4014, '粤A88998D', '0', 4, 4, 'white', 0.00, NULL, NULL, NULL, NULL, 1, 'offline', NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, 2061273780239122433, '2026-06-01 11:53:00', 'alex04', '2026-06-01 14:18:44', 'admin', '0', '1');

-- ----------------------------
-- Table structure for bus_vehicle_archive
-- ----------------------------
DROP TABLE IF EXISTS `bus_vehicle_archive`;
CREATE TABLE `bus_vehicle_archive`  (
  `id` bigint NOT NULL AUTO_INCREMENT COMMENT 'ID',
  `vehicle_id` bigint NOT NULL COMMENT '车辆ID',
  `document_type` varchar(50) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci NOT NULL COMMENT '档案类型：driving_license-行驶证，insurance-保险单，registration-登记证，inspection-检验合格证',
  `document_name` varchar(200) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci NOT NULL COMMENT '文件名称',
  `file_url` varchar(500) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci NOT NULL COMMENT '文件URL',
  `file_size` bigint NULL DEFAULT NULL COMMENT '文件大小(字节)',
  `upload_time` datetime NOT NULL COMMENT '上传时间',
  `upload_by` varchar(50) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci NULL DEFAULT NULL COMMENT '上传人',
  `expiry_date` datetime NULL DEFAULT NULL COMMENT '到期日期',
  `remark` varchar(500) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci NULL DEFAULT NULL COMMENT '备注',
  PRIMARY KEY (`id`) USING BTREE,
  INDEX `idx_vehicle_id`(`vehicle_id` ASC) USING BTREE,
  INDEX `idx_document_type`(`document_type` ASC) USING BTREE,
  INDEX `idx_upload_time`(`upload_time` ASC) USING BTREE
) ENGINE = InnoDB AUTO_INCREMENT = 1 CHARACTER SET = utf8mb4 COLLATE = utf8mb4_0900_ai_ci COMMENT = '车辆档案表' ROW_FORMAT = DYNAMIC;

-- ----------------------------
-- Records of bus_vehicle_archive
-- ----------------------------

-- ----------------------------
-- Table structure for bus_vehicle_driver_history
-- ----------------------------
DROP TABLE IF EXISTS `bus_vehicle_driver_history`;
CREATE TABLE `bus_vehicle_driver_history`  (
  `id` bigint NOT NULL AUTO_INCREMENT COMMENT 'ID',
  `vehicle_id` bigint NOT NULL COMMENT '车辆ID',
  `driver_id` bigint NOT NULL COMMENT '司机ID',
  `bind_time` datetime NOT NULL COMMENT '绑定时间',
  `unbind_time` datetime NULL DEFAULT NULL COMMENT '解绑时间',
  `operator` varchar(50) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci NULL DEFAULT NULL COMMENT '操作人',
  `create_time` datetime NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
  PRIMARY KEY (`id`) USING BTREE,
  INDEX `idx_vehicle_id`(`vehicle_id` ASC) USING BTREE,
  INDEX `idx_driver_id`(`driver_id` ASC) USING BTREE,
  INDEX `idx_bind_time`(`bind_time` ASC) USING BTREE
) ENGINE = InnoDB AUTO_INCREMENT = 25 CHARACTER SET = utf8mb4 COLLATE = utf8mb4_0900_ai_ci COMMENT = '车辆司机绑定历史表' ROW_FORMAT = DYNAMIC;

-- ----------------------------
-- Records of bus_vehicle_driver_history
-- ----------------------------
INSERT INTO `bus_vehicle_driver_history` VALUES (1, 2, 3, '2026-04-06 13:36:36', '2026-04-06 13:37:04', 'admin', '2026-04-06 13:36:36');
INSERT INTO `bus_vehicle_driver_history` VALUES (2, 1, 1, '2026-04-06 13:51:34', '2026-04-30 16:33:51', 'admin', '2026-04-06 13:51:34');
INSERT INTO `bus_vehicle_driver_history` VALUES (3, 1, 1, '2026-04-30 16:33:59', '2026-05-14 16:50:16', 'admin', '2026-04-30 16:33:59');
INSERT INTO `bus_vehicle_driver_history` VALUES (4, 2, 2, '2026-05-13 14:31:23', '2026-05-26 10:34:56', 'admin', '2026-05-13 14:31:23');
INSERT INTO `bus_vehicle_driver_history` VALUES (5, 3, 5, '2026-05-13 14:44:08', '2026-05-19 17:33:09', 'admin', '2026-05-13 14:44:08');
INSERT INTO `bus_vehicle_driver_history` VALUES (6, 1, 3, '2026-05-14 16:50:23', '2026-05-18 15:29:08', 'admin', '2026-05-14 16:50:23');
INSERT INTO `bus_vehicle_driver_history` VALUES (7, 1, 1, '2026-05-18 15:29:14', '2026-05-26 10:34:52', 'admin', '2026-05-18 15:29:14');
INSERT INTO `bus_vehicle_driver_history` VALUES (8, 8, 4, '2026-05-22 15:24:28', NULL, '13802402145', '2026-05-22 15:24:28');
INSERT INTO `bus_vehicle_driver_history` VALUES (9, 4, 5, '2026-05-25 16:23:12', '2026-05-25 16:37:53', 'admin', '2026-05-25 16:23:12');
INSERT INTO `bus_vehicle_driver_history` VALUES (10, 4, 5, '2026-05-25 16:39:41', '2026-05-25 17:48:12', '13652944754', '2026-05-25 16:39:41');
INSERT INTO `bus_vehicle_driver_history` VALUES (11, 4, 5, '2026-05-27 09:41:19', '2026-05-29 18:01:03', '13652944754', '2026-05-27 09:41:19');
INSERT INTO `bus_vehicle_driver_history` VALUES (12, 4012, 2009, '2026-05-28 15:45:41', '2026-05-28 17:55:03', '13042071722', '2026-05-28 15:45:41');
INSERT INTO `bus_vehicle_driver_history` VALUES (13, 4012, 2009, '2026-05-28 17:55:49', NULL, '13042071722', '2026-05-28 17:55:49');
INSERT INTO `bus_vehicle_driver_history` VALUES (14, 4009, 1, '2026-05-29 10:01:25', '2026-05-29 10:26:09', '13432496353', '2026-05-29 10:01:25');
INSERT INTO `bus_vehicle_driver_history` VALUES (15, 4009, 1, '2026-05-29 10:28:35', '2026-06-01 09:41:13', '13432496353', '2026-05-29 10:28:35');
INSERT INTO `bus_vehicle_driver_history` VALUES (16, 4, 5, '2026-05-29 18:04:18', NULL, '13652944754', '2026-05-29 18:04:18');
INSERT INTO `bus_vehicle_driver_history` VALUES (17, 4010, 2012, '2026-05-29 18:37:02', '2026-05-30 11:06:49', '19102053473', '2026-05-29 18:37:02');
INSERT INTO `bus_vehicle_driver_history` VALUES (18, 4010, 2012, '2026-05-30 11:06:55', '2026-05-30 14:37:14', 'admin', '2026-05-30 11:06:55');
INSERT INTO `bus_vehicle_driver_history` VALUES (19, 4010, 2012, '2026-05-30 14:37:19', NULL, 'admin', '2026-05-30 14:37:19');
INSERT INTO `bus_vehicle_driver_history` VALUES (20, 4008, 2011, '2026-06-01 09:32:06', '2026-06-01 09:40:02', 'felix', '2026-06-01 09:32:06');
INSERT INTO `bus_vehicle_driver_history` VALUES (21, 4008, 2011, '2026-06-01 09:40:23', '2026-06-01 11:05:35', 'felix', '2026-06-01 09:40:23');
INSERT INTO `bus_vehicle_driver_history` VALUES (22, 4009, 2014, '2026-06-01 10:14:56', '2026-06-01 17:22:31', 'felix', '2026-06-01 10:14:56');
INSERT INTO `bus_vehicle_driver_history` VALUES (23, 4009, 2014, '2026-06-01 17:24:25', '2026-06-01 17:53:39', '13533746715', '2026-06-01 17:24:25');
INSERT INTO `bus_vehicle_driver_history` VALUES (24, 4013, 2015, '2026-06-02 09:34:09', NULL, 'admin', '2026-06-02 09:34:09');

-- ----------------------------
-- Table structure for bus_vehicle_location
-- ----------------------------
DROP TABLE IF EXISTS `bus_vehicle_location`;
CREATE TABLE `bus_vehicle_location`  (
  `id` bigint NOT NULL AUTO_INCREMENT COMMENT '主键',
  `vehicle_id` bigint NOT NULL COMMENT '车辆ID（bus_vehicle.id）',
  `driver_id` bigint NULL DEFAULT NULL COMMENT '当前司机ID',
  `lng` double NOT NULL COMMENT '经度',
  `lat` double NOT NULL COMMENT '纬度',
  `speed` double NULL DEFAULT NULL COMMENT '速度 km/h',
  `heading` double NULL DEFAULT NULL COMMENT '方向角',
  `update_time` datetime NOT NULL COMMENT '位置更新时间',
  `tenant_id` varchar(32) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci NULL DEFAULT NULL COMMENT '租户ID',
  PRIMARY KEY (`id`) USING BTREE,
  UNIQUE INDEX `uk_bvl_vehicle`(`vehicle_id` ASC) USING BTREE,
  INDEX `idx_bvl_driver`(`driver_id` ASC) USING BTREE,
  INDEX `idx_bvl_tenant`(`tenant_id` ASC) USING BTREE,
  INDEX `idx_bvl_time`(`update_time` ASC) USING BTREE
) ENGINE = InnoDB AUTO_INCREMENT = 17 CHARACTER SET = utf8mb4 COLLATE = utf8mb4_0900_ai_ci COMMENT = '车辆最新位置快照' ROW_FORMAT = DYNAMIC;

-- ----------------------------
-- Records of bus_vehicle_location
-- ----------------------------
INSERT INTO `bus_vehicle_location` VALUES (1, 3, 700045867025624230, 113.334797, 22.996249, NULL, NULL, '2026-05-18 18:09:38', '1');
INSERT INTO `bus_vehicle_location` VALUES (2, 1, 700045867025624230, 113.330053, 23.131915, NULL, NULL, '2026-05-26 10:33:48', '1');
INSERT INTO `bus_vehicle_location` VALUES (3, 8, 4, 113.329688, 23.131629, NULL, NULL, '2026-05-22 16:31:28', '1');
INSERT INTO `bus_vehicle_location` VALUES (4, 4, 5, 113.330012, 23.1318, NULL, NULL, '2026-05-29 18:46:51', '1');
INSERT INTO `bus_vehicle_location` VALUES (5, 4001, 2001, 113.3218, 23.1269, 45.5, 90, '2026-05-27 11:00:01', '1');
INSERT INTO `bus_vehicle_location` VALUES (6, 4002, 2002, 113.3245, 23.1088, 38.2, 85, '2026-05-27 11:00:01', '1');
INSERT INTO `bus_vehicle_location` VALUES (7, 4003, NULL, 113.33, 23.13, 0, 0, '2026-05-27 11:00:01', '1');
INSERT INTO `bus_vehicle_location` VALUES (8, 4004, 2003, 113.2675, 23.1275, 42, 180, '2026-05-27 11:00:01', '1');
INSERT INTO `bus_vehicle_location` VALUES (9, 4005, NULL, 113.241, 23.123, 0, 0, '2026-05-27 11:00:01', '1');
INSERT INTO `bus_vehicle_location` VALUES (10, 4006, 2006, 113.3225, 23.1272, 0, 0, '2026-05-27 11:00:01', '1');
INSERT INTO `bus_vehicle_location` VALUES (11, 4007, NULL, 113.4, 23.06, 0, 0, '2026-05-27 11:00:01', '1');
INSERT INTO `bus_vehicle_location` VALUES (12, 4008, 2008, 113.3655, 22.9455, 52.3, 90, '2026-05-27 11:00:01', '1');
INSERT INTO `bus_vehicle_location` VALUES (13, 4009, 700045867025624230, 113.334529, 22.996153, 35, 270, '2026-05-30 14:16:20', '1');
INSERT INTO `bus_vehicle_location` VALUES (14, 4010, 28888, 113.330195, 23.131879, 0, 0, '2026-06-01 18:29:34', '1');
INSERT INTO `bus_vehicle_location` VALUES (15, 700045867025624230, 700045867025624230, 113.334532, 22.996097, NULL, NULL, '2026-05-28 16:51:03', '1');
INSERT INTO `bus_vehicle_location` VALUES (16, 4013, 88885566, 113.330035, 23.131801, NULL, NULL, '2026-06-02 10:11:31', '1');

-- ----------------------------
-- Table structure for bus_vehicle_tablet_history
-- ----------------------------
DROP TABLE IF EXISTS `bus_vehicle_tablet_history`;
CREATE TABLE `bus_vehicle_tablet_history`  (
  `id` bigint NOT NULL AUTO_INCREMENT COMMENT 'ID',
  `vehicle_id` bigint NOT NULL COMMENT '车辆ID',
  `device_number` varchar(50) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci NOT NULL COMMENT '设备号',
  `bind_time` datetime NOT NULL COMMENT '绑定时间',
  `unbind_time` datetime NULL DEFAULT NULL COMMENT '解绑时间',
  `operator` varchar(50) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci NULL DEFAULT NULL COMMENT '操作人',
  `create_time` datetime NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
  PRIMARY KEY (`id`) USING BTREE,
  INDEX `idx_vehicle_id`(`vehicle_id` ASC) USING BTREE,
  INDEX `idx_device_number`(`device_number` ASC) USING BTREE,
  INDEX `idx_bind_time`(`bind_time` ASC) USING BTREE
) ENGINE = InnoDB AUTO_INCREMENT = 2 CHARACTER SET = utf8mb4 COLLATE = utf8mb4_0900_ai_ci COMMENT = '车辆平板绑定历史表' ROW_FORMAT = DYNAMIC;

-- ----------------------------
-- Records of bus_vehicle_tablet_history
-- ----------------------------
INSERT INTO `bus_vehicle_tablet_history` VALUES (1, 4013, 'invocation258270915', '2026-06-02 09:37:27', NULL, 'admin', '2026-06-02 09:37:27');

-- ----------------------------
-- Table structure for bus_waiting_station
-- ----------------------------
DROP TABLE IF EXISTS `bus_waiting_station`;
CREATE TABLE `bus_waiting_station`  (
  `id` bigint NOT NULL AUTO_INCREMENT COMMENT '主键',
  `station_id` bigint NOT NULL COMMENT '基础站点ID（关联 bus_station.id）',
  `station_name` varchar(100) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci NOT NULL COMMENT '站点名称',
  `area_id` bigint NOT NULL COMMENT '运营区域ID（关联 bus_area.id）',
  `area_name` varchar(100) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci NULL DEFAULT NULL COMMENT '运营区域名称',
  `waiting_radius` decimal(4, 1) NOT NULL COMMENT '候客半径(米)',
  `status` tinyint NULL DEFAULT 1 COMMENT '状态：0-停用，1-启用',
  `dept_id` bigint NULL DEFAULT NULL COMMENT '部门ID（数据权限）',
  `create_time` datetime NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
  `create_by` varchar(64) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci NULL DEFAULT NULL COMMENT '创建人',
  `update_time` datetime NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
  `update_by` varchar(64) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci NULL DEFAULT NULL COMMENT '更新人',
  `tenant_id` varchar(32) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci NULL DEFAULT NULL COMMENT '租户ID',
  `del_flag` varchar(1) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci NULL DEFAULT '0' COMMENT '删除标记：0-未删除，1-已删除',
  PRIMARY KEY (`id`) USING BTREE,
  INDEX `idx_bws_station_id`(`station_id` ASC) USING BTREE,
  INDEX `idx_bws_area_id`(`area_id` ASC) USING BTREE,
  INDEX `idx_bws_status`(`status` ASC) USING BTREE,
  INDEX `idx_bws_tenant_id`(`tenant_id` ASC) USING BTREE,
  INDEX `idx_bws_del_flag`(`del_flag` ASC) USING BTREE
) ENGINE = InnoDB AUTO_INCREMENT = 14 CHARACTER SET = utf8mb4 COLLATE = utf8mb4_0900_ai_ci COMMENT = '候客站点表' ROW_FORMAT = DYNAMIC;

-- ----------------------------
-- Records of bus_waiting_station
-- ----------------------------
INSERT INTO `bus_waiting_station` VALUES (1, 1, '测试站点A', 1, '测试区域A', 50.0, 1, NULL, '2026-04-06 17:25:13', 'admin', '2026-04-06 17:25:13', 'admin', '1', '0');
INSERT INTO `bus_waiting_station` VALUES (2, 9, '创展中心', 6, '海珠区', 30.0, 1, NULL, '2026-04-24 16:04:45', 'admin', '2026-04-24 16:04:44', NULL, '1', '0');
INSERT INTO `bus_waiting_station` VALUES (3, 10, '体育中心站', 10, '天河区', 50.0, 1, NULL, '2026-04-30 16:47:52', 'admin', '2026-05-14 17:06:31', NULL, '1', '1');
INSERT INTO `bus_waiting_station` VALUES (4, 2001, '体育西路站', 201, '天河核心区', 50.0, 1, NULL, '2026-05-27 11:00:07', NULL, '2026-05-27 11:00:07', NULL, '1', '0');
INSERT INTO `bus_waiting_station` VALUES (5, 2002, '珠江新城站', 201, '天河核心区', 60.0, 1, NULL, '2026-05-27 11:00:07', NULL, '2026-05-27 11:00:07', NULL, '1', '0');
INSERT INTO `bus_waiting_station` VALUES (6, 2003, '广州塔站', 202, '海珠滨江带', 45.0, 1, NULL, '2026-05-27 11:00:07', NULL, '2026-05-27 11:00:07', NULL, '1', '0');
INSERT INTO `bus_waiting_station` VALUES (7, 2004, '客村站', 202, '海珠滨江带', 55.0, 1, NULL, '2026-05-27 11:00:07', NULL, '2026-05-27 11:00:07', NULL, '1', '0');
INSERT INTO `bus_waiting_station` VALUES (8, 2005, '大学城北站', 203, '番禺大学城', 70.0, 1, NULL, '2026-05-27 11:00:07', NULL, '2026-05-27 11:00:07', NULL, '1', '0');
INSERT INTO `bus_waiting_station` VALUES (9, 2006, '番禺广场站', 203, '番禺大学城', 65.0, 1, NULL, '2026-05-27 11:00:07', NULL, '2026-05-27 11:00:07', NULL, '1', '0');
INSERT INTO `bus_waiting_station` VALUES (10, 2007, '公园前站', 204, '越秀老城区', 40.0, 1, NULL, '2026-05-27 11:00:07', NULL, '2026-05-27 11:00:07', NULL, '1', '0');
INSERT INTO `bus_waiting_station` VALUES (11, 2008, '北京路站', 204, '越秀老城区', 50.0, 1, NULL, '2026-05-27 11:00:07', NULL, '2026-05-27 11:00:07', NULL, '1', '0');
INSERT INTO `bus_waiting_station` VALUES (12, 2009, '陈家祠站', 205, '荔湾老西关', 45.0, 1, NULL, '2026-05-27 11:00:07', NULL, '2026-05-27 11:00:07', NULL, '1', '0');
INSERT INTO `bus_waiting_station` VALUES (13, 2010, '长寿路站', 205, '荔湾老西关', 55.0, 1, NULL, '2026-05-27 11:00:07', NULL, '2026-05-27 11:00:07', NULL, '1', '0');

-- ----------------------------
-- Table structure for bus_waiting_time_slot
-- ----------------------------
DROP TABLE IF EXISTS `bus_waiting_time_slot`;
CREATE TABLE `bus_waiting_time_slot`  (
  `id` bigint NOT NULL AUTO_INCREMENT COMMENT '主键',
  `waiting_station_id` bigint NOT NULL COMMENT '候客站点ID（关联 bus_waiting_station.id）',
  `date` date NOT NULL COMMENT '日期',
  `start_time` varchar(5) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci NOT NULL COMMENT '开始时间(HH:mm)',
  `end_time` varchar(5) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci NOT NULL COMMENT '结束时间(HH:mm)',
  `waiting_duration` int NOT NULL COMMENT '候客时长(分钟)',
  `driver_count` int NOT NULL DEFAULT 1 COMMENT '候客司机人数',
  `create_time` datetime NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
  `create_by` varchar(64) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci NULL DEFAULT NULL COMMENT '创建人',
  `update_time` datetime NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
  `update_by` varchar(64) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci NULL DEFAULT NULL COMMENT '更新人',
  `tenant_id` varchar(32) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci NULL DEFAULT NULL COMMENT '租户ID',
  `del_flag` varchar(1) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci NULL DEFAULT '0' COMMENT '删除标记：0-未删除，1-已删除',
  PRIMARY KEY (`id`) USING BTREE,
  INDEX `idx_bwts_station_date`(`waiting_station_id` ASC, `date` ASC) USING BTREE,
  INDEX `idx_bwts_date`(`date` ASC) USING BTREE,
  INDEX `idx_bwts_tenant_id`(`tenant_id` ASC) USING BTREE,
  INDEX `idx_bwts_del_flag`(`del_flag` ASC) USING BTREE
) ENGINE = InnoDB AUTO_INCREMENT = 23 CHARACTER SET = utf8mb4 COLLATE = utf8mb4_0900_ai_ci COMMENT = '候客时段表' ROW_FORMAT = DYNAMIC;

-- ----------------------------
-- Records of bus_waiting_time_slot
-- ----------------------------
INSERT INTO `bus_waiting_time_slot` VALUES (1, 1, '2026-04-06', '08:00', '10:00', 30, 3, '2026-04-06 17:25:13', 'admin', '2026-04-06 17:25:13', 'admin', '1', '0');
INSERT INTO `bus_waiting_time_slot` VALUES (2, 2, '2026-04-20', '16:04', '16:06', 30, 4, '2026-04-24 16:05:04', 'admin', '2026-04-24 16:05:03', NULL, '1', '0');
INSERT INTO `bus_waiting_time_slot` VALUES (3, 3, '2026-04-27', '06:00', '22:00', 30, 1, '2026-04-30 16:48:36', 'admin', '2026-04-30 16:48:40', NULL, '1', '1');
INSERT INTO `bus_waiting_time_slot` VALUES (4, 3, '2026-04-27', '06:00', '22:00', 30, 1, '2026-04-30 16:48:44', 'admin', '2026-04-30 16:48:42', NULL, '1', '1');
INSERT INTO `bus_waiting_time_slot` VALUES (5, 3, '2026-04-27', '06:00', '22:00', 30, 1, '2026-04-30 16:48:46', 'admin', '2026-04-30 16:48:44', NULL, '1', '1');
INSERT INTO `bus_waiting_time_slot` VALUES (6, 3, '2026-04-27', '06:00', '22:00', 30, 1, '2026-04-30 16:48:48', 'admin', '2026-04-30 16:48:51', NULL, '1', '1');
INSERT INTO `bus_waiting_time_slot` VALUES (7, 3, '2026-04-27', '06:00', '22:00', 30, 1, '2026-04-30 16:48:55', 'admin', '2026-04-30 16:58:18', NULL, '1', '1');
INSERT INTO `bus_waiting_time_slot` VALUES (8, 3, '2026-04-27', '06:00', '22:00', 30, 1, '2026-04-30 16:58:22', 'admin', '2026-05-14 17:06:31', NULL, '1', '1');
INSERT INTO `bus_waiting_time_slot` VALUES (9, 2, '2026-05-11', '17:05', '18:05', 30, 1, '2026-05-14 17:06:42', 'admin', '2026-05-15 15:36:51', NULL, '1', '1');
INSERT INTO `bus_waiting_time_slot` VALUES (10, 2, '2026-05-12', '18:06', '21:06', 30, 1, '2026-05-14 17:06:59', 'admin', '2026-05-14 17:06:57', NULL, '1', '0');
INSERT INTO `bus_waiting_time_slot` VALUES (11, 2, '2026-05-11', '17:05', '18:05', 30, 1, '2026-05-15 15:36:53', 'admin', '2026-05-15 15:36:51', NULL, '1', '0');
INSERT INTO `bus_waiting_time_slot` VALUES (12, 2, '2026-05-11', '18:36', '19:36', 30, 1, '2026-05-15 15:36:53', 'admin', '2026-05-15 15:36:51', NULL, '1', '0');
INSERT INTO `bus_waiting_time_slot` VALUES (13, 1, '2026-05-27', '07:00', '09:00', 30, 3, '2026-05-27 11:00:12', NULL, '2026-05-27 11:00:12', NULL, '1', '0');
INSERT INTO `bus_waiting_time_slot` VALUES (14, 1, '2026-05-27', '17:00', '19:00', 30, 4, '2026-05-27 11:00:12', NULL, '2026-05-27 11:00:12', NULL, '1', '0');
INSERT INTO `bus_waiting_time_slot` VALUES (15, 2, '2026-05-27', '08:00', '10:00', 30, 2, '2026-05-27 11:00:12', NULL, '2026-05-27 11:00:12', NULL, '1', '0');
INSERT INTO `bus_waiting_time_slot` VALUES (16, 2, '2026-05-27', '18:00', '20:00', 30, 3, '2026-05-27 11:00:12', NULL, '2026-05-27 11:00:12', NULL, '1', '0');
INSERT INTO `bus_waiting_time_slot` VALUES (17, 3, '2026-05-27', '07:30', '09:30', 30, 2, '2026-05-27 11:00:12', NULL, '2026-05-27 11:00:12', NULL, '1', '0');
INSERT INTO `bus_waiting_time_slot` VALUES (18, 3, '2026-05-27', '16:00', '18:00', 30, 3, '2026-05-27 11:00:12', NULL, '2026-05-27 11:00:12', NULL, '1', '0');
INSERT INTO `bus_waiting_time_slot` VALUES (19, 4, '2026-05-27', '08:00', '10:00', 30, 2, '2026-05-27 11:00:12', NULL, '2026-05-27 11:00:12', NULL, '1', '0');
INSERT INTO `bus_waiting_time_slot` VALUES (20, 5, '2026-05-27', '08:00', '17:00', 60, 1, '2026-05-27 11:00:12', NULL, '2026-05-27 11:00:12', NULL, '1', '0');
INSERT INTO `bus_waiting_time_slot` VALUES (21, 6, '2026-05-27', '09:00', '18:00', 60, 1, '2026-05-27 11:00:12', NULL, '2026-05-27 11:00:12', NULL, '1', '0');
INSERT INTO `bus_waiting_time_slot` VALUES (22, 7, '2026-05-27', '07:00', '09:00', 30, 2, '2026-05-27 11:00:12', NULL, '2026-05-27 11:00:12', NULL, '1', '0');

SET FOREIGN_KEY_CHECKS = 1;
