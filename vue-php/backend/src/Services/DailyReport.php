<?php

declare(strict_types=1);

namespace App\Services;

use App\Config;
use PhpOffice\PhpSpreadsheet\Cell\Coordinate;
use PhpOffice\PhpSpreadsheet\IOFactory;
use PhpOffice\PhpSpreadsheet\Worksheet\Worksheet;

/**
 * 日报输出：按 report_group 分组组织数值，并导出 Excel。
 * 与 Python 版 services/daily_report.py 对等。
 */
final class DailyReport
{
    public const DAILY_TEMPLATE_NAME = '日报模板.xlsx';

    /** @return string[] files 目录下可供店铺绑定的 Excel 导出模板（文件名含「模板」） */
    public static function listExcelTemplates(): array
    {
        $filesDir = rtrim(Config::get()->filesDir, '/\\');
        $names = [];
        if (is_dir($filesDir)) {
            foreach (glob($filesDir . DIRECTORY_SEPARATOR . '*.xlsx') ?: [] as $path) {
                $name = basename($path);
                if (str_contains($name, '模板')) {
                    $names[] = $name;
                }
            }
            sort($names);
        }
        if (!in_array(self::DAILY_TEMPLATE_NAME, $names, true)) {
            array_unshift($names, self::DAILY_TEMPLATE_NAME);
        }
        return $names ?: [self::DAILY_TEMPLATE_NAME];
    }
    public const TEMPLATE_DATA_ROW = 4;
    public const METRIC_START_COLUMN = 6; // Excel 列 F

    /** 与 files/日报模板.xlsx 第 4 行列位一致；值为 ReportValue.line_label */
    public const TEMPLATE_COLUMN_LABELS = [
        'F' => '实际支付金额',
        'G' => '应支付金额',
        'H' => '应收金额',
        'I' => '退单金额',
        'J' => '刷单金额',
        'K' => '刷单佣金',
        'L' => '刷单服务费',
        'M' => '刷单物流费用',
        'N' => '刷单成本',
        'O' => '样品单运费',
        'P' => '样品单成本',
        'Q' => null,
        'R' => '站内消耗',
        'S' => null,
        'T' => '下单数',
        'U' => '物流费用',
        'V' => '达人佣金',
        'W' => '店铺佣金',
        'X' => '产品成本',
        'Y' => null,
        'Z' => null,
        'AA' => null,
        'AB' => '固定费用',
        'AC' => '利润',
        'AD' => '框返',
        'AE' => '总利润',
    ];

    public const META_COLUMNS = [
        'A' => '店铺名称',
        'B' => '平台',
        'C' => '区域',
        'D' => '项目',
        'E' => '日期',
    ];

    public const MANUAL_EXPORT_LABELS = ['利润', '总利润', '利润(估算)', '总利润(估算)'];

    public const APPEND_START_COLUMN = 32; // AF，模板 AE(31) 之后追加自定义字段

    /** @return array<string, string> label => col */
    public static function templateLabelToCol(): array
    {
        $out = [];
        foreach (self::TEMPLATE_COLUMN_LABELS as $col => $label) {
            if ($label) {
                $out[$label] = $col;
            }
        }
        return $out;
    }

    /** 按当前报表字段顺序生成 Excel 列号（从 F 起）。 */
    public static function metricColLetter(int $index): string
    {
        return Coordinate::stringFromColumnIndex(self::METRIC_START_COLUMN + $index);
    }

    /** @param array[] $mappings */
    private static function customReportMappings(array $mappings): array
    {
        $labelToCol = self::templateLabelToCol();
        return array_values(array_filter(
            MappingUtils::reportDisplayMappings($mappings),
            fn($m) => !isset($labelToCol[MappingUtils::mappingLabel($m)])
        ));
    }

