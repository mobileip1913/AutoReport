<?php

declare(strict_types=1);

namespace App\Services;

use App\Config;
use App\Database;

/**
 * 报表配置 JSON 导出，与 Python 版 services/config_export.py 对等。
 */
final class ConfigExport
{
    public const EXPORT_VERSION = '1.0';

    private const SETTINGS_KEYS = [
        'order_file',
        'order_sheet',
        'order_date_col',
        'order_date_format',
        'order_id_col',
        'sku_id_col',
        'daily_generate_at',
        'sample_rule',
        'meta',
        'excel_template_file',
    ];

    private static function serializePart(array $part): array
    {
        return [
            'sort_order' => (int) ($part['sort_order'] ?? 0),
            'label' => $part['label'] ?? null,
            'ref_field_code' => $part['ref_field_code'] ?? null,
            'source_file_keyword' => $part['source_file_keyword'] ?? null,
            'sheet_name' => $part['sheet_name'] ?? null,
            'column_header' => $part['column_header'] ?? null,
            'aliases' => Database::jsonDecode($part['aliases'] ?? null, []) ?: [],
            'sources' => Database::jsonDecode($part['sources'] ?? null, []) ?: [],
            'combine_op' => $part['combine_op'] ?? 'add',
            'aggregation' => $part['aggregation'] ?? 'sum',
            'dedup_keys' => Database::jsonDecode($part['dedup_keys'] ?? null, []) ?: [],
            'date_filter_column' => $part['date_filter_column'] ?? null,
            'date_format' => $part['date_format'] ?? null,
            'row_filters' => Database::jsonDecode($part['row_filters'] ?? null, []) ?: [],
            'exclude_sample' => (bool) ($part['exclude_sample'] ?? false),
            'exclude_review' => (bool) ($part['exclude_review'] ?? false),
            'join_to_orders' => (bool) ($part['join_to_orders'] ?? false),
            'join_keys' => Database::jsonDecode($part['join_keys'] ?? null, []) ?: [],
            'benchmark_keys' => Database::jsonDecode($part['benchmark_keys'] ?? null, []) ?: [],
            'only_sample' => (bool) ($part['only_sample'] ?? false),
        ];
    }

    private static function serializeReportLine(array $mapping): array
    {
        $lineType = $mapping['line_type'] ?? null;
        if (!$lineType) {
            if (MappingUtils::isFormulaLine($mapping)) {
                $lineType = 'formula';
            } elseif (MappingUtils::isManualLine($mapping)) {
                $lineType = 'manual';
            } else {
                $lineType = 'fetch';
            }
        }
        $parts = $mapping['parts'] ?? [];
        usort($parts, fn($a, $b) => ($a['sort_order'] ?? 0) <=> ($b['sort_order'] ?? 0));
        return [
            'line_type' => $lineType,
            'line_code' => MappingUtils::mappingLineCode($mapping),
            'label' => MappingUtils::mappingLabel($mapping),
            'report_group' => $mapping['report_group'] ?? null,
            'sort_order' => (int) ($mapping['sort_order'] ?? 0),
            'expression' => $mapping['expression'] ?? null,
            'format_type' => ($mapping['format_type'] ?? '') ?: 'usd',
            'is_highlight' => (bool) ($mapping['is_highlight'] ?? false),
            'description' => $mapping['description'] ?? null,
            'logical_field_code' => $mapping['logical_field_code'] ?? null,
            'parts' => array_map(fn($p) => self::serializePart($p), $parts),
        ];
    }

    private static function exportCatalog(int $dataSourceId): array
    {
        $filesOut = [];
        $files = Database::fetchAll(
            'SELECT * FROM catalog_files WHERE data_source_id = ? AND is_active = 1 ORDER BY id',
            [$dataSourceId]
        );
        foreach ($files as $file) {
            $sheetsOut = [];
            $sheets = Database::fetchAll(
                'SELECT * FROM catalog_sheets WHERE file_id = ? AND is_active = 1 ORDER BY sheet_name',
                [(int) $file['id']]
            );
            foreach ($sheets as $sheet) {
                $columns = Database::fetchAll(
                    'SELECT header_name, db_column, column_aliases, data_type FROM catalog_columns
                     WHERE sheet_id = ? AND is_active = 1 ORDER BY header_name',
                    [(int) $sheet['id']]
                );
                $columnsOut = array_map(fn($col) => [
                    'header_name' => $col['header_name'],
                    'db_column' => $col['db_column'],
                    'column_aliases' => Database::jsonDecode($col['column_aliases'] ?? null, []) ?: [],
                    'data_type' => ($col['data_type'] ?? '') ?: 'string',
                ], $columns);
                $sheetsOut[] = [
                    'sheet_name' => $sheet['sheet_name'],
                    'fact_table' => $sheet['fact_table'],
                    'columns' => $columnsOut,
                ];
            }
            $filesOut[] = [
                'keyword' => $file['keyword'],
                'file_label' => $file['file_label'],
                'file_name' => $file['file_name'],
                'sheets' => $sheetsOut,
            ];
        }
        return ['files' => $filesOut];
    }

    private static function exportSettings(array $cfg, bool $includeReviewOrders): array
    {
        $out = [];
        foreach (self::SETTINGS_KEYS as $key) {
            if (array_key_exists($key, $cfg)) {
                $out[$key] = $cfg[$key];
            }
        }
        if ($includeReviewOrders) {
            if (!empty($cfg['review_orders'])) {
                $out['review_orders'] = $cfg['review_orders'];
            } elseif (!empty($cfg['review_order_ids'])) {
                $out['review_order_ids'] = $cfg['review_order_ids'];
            }
        }
        return $out;
    }

    public static function buildConfigExport(array $ds, bool $includeReviewOrders = true): array
    {
        $cfg = DsSettings::getDsConfig($ds);
        $store = Database::fetchOne('SELECT * FROM stores WHERE data_source_id = ?', [(int) $ds['id']]);
        $mappings = MappingRepo::forDataSource((int) $ds['id'], true);
        return [
            'export_version' => self::EXPORT_VERSION,
            'exported_at' => (new \DateTimeImmutable('now', new \DateTimeZone('Asia/Shanghai')))->format('Y-m-d\TH:i:s'),
            'store' => [
                'name' => $store['name'] ?? null,
                'platform' => $store['platform'] ?? null,
            ],
            'data_source' => [
                'name' => $ds['name'],
                'platform' => $ds['platform'],
                'description' => $ds['description'] ?? null,
            ],
            'settings' => self::exportSettings($cfg, $includeReviewOrders),
            'catalog' => self::exportCatalog((int) $ds['id']),
            'report_lines' => array_map(fn($m) => self::serializeReportLine($m), $mappings),
        ];
    }

    public static function exportFilename(array $ds): string
    {
        $stamp = (new \DateTimeImmutable('now', new \DateTimeZone('Asia/Shanghai')))->format('Ymd');
        return "autoreport-config_ds{$ds['id']}_{$stamp}.json";
    }
}
