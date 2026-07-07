<?php

declare(strict_types=1);

namespace App\Services;

use App\Database;

/**
 * 数据源种子，与 Python 版 services/seed.py 中启动用到的部分对等。
 * （老 Demo 数据源 Amazon/Shopee/TikTok UK 已停用，仅保留美宠真实数据源。）
 */
final class Seed
{
    public const MEICHONG_STORE = '平衡贴美国本土店铺';
    public const MEICHONG_SOURCE_NAME = '美宠-平衡贴美国本土店铺(TK-US)';

    /** 注册美宠 TikTok 美国本土店数据源（不自动导入大文件，导入用独立脚本触发）。 */
    public static function ensureMeichongDatasource(): array
    {
        $existing = Database::fetchOne('SELECT * FROM data_sources WHERE name = ?', [self::MEICHONG_SOURCE_NAME]);
        if ($existing) {
            return $existing;
        }
        $id = Database::insert('data_sources', [
            'name' => self::MEICHONG_SOURCE_NAME,
            'platform' => 'TikTok Shop',
            'description' => '美宠项目·美国区域·TikTok·平衡贴美国本土店铺。源数据：订单/退货退款/结算/未结算/联盟达人佣金/联盟服务商佣金，按日报规则配置计算逻辑。',
            'created_at' => Database::utcNow(),
        ]);
        return Database::fetchOne('SELECT * FROM data_sources WHERE id = ?', [$id]);
    }
}