    /** 模板内字段用固定列；新增字段追加到 AF 起。 */
    public static function columnForReportField(array $mapping, array $mappings): string
    {
        $label = MappingUtils::mappingLabel($mapping);
        $labelToCol = self::templateLabelToCol();
        if (isset($labelToCol[$label])) {
            return $labelToCol[$label];
        }
        $custom = self::customReportMappings($mappings);
        foreach ($custom as $idx => $m) {
            if ((int) $m['id'] === (int) $mapping['id']) {
                return Coordinate::stringFromColumnIndex(self::APPEND_START_COLUMN + $idx);
            }
        }
        return Coordinate::stringFromColumnIndex(self::APPEND_START_COLUMN + count($custom));
    }

    /**
     * 按 FieldMapping.sort_order 构建报表字段行（日报 + 报表配置共用）。
     * @param array[] $mappings
     * @param array[]|null $values report_values 行
     * @param string[] $pendingFileCodes
     */
    public static function buildDynamicReportRows(array $mappings, ?array $values = null, array $pendingFileCodes = []): array
    {
        $pending = array_flip($pendingFileCodes);

        $byMappingId = [];
        $byLabel = [];
        $byCode = [];
        foreach ($values ?? [] as $v) {
            if (!empty($v['mapping_id'])) {
                $byMappingId[(int) $v['mapping_id']] = $v;
            }
            $byLabel[(string) $v['line_label']] = $v;
            if (!empty($v['line_code'])) {
                $byCode[(string) $v['line_code']] = $v;
            }
        }

        $rows = [];
        $ordered = MappingUtils::reportDisplayMappings($mappings);
        foreach ($ordered as $m) {
            $label = MappingUtils::mappingLabel($m);
            $code = MappingUtils::mappingLineCode($m);
            $rv = $byMappingId[(int) $m['id']] ?? $byLabel[$label] ?? $byCode[$code] ?? null;
            $isManual = MappingUtils::isManualLine($m);
            $computedDisplay = '';
            if ($rv && $rv['computed_raw_value'] !== null) {
                $fmt = ($m['format_type'] ?? '') ?: 'usd';
                $computedDisplay = Formula::formatValue((float) $rv['computed_raw_value'], $fmt);
            } elseif ($rv && empty($rv['is_overridden']) && !empty($rv['display_value'])) {
                $computedDisplay = (string) $rv['display_value'];
            }

            $configured = !empty($m['parts']) || (!empty($m['sheet_name']) && !empty($m['column_header']));
            $rows[] = [
                'col' => self::columnForReportField($m, $mappings),
                'sort_order' => (int) ($m['sort_order'] ?? 0),
                'label' => $label,
                'mapping' => $m,
                'mapping_id' => (int) $m['id'],
                'line_code' => $code,
                'is_manual' => $isManual,
                'is_formula' => MappingUtils::isFormulaLine($m),
                'is_fetch' => !$isManual && !MappingUtils::isFormulaLine($m),
                'configured' => $configured,
                'pending_file' => isset($pending[$code]),
                'format_type' => ($m['format_type'] ?? '') ?: 'usd',
                'value_id' => $rv ? (int) $rv['id'] : null,
                'is_overridden' => $rv ? (bool) ($rv['is_overridden'] ?? false) : false,
                'display_value' => $rv ? (string) ($rv['display_value'] ?? '') : '',
                'raw_value' => $rv ? $rv['raw_value'] : null,
                'computed_display' => $computedDisplay,
                'computed_raw' => $rv ? $rv['computed_raw_value'] : null,
                'expression' => $rv ? (string) ($rv['expression'] ?? '') : '',
                'editable' => (bool) $rv,
                'is_reserved' => false,
            ];
        }
        return $rows;
    }

