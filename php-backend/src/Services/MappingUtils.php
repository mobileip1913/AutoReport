<?php

declare(strict_types=1);

namespace App\Services;

/**
 * 报表行（field_mapping）辅助：code / 展示名 / 分组。
 * mapping 为关联数组（含 logical_field_code / logical_field_name / parts）。
 */
final class MappingUtils
{
    public static function mappingLineCode(array $m): string
    {
        if (!empty($m['line_code'])) {
            return (string) $m['line_code'];
        }
        if (!empty($m['logical_field_code'])) {
            return (string) $m['logical_field_code'];
        }
        return 'line_' . $m['id'];
    }

    public static function mappingLabel(array $m): string
    {
        if (!empty($m['label'])) {
            return (string) $m['label'];
        }
        if (!empty($m['logical_field_name'])) {
            return (string) $m['logical_field_name'];
        }
        return '指标' . $m['id'];
    }

    public static function isManualLine(array $m): bool
    {
        return strtolower((string) ($m['line_type'] ?? '')) === 'manual';
    }

    public static function isPerOrderLine(array $m): bool
    {
        return strtolower((string) ($m['line_type'] ?? '')) === 'per_order';
    }

    public static function isRatioLine(array $m): bool
    {
        return strtolower((string) ($m['line_type'] ?? '')) === 'ratio';
    }

    public static function isRefComputeLine(array $m): bool
    {
        $parts = $m['parts'] ?? [];
        if (!$parts) {
            return false;
        }
        foreach ($parts as $p) {
            if (trim((string) ($p['ref_field_code'] ?? '')) === '') {
                return false;
            }
        }
        return true;
    }

    public static function isFormulaLine(array $m): bool
    {
        if (self::isManualLine($m)) {
            return false;
        }
        $lineType = strtolower((string) ($m['line_type'] ?? ''));
        if ($lineType === 'formula') {
            return true;
        }
        if ($lineType === 'fetch') {
            return false;
        }
        $hasExpr = trim((string) ($m['expression'] ?? '')) !== '';
        $hasParts = !empty($m['parts']);
        $hasLegacy = !empty($m['sheet_name']) && !empty($m['column_header']);
        return $hasExpr && !$hasParts && !$hasLegacy;
    }

    /** 日报字段展示分类：placeholder | review | sample | compute | fetch | per_order | ratio | formula */
    public static function fieldDisplayType(array $m, ?string $lineCode = null): string
    {
        $code = $lineCode ?? self::mappingLineCode($m);
        $label = self::mappingLabel($m);
        if (self::isPerOrderLine($m)) {
            return 'per_order';
        }
        if (self::isRatioLine($m)) {
            return 'ratio';
        }
        if (self::isManualLine($m)) {
            return 'placeholder';
        }
        if (!empty($m['parts'])) {
            return self::isRefComputeLine($m) ? 'compute' : 'fetch';
        }
        if (in_array($label, MeichongRules::MANUAL_FILL_LABELS, true)) {
            return 'placeholder';
        }
        if (in_array($code, MeichongRules::REVIEW_IMPORT_CODES, true)) {
            return 'review';
        }
        if (in_array($code, MeichongRules::SAMPLE_IMPORT_CODES, true)) {
            return 'sample';
        }
        if (in_array($code, MeichongRules::PENDING_FILE_CODES, true)) {
            return 'placeholder';
        }
        if (self::isFormulaLine($m)) {
            return 'formula';
        }
        return 'fetch';
    }

    public static function isFetchLine(array $m): bool
    {
        return self::fieldDisplayType($m) === 'fetch';
    }

