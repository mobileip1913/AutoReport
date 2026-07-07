<?php

declare(strict_types=1);

namespace App\Services;

/**
 * 逻辑字段取数：多 Sheet/多文件、加减组合、去重聚合，并支持日报规则增强：
 * 行级日期过滤、行条件过滤、样品/刷单排除、与订单表关联。
 * 与 Python 版 services/field_aggregator.py 对等。
 *
 * 行结构 row: ['data_import_id' => int, 'sheet_name' => string, 'row_data' => array]
 * part 为 field_mapping_parts 关联数组（JSON 字段已解码）。
 */
final class FieldAggregator
{
    public const ORDER_ID_CANDIDATES = ['Order ID', 'Related order ID', 'Order/adjustment ID', '订单号'];
    public const SKU_ID_CANDIDATES = ['SKU ID', 'Sku Id', 'Sku ID', 'SKU Id'];

    public const AGGREGATION_LABELS = [
        'sum' => '求和 sum — 所有行相加（SKU 级折扣）',
        'count' => '计数 count — 行数',
        'count_distinct' => '去重计数 — 按去重键统计唯一值（订单数）',
        'sum_dedup' => '去重求和 — 每组只取一次再相加（订单级金额/折扣）',
        'max_dedup' => '去重取最大 — 每组取最大再相加',
        'avg' => '平均值 avg',
    ];

    public static function toNumber(mixed $value): float
    {
        if ($value === null || $value === '') {
            return 0.0;
        }
        if (is_int($value) || is_float($value)) {
            return (float) $value;
        }
        $text = trim((string) $value);
        if ($text === '' || $text === '/' || $text === '-') {
            return 0.0;
        }
        $neg = str_starts_with($text, '(') && str_ends_with($text, ')');
        $text = trim($text, '()');
        $text = trim(str_replace([',', '$', '%', "\u{00a5}"], '', $text));
        if (!is_numeric($text)) {
            return 0.0;
        }
        $num = (float) $text;
        return $neg ? -$num : $num;
    }

    /** key 去空格标准化 */
    public static function normalized(array $rowData): array
    {
        $out = [];
        foreach ($rowData as $k => $v) {
            $out[trim((string) $k)] = $v;
        }
        return $out;
    }

    /** @param string[] $aliases */
    public static function cell(array $rowData, string $columnHeader, array $aliases): ?float
    {
        $candidates = array_merge([$columnHeader], $aliases);
        $normalized = self::normalized($rowData);
        foreach ($candidates as $name) {
            $key = trim((string) $name);
            if (array_key_exists($key, $normalized)) {
                return self::toNumber($normalized[$key]);
            }
        }
        return null;
    }

    /** @param string[] $candidates */
    public static function extract(array $rowData, array $candidates): string
    {
        $normalized = self::normalized($rowData);
        foreach ($candidates as $name) {
            if (array_key_exists($name, $normalized)) {
                $v = $normalized[$name];
                if ($v !== null && trim((string) $v) !== '') {
                    return trim((string) $v);
                }
            }
        }
        return '';
    }

    /**
     * 解析多格式日期为 'Y-m-d'：us=MM/DD/YYYY, eu=DD/MM/YYYY, iso=YYYY/MM/DD，null=自动。
     */
    public static function parseDate(mixed $value, ?string $fmt = null): ?string
    {
        if ($value === null) {
            return null;
        }
        if ($value instanceof \DateTimeInterface) {
            return $value->format('Y-m-d');
        }
        $text = trim((string) $value);
        if ($text === '' || $text === '/' || $text === '-') {
            return null;
        }
        $token = explode('T', explode(' ', $text)[0])[0];
        $sep = str_contains($token, '/') ? '/' : (str_contains($token, '-') ? '-' : null);
        if ($sep === null) {
            return null;
        }
        $parts = explode($sep, $token);
        if (count($parts) !== 3) {
            return null;
        }
        foreach ($parts as $p) {
            if (!preg_match('/^\d+$/', $p)) {
                return null;
            }
        }
        [$a, $b, $c] = array_map('intval', $parts);

        if ($fmt === 'iso' || strlen($parts[0]) === 4 || $a > 31) {
            [$y, $m, $d] = [$a, $b, $c];
        } elseif ($fmt === 'eu') {
            [$d, $m, $y] = [$a, $b, $c];
        } elseif ($fmt === 'us') {
            [$m, $d, $y] = [$a, $b, $c];
        } else { // 自动判别
            if ($a > 12) {
                [$d, $m, $y] = [$a, $b, $c];
            } else {
                // b > 12 或默认均按美国格式（TK-US 店铺）
                [$m, $d, $y] = [$a, $b, $c];
            }
        }
        if (!checkdate($m, $d, $y)) {
            return null;
        }
        return sprintf('%04d-%02d-%02d', $y, $m, $d);
    }

