<?php

declare(strict_types=1);

namespace App\Services;

use App\Database;

/**
 * 从 MySQL 事实表加载聚合用行数据，与 Python 版 services/fact_provider.py 对等。
 * 行结构：['data_import_id' => int, 'sheet_name' => string, 'row_data' => array]
 */
final class FactProvider
{
    /**
     * @return array{0: array[], 1: array<int, string>} [rows, import_file_names]
     */
    public static function loadFactRows(int $dataSourceId, string $storeName): array
    {
        $sheets = Database::fetchAll(
            'SELECT cs.id AS sheet_id, cs.sheet_name, cs.fact_table, cf.id AS file_id, cf.file_name
             FROM catalog_sheets cs
             JOIN catalog_files cf ON cs.file_id = cf.id
             WHERE cf.data_source_id = ? AND cf.is_active = 1 AND cs.is_active = 1',
            [$dataSourceId]
        );
        if (!$sheets) {
            return [[], []];
        }

        $importFileNames = [];
        foreach ($sheets as $s) {
            $importFileNames[(int) $s['file_id']] = (string) $s['file_name'];
        }

        $rows = [];
        foreach ($sheets as $s) {
            $columns = Database::fetchAll(
                'SELECT header_name, db_column, column_aliases FROM catalog_columns
                 WHERE sheet_id = ? AND is_active = 1',
                [(int) $s['sheet_id']]
            );
            if (!$columns) {
                continue;
            }
            $tableCols = Database::tableColumns((string) $s['fact_table']);
            $tableColSet = array_flip($tableCols);
            $activeCols = array_values(array_filter($columns, fn($c) => isset($tableColSet[$c['db_column']])));
            if (!$activeCols) {
                continue;
            }
            $dbCols = array_merge(['id'], array_map(fn($c) => (string) $c['db_column'], $activeCols));
            $selectSql = implode(', ', array_map(fn($c) => "`$c`", $dbCols));
            $factTable = (string) $s['fact_table'];
            $records = Database::fetchAll(
                "SELECT {$selectSql} FROM `{$factTable}` WHERE data_source_id = ? AND store_name = ?",
                [$dataSourceId, $storeName]
            );
            foreach ($records as $record) {
                $rowData = [];
                foreach ($activeCols as $col) {
                    $val = $record[$col['db_column']] ?? null;
                    $rowData[(string) $col['header_name']] = $val;
                    foreach (Database::jsonDecode($col['column_aliases'], []) ?: [] as $alias) {
                        $rowData[(string) $alias] = $val;
                    }
                }
                $rows[] = [
                    'data_import_id' => (int) $s['file_id'],
                    'sheet_name' => (string) $s['sheet_name'],
                    'row_data' => $rowData,
                ];
            }
        }
        return [$rows, $importFileNames];
    }
}