    /**
     * 字段 code → 展示名（逻辑字段名 + 报表行 label）。
     * @param array[] $mappings
     * @param array[] $logicalFields
     * @return array<string, string>
     */
    public static function buildFieldLabelsMap(array $mappings, array $logicalFields): array
    {
        $out = [];
        foreach ($logicalFields as $lf) {
            $code = (string) ($lf['code'] ?? '');
            $name = (string) ($lf['name'] ?? '');
            if ($code !== '' && $name !== '') {
                $out[$code] = $name;
            }
        }
        foreach ($mappings as $m) {
            $code = self::mappingLineCode($m);
            $label = self::mappingLabel($m);
            if ($code !== '' && $label !== '') {
                $out[$code] = $label;
            }
        }
        return $out;
    }

    /** @return string[] */
    public static function mappingSourceFileKeywords(array $m): array
    {
        $keywords = [];
        $parts = $m['parts'] ?? [];
        usort($parts, fn($a, $b) => ((int) ($a['sort_order'] ?? 0)) <=> ((int) ($b['sort_order'] ?? 0)));
        foreach ($parts as $p) {
            if (trim((string) ($p['ref_field_code'] ?? '')) !== '') {
                continue;
            }
            $kw = trim((string) ($p['source_file_keyword'] ?? ''));
            if ($kw !== '') {
                $keywords[$kw] = true;
            }
            foreach ($p['sources'] ?? [] as $s) {
                if (!is_array($s)) {
                    continue;
                }
                $sk = trim((string) ($s['source_file_keyword'] ?? ''));
                if ($sk !== '') {
                    $keywords[$sk] = true;
                }
            }
        }
        $keys = array_keys($keywords);
        sort($keys);
        return $keys;
    }

    private const AGG_LABELS = [
        'sum' => '求和',
        'count' => '计数',
        'count_distinct' => '去重计数',
        'sum_dedup' => '去重求和',
        'max_dedup' => '去重取最大',
        'avg' => '平均值',
    ];

    private static function resolveFileLabel(?string $keyword, ?array $fileLabels): string
    {
        $kw = trim((string) $keyword);
        if ($kw === '') {
            return '';
        }
        $labels = $fileLabels ?? [];
        return $labels[$kw] ?? $labels[strtolower($kw)] ?? $kw;
    }

    private static function sourceLoc(array $source, ?array $fileLabels): string
    {
        $fl = self::resolveFileLabel($source['source_file_keyword'] ?? null, $fileLabels);
        $col = trim((string) ($source['column_header'] ?? ''));
        if ($fl !== '' && $col !== '') {
            return "{$fl}.{$col}";
        }
        return $col !== '' ? $col : ($fl !== '' ? $fl : '未指定');
    }

    /** 列表页规则摘要：订单.Order Amount · 去重求和 */
    public static function partRuleBrief(array $part, ?array $fileLabels = null, ?array $fieldLabels = null): string
    {
        $ref = trim((string) ($part['ref_field_code'] ?? ''));
        if ($ref !== '') {
            $labels = $fieldLabels ?? [];
            return $labels[$ref] ?? $ref;
        }

        $sources = $part['sources'] ?? [];
        if ($sources) {
            $pieces = [];
            foreach ($sources as $i => $src) {
                $loc = self::sourceLoc(is_array($src) ? $src : [], $fileLabels);
                $pieces[] = $i ? "+ {$loc}" : $loc;
            }
            $srcText = implode(' ', $pieces);
        } else {
            $srcText = self::sourceLoc([
                'source_file_keyword' => $part['source_file_keyword'] ?? null,
                'column_header' => $part['column_header'] ?? null,
            ], $fileLabels);
        }

        $agg = trim((string) ($part['aggregation'] ?? 'sum'));
        $aggLabel = self::AGG_LABELS[$agg] ?? $agg;
        return "{$srcText} · {$aggLabel}";
    }

    /** 纳入日报结构的行（非基础取数字段）。 */
    public static function isReportLine(array $m): bool
    {
        return (int) ($m['sort_order'] ?? 0) > 0 || !empty($m['report_group']);
    }