    /** @param array[] $rows */
    public static function buildDailyContext(array $rows, array $dsConfig, string $reportDate): DailyContext
    {
        $cfg = $dsConfig ?: [];
        $orderSheet = $cfg['order_sheet'] ?? null;
        $orderIdCol = $cfg['order_id_col'] ?? 'Order ID';
        $skuIdCol = $cfg['sku_id_col'] ?? 'SKU ID';
        $orderDateCol = $cfg['order_date_col'] ?? null;
        $orderDateFmt = $cfg['order_date_format'] ?? null;
        $sampleRule = $cfg['sample_rule'] ?? [];
        $sumCols = $sampleRule['sum_cols'] ?? [];

        $reportD = self::parseDate($reportDate, 'iso');

        $perOrder = [];
        $orderKeys = [];
        $orderIdSet = [];

        foreach ($rows as $r) {
            if ($orderSheet && $r['sheet_name'] !== $orderSheet) {
                continue;
            }
            $nd = self::normalized($r['row_data']);
            $oid = trim((string) ($nd[$orderIdCol] ?? ''));
            if ($oid === '') {
                continue;
            }
            $orderIdSet[$oid] = true;
            $sku = trim((string) ($nd[$skuIdCol] ?? ''));
            $orderKeys[json_encode([$oid, $sku])] = true;
            if ($sumCols) {
                $sum = 0.0;
                foreach ($sumCols as $c) {
                    $sum += self::toNumber($nd[$c] ?? null);
                }
                $perOrder[$oid] = ($perOrder[$oid] ?? 0.0) + $sum;
            }
        }

        $sampleIds = [];
        foreach ($perOrder as $oid => $total) {
            if (abs($total) < 0.01) {
                $sampleIds[(string) $oid] = true;
            }
        }
        $reviewIds = [];
        foreach (($cfg['review_order_ids'] ?? []) as $x) {
            $reviewIds[trim((string) $x)] = true;
        }

        $validKeys = [];
        $validIds = [];
        $validRowNorms = [];
        foreach ($rows as $r) {
            if ($orderSheet && $r['sheet_name'] !== $orderSheet) {
                continue;
            }
            $nd = self::normalized($r['row_data']);
            $oid = trim((string) ($nd[$orderIdCol] ?? ''));
            if ($oid === '') {
                continue;
            }
            $sku = trim((string) ($nd[$skuIdCol] ?? ''));
            $d = $orderDateCol ? self::parseDate($nd[$orderDateCol] ?? null, $orderDateFmt) : null;
            if (isset($sampleIds[$oid]) || isset($reviewIds[$oid])) {
                continue;
            }
            if ($reportD !== null && $d !== $reportD) {
                continue;
            }
            $validKeys[json_encode([$oid, $sku])] = true;
            $validIds[$oid] = true;
            $validRowNorms[] = $nd;
        }

        $joinSet = function (array $cols) use ($validRowNorms): array {
            $out = [];
            foreach ($validRowNorms as $nd) {
                $t = array_map(fn($c) => trim((string) ($nd[$c] ?? '')), $cols);
                $allFilled = true;
                foreach ($t as $v) {
                    if ($v === '') {
                        $allFilled = false;
                        break;
                    }
                }
                if ($allFilled) {
                    $out[json_encode($t)] = true;
                }
            }
            return $out;
        };

        $validJoinMap = [
            json_encode([$orderIdCol]) => $joinSet([$orderIdCol]),
            json_encode([$orderIdCol, $skuIdCol]) => $joinSet([$orderIdCol, $skuIdCol]),
            json_encode(DsSettings::DEFAULT_JOIN_KEYS) => $joinSet(DsSettings::DEFAULT_JOIN_KEYS),
        ];

        return new DailyContext(
            reportDate: $reportD,
            sampleOrderIds: $sampleIds,
            reviewOrderIds: $reviewIds,
            orderKeys: $orderKeys,
            orderIdSet: $orderIdSet,
            validOrderKeys: $validKeys,
            validOrderIds: $validIds,
            validJoinMap: $validJoinMap,
            validMasterRows: $validRowNorms,
        );
    }

