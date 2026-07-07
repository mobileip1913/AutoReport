<?php

declare(strict_types=1);

namespace App;

use App\Services\DemoAccounts;
use App\Services\MeichongRules;
use App\Services\ReportLineSync;
use App\Services\Seed;

/**
 * 启动初始化，与 Python 版 main.py on_startup 对等。
 * 由 bin/init.php 调用（一次性），Web 请求不重复执行。
 */
final class Bootstrap
{
    public static function startup(): void
    {
        @mkdir(Config::rootDir() . '/data', 0777, true);
        Migrate::runMigrations();

        // 老 Demo 数据源（Amazon/Shopee/TikTok UK）已停用，仅保留美宠真实数据源
        Seed::ensureMeichongDatasource();
        ReportLineSync::ensureLogicalFields();
        ReportLineSync::migrateLegacyMappings();
        MeichongRules::ensureMeichongRules();
        ReportLineSync::backfillMappingLineCodes();

        foreach (self::configuredDataSources() as $ds) {
            $hasGrouped = (int) Database::fetchValue(
                'SELECT COUNT(*) FROM field_mappings WHERE data_source_id = ? AND report_group IS NOT NULL',
                [(int) $ds['id']]
            );
            if (!$hasGrouped) {
                ReportLineSync::syncReportLines(
                    (int) $ds['id'],
                    MeichongRules::templateLines(),
                    MeichongRules::templateGroups(),
                    true
                );
            }
        }

        DemoAccounts::ensureDemoAccounts();

        foreach (self::configuredDataSources() as $ds) {
            ReportLineSync::convertFormulaLinesToFetch((int) $ds['id']);
        }
    }

    /** @return array[] config 非空的数据源 */
    private static function configuredDataSources(): array
    {
        return Database::fetchAll("SELECT * FROM data_sources WHERE config IS NOT NULL AND config != ''");
    }
}
