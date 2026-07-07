<?php

declare(strict_types=1);

namespace App\Services;

use App\Database;

/**
 * 逻辑 file/sheet/列头 → 物理表字段，与 Python 版 services/catalog_resolver.py 对等。
 */
final class CatalogResolver
{
    public static function hasCatalog(int $dataSourceId): bool
    {
        return (bool) Database::fetchValue(
            'SELECT id FROM catalog_files WHERE data_source_id = ? AND is_active = 1 LIMIT 1',
            [$dataSourceId]
        );
    }

    /** @return array<int, array{file_name: string, keyword: string}> */
    public static function listCatalogFiles(int $dataSourceId): array
    {
        $rows = Database::fetchAll(
            'SELECT file_name, keyword FROM catalog_files WHERE data_source_id = ? AND is_active = 1 ORDER BY id',
            [$dataSourceId]
        );
        return array_map(fn($r) => ['file_name' => $r['file_name'], 'keyword' => $r['keyword']], $rows);
    }

    /** @return string[] */
    public static function listCatalogSheets(int $dataSourceId, string $fileKeyword): array
    {
        $rows = Database::fetchAll(
            'SELECT DISTINCT cs.sheet_name FROM catalog_sheets cs
             JOIN catalog_files cf ON cs.file_id = cf.id
             WHERE cf.data_source_id = ? AND cf.keyword = ? AND cf.is_active = 1 AND cs.is_active = 1',
            [$dataSourceId, $fileKeyword]
        );
        $names = array_map(fn($r) => (string) $r['sheet_name'], $rows);
        sort($names);
        return $names;
    }

    /** @return string[] */
    public static function listCatalogColumns(int $dataSourceId, string $fileKeyword, string $sheetName): array
    {
        $rows = Database::fetchAll(
            'SELECT cc.header_name FROM catalog_columns cc
             JOIN catalog_sheets cs ON cc.sheet_id = cs.id
             JOIN catalog_files cf ON cs.file_id = cf.id
             WHERE cf.data_source_id = ? AND cf.keyword = ? AND cs.sheet_name = ?
               AND cf.is_active = 1 AND cs.is_active = 1 AND cc.is_active = 1',
            [$dataSourceId, $fileKeyword, $sheetName]
        );
        $names = [];
        foreach ($rows as $r) {
            if ($r['header_name'] !== null && $r['header_name'] !== '') {
                $names[$r['header_name']] = true;
            }
        }
        $out = array_keys($names);
        sort($out);
        return $out;
    }
}