    private static function cellStr(mixed $raw): string
    {
        return $raw === null ? '' : trim((string) $raw);
    }

    /** @param array[] $filters */
    public static function passesRowFilters(array $rowData, array $filters): bool
    {
        if (!$filters) {
            return true;
        }
        $normalized = self::normalized($rowData);
        foreach ($filters as $cond) {
            $col = trim((string) ($cond['column'] ?? ''));
            $op = $cond['op'] ?? 'eq';
            $values = $cond['values'] ?? [];
            if (is_string($values) || is_int($values) || is_float($values)) {
                $values = [$values];
            }
            $raw = $normalized[$col] ?? null;
            $cellVal = self::cellStr($raw);
            $vals = array_map(fn($v) => trim((string) $v), $values);
            $lowerCell = mb_strtolower($cellVal);
            $lowerVals = array_map(fn($v) => mb_strtolower($v), $vals);

            switch ($op) {
                case 'nonempty':
                    if ($cellVal === '') {
                        return false;
                    }
                    break;
                case 'empty':
                    if ($cellVal !== '') {
                        return false;
                    }
                    break;
                case 'eq':
                    if ($cellVal !== ($vals[0] ?? '')) {
                        return false;
                    }
                    break;
                case 'ne':
                    if ($cellVal === ($vals[0] ?? '')) {
                        return false;
                    }
                    break;
                case 'in':
                    if (!in_array($cellVal, $vals, true)) {
                        return false;
                    }
                    break;
                case 'not_in':
                    if (in_array($cellVal, $vals, true)) {
                        return false;
                    }
                    break;
                case 'contains':
                    $needle = $lowerVals[0] ?? '';
                    if (!str_contains($lowerCell, $needle)) {
                        return false;
                    }
                    break;
                case 'not_contains':
                    $needle = $lowerVals[0] ?? '';
                    if (str_contains($lowerCell, $needle)) {
                        return false;
                    }
                    break;
                case 'starts_with':
                    $prefix = $lowerVals[0] ?? '';
                    if (!str_starts_with($lowerCell, $prefix)) {
                        return false;
                    }
                    break;
                case 'ends_with':
                    $suffix = $lowerVals[0] ?? '';
                    if (!str_ends_with($lowerCell, $suffix)) {
                        return false;
                    }
                    break;
                case 'between':
                    $num = self::toNumber($raw);
                    $lo = isset($vals[0]) ? self::toNumber($vals[0]) : 0.0;
                    $hi = isset($vals[1]) ? self::toNumber($vals[1]) : $lo;
                    if (!($lo <= $num && $num <= $hi)) {
                        return false;
                    }
                    break;
                case 'gt':
                case 'gte':
                case 'lt':
                case 'lte':
                    $num = self::toNumber($raw);
                    $target = $vals ? self::toNumber($vals[0]) : 0.0;
                    if ($op === 'gt' && !($num > $target)) {
                        return false;
                    }
                    if ($op === 'gte' && !($num >= $target)) {
                        return false;
                    }
                    if ($op === 'lt' && !($num < $target)) {
                        return false;
                    }
                    if ($op === 'lte' && !($num <= $target)) {
                        return false;
                    }
                    break;
            }
        }
        return true;
    }

    /** @param string[] $joinKeys */
    private static function matchJoinKeys(array $rowData, array $joinKeys, DailyContext $context): bool
    {
        $keys = array_values(array_filter(array_map(fn($k) => trim((string) $k), $joinKeys), fn($k) => $k !== ''));
        if (!$keys) {
            $keys = DsSettings::DEFAULT_JOIN_KEYS;
        }
        $keyJson = json_encode($keys);
        $nd = self::normalized($rowData);
        $parts = array_map(fn($k) => trim((string) ($nd[$k] ?? '')), $keys);
        $anyFilled = false;
        $allFilled = true;
        foreach ($parts as $v) {
            if ($v !== '') {
                $anyFilled = true;
            } else {
                $allFilled = false;
            }
        }
        if (!$anyFilled) {
            return false;
        }
        $validSet = $context->validJoinMap[$keyJson] ?? null;
        if ($validSet === null && $context->validMasterRows) {
            $validSet = [];
            foreach ($context->validMasterRows as $mnd) {
                $t = array_map(fn($k) => trim((string) ($mnd[$k] ?? '')), $keys);
                $tAll = true;
                foreach ($t as $v) {
                    if ($v === '') {
                        $tAll = false;
                        break;
                    }
                }
                if ($tAll) {
                    $validSet[json_encode($t)] = true;
                }
            }
            $context->validJoinMap[$keyJson] = $validSet;
        }
        if ($validSet === null) {
            if (count($keys) === 2) {
                return isset($context->validOrderKeys[json_encode($parts)]);
            }
            if (count($keys) === 1) {
                return isset($context->validOrderIds[$parts[0]]);
            }
            return false;
        }
        if ($allFilled) {
            return isset($validSet[json_encode($parts)]);
        }
        if (count($keys) === 1) {
            return isset($context->validOrderIds[$parts[0]]);
        }
        return false;
    }

