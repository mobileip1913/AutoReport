<?php

declare(strict_types=1);

namespace App\Services;

use PhpOffice\PhpSpreadsheet\IOFactory;
use PhpOffice\PhpSpreadsheet\Spreadsheet;
use PhpOffice\PhpSpreadsheet\Writer\Xlsx;

/**
 * 刷单清单：模板下载、导入校验、写入 config.review_orders。
 * 与 Python 版 services/review_import.py 对等。
 */
final class ReviewImport
{
    public const REVIEW_LOGISTICS_MODE_FIXED = 'per_order_fixed';
    public const REVIEW_LOGISTICS_MODE_IMPORT = 'from_import';
    public const DEFAULT_REVIEW_LOGISTICS_PER_ORDER = 1.0;

    /** [内部键, 模板列名, 是否必填] — 物流费不在 Excel 中维护 */
    public const REVIEW_COLUMNS = [
        ['order_id', 'Order ID', true],
        ['sku_id', 'SKU ID', true],
        ['amount', '刷单金额', false],
        ['commission', '刷单佣金', false],
        ['service_fee', '刷单服务费', false],
        ['cost', '刷单成本', false],
    ];

    public const REVIEW_FIELD_CODES = [
        'amount' => 'mc_review_amount',
        'commission' => 'mc_review_commission',
        'service_fee' => 'mc_review_service_fee',
        'logistics' => 'mc_review_logistics',
        'cost' => 'mc_review_cost',
    ];

    /** 运费单独导入列 */
    public const REVIEW_LOGISTICS_IMPORT_COLUMNS = [
        ['order_id', 'Order ID', true],
        ['sku_id', 'SKU ID', true],
        ['logistics', '刷单运费', false],
    ];

    /** @return string[] */
    public static function templateHeaders(): array
    {
        return array_map(fn($c) => $c[1], self::REVIEW_COLUMNS);
    }

    /** @return string[] */
    public static function logisticsTemplateHeaders(): array
    {
        return array_map(fn($c) => $c[1], self::REVIEW_LOGISTICS_IMPORT_COLUMNS);
    }

    public static function reviewLogisticsMode(array $cfg): string
    {
        $mode = trim((string) ($cfg['review_logistics_mode'] ?? ''));
        return $mode === self::REVIEW_LOGISTICS_MODE_IMPORT
            ? self::REVIEW_LOGISTICS_MODE_IMPORT
            : self::REVIEW_LOGISTICS_MODE_FIXED;
    }

    public static function reviewLogisticsPerOrder(array $cfg): float
    {
        $raw = $cfg['review_logistics_per_order'] ?? null;
        if ($raw === null || trim((string) $raw) === '') {
            return self::DEFAULT_REVIEW_LOGISTICS_PER_ORDER;
        }
        return max(0.0, FieldAggregator::toNumber($raw));
    }

    public static function reviewLogisticsExcludeSameDayRefund(array $cfg): bool
    {
        return (bool) ($cfg['review_logistics_exclude_same_day_refund'] ?? false);
    }

    /**
     * @param array[] $reviews
     * @param array<string, true>|null $excludeOrderIds
     */
    public static function distinctReviewOrderCount(array $reviews, ?array $excludeOrderIds = null): int
    {
        $exclude = $excludeOrderIds ?? [];
        $ids = [];
        foreach ($reviews as $r) {
            $oid = trim((string) ($r['order_id'] ?? ''));
            if ($oid !== '' && !isset($exclude[$oid])) {
                $ids[$oid] = true;
            }
        }
        return count($ids);
    }

    /**
     * @param array[] $reviews
     * @param array<string, true>|null $excludeSameDayOrderIds
     */
    public static function reviewLogisticsTotal(
        array $reviews,
        array $cfg,
        ?array $excludeSameDayOrderIds = null,
    ): float {
        $exclude = [];
        if (self::reviewLogisticsExcludeSameDayRefund($cfg) && $excludeSameDayOrderIds) {
            $exclude = $excludeSameDayOrderIds;
        }
        if (self::reviewLogisticsMode($cfg) === self::REVIEW_LOGISTICS_MODE_IMPORT) {
            $total = 0.0;
            foreach ($reviews as $row) {
                $oid = trim((string) ($row['order_id'] ?? ''));
                if ($oid !== '' && isset($exclude[$oid])) {
                    continue;
                }
                $total += FieldAggregator::toNumber($row['logistics'] ?? null);
            }
            return $total;
        }
        return self::distinctReviewOrderCount($reviews, $exclude) * self::reviewLogisticsPerOrder($cfg);
    }