    /** @param array[] $mappings */
    public static function reportDisplayMappings(array $mappings): array
    {
        $lines = array_values(array_filter($mappings, fn($m) => self::isReportLine($m)));
        usort($lines, fn($a, $b) => [(int) ($a['sort_order'] ?? 0), (int) $a['id']] <=> [(int) ($b['sort_order'] ?? 0), (int) $b['id']]);
        return $lines;
    }

    public static function defaultExpression(array $m): string
    {
        $expr = trim((string) ($m['expression'] ?? ''));
        if ($expr !== '') {
            return $expr;
        }
        $code = self::mappingLineCode($m);
        return '{field:' . $code . '}';
    }

    /** @param array<string, bool>|array<int, string> $used 引用传递的已用 code 集合（code => true） */
    public static function slugLineCode(string $text, array &$used): string
    {
        $lower = mb_strtolower(trim($text));
        $ascii = preg_replace('/[^a-z0-9_]+/', '_', $lower) ?? '';
        $ascii = trim($ascii, '_');
        if ($ascii === '' || in_array($ascii, ['line', 'r_line'], true)) {
            $digest = substr(md5($text !== '' ? $text : 'line'), 0, 8);
            $base = "rpt_$digest";
        } else {
            $base = substr($ascii, 0, 40);
            if (ctype_digit($base[0])) {
                $base = "r_$base";
            }
        }
        $name = $base;
        $i = 2;
        while (isset($used[$name])) {
            $name = "{$base}_{$i}";
            $i++;
        }
        $used[$name] = true;
        return $name;
    }

    private const ROW_FILTER_HINTS = [
        'nonempty' => '非空',
        'empty' => '为空',
        'eq' => '=',
        'ne' => '≠',
        'in' => '∈',
        'not_in' => '∉',
        'contains' => '含',
        'not_contains' => '不含',
        'starts_with' => '开头',
        'ends_with' => '结尾',
        'gt' => '>',
        'gte' => '≥',
        'lt' => '<',
        'lte' => '≤',
        'between' => '介于',
    ];

    /** @return string[] */
    public static function partRuleHints(array $part): array
    {
        $hints = [];
        $dateCol = trim((string) ($part['date_filter_column'] ?? ''));
        if ($dateCol !== '') {
            $hints[] = "{$dateCol}=日报";
        }
        foreach ($part['row_filters'] ?? [] as $cond) {
            $col = trim((string) ($cond['column'] ?? ''));
            $op = $cond['op'] ?? 'eq';
            $values = $cond['values'] ?? [];
            if (is_string($values) || is_int($values) || is_float($values)) {
                $values = [$values];
            }
            $label = self::ROW_FILTER_HINTS[$op] ?? $op;
            if (in_array($op, ['nonempty', 'empty'], true)) {
                if ($col !== '') {
                    $hints[] = "{$col}{$label}";
                }
            } elseif (in_array($op, ['eq', 'ne', 'contains', 'not_contains', 'starts_with', 'ends_with', 'gt', 'gte', 'lt', 'lte'], true)) {
                $val = isset($values[0]) ? trim((string) $values[0]) : '';
                if ($col !== '' && $val !== '') {
                    $hints[] = "{$col}{$label}{$val}";
                }
            } elseif (in_array($op, ['in', 'not_in', 'between'], true) && $col !== '') {
                $vals = implode('、', array_map('strval', array_slice($values, 0, 3)));
                if ($vals !== '') {
                    $hints[] = "{$col}{$label}{$vals}";
                }
            }
        }
        $adv = [];
        if (!empty($part['exclude_sample'])) {
            $adv[] = '排除样品';
        }
        if (!empty($part['exclude_review'])) {
            $adv[] = '排除刷单';
        }
        if (!empty($part['join_to_orders'])) {
            $adv[] = '关联主表';
        }
        if (!empty($part['only_sample'])) {
            $adv[] = '仅样品';
        }
        if ($adv) {
            $hints[] = implode('、', $adv);
        }
        return $hints;
    }
}
