<?php

declare(strict_types=1);

namespace App\Services;

use PhpOffice\PhpSpreadsheet\IOFactory;
use PhpOffice\PhpSpreadsheet\Spreadsheet;
use PhpOffice\PhpSpreadsheet\Writer\Xlsx;

/**
 * 样品单清单：模板下载、导入校验、写入 config.sample_orders。
 * 与 Python 版 services/sample_import.py 对等。
 */
final class SampleImport
{
    public const SAMPLE_COLUMNS = [
        ['order_id', 'Order ID', true],
        ['sku_id', 'SKU ID', true],
        ['logistics', '样品单运费', false],
        ['cost', '样品单成本', false],
    ];

    public const SAMPLE_FIELD_CODES = [
        'logistics' => 'mc_sample_logistics',
        'cost' => 'mc_sample_cost',
    ];

    /** @return string[] */
    public static function templateHeaders(): array
    {
        return array_map(fn($c) => $c[1], self::SAMPLE_COLUMNS);
    }

    /** @return array<string, string> */
    private static function headerAliases(): array
    {
        $aliases = [];
        foreach (self::SAMPLE_COLUMNS as [$key, $header]) {
            $aliases[mb_strtolower($header)] = $key;
            $aliases[mb_strtolower(str_replace(' ', '', $header))] = $key;
        }
        $aliases['order id'] = 'order_id';
        $aliases['skuid'] = 'sku_id';
        $aliases['运费'] = 'logistics';
        $aliases['样品运费'] = 'logistics';
        $aliases['样品单运费'] = 'logistics';
        $aliases['成本'] = 'cost';
        $aliases['样品成本'] = 'cost';
        $aliases['样品单成本'] = 'cost';
        return $aliases;
    }

    private static function normalizeHeader(mixed $cell): string
    {
        return preg_replace('/\s+/u', ' ', trim((string) ($cell ?? ''))) ?? '';
    }

    private static function headerToKey(string $header): ?string
    {
        $aliases = self::headerAliases();
        $h = mb_strtolower(self::normalizeHeader($header));
        return $aliases[$h] ?? $aliases[str_replace(' ', '', $h)] ?? null;
    }

    public static function buildSampleTemplateBytes(): string
    {
        $spreadsheet = new Spreadsheet();
        $ws = $spreadsheet->getActiveSheet();
        $ws->setTitle('样品单');
        $ws->fromArray(['说明：每行一条样品 SKU；Order ID、SKU ID 必填；样品单运费/成本填在对应列；导入后汇总至日报「样品单运费」「样品单成本」，并用于识别样品单'], null, 'A1');
        $ws->fromArray(self::templateHeaders(), null, 'A2');
        $ws->getStyle('A3:B3')->getNumberFormat()->setFormatCode('@');
        $ws->setCellValueExplicit('A3', '1234567890123456789', \PhpOffice\PhpSpreadsheet\Cell\DataType::TYPE_STRING);
        $ws->setCellValueExplicit('B3', '9876543210', \PhpOffice\PhpSpreadsheet\Cell\DataType::TYPE_STRING);
        $ws->fromArray([2.5, 8], null, 'C3');

        $tmp = tempnam(sys_get_temp_dir(), 'smp');
        (new Xlsx($spreadsheet))->save($tmp);
        $spreadsheet->disconnectWorksheets();
        $bytes = (string) file_get_contents($tmp);
        @unlink($tmp);
        return $bytes;
    }

    /** @return array{0: array[], 1: string[]} */
    public static function parseSampleUpload(string $content): array
    {
        $errors = [];
        $tmp = tempnam(sys_get_temp_dir(), 'smpu');
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
        foreach (self::SAMPLE_COLUMNS as [$key, $header]) {
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
            foreach (self::SAMPLE_COLUMNS as [$key]) {
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
            $errors[] = '未解析到有效样品单数据';
        }
        return [$parsed, $errors];
    }

    /** @return string[] */
    public static function sampleOrderIdsFromRows(array $rows): array
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

    public static function distinctSampleOrderCount(array $rows): int
    {
        return count(self::sampleOrderIdsFromRows($rows));
    }

    /** @return array<string, float> */
    public static function sampleFieldValues(array $dsConfig): array
    {
        $rows = $dsConfig['sample_orders'] ?? [];
        $out = [];
        foreach (self::SAMPLE_FIELD_CODES as $code) {
            $out[$code] = 0.0;
        }
        foreach ($rows as $row) {
            foreach (self::SAMPLE_FIELD_CODES as $key => $code) {
                $out[$code] += FieldAggregator::toNumber($row[$key] ?? null);
            }
        }
        return $out;
    }

    public static function importSampleOrders(array &$ds, string $content, bool $strict = true): array
    {
        [$sampleRows, $parseErrors] = self::parseSampleUpload($content);
        if ($parseErrors && !$sampleRows) {
            return ['ok' => false, 'errors' => $parseErrors, 'imported' => 0];
        }

        $known = ReviewImport::knownOrderSkuKeysPublic($ds);
        $unknown = [];
        foreach ($sampleRows as $r) {
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
            'sample_orders' => $sampleRows,
            'sample_order_ids' => self::sampleOrderIdsFromRows($sampleRows),
        ]);
        $logistics = 0.0;
        $cost = 0.0;
        foreach ($sampleRows as $r) {
            $logistics += FieldAggregator::toNumber($r['logistics'] ?? null);
            $cost += FieldAggregator::toNumber($r['cost'] ?? null);
        }
        return [
            'ok' => true,
            'imported' => count($sampleRows),
            'sample_order_count' => count($cfg['sample_orders'] ?? []),
            'sample_order_distinct' => self::distinctSampleOrderCount($sampleRows),
            'sample_logistics_total' => $logistics,
            'sample_cost_total' => $cost,
        ];
    }
}
