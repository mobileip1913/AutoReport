<?php

declare(strict_types=1);

namespace App\Services;

use App\Database;

/**
 * 将模板行定义同步到 field_mappings（报表配置）。
 * 与 Python 版 services/report_line_sync.py 对等。
 */
final class ReportLineSync
{
    /** @param array<int, array{0:string,1:array}> $groups @return array<string,string> label => group */
    private static function labelToGroup(array $groups): array
    {
        $out = [];
        foreach ($groups as [$title, $labels]) {
            foreach ($labels as $label) {
                $out[$label] = $title;
            }
        }
        return $out;
    }

    /** @param array<int, array{0:string,1:string}> $refParts [code, combine_op][] */
    private static function applyRefParts(int $mappingId, array $refParts): void
    {
        Database::execute('DELETE FROM field_mapping_parts WHERE mapping_id = ?', [$mappingId]);
        foreach ($refParts as $idx => [$refCode, $combineOp]) {
            Database::insert('field_mapping_parts', [
                'mapping_id' => $mappingId,
                'sort_order' => $idx,
                'label' => null,
                'ref_field_code' => $refCode,
                'sheet_name' => '',
                'column_header' => '',
                'combine_op' => $combineOp,
                'aggregation' => 'sum',
            ]);
        }
    }

    /** 把已有公式行改为「复用字段」取数行。 */
    public static function convertFormulaLinesToFetch(int $dataSourceId): int
    {
        $n = 0;
        foreach (MappingRepo::forDataSource($dataSourceId, false) as $mapping) {
            if (strtolower((string) ($mapping['line_type'] ?? '')) === 'manual') {
                continue;
            }
            if (!MappingUtils::isFormulaLine($mapping)) {
                continue;
            }
            $refParts = Formula::expressionToRefParts((string) ($mapping['expression'] ?? ''));
            if (!$refParts) {
                continue;
            }
            Database::updateById('field_mappings', (int) $mapping['id'], [
                'line_type' => 'fetch',
                'expression' => null,
            ]);
            self::applyRefParts((int) $mapping['id'], $refParts);
            $n++;
        }
        return $n;
    }