    /**
     * @param array[] $rows
     * @param array<int, string> $importFileNames
     * @return array[]
     */
    private static function filterRows(array $rows, array $part, array $importFileNames, ?DailyContext $context): array
    {
        $result = [];
        $keyword = mb_strtolower(trim((string) ($part['source_file_keyword'] ?? '')));
        $dateCol = trim((string) ($part['date_filter_column'] ?? ''));
        $dateFmt = $part['date_format'] ?? null;
        $rowFilters = $part['row_filters'] ?? [];
        $excludeSample = (bool) ($part['exclude_sample'] ?? false);
        $excludeReview = (bool) ($part['exclude_review'] ?? false);
        $joinToOrders = (bool) ($part['join_to_orders'] ?? false);
        $onlySample = (bool) ($part['only_sample'] ?? false);

        foreach ($rows as $row) {
            if ($row['sheet_name'] !== ($part['sheet_name'] ?? '')) {
                continue;
            }
            if ($keyword !== '') {
                $fileName = mb_strtolower((string) ($importFileNames[$row['data_import_id']] ?? ''));
                if (!str_contains($fileName, $keyword)) {
                    continue;
                }
            }

            $nd = self::normalized($row['row_data']);

            if ($dateCol !== '' && $context !== null && $context->reportDate !== null) {
                $d = self::parseDate($nd[$dateCol] ?? null, $dateFmt);
                if ($d !== $context->reportDate) {
                    continue;
                }
            }

            if ($context !== null && ($excludeSample || $excludeReview || $joinToOrders || $onlySample)) {
                $oid = self::extract($row['row_data'], self::ORDER_ID_CANDIDATES);
                if ($onlySample && !isset($context->sampleOrderIds[$oid])) {
                    continue;
                }
                if ($excludeSample && isset($context->sampleOrderIds[$oid])) {
                    continue;
                }
                if ($excludeReview && isset($context->reviewOrderIds[$oid])) {
                    continue;
                }
                if ($joinToOrders) {
                    $joinKeys = $part['join_keys'] ?? [];
                    if (!self::matchJoinKeys($row['row_data'], $joinKeys, $context)) {
                        continue;
                    }
                }
            }

            if (!self::passesRowFilters($row['row_data'], $rowFilters)) {
                continue;
            }

            $result[] = $row;
        }
        return $result;
    }

    /** @param string[] $dedupKeys */
    private static function dedupKey(array $rowData, array $dedupKeys, int $rowIndex): string
    {
        if (!$dedupKeys) {
            return '__row_' . $rowIndex;
        }
        $normalized = self::normalized($rowData);
        $parts = [];
        foreach ($dedupKeys as $key) {
            $v = $normalized[trim((string) $key)] ?? '';
            $parts[] = (string) ($v ?? '');
        }
        return json_encode($parts);
    }

    /** 组内单列：继承块级规则，覆盖文件/Sheet/列头。 */
    private static function sourcePart(array $base, array $src): array
    {
        return [
            'source_file_keyword' => trim((string) (($src['source_file_keyword'] ?? '') ?: ($base['source_file_keyword'] ?? ''))) ?: null,
            'sheet_name' => trim((string) (($src['sheet_name'] ?? '') ?: ($base['sheet_name'] ?? ''))),
            'column_header' => trim((string) (($src['column_header'] ?? '') ?: ($base['column_header'] ?? ''))),
            'aliases' => $base['aliases'] ?? [],
            'aggregation' => $base['aggregation'] ?? 'sum',
            'dedup_keys' => $base['dedup_keys'] ?? [],
            'date_filter_column' => $base['date_filter_column'] ?? null,
            'date_format' => $base['date_format'] ?? null,
            'row_filters' => $base['row_filters'] ?? [],
            'exclude_sample' => $base['exclude_sample'] ?? false,
            'exclude_review' => $base['exclude_review'] ?? false,
            'join_to_orders' => $base['join_to_orders'] ?? false,
            'join_keys' => $base['join_keys'] ?? [],
            'only_sample' => $base['only_sample'] ?? false,
        ];
    }

