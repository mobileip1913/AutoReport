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

    public static function isFetchLine(array $m): bool
    {
        return !self::isFormulaLine($m) && !self::isManualLine($m);
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
