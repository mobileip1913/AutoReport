<?php

declare(strict_types=1);

namespace App\Services;

use App\Database;

/**
 * 生产事实表读写辅助：store_id 解析、extra_data 展开。
 * 与 Python 版 services/production_fact.py 对等（出报读数所需子集）。
 */
final class ProductionFact
{
    public static function isProductionFactTable(string $tableName): bool
    {
        return str_starts_with($tableName, 'eb_overseas_tk_');
    }

    /** @return array{0: ?int, 1: ?string} [production_store_id, shop_code] */
    public static function resolveProductionStore(int $dataSourceId, string $storeName): array
    {
        $store = Database::fetchOne('SELECT * FROM stores WHERE data_source_id = ?', [$dataSourceId]);
        if ($store && !empty($store['production_store_id'])) {
            return [(int) $store['production_store_id'], $store['shop_code'] ?? null];
        }

        $ds = Database::fetchOne('SELECT * FROM data_sources WHERE id = ?', [$dataSourceId]);
        $cfg = DsSettings::getDsConfig($ds);
        $storeId = $cfg['production_store_id'] ?? null;
        $shopCode = $cfg['shop_code'] ?? null;
        if ($storeId !== null && $storeId !== '') {
            return [(int) $storeId, is_string($shopCode) ? $shopCode : null];
        }

        return [null, is_string($shopCode) ? $shopCode : null];
    }

    /**
     * DB 行 → 聚合器使用的 header 键字典。
     * @param array<string, string> $headerByDb
     * @return array<string, mixed>
     */
    public static function expandProductionRecord(array $record, string $tableName, array $headerByDb): array
    {
        $rowData = [];
        foreach ($headerByDb as $dbCol => $header) {
            if (array_key_exists($dbCol, $record) && $record[$dbCol] !== null) {
                $rowData[$header] = $record[$dbCol];
            }
        }

        $extra = $record['extra_data'] ?? null;
        if (!$extra) {
            return $rowData;
        }
        if (is_string($extra)) {
            $extra = Database::jsonDecode($extra, []);
        }
        if (!is_array($extra)) {
            return $rowData;
        }
        foreach ($extra as $key => $val) {
            $header = is_string($key) ? $key : (string) $key;
            if (!array_key_exists($header, $rowData) || $rowData[$header] === null) {
                $rowData[$header] = $val;
            }
        }
        return $rowData;
    }
}