    public static function reviewLogisticsRuleSummary(array $cfg): string
    {
        $reviews = $cfg['review_orders'] ?? [];
        $suffix = self::reviewLogisticsExcludeSameDayRefund($cfg) ? ' · 排除当日退单' : '';
        if (self::reviewLogisticsMode($cfg) === self::REVIEW_LOGISTICS_MODE_IMPORT) {
            $total = self::reviewLogisticsTotal($reviews, $cfg);
            return sprintf('Excel 导入运费合计 $%g%s · %d 行', $total, $suffix, count($reviews));
        }
        $orderCount = self::distinctReviewOrderCount($reviews);
        $perOrder = self::reviewLogisticsPerOrder($cfg);
        return sprintf('按单固定 $%g/单 × %d 单刷单订单%s', $perOrder, $orderCount, $suffix);
    }

    /**
     * @param array[] $reviews
     * @param array<string, true>|null $excludeSameDayOrderIds
     * @return array{row_count: int, order_count: int, logistics_total: float, logistics_mode: string, logistics_per_order: float}
     */
    public static function reviewImportStats(
        array $reviews,
        array $cfg,
        ?array $excludeSameDayOrderIds = null,
    ): array {
        $exclude = [];
        if (self::reviewLogisticsExcludeSameDayRefund($cfg) && $excludeSameDayOrderIds) {
            $exclude = $excludeSameDayOrderIds;
        }
        $mode = self::reviewLogisticsMode($cfg);
        return [
            'row_count' => count($reviews),
            'order_count' => self::distinctReviewOrderCount($reviews, $exclude),
            'logistics_total' => self::reviewLogisticsTotal($reviews, $cfg, $excludeSameDayOrderIds),
            'logistics_mode' => $mode,
            'logistics_per_order' => self::reviewLogisticsPerOrder($cfg),
        ];
    }

    /** @return array<string, string> 小写列头（含去空格版本）=> 内部键 */
    private static function headerAliases(): array
    {
        $aliases = [];
        foreach (self::REVIEW_COLUMNS as [$key, $header]) {
            $aliases[mb_strtolower($header)] = $key;
            $aliases[mb_strtolower(str_replace(' ', '', $header))] = $key;
        }
        foreach (self::REVIEW_LOGISTICS_IMPORT_COLUMNS as [$key, $header]) {
            $aliases[mb_strtolower($header)] = $key;
            $aliases[mb_strtolower(str_replace(' ', '', $header))] = $key;
            if ($key === 'logistics') {
                $aliases['运费'] = $key;
                $aliases['物流费'] = $key;
                $aliases['刷单运费'] = $key;
                $aliases['刷单物流费'] = $key;
                $aliases['刷单物流费用'] = $key;
            }
        }
        $aliases['order id'] = 'order_id';
        $aliases['skuid'] = 'sku_id';
        return $aliases;
    }

    private static function normalizeHeader(mixed $cell): string
    {
        return preg_replace('/\s+/u', ' ', trim((string) ($cell ?? '')));
    }

    private static function headerToKey(string $header): ?string
    {
        $aliases = self::headerAliases();
        $h = mb_strtolower(self::normalizeHeader($header));
        return $aliases[$h] ?? $aliases[str_replace(' ', '', $h)] ?? null;
    }

