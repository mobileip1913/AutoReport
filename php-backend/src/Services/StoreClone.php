<?php

declare(strict_types=1);

namespace App\Services;

use App\Database;

/**
 * 店铺级配置克隆：Catalog + 报表行（含 parts），与 Python 版 services/store_clone.py 对等。
 */
final class StoreClone
{
    public static function cloneCatalog(int $srcDsId, int $dstDsId): int
    {
        $count = (int) Database::fetchValue('SELECT COUNT(*) FROM catalog_files WHERE data_source_id = ?', [$dstDsId]);
        if ($count) {
            return 0;
        }

        $n = 0;
        foreach (Database::fetchAll('SELECT * FROM catalog_files WHERE data_source_id = ?', [$srcDsId]) as $srcFile) {
            $dstFileId = Database::insert('catalog_files', [
                'data_source_id' => $dstDsId,
                'keyword' => $srcFile['keyword'],
                'file_label' => $srcFile['file_label'],
                'file_name' => $srcFile['file_name'],
                'is_active' => $srcFile['is_active'],
                'created_at' => Database::utcNow(),
            ]);
            $n++;
            foreach (Database::fetchAll('SELECT * FROM catalog_sheets WHERE file_id = ?', [(int) $srcFile['id']]) as $srcSheet) {
                $dstSheetId = Database::insert('catalog_sheets', [
                    'file_id' => $dstFileId,
                    'sheet_name' => $srcSheet['sheet_name'],
                    'fact_table' => $srcSheet['fact_table'],
                    'is_active' => $srcSheet['is_active'],
                ]);
                foreach (Database::fetchAll('SELECT * FROM catalog_columns WHERE sheet_id = ?', [(int) $srcSheet['id']]) as $srcCol) {
                    Database::insert('catalog_columns', [
                        'sheet_id' => $dstSheetId,
                        'header_name' => $srcCol['header_name'],
                        'db_column' => $srcCol['db_column'],
                        'column_aliases' => $srcCol['column_aliases'],
                        'data_type' => $srcCol['data_type'],
                        'is_active' => $srcCol['is_active'],
                    ]);
                }
            }
        }
        return $n;
    }

    public static function cloneFieldMappings(int $srcDsId, int $dstDsId): int
    {
        $count = (int) Database::fetchValue('SELECT COUNT(*) FROM field_mappings WHERE data_source_id = ?', [$dstDsId]);
        if ($count) {
            return 0;
        }

        $n = 0;
        $srcMappings = Database::fetchAll(
            'SELECT * FROM field_mappings WHERE data_source_id = ? ORDER BY sort_order, id',
            [$srcDsId]
        );
        foreach ($srcMappings as $src) {
            $dstId = Database::insert('field_mappings', [
                'data_source_id' => $dstDsId,
                'logical_field_id' => $src['logical_field_id'],
                'line_type' => $src['line_type'],
                'label' => $src['label'],
                'line_code' => $src['line_code'],
                'report_group' => $src['report_group'],
                'sort_order' => $src['sort_order'],
                'expression' => $src['expression'],
                'format_type' => $src['format_type'],
                'is_highlight' => $src['is_highlight'],
                'owner_id' => $src['owner_id'],
                'description' => $src['description'],
                'sheet_name' => $src['sheet_name'],
                'column_header' => $src['column_header'],
                'aliases' => $src['aliases'],
                'aggregation' => $src['aggregation'],
            ]);
            $n++;
            $parts = Database::fetchAll(
                'SELECT * FROM field_mapping_parts WHERE mapping_id = ? ORDER BY sort_order, id',
                [(int) $src['id']]
            );
            foreach ($parts as $part) {
                Database::insert('field_mapping_parts', [
                    'mapping_id' => $dstId,
                    'sort_order' => $part['sort_order'],
                    'label' => $part['label'],
                    'source_file_keyword' => $part['source_file_keyword'],
                    'sheet_name' => $part['sheet_name'],
                    'column_header' => $part['column_header'],
                    'aliases' => $part['aliases'],
                    'combine_op' => $part['combine_op'],
                    'aggregation' => $part['aggregation'],
                    'dedup_keys' => $part['dedup_keys'],
                    'date_filter_column' => $part['date_filter_column'],
                    'date_format' => $part['date_format'],
                    'row_filters' => $part['row_filters'],
                    'exclude_sample' => $part['exclude_sample'],
                    'exclude_review' => $part['exclude_review'],
                    'join_to_orders' => $part['join_to_orders'],
                    'join_keys' => $part['join_keys'],
                    'only_sample' => $part['only_sample'],
                    'sources' => $part['sources'],
                    'ref_field_code' => $part['ref_field_code'],
                ]);
            }
        }
        return $n;
    }
}