    /** @param array[] $rows @param array<int, string> $importFileNames */
    private static function aggregateSingleSource(array $rows, array $part, array $importFileNames, ?DailyContext $context = null): float
    {
        $matched = self::filterRows($rows, $part, $importFileNames, $context);
        if (!$matched) {
            return 0.0;
        }

        $agg = ($part['aggregation'] ?? '') ?: 'sum';
        $dedupKeys = $part['dedup_keys'] ?? [];

        if ($agg === 'count') {
            return (float) count($matched);
        }

        if ($agg === 'count_distinct') {
            $keys = [];
            foreach ($matched as $i => $r) {
                $keys[self::dedupKey($r['row_data'], $dedupKeys, $i)] = true;
            }
            return (float) count($keys);
        }

        if ($agg === 'sum_dedup') {
            $groups = [];
            foreach ($matched as $i => $row) {
                $val = self::cell($row['row_data'], (string) $part['column_header'], $part['aliases'] ?? []);
                if ($val === null) {
                    continue;
                }
                $groups[self::dedupKey($row['row_data'], $dedupKeys, $i)] = $val;
            }
            return array_sum($groups);
        }

        if ($agg === 'max_dedup') {
            $groups = [];
            foreach ($matched as $i => $row) {
                $val = self::cell($row['row_data'], (string) $part['column_header'], $part['aliases'] ?? []);
                if ($val === null) {
                    continue;
                }
                $key = self::dedupKey($row['row_data'], $dedupKeys, $i);
                $groups[$key] = max($groups[$key] ?? $val, $val);
            }
            return array_sum($groups);
        }

        $values = [];
        foreach ($matched as $row) {
            $val = self::cell($row['row_data'], (string) $part['column_header'], $part['aliases'] ?? []);
            if ($val !== null) {
                $values[] = $val;
            }
        }

        if (!$values) {
            return 0.0;
        }
        if ($agg === 'avg') {
            return array_sum($values) / count($values);
        }
        return array_sum($values);
    }

    /** 单条规则块：组内多列先各自聚合，再按 combine_op 组合。 */
    public static function aggregatePart(array $rows, array $part, array $importFileNames, ?DailyContext $context = null): float
    {
        $sources = $part['sources'] ?? [];
        if (!$sources) {
            $sources = [[
                'source_file_keyword' => $part['source_file_keyword'] ?? null,
                'sheet_name' => $part['sheet_name'] ?? '',
                'column_header' => $part['column_header'] ?? '',
                'combine_op' => 'add',
            ]];
        }
        $total = 0.0;
        $started = false;
        foreach ($sources as $src) {
            $sub = self::sourcePart($part, $src);
            $val = self::aggregateSingleSource($rows, $sub, $importFileNames, $context);
            $op = ($src['combine_op'] ?? '') ?: 'add';
            if (!$started) {
                $total = $op === 'subtract' ? -$val : $val;
                $started = true;
                continue;
            }
            if ($op === 'subtract') {
                $total -= $val;
            } else {
                $total += $val;
            }
        }
        return $started ? $total : 0.0;
    }

    /** @param array<string, float> $fieldValues */
    public static function resolvePartValue(array $part, array $rows, array $importFileNames, ?DailyContext $context, array $fieldValues): float
    {
        if (!empty($part['ref_field_code'])) {
            return (float) ($fieldValues[$part['ref_field_code']] ?? 0.0);
        }
        return self::aggregatePart($rows, $part, $importFileNames, $context);
    }

    /** @param array[] $parts @param float[] $partValues */
    public static function combineParts(array $parts, array $partValues): float
    {
        $total = 0.0;
        $started = false;
        foreach ($parts as $i => $part) {
            if (!array_key_exists($i, $partValues)) {
                break;
            }
            $value = $partValues[$i];
            $op = ($part['combine_op'] ?? '') ?: 'add';
            if (!$started) {
                $total = $op !== 'subtract' ? $value : -$value;
                $started = true;
                continue;
            }
            if ($op === 'subtract') {
                $total -= $value;
            } else {
                $total += $value;
            }
        }
        return $started ? $total : 0.0;
    }
}