    /** @return string 生成的 xlsx 二进制内容 */
    public static function buildReviewTemplateBytes(): string
    {
        $spreadsheet = new Spreadsheet();
        $ws = $spreadsheet->getActiveSheet();
        $ws->setTitle('刷单清单');
        $ws->fromArray(['说明：每行一条刷单 SKU；Order ID、SKU ID 必填；金额/佣金/服务费/成本填在对应列；物流费不在此表维护，请在「刷单设置」配置每单固定金额'], null, 'A1');
        $ws->fromArray(self::templateHeaders(), null, 'A2');
        $ws->getStyle('A3:B3')->getNumberFormat()->setFormatCode('@');
        $ws->setCellValueExplicit('A3', '1234567890123456789', \PhpOffice\PhpSpreadsheet\Cell\DataType::TYPE_STRING);
        $ws->setCellValueExplicit('B3', '9876543210', \PhpOffice\PhpSpreadsheet\Cell\DataType::TYPE_STRING);
        $ws->fromArray([100, 10, 5, 50], null, 'C3');

        $tmp = tempnam(sys_get_temp_dir(), 'rvw');
        (new Xlsx($spreadsheet))->save($tmp);
        $spreadsheet->disconnectWorksheets();
        $bytes = (string) file_get_contents($tmp);
        @unlink($tmp);
        return $bytes;
    }

    /** @return array<string, true> "oid|sku" 组合键集合 */
    private static function knownOrderSkuKeys(array $ds): array
    {
        $cfg = DsSettings::getDsConfig($ds);
        $store = (($cfg['meta'] ?? [])['店铺名称'] ?? null) ?: $ds['name'];
        [$rows] = FactProvider::loadFactRows((int) $ds['id'], (string) $store);
        $orderSheet = $cfg['order_sheet'] ?? null;
        $orderIdCol = ($cfg['order_id_col'] ?? '') ?: 'Order ID';
        $skuIdCol = ($cfg['sku_id_col'] ?? '') ?: 'SKU ID';
        $keys = [];
        foreach ($rows as $r) {
            if ($orderSheet && $r['sheet_name'] !== $orderSheet) {
                continue;
            }
            $oid = FieldAggregator::extract($r['row_data'], array_merge([$orderIdCol], FieldAggregator::ORDER_ID_CANDIDATES));
            $sku = FieldAggregator::extract($r['row_data'], array_merge([$skuIdCol], FieldAggregator::SKU_ID_CANDIDATES));
            if ($oid !== '' && $sku !== '') {
                $keys[$oid . '|' . $sku] = true;
            }
        }
        return $keys;
    }

    /** 供 SampleImport 等复用 */
    public static function knownOrderSkuKeysPublic(array $ds): array
    {
        return self::knownOrderSkuKeys($ds);
    }

    public static function buildReviewLogisticsTemplateBytes(): string
    {
        $spreadsheet = new Spreadsheet();
        $ws = $spreadsheet->getActiveSheet();
        $ws->setTitle('刷单运费');
        $ws->fromArray(['说明：每行一条刷单 SKU 的运费；Order ID、SKU ID 必填；刷单运费填在对应列；导入后汇总至日报「刷单物流费用」，同 Order+SKU 覆盖'], null, 'A1');
        $ws->fromArray(self::logisticsTemplateHeaders(), null, 'A2');
        $ws->getStyle('A3:B3')->getNumberFormat()->setFormatCode('@');
        $ws->setCellValueExplicit('A3', '1234567890123456789', \PhpOffice\PhpSpreadsheet\Cell\DataType::TYPE_STRING);
        $ws->setCellValueExplicit('B3', '9876543210', \PhpOffice\PhpSpreadsheet\Cell\DataType::TYPE_STRING);
        $ws->fromArray([1.5], null, 'C3');

        $tmp = tempnam(sys_get_temp_dir(), 'rlg');
        (new Xlsx($spreadsheet))->save($tmp);
        $spreadsheet->disconnectWorksheets();
        $bytes = (string) file_get_contents($tmp);
        @unlink($tmp);
        return $bytes;
    }