    /** 把 report_values 列表按 report_group 分组；无分组时按 sort_order 顺序单列展示。 */
    public static function buildGrouped(array $values): array
    {
        if (!$values) {
            return [];
        }
        usort($values, fn($a, $b) => (int) ($a['sort_order'] ?? 0) <=> (int) ($b['sort_order'] ?? 0));

        $hasGroup = (bool) array_filter($values, fn($v) => !empty($v['report_group']));
        if (!$hasGroup) {
            return [[
                'title' => '报表指标',
                'metrics' => array_map(fn($v) => [
                    'label' => $v['line_label'],
                    'value' => $v['display_value'],
                    'expression' => $v['expression'],
                ], $values),
            ]];
        }

        $order = [];
        $bucket = [];
        foreach ($values as $v) {
            $title = ($v['report_group'] ?? '') ?: '其他';
            if (!isset($bucket[$title])) {
                $bucket[$title] = [];
                $order[] = $title;
            }
            $bucket[$title][] = [
                'label' => $v['line_label'],
                'value' => $v['display_value'],
                'expression' => $v['expression'],
            ];
        }
        $groups = [];
        foreach ($order as $title) {
            $groups[] = ['title' => $title, 'metrics' => $bucket[$title]];
        }
        return $groups;
    }

    public static function reportMeta(?array $dataSource, array $run): array
    {
        if ($dataSource) {
            $cfg = DsSettings::getDsConfig($dataSource);
            $meta = (array) ($cfg['meta'] ?? []);
            $meta['平台'] = $meta['平台'] ?? $dataSource['platform'];
        } else {
            $meta = [];
        }
        $meta['店铺名称'] = $meta['店铺名称'] ?? $run['store_name'];
        $meta['区域'] = $meta['区域'] ?? '';
        $meta['项目'] = $meta['项目'] ?? '';
        $meta['日期'] = $run['report_date'];
        return $meta;
    }

    private static function templatePath(?array $dataSource = null): string
    {
        $chosen = self::DAILY_TEMPLATE_NAME;
        if ($dataSource) {
            $cfg = DsSettings::getDsConfig($dataSource);
            $chosen = trim((string) ($cfg['excel_template_file'] ?? '')) ?: self::DAILY_TEMPLATE_NAME;
        }
        $path = rtrim(Config::get()->filesDir, '/\\') . DIRECTORY_SEPARATOR . $chosen;
        if (is_file($path)) {
            return $path;
        }
        $fallback = rtrim(Config::get()->filesDir, '/\\') . DIRECTORY_SEPARATOR . self::DAILY_TEMPLATE_NAME;
        if (is_file($fallback)) {
            return $fallback;
        }
        throw new \RuntimeException("未找到日报模板：{$chosen}");
    }

    /** 将模板表头行样式复制到数据行，保持与日报模板一致。 */
    private static function copyRowStyle(Worksheet $ws, int $srcRow, int $dstRow, int $maxCol): void
    {
        $srcHeight = $ws->getRowDimension($srcRow)->getRowHeight();
        $ws->getRowDimension($dstRow)->setRowHeight($srcHeight);
        for ($col = 1; $col <= $maxCol; $col++) {
            $letter = Coordinate::stringFromColumnIndex($col);
            $ws->duplicateStyle($ws->getStyle("{$letter}{$srcRow}"), "{$letter}{$dstRow}");
        }
    }

    private static function exportCellValue(mixed $value): mixed
    {
        if ($value === null) {
            return null;
        }
        if (is_int($value) || is_float($value) || is_numeric($value)) {
            return (float) $value;
        }
        return $value;
    }

    private static function writeReportValueCell(Worksheet $ws, string $coord, ?array $rv, string $label): void
    {
        if ($rv === null) {
            $ws->getCell($coord)->setValue(null);
            return;
        }
        if ($rv['raw_value'] !== null) {
            $ws->getCell($coord)->setValue(self::exportCellValue($rv['raw_value']));
            return;
        }
        if (in_array($label, self::MANUAL_EXPORT_LABELS, true) || ($rv['display_value'] ?? '') === '') {
            $ws->getCell($coord)->setValue(null);
            return;
        }
        $ws->getCell($coord)->setValue(self::exportCellValue($rv['raw_value']));
    }