    /**
     * 把 template_lines 合并写入 field_mappings，返回新增/更新行数。
     * @param array<int, array{0:int,1:string,2:string,3:string,4:bool}> $templateLines
     */
    public static function syncReportLines(int $dataSourceId, array $templateLines, array $templateGroups, bool $onlyMissing = false): int
    {
        $labelGroup = self::labelToGroup($templateGroups);
        $fieldMap = [];
        foreach (Database::fetchAll('SELECT * FROM logical_fields') as $f) {
            $fieldMap[(string) $f['code']] = $f;
        }

        $existing = MappingRepo::forDataSource($dataSourceId, false);
        $byLineCode = [];
        $byLabel = [];
        foreach ($existing as $m) {
            $code = MappingUtils::mappingLineCode($m);
            $byLineCode[$code] = $m;
            if (!empty($m['label'])) {
                $byLabel[(string) $m['label']] = $m;
            }
            if (!empty($m['logical_field_code'])) {
                $byLineCode[(string) $m['logical_field_code']] = $m;
            }
        }

        $usedCodes = [];
        foreach ($existing as $m) {
            $c = MappingUtils::mappingLineCode($m);
            if ($c !== '') {
                $usedCodes[$c] = true;
            }
        }
        $touched = 0;

        $reload = fn(int $id) => MappingRepo::byId($id);

        foreach ($templateLines as [$sortOrder, $label, $expr, $fmt, $highlight]) {
            if (in_array($label, MeichongRules::MANUAL_FILL_LABELS, true) || isset(MeichongRules::LEGACY_MANUAL_LABELS[$label])) {
                $canonical = str_replace('(估算)', '', $label);
                $mapping = $byLabel[$canonical] ?? $byLabel[$label] ?? null;
                if (!$mapping && isset(MeichongRules::LEGACY_MANUAL_LABELS[$canonical])) {
                    $mapping = $byLabel[MeichongRules::LEGACY_MANUAL_LABELS[$canonical]] ?? null;
                }
                if (!$mapping) {
                    $lineCode = MappingUtils::slugLineCode($canonical, $usedCodes);
                    $mid = Database::insert('field_mappings', [
                        'data_source_id' => $dataSourceId,
                        'line_code' => $lineCode,
                        'line_type' => 'manual',
                        'label' => $canonical,
                        'sort_order' => 0,
                        'is_highlight' => 0,
                        'aggregation' => 'sum',
                        'aliases' => Database::jsonEncode([]),
                    ]);
                    $mapping = $reload($mid);
                    $byLabel[$canonical] = $mapping;
                    $touched++;
                }
                Database::updateById('field_mappings', (int) $mapping['id'], [
                    'line_type' => 'manual',
                    'label' => $canonical,
                    'sort_order' => $sortOrder,
                    'expression' => null,
                    'format_type' => $fmt,
                    'is_highlight' => $highlight ? 1 : 0,
                    'report_group' => $labelGroup[$canonical] ?? $labelGroup[$label] ?? null,
                    'description' => ($mapping['description'] ?? null) ?: '导出 Excel 后由财务手工填写',
                ]);
                continue;
            }

            $fieldCodes = Formula::extractFieldCodes($expr);
            $simpleFetch = count($fieldCodes) === 1 && trim($expr) === '{field:' . $fieldCodes[0] . '}';

            if ($simpleFetch) {
                $mcCode = $fieldCodes[0];
                $mapping = $byLineCode[$mcCode] ?? null;
                if ($mapping && $onlyMissing && !empty($mapping['report_group'])) {
                    continue;
                }
                if (!$mapping) {
                    $lf = $fieldMap[$mcCode] ?? null;
                    $mid = Database::insert('field_mappings', [
                        'data_source_id' => $dataSourceId,
                        'logical_field_id' => $lf ? (int) $lf['id'] : null,
                        'line_code' => $mcCode,
                        'line_type' => 'fetch',
                        'label' => $label,
                        'sort_order' => 0,
                        'is_highlight' => 0,
                        'aggregation' => 'sum',
                        'aliases' => Database::jsonEncode([]),
                    ]);
                    $mapping = $reload($mid);
                    $byLineCode[$mcCode] = $mapping;
                    $byLabel[$label] = $mapping;
                    $touched++;
                }
                Database::updateById('field_mappings', (int) $mapping['id'], [
                    'label' => $label,
                    'line_code' => $mcCode,
                    'line_type' => 'fetch',
                    'sort_order' => $sortOrder,
                    'expression' => null,
                    'format_type' => $fmt,
                    'is_highlight' => $highlight ? 1 : 0,
                    'report_group' => $labelGroup[$label] ?? null,
                ]);
                if (!$onlyMissing || ($labelGroup[$label] ?? null)) {
                    $touched++;
                }
                continue;
            }

            $refParts = Formula::expressionToRefParts($expr);
            if (!$refParts) {
                continue;
            }

            $mapping = $byLabel[$label] ?? null;
            if ($mapping && $onlyMissing && !empty($mapping['report_group']) && !empty($mapping['parts'])) {
                continue;
            }
            if (!$mapping) {
                $lineCode = MappingUtils::slugLineCode($label, $usedCodes);
                $mid = Database::insert('field_mappings', [
                    'data_source_id' => $dataSourceId,
                    'line_code' => $lineCode,
                    'line_type' => 'fetch',
                    'label' => $label,
                    'sort_order' => 0,
                    'is_highlight' => 0,
                    'aggregation' => 'sum',
                    'aliases' => Database::jsonEncode([]),
                ]);
                $mapping = $reload($mid);
                $byLabel[$label] = $mapping;
                $byLineCode[$lineCode] = $mapping;
                $touched++;
            }

            Database::updateById('field_mappings', (int) $mapping['id'], [
                'line_type' => 'fetch',
                'label' => $label,
                'sort_order' => $sortOrder,
                'expression' => null,
                'format_type' => $fmt,
                'is_highlight' => $highlight ? 1 : 0,
                'report_group' => $labelGroup[$label] ?? null,
            ]);
            self::applyRefParts((int) $mapping['id'], $refParts);
            $touched++;
        }

        // 清理旧「(估算)」命名的非手工行
        foreach (MappingRepo::forDataSource($dataSourceId, false) as $m) {
            if (in_array($m['label'] ?? '', array_values(MeichongRules::LEGACY_MANUAL_LABELS), true)
                && (string) ($m['line_type'] ?? '') !== 'manual'
            ) {
                Database::execute('DELETE FROM field_mapping_parts WHERE mapping_id = ?', [(int) $m['id']]);
                Database::execute('DELETE FROM field_mappings WHERE id = ?', [(int) $m['id']]);
                $touched++;
            }
        }

        self::convertFormulaLinesToFetch($dataSourceId);
        return $touched;
    }