    /** @return array{0: array[], 1: string[]} */
    public static function parseReviewLogisticsUpload(string $content): array
    {
        $errors = [];
        $tmp = tempnam(sys_get_temp_dir(), 'rlgu');
        file_put_contents($tmp, $content);
        try {
            $spreadsheet = IOFactory::load($tmp);
        } catch (\Throwable) {
            @unlink($tmp);
            return [[], ['无法读取 Excel 文件，请使用 .xlsx 格式']];
        }
        $ws = $spreadsheet->getActiveSheet();
        $rows = $ws->toArray(null, true, false, false);
        $spreadsheet->disconnectWorksheets();
        @unlink($tmp);

        if (!$rows) {
            return [[], ['文件为空']];
        }

        $headerRowIdx = null;
        $colMap = [];
        foreach (array_slice($rows, 0, 15) as $i => $row) {
            $mapping = [];
            foreach (($row ?? []) as $j => $h) {
                $key = self::headerToKey((string) ($h ?? ''));
                if ($key !== null && !isset($mapping[$key])) {
                    $mapping[$key] = $j;
                }
            }
            if (isset($mapping['order_id'], $mapping['sku_id'], $mapping['logistics'])) {
                $headerRowIdx = $i;
                $colMap = $mapping;
                break;
            }
        }

        if ($headerRowIdx === null) {
            return [[], ['缺少必填列「Order ID」「SKU ID」与「刷单运费」（或对应中文列头）']];
        }

        $parsed = [];
        $seen = [];
        foreach (array_slice($rows, $headerRowIdx + 1, null, true) as $idx => $row) {
            $lineNo = $idx + 1;
            $row = $row ?? [];
            $allEmpty = true;
            foreach ($row as $c) {
                if ($c !== null && trim((string) $c) !== '') {
                    $allEmpty = false;
                    break;
                }
            }
            if ($allEmpty) {
                continue;
            }

            $cell = function (string $key) use ($colMap, $row) {
                $i = $colMap[$key] ?? null;
                return $i === null ? null : ($row[$i] ?? null);
            };

            $oid = trim((string) ($cell('order_id') ?? ''));
            $sku = trim((string) ($cell('sku_id') ?? ''));
            if ($oid === '' && $sku === '') {
                continue;
            }
            if (str_starts_with($oid, '1234567890') && $sku === '9876543210') {
                continue;
            }
            if ($oid === '') {
                $errors[] = "第 {$lineNo} 行：Order ID 不能为空";
                continue;
            }
            if ($sku === '') {
                $errors[] = "第 {$lineNo} 行：SKU ID 不能为空";
                continue;
            }
            $pair = $oid . '|' . $sku;
            if (isset($seen[$pair])) {
                $errors[] = "第 {$lineNo} 行：Order ID + SKU ID 重复（{$oid} / {$sku}）";
                continue;
            }
            $seen[$pair] = true;

            $raw = $cell('logistics');
            $text = trim((string) ($raw ?? ''));
            if ($text === '') {
                $logistics = 0.0;
            } else {
                $num = FieldAggregator::toNumber($raw);
                if ($text !== '0' && $text !== '0.0' && $num === 0.0 && !is_int($raw) && !is_float($raw)) {
                    $errors[] = "第 {$lineNo} 行：刷单运费 不是有效数字";
                    continue;
                }
                $logistics = $num;
            }
            $parsed[] = ['order_id' => $oid, 'sku_id' => $sku, 'logistics' => $logistics];
        }

        if (!$parsed && !$errors) {
            $errors[] = '未解析到有效运费数据';
        }
        return [$parsed, $errors];
    }

    /** @param array[] $existing @param array[] $logisticsRows @return array[] */
    private static function mergeReviewLogistics(array $existing, array $logisticsRows): array
    {
        $merged = [];
        foreach ($existing as $row) {
            $oid = trim((string) ($row['order_id'] ?? ''));
            $sku = trim((string) ($row['sku_id'] ?? ''));
            if ($oid !== '' && $sku !== '') {
                $merged[$oid . '|' . $sku] = $row;
            }
        }
        foreach ($logisticsRows as $row) {
            $oid = $row['order_id'];
            $sku = $row['sku_id'];
            $key = $oid . '|' . $sku;
            $base = $merged[$key] ?? [
                'order_id' => $oid,
                'sku_id' => $sku,
                'amount' => 0.0,
                'commission' => 0.0,
                'service_fee' => 0.0,
                'cost' => 0.0,
            ];
            $base['logistics'] = $row['logistics'] ?? 0.0;
            $merged[$key] = $base;
        }
        return array_values($merged);
    }