    /**
     * 按 files/日报模板.xlsx 版式导出：保留前 3 行表头，在第 4 行填入数据。
     * @param array[] $values report_values 行
     * @param array[]|null $mappings
     * @return string 导出文件绝对路径
     */
    public static function exportDailyExcel(?array $dataSource, array $run, array $values, ?array $mappings = null): string
    {
        $meta = self::reportMeta($dataSource, $run);

        $template = self::templatePath($dataSource);
        $outDir = dirname(rtrim(Config::get()->uploadDir, '/\\')) . DIRECTORY_SEPARATOR . 'exports';
        @mkdir($outDir, 0777, true);
        $outPath = $outDir . DIRECTORY_SEPARATOR . sprintf('美宠日报_%s_run%d.xlsx', $meta['日期'] ?? '', (int) $run['id']);
        copy($template, $outPath);

        $spreadsheet = IOFactory::load($outPath);
        $ws = $spreadsheet->getActiveSheet();
        $styleRow = 3;
        $dataRow = self::TEMPLATE_DATA_ROW;
        $maxCol = Coordinate::columnIndexFromString($ws->getHighestColumn());

        self::copyRowStyle($ws, $styleRow, $dataRow, $maxCol);

        foreach (self::META_COLUMNS as $colLetter => $metaKey) {
            $ws->getCell("{$colLetter}{$dataRow}")->setValue($meta[$metaKey] ?? '');
        }

        $mappings = $mappings ?? [];

        $byMappingId = [];
        $byLabel = [];
        foreach ($values as $v) {
            if (!empty($v['mapping_id'])) {
                $byMappingId[(int) $v['mapping_id']] = $v;
            }
            $byLabel[(string) $v['line_label']] = $v;
        }

        $findValue = function (array $m) use ($byMappingId, $byLabel): ?array {
            $lbl = MappingUtils::mappingLabel($m);
            return $byMappingId[(int) $m['id']] ?? $byLabel[$lbl] ?? null;
        };

        $displayMappings = MappingUtils::reportDisplayMappings($mappings);

        // 1) 模板固定列：按列名写入
        foreach (self::TEMPLATE_COLUMN_LABELS as $colLetter => $label) {
            if (!$label) {
                continue;
            }
            $m = null;
            foreach ($displayMappings as $x) {
                if (MappingUtils::mappingLabel($x) === $label) {
                    $m = $x;
                    break;
                }
            }
            $rv = $m ? $findValue($m) : ($byLabel[$label] ?? null);
            self::writeReportValueCell($ws, "{$colLetter}{$dataRow}", $rv, $label);
        }

        // 2) 新增自定义字段：AF 起追加，并写表头
        $headerRow = 3;
        $styleSrcCoord = Coordinate::stringFromColumnIndex(31) . $headerRow; // AE3
        $custom = self::customReportMappings($mappings);
        if ($custom) {
            $maxCol = max($maxCol, self::APPEND_START_COLUMN + count($custom) - 1);
            self::copyRowStyle($ws, $styleRow, $dataRow, $maxCol);
        }
        foreach ($custom as $idx => $m) {
            $colNum = self::APPEND_START_COLUMN + $idx;
            $letter = Coordinate::stringFromColumnIndex($colNum);
            $label = MappingUtils::mappingLabel($m);
            $ws->getCell("{$letter}{$headerRow}")->setValue($label);
            $ws->duplicateStyle($ws->getStyle($styleSrcCoord), "{$letter}{$headerRow}");
            self::writeReportValueCell($ws, "{$letter}{$dataRow}", $findValue($m), $label);
        }

        $writer = IOFactory::createWriter($spreadsheet, 'Xlsx');
        $writer->save($outPath);
        $spreadsheet->disconnectWorksheets();
        return $outPath;
    }
}