    /** 为旧映射补 line_code / label / line_type。 */
    public static function backfillMappingLineCodes(): int
    {
        $n = 0;
        $rows = Database::fetchAll(
            'SELECT fm.*, lf.code AS logical_field_code, lf.name AS logical_field_name
             FROM field_mappings fm LEFT JOIN logical_fields lf ON fm.logical_field_id = lf.id'
        );
        foreach ($rows as $m) {
            $patch = [];
            if (empty($m['line_code']) && !empty($m['logical_field_code'])) {
                $patch['line_code'] = $m['logical_field_code'];
            }
            if (empty($m['label']) && !empty($m['logical_field_name'])) {
                $patch['label'] = $m['logical_field_name'];
            }
            if (empty($m['line_type'])) {
                $patch['line_type'] = 'fetch';
            }
            if ($patch) {
                Database::updateById('field_mappings', (int) $m['id'], $patch);
                $n++;
            }
        }
        return $n;
    }

    /** 旧版单列映射 → 多规则 parts（migrate_legacy_mappings 对等）。 */
    public static function migrateLegacyMappings(): void
    {
        foreach (MappingRepo::all() as $mapping) {
            if (!empty($mapping['parts'])) {
                continue;
            }
            if (empty($mapping['sheet_name']) || empty($mapping['column_header'])) {
                continue;
            }
            Database::insert('field_mapping_parts', [
                'mapping_id' => (int) $mapping['id'],
                'sort_order' => 0,
                'label' => '默认规则',
                'sheet_name' => $mapping['sheet_name'],
                'column_header' => $mapping['column_header'],
                'aliases' => Database::jsonEncode($mapping['aliases'] ?? []),
                'combine_op' => 'add',
                'aggregation' => ($mapping['aggregation'] ?? '') ?: 'sum',
                'dedup_keys' => Database::jsonEncode([]),
            ]);
        }
    }

    /** 额外逻辑字段种子（migrate.ensure_logical_fields 对等）。 */
    public static function ensureLogicalFields(): void
    {
        $extra = [
            ['sku_discount', 'SKU折扣', '每 SKU 行折扣，用 sum'],
            ['order_discount', '订单折扣', '订单级折扣，用 sum_dedup + Order ID'],
            ['settlement_credit', '结算调整(加)', 'B 文件贷项'],
            ['settlement_charge', '结算扣费(减)', 'B 文件借项'],
        ];
        foreach ($extra as [$code, $name, $desc]) {
            if (!Database::fetchOne('SELECT id FROM logical_fields WHERE code = ?', [$code])) {
                Database::insert('logical_fields', [
                    'code' => $code,
                    'name' => $name,
                    'data_type' => 'number',
                    'description' => $desc,
                ]);
            }
        }
    }
}