    public static function importReviewLogistics(array &$ds, string $content, bool $strict = true): array
    {
        [$logisticsRows, $parseErrors] = self::parseReviewLogisticsUpload($content);
        if ($parseErrors && !$logisticsRows) {
            return ['ok' => false, 'errors' => $parseErrors, 'imported' => 0];
        }

        $known = self::knownOrderSkuKeys($ds);
        $unknown = [];
        foreach ($logisticsRows as $r) {
            if (!isset($known[$r['order_id'] . '|' . $r['sku_id']])) {
                $unknown[] = "{$r['order_id']}/{$r['sku_id']}";
            }
        }
        $errors = $parseErrors;
        if ($strict && $unknown) {
            $preview = implode('、', array_slice($unknown, 0, 5));
            $suffix = count($unknown) > 5 ? ' 等 ' . count($unknown) . ' 条' : '';
            $errors[] = "以下 Order ID + SKU ID 在订单主表中不存在：{$preview}{$suffix}";
        }
        if ($errors) {
            return ['ok' => false, 'errors' => $errors, 'imported' => 0, 'unknown_count' => count($unknown)];
        }

        $cfg0 = DsSettings::getDsConfig($ds);
        $merged = self::mergeReviewLogistics($cfg0['review_orders'] ?? [], $logisticsRows);
        $cfg = DsSettings::saveDsConfig($ds, [
            'review_orders' => $merged,
            'review_order_ids' => self::reviewOrderIdsFromRows($merged),
            'review_logistics_mode' => self::REVIEW_LOGISTICS_MODE_IMPORT,
        ]);
        $stats = self::reviewImportStats($merged, $cfg);
        return [
            'ok' => true,
            'imported' => count($logisticsRows),
            'review_order_count' => count($cfg['review_orders'] ?? []),
            'review_order_distinct' => $stats['order_count'],
            'review_logistics_total' => $stats['logistics_total'],
            'review_logistics_summary' => self::reviewLogisticsRuleSummary($cfg),
        ];
    }

    /**
     * @return array{0: array[], 1: string[]}
     */
    public static function parseReviewUpload(string $content): array
    {
        $errors = [];
        $tmp = tempnam(sys_get_temp_dir(), 'rvu');
        file_put_contents($tmp, $content);
        try {
            $spreadsheet = IOFactory::load($tmp);
        } catch (\Throwable) {
            @unlink($tmp);
            return [[], ['无法读取 Excel 文件，请使用 .xlsx 格式']];
        }
        $ws = $spreadsheet->getActiveSheet();
        $rows = $ws->toArray(null, true, false, false);
        $spreadsheet->disconnectWorksheets();
        @unlink($tmp);

        if (!$rows) {
            return [[], ['文件为空']];
        }

        $headerRowIdx = null;
        $colMap = [];
        foreach (array_slice($rows, 0, 15) as $i => $row) {
            $mapping = [];
            foreach (($row ?? []) as $j => $h) {
                $key = self::headerToKey((string) ($h ?? ''));
                if ($key !== null && !isset($mapping[$key])) {
                    $mapping[$key] = $j;
                }
            }
            if (isset($mapping['order_id'], $mapping['sku_id'])) {
                $headerRowIdx = $i;
                $colMap = $mapping;
                break;
            }
        }

        if ($headerRowIdx === null) {
            return [[], ['缺少必填列「Order ID」和「SKU ID」（或对应中文列头）']];
        }

        $labelByKey = [];
        foreach (self::REVIEW_COLUMNS as [$key, $header]) {
            $labelByKey[$key] = $header;
        }

        $parsed = [];
        $seen = [];
        foreach (array_slice($rows, $headerRowIdx + 1, null, true) as $idx => $row) {
            $lineNo = $idx + 1;
            $row = $row ?? [];
            $allEmpty = true;
            foreach ($row as $c) {
                if ($c !== null && trim((string) $c) !== '') {
                    $allEmpty = false;
                    break;
                }
            }
            if ($allEmpty) {
                continue;
            }

            $cell = function (string $key) use ($colMap, $row) {
                $i = $colMap[$key] ?? null;
                return $i === null ? null : ($row[$i] ?? null);
            };

            $oid = trim((string) ($cell('order_id') ?? ''));
            $sku = trim((string) ($cell('sku_id') ?? ''));
            if ($oid === '' && $sku === '') {
                continue;
            }
            if (str_starts_with($oid, '1234567890') && $sku === '9876543210') {
                continue;
            }

            if ($oid === '') {
                $errors[] = "第 {$lineNo} 行：Order ID 不能为空";
                continue;
            }
            if ($sku === '') {
                $errors[] = "第 {$lineNo} 行：SKU ID 不能为空";
                continue;
            }

            $pair = $oid . '|' . $sku;
            if (isset($seen[$pair])) {
                $errors[] = "第 {$lineNo} 行：Order ID + SKU ID 重复（{$oid} / {$sku}）";
                continue;
            }
            $seen[$pair] = true;

            $record = ['order_id' => $oid, 'sku_id' => $sku];
            foreach (self::REVIEW_COLUMNS as [$key]) {
                if ($key === 'order_id' || $key === 'sku_id') {
                    continue;
                }
                $raw = $cell($key);
                $text = trim((string) ($raw ?? ''));
                if ($text === '') {
                    $record[$key] = 0.0;
                    continue;
                }
                $num = FieldAggregator::toNumber($raw);
                if ($text !== '0' && $text !== '0.0' && $num === 0.0 && !is_int($raw) && !is_float($raw)) {
                    $errors[] = "第 {$lineNo} 行：{$labelByKey[$key]} 不是有效数字";
                    continue;
                }
                $record[$key] = $num;
            }
            $parsed[] = $record;
        }

        if (!$parsed && !$errors) {
            $errors[] = '未解析到有效刷单数据';
        }
        return [$parsed, $errors];
    }

