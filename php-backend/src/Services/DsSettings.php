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
            'review_logistics_mode',
            'review_logistics_exclude_same_day_refund',
        ] as $key) {
            if (array_key_exists($key, $body)) {
                $val = $body[$key];
                if (is_string($val)) {
                    $val = trim($val);
                }
                $out[$key] = ($val === '' || $val === null) ? null : $val;
            }
        }
        if (array_key_exists('review_logistics_per_order', $body)) {
            $raw = $body['review_logistics_per_order'];
            if ($raw === null || $raw === '') {
                $out['review_logistics_per_order'] = null;
            } else {
                $out['review_logistics_per_order'] = max(0.0, (float) $raw);
            }
        }
        if (array_key_exists('review_logistics_exclude_same_day_refund', $body)) {
            $out['review_logistics_exclude_same_day_refund'] = (bool) $body['review_logistics_exclude_same_day_refund'];
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
        if (array_key_exists('sample_orders', $patch)) {
            $cfg['sample_orders'] = array_values($patch['sample_orders'] ?? []);
        }
        if (array_key_exists('sample_order_ids', $patch)) {
            $cfg['sample_order_ids'] = array_values($patch['sample_order_ids'] ?? []);
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
        $reviews = $cfg['review_orders'] ?? [];
        $samples = $cfg['sample_orders'] ?? [];
        $sampleDistinct = [];
        foreach ($samples as $r) {
            $oid = trim((string) ($r['order_id'] ?? ''));
            if ($oid !== '') {
                $sampleDistinct[$oid] = true;
            }
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
            'review_order_count' => count($reviews ?: ($cfg['review_order_ids'] ?? [])),
            'review_order_distinct' => ReviewImport::distinctReviewOrderCount($reviews),
            'review_logistics_mode' => ReviewImport::reviewLogisticsMode($cfg),
            'review_logistics_per_order' => ReviewImport::reviewLogisticsPerOrder($cfg),
            'review_logistics_exclude_same_day_refund' => ReviewImport::reviewLogisticsExcludeSameDayRefund($cfg),
            'review_logistics_rule_summary' => ReviewImport::reviewLogisticsRuleSummary($cfg),
            'sample_order_count' => count($samples),
            'sample_order_distinct' => count($sampleDistinct),
            'date_master_summary' => self::dateMasterSummary($cfg),
        ];
    }
}
