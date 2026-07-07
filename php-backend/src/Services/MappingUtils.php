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
}