    /**
     * @param array<string, true>|null $sameDayRefundOrderIds
     * @return array<string, float>
     */
    public static function reviewFieldValues(array $dsConfig, ?array $sameDayRefundOrderIds = null): array
    {
        $reviews = $dsConfig['review_orders'] ?? [];
        $out = [];
        foreach (self::REVIEW_FIELD_CODES as $code) {
            $out[$code] = 0.0;
        }
        foreach ($reviews as $row) {
            foreach (self::REVIEW_FIELD_CODES as $key => $code) {
                if ($key === 'logistics') {
                    continue;
                }
                $out[$code] += FieldAggregator::toNumber($row[$key] ?? null);
            }
        }
        $stats = self::reviewImportStats($reviews, $dsConfig, $sameDayRefundOrderIds);
        $out[self::REVIEW_FIELD_CODES['logistics']] = $stats['logistics_total'];
        return $out;
    }

    /** @return string[] */
    public static function reviewOrderIdsFromRows(array $rows): array
    {
        $ids = [];
        foreach ($rows as $r) {
            $oid = trim((string) ($r['order_id'] ?? ''));
            if ($oid !== '') {
                $ids[$oid] = true;
            }
        }
        $out = array_keys($ids);
        sort($out);
        return $out;
    }

    public static function importReviewOrders(array &$ds, string $content, bool $strict = true): array
    {
        [$reviewRows, $parseErrors] = self::parseReviewUpload($content);
        if ($parseErrors && !$reviewRows) {
            return ['ok' => false, 'errors' => $parseErrors, 'imported' => 0];
        }

        $known = self::knownOrderSkuKeys($ds);
        $unknown = [];
        foreach ($reviewRows as $r) {
            if (!isset($known[$r['order_id'] . '|' . $r['sku_id']])) {
                $unknown[] = "{$r['order_id']}/{$r['sku_id']}";
            }
        }
        $errors = $parseErrors;
        if ($strict && $unknown) {
            $preview = implode('、', array_slice($unknown, 0, 5));
            $suffix = count($unknown) > 5 ? ' 等 ' . count($unknown) . ' 条' : '';
            $errors[] = "以下 Order ID + SKU ID 在订单主表中不存在：{$preview}{$suffix}";
        }

        if ($errors) {
            return ['ok' => false, 'errors' => $errors, 'imported' => 0, 'unknown_count' => count($unknown)];
        }

        $cfg = DsSettings::saveDsConfig($ds, [
            'review_orders' => $reviewRows,
            'review_order_ids' => self::reviewOrderIdsFromRows($reviewRows),
        ]);
        $stats = self::reviewImportStats($reviewRows, $cfg);
        return [
            'ok' => true,
            'imported' => count($reviewRows),
            'review_order_count' => count($cfg['review_orders'] ?? []),
            'review_order_distinct' => $stats['order_count'],
            'review_logistics_total' => $stats['logistics_total'],
            'review_logistics_summary' => self::reviewLogisticsRuleSummary($cfg),
        ];
    }
}
