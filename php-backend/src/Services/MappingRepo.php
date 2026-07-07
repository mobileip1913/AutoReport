<?php

declare(strict_types=1);

namespace App\Services;

use App\Database;

/**
 * field_mappings 读取与序列化（含 parts 与逻辑字段信息）。
 * 对应 Python 版 ORM 关系加载 + routers/api.py 的 _serialize_mapping。
 */
final class MappingRepo
{
    private const SELECT = 'SELECT fm.*, lf.code AS logical_field_code, lf.name AS logical_field_name, ds.name AS data_source_name
        FROM field_mappings fm
        LEFT JOIN logical_fields lf ON fm.logical_field_id = lf.id
        LEFT JOIN data_sources ds ON fm.data_source_id = ds.id';

    public static function byId(int $mappingId): ?array
    {
        $row = Database::fetchOne(self::SELECT . ' WHERE fm.id = ?', [$mappingId]);
        if (!$row) {
            return null;
        }
        return self::hydrate($row);
    }

    /** @return array[] */
    public static function forDataSource(int $dataSourceId, bool $ordered = true): array
    {
        $sql = self::SELECT . ' WHERE fm.data_source_id = ?';
        if ($ordered) {
            $sql .= ' ORDER BY fm.sort_order, fm.id';
        }
        $rows = Database::fetchAll($sql, [$dataSourceId]);
        return self::hydrateMany($rows);
    }

    /** @return array[] 全部映射（跨数据源） */
    public static function all(): array
    {
        $rows = Database::fetchAll(self::SELECT . ' ORDER BY fm.id');
        return self::hydrateMany($rows);
    }

    /** @param int[] $dataSourceIds @return array[] */
    public static function forDataSources(array $dataSourceIds): array
    {
        if (!$dataSourceIds) {
            return [];
        }
        $ph = implode(',', array_fill(0, count($dataSourceIds), '?'));
        $rows = Database::fetchAll(
            self::SELECT . " WHERE fm.data_source_id IN ($ph) ORDER BY fm.data_source_id, fm.sort_order, fm.id",
            array_values($dataSourceIds)
        );
        return self::hydrateMany($rows);
    }

    /** @param array[] $rows */
    private static function hydrateMany(array $rows): array
    {
        if (!$rows) {
            return [];
        }
        $ids = array_map(fn($r) => (int) $r['id'], $rows);
        $ph = implode(',', array_fill(0, count($ids), '?'));
        $partRows = Database::fetchAll(
            "SELECT * FROM field_mapping_parts WHERE mapping_id IN ($ph) ORDER BY sort_order, id",
            $ids
        );
        $partsByMapping = [];
        foreach ($partRows as $p) {
            $partsByMapping[(int) $p['mapping_id']][] = self::decodePart($p);
        }
        $out = [];
        foreach ($rows as $r) {
            $m = self::decodeMapping($r);
            $m['parts'] = $partsByMapping[(int) $r['id']] ?? [];
            $out[] = $m;
        }
        return $out;
    }

    private static function hydrate(array $row): array
    {
        $m = self::decodeMapping($row);
        $partRows = Database::fetchAll(
            'SELECT * FROM field_mapping_parts WHERE mapping_id = ? ORDER BY sort_order, id',
            [(int) $row['id']]
        );
        $m['parts'] = array_map(fn($p) => self::decodePart($p), $partRows);
        return $m;
    }

    private static function decodeMapping(array $r): array
    {
        $r['id'] = (int) $r['id'];
        $r['data_source_id'] = (int) $r['data_source_id'];
        $r['logical_field_id'] = $r['logical_field_id'] !== null ? (int) $r['logical_field_id'] : null;
        $r['sort_order'] = (int) ($r['sort_order'] ?? 0);
        $r['is_highlight'] = (bool) ($r['is_highlight'] ?? false);
        $r['aliases'] = Database::jsonDecode($r['aliases'] ?? null, []) ?: [];
        return $r;
    }

    public static function decodePart(array $p): array
    {
        $p['id'] = (int) $p['id'];
        $p['mapping_id'] = (int) $p['mapping_id'];
        $p['sort_order'] = (int) ($p['sort_order'] ?? 0);
        $p['aliases'] = Database::jsonDecode($p['aliases'] ?? null, []) ?: [];
        $p['dedup_keys'] = Database::jsonDecode($p['dedup_keys'] ?? null, []) ?: [];
        $p['row_filters'] = Database::jsonDecode($p['row_filters'] ?? null, []) ?: [];
        $p['join_keys'] = Database::jsonDecode($p['join_keys'] ?? null, []) ?: [];
        $p['sources'] = Database::jsonDecode($p['sources'] ?? null, []) ?: [];
        $p['exclude_sample'] = (bool) ($p['exclude_sample'] ?? false);
        $p['exclude_review'] = (bool) ($p['exclude_review'] ?? false);
        $p['join_to_orders'] = (bool) ($p['join_to_orders'] ?? false);
        $p['only_sample'] = (bool) ($p['only_sample'] ?? false);
        return $p;
    }

    /** 与 FastAPI /api 的 _serialize_mapping 输出结构一致。 */
    public static function serialize(array $m): array
    {
        $code = MappingUtils::mappingLineCode($m);
        $parts = $m['parts'] ?? [];
        usort($parts, fn($a, $b) => $a['sort_order'] <=> $b['sort_order']);
        return [
            'id' => $m['id'],
            'data_source_id' => $m['data_source_id'],
            'logical_field_id' => $m['logical_field_id'],
            'logical_field_name' => $m['logical_field_name'] ?? null,
            'logical_field_code' => $m['logical_field_code'] ?? null,
            'data_source_name' => $m['data_source_name'] ?? null,
            'line_type' => ($m['line_type'] ?? null) ?: (MappingUtils::isFormulaLine($m) ? 'formula' : 'fetch'),
            'label' => MappingUtils::mappingLabel($m),
            'line_code' => $code,
            'report_group' => $m['report_group'] ?? null,
            'sort_order' => (int) ($m['sort_order'] ?? 0),
            'expression' => $m['expression'] ?? null,
            'format_type' => ($m['format_type'] ?? null) ?: 'usd',
            'is_highlight' => (bool) ($m['is_highlight'] ?? false),
            'description' => $m['description'] ?? null,
            'parts' => array_map(fn($p) => [
                'id' => $p['id'],
                'sort_order' => $p['sort_order'],
                'label' => $p['label'],
                'source_file_keyword' => $p['source_file_keyword'],
                'sheet_name' => $p['sheet_name'],
                'column_header' => $p['column_header'],
                'aliases' => $p['aliases'],
                'sources' => $p['sources'],
                'ref_field_code' => $p['ref_field_code'],
                'combine_op' => $p['combine_op'],
                'aggregation' => $p['aggregation'],
                'dedup_keys' => $p['dedup_keys'],
                'date_filter_column' => $p['date_filter_column'],
                'date_format' => $p['date_format'],
                'row_filters' => $p['row_filters'],
                'exclude_sample' => $p['exclude_sample'],
                'exclude_review' => $p['exclude_review'],
                'join_to_orders' => $p['join_to_orders'],
                'join_keys' => $p['join_keys'],
                'only_sample' => $p['only_sample'],
            ], $parts),
        ];
    }
}
