<?php

declare(strict_types=1);

namespace App\Services;

use App\Database;

/**
 * 数据源级配置：日期主表、定时出报等，与 Python 版 services/ds_settings.py 对等。
 */
final class DsSettings
{
    public const DEFAULT_JOIN_KEYS = ['Order ID', 'SKU ID'];

    /** @param array|null $ds data_sources 行 */
    public static function getDsConfig(?array $ds): array
    {
        if (!$ds || empty($ds['config'])) {
            return [];
        }
        return Database::jsonDecode($ds['config'], []) ?: [];
    }

    public static function dateMasterSummary(array $cfg): string
    {
        $parts = [];
        if (!empty($cfg['order_file'])) {
            $parts[] = '[' . $cfg['order_file'] . ']';
        }
        if (!empty($cfg['order_sheet'])) {
            $parts[] = $cfg['order_sheet'];
        }
        if (!empty($cfg['order_date_col'])) {
            $parts[] = $cfg['order_date_col'];
        }
        return $parts ? implode(' · ', $parts) : '未配置';
    }

    public static function applyDateMaster(array $cfg, array $body): array
    {
        $out = $cfg;
        foreach ([
            'order_file',
            'order_sheet',
            'order_date_col',
            'order_date_format',
            'order_id_col',
            'sku_id_col',
            'daily_generate_at',
            'excel_template_file',
        ] as $key) {
            if (array_key_exists($key, $body)) {
                $val = $body[$key];
                if (is_string($val)) {
                    $val = trim($val);
                }
                $out[$key] = ($val === '' || $val === null) ? null : $val;
            }
        }
        return $out;
    }

    /** 保存配置并返回新 config；$ds 引用会被更新。 */
    public static function saveDsConfig(array &$ds, array $patch): array
    {
        $cfg = self::applyDateMaster(self::getDsConfig($ds), $patch);
        if (array_key_exists('review_order_ids', $patch)) {
            $cfg['review_order_ids'] = array_values($patch['review_order_ids'] ?? []);
        }
        if (array_key_exists('review_orders', $patch)) {
            $cfg['review_orders'] = array_values($patch['review_orders'] ?? []);
        }
        Database::updateById('data_sources', (int) $ds['id'], ['config' => Database::jsonEncode($cfg)]);
        $ds['config'] = Database::jsonEncode($cfg);
        return $cfg;
    }

    public static function serializeDsSettings(array $ds, ?array $store = null): array
    {
        $cfg = self::getDsConfig($ds);
        if ($store === null) {
            $store = Database::fetchOne('SELECT * FROM stores WHERE data_source_id = ?', [(int) $ds['id']]);
        }
        return [
            'data_source_id' => (int) $ds['id'],
            'store_id' => $store ? (int) $store['id'] : null,
            'store_name' => $store ? (string) $store['name'] : '',
            'order_file' => $cfg['order_file'] ?? '',
            'order_sheet' => $cfg['order_sheet'] ?? '',
            'order_date_col' => $cfg['order_date_col'] ?? '',
            'order_date_format' => $cfg['order_date_format'] ?? '',
            'order_id_col' => ($cfg['order_id_col'] ?? '') ?: 'Order ID',
            'sku_id_col' => ($cfg['sku_id_col'] ?? '') ?: 'SKU ID',
            'daily_generate_at' => $cfg['daily_generate_at'] ?? '',
            'excel_template_file' => $cfg['excel_template_file'] ?? '',
            'review_order_count' => count(($cfg['review_orders'] ?? []) ?: ($cfg['review_order_ids'] ?? [])),
            'date_master_summary' => self::dateMasterSummary($cfg),
        ];
    }
}
