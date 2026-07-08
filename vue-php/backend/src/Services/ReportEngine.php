<?php

declare(strict_types=1);

namespace App\Services;

use App\Database;

/**
 * 出报引擎，与 Python 版 services/report_engine.py 对等。
 */
final class ReportEngine
{
    private static function toNumber(mixed $value): float
    {
        if ($value === null || $value === '') {
            return 0.0;
        }
        return is_numeric($value) ? (float) $value : 0.0;
    }

    /** @param string[] $aliases */
    private static function resolveColumnValue(array $rowData, string $columnHeader, array $aliases): ?float
    {
        $candidates = array_merge([$columnHeader], $aliases);
        $normalized = [];
        foreach ($rowData as $k => $v) {
            $normalized[trim((string) $k)] = $v;
        }
        foreach ($candidates as $candidate) {
            $key = trim((string) $candidate);
            if (array_key_exists($key, $normalized)) {
                return self::toNumber($normalized[$key]);
            }
        }
        return null;
    }

    /**
     * @return array{0: array<string, float>, 1: string[]} [field_values, warnings]
     */
    public static function aggregateFieldValues(int $dataSourceId, string $reportDate, string $storeName): array
    {
        $dataSource = Database::fetchOne('SELECT * FROM data_sources WHERE id = ?', [$dataSourceId]);
        $dsConfig = DsSettings::getDsConfig($dataSource);
        $dailyMode = $dataSource && $dsConfig;

        if (CatalogResolver::hasCatalog($dataSourceId)) {
            [$rows, $importFileNames] = FactProvider::loadFactRows($dataSourceId, $storeName);
            if (!$rows) {
                return [[], ["未找到 {$storeName} 的事实数据，请先运行 ETL 导入"]];
            }
        } else {
            if ($dailyMode) {
                $imports = Database::fetchAll(
                    'SELECT * FROM data_imports WHERE data_source_id = ? AND store_name = ? ORDER BY created_at DESC',
                    [$dataSourceId, $storeName]
                );
            } else {
                $imports = Database::fetchAll(
                    'SELECT * FROM data_imports WHERE data_source_id = ? AND report_date = ? AND store_name = ? ORDER BY created_at DESC',
                    [$dataSourceId, $reportDate, $storeName]
                );
            }
            if (!$imports) {
                return [[], ["未找到 {$storeName} 的导入数据"]];
            }
            $importIds = array_map(fn($i) => (int) $i['id'], $imports);
            $importFileNames = [];
            foreach ($imports as $i) {
                $importFileNames[(int) $i['id']] = (string) $i['file_name'];
            }
            $ph = implode(',', array_fill(0, count($importIds), '?'));
            $dataRows = Database::fetchAll("SELECT * FROM data_rows WHERE data_import_id IN ($ph)", $importIds);
            $rows = array_map(fn($r) => [
                'data_import_id' => (int) $r['data_import_id'],
                'sheet_name' => (string) $r['sheet_name'],
                'row_data' => Database::jsonDecode($r['row_data'], []) ?: [],
            ], $dataRows);
        }

        $context = null;
        if ($dailyMode) {
            $context = FieldAggregator::buildDailyContext($rows, $dsConfig, $reportDate);
        }

        $mappings = MappingRepo::forDataSource($dataSourceId, false);
        $fetchMappings = array_values(array_filter($mappings, fn($m) => MappingUtils::isFetchLine($m)));

        $fieldValues = [];
        $warnings = [];

        // 刷单字段来自 config.review_orders 汇总（与 Python 版 review_field_values 一致）
        if ($dailyMode) {
            $sameDayIds = $context?->sameDayRefundOrderIds;
            $fieldValues = ReviewImport::reviewFieldValues($dsConfig, $sameDayIds);
        }

        // 迭代求值以支持「复用字段」引用（与 Python 版循环收敛逻辑一致）
        for ($iter = 0; $iter <= count($fetchMappings); $iter++) {
            $changed = false;
            foreach ($fetchMappings as $mapping) {
                $code = MappingUtils::mappingLineCode($mapping);
                $display = ($mapping['label'] ?? null) ?: (($mapping['logical_field_name'] ?? null) ?: $code);
                $parts = $mapping['parts'] ?? [];
                usort($parts, fn($a, $b) => $a['sort_order'] <=> $b['sort_order']);

                if ($parts) {
                    $partValues = array_map(
                        fn($p) => FieldAggregator::resolvePartValue(
                            $p,
                            $rows,
                            $importFileNames,
                            $context,
                            $fieldValues,
                            $dataSourceId,
                        ),
                        $parts
                    );
                    $newVal = FieldAggregator::combineParts($parts, $partValues);
                    if (($fieldValues[$code] ?? null) !== $newVal) {
                        $changed = true;
                    }
                    $fieldValues[$code] = $newVal;
                    $allZero = !array_filter($partValues, fn($v) => $v != 0.0);
                    $hasRef = (bool) array_filter($parts, fn($p) => !empty($p['ref_field_code']));
                    if ($iter === 0 && $allZero && !$hasRef) {
                        $warnings[] = "字段「{$display}」所有取数规则均未匹配到数据";
                    }
                    continue;
                }

                if (!empty($mapping['sheet_name']) && !empty($mapping['column_header'])) {
                    $matchedValues = [];
                    foreach ($rows as $row) {
                        if ($row['sheet_name'] !== $mapping['sheet_name']) {
                            continue;
                        }
                        $value = self::resolveColumnValue($row['row_data'], (string) $mapping['column_header'], $mapping['aliases'] ?? []);
                        if ($value !== null) {
                            $matchedValues[] = $value;
                        }
                    }
                    if (!$matchedValues) {
                        if ($iter === 0) {
                            $warnings[] = "字段「{$display}」未取到数据";
                        }
                        $newVal = 0.0;
                    } elseif (($mapping['aggregation'] ?? '') === 'count') {
                        $newVal = (float) count($matchedValues);
                    } elseif (($mapping['aggregation'] ?? '') === 'avg') {
                        $newVal = array_sum($matchedValues) / count($matchedValues);
                    } else {
                        $newVal = array_sum($matchedValues);
                    }
                    if (($fieldValues[$code] ?? null) !== $newVal) {
                        $changed = true;
                    }
                    $fieldValues[$code] = $newVal;
                } else {
                    if (!array_key_exists($code, $fieldValues)) {
                        $fieldValues[$code] = 0.0;
                        $warnings[] = "字段「{$display}」未配置取数规则";
                    }
                }
            }
            if (!$changed) {
                break;
            }
        }

        return [$fieldValues, $warnings];
    }

    /** 仅输出已纳入报表结构的行（有排序或分组）；辅助取数字段不参与出报。 @param array[] $allLines */
    private static function reportDisplayLines(array $allLines): array
    {
        return array_values(array_filter(
            $allLines,
            fn($line) => (int) ($line['sort_order'] ?? 0) > 0 || !empty($line['report_group'])
        ));
    }

    /**
     * 为数据源生成日报。返回 run 关联数组（含 _warnings）。
     */
    public static function generateReportForDataSource(
        int $dataSourceId,
        string $reportDate,
        string $storeName,
        bool $isTest = true,
        ?int $templateId = null,
    ): array {
        [$fieldValues, $warnings] = self::aggregateFieldValues($dataSourceId, $reportDate, $storeName);

        $allLines = MappingRepo::forDataSource($dataSourceId);
        $reportLines = self::reportDisplayLines($allLines);
        if (!$reportLines) {
            throw new \RuntimeException('该数据源尚未配置报表行，请先在「报表配置」页添加');
        }

        foreach ($reportLines as $line) {
            if (MappingUtils::isManualLine($line)) {
                continue;
            }
            $expr = MappingUtils::defaultExpression($line);
            foreach (Formula::extractFieldCodes($expr) as $code) {
                if (!array_key_exists($code, $fieldValues)) {
                    $fieldValues[$code] = 0.0;
                }
            }
        }

        $status = $warnings ? 'warning' : 'success';
        $runId = Database::insert('report_runs', [
            'template_id' => $templateId,
            'data_source_id' => $dataSourceId,
            'report_date' => $reportDate,
            'store_name' => $storeName,
            'is_test' => $isTest ? 1 : 0,
            'status' => $status,
            'created_at' => Database::utcNow(),
        ]);

        foreach ($reportLines as $line) {
            $code = MappingUtils::mappingLineCode($line);
            $lbl = MappingUtils::mappingLabel($line);
            if (MappingUtils::isManualLine($line)) {
                Database::insert('report_values', [
                    'report_run_id' => $runId,
                    'mapping_id' => $line['id'],
                    'line_code' => $code,
                    'line_label' => $lbl,
                    'expression' => '',
                    'raw_value' => null,
                    'computed_raw_value' => null,
                    'display_value' => '',
                    'is_overridden' => 0,
                    'sort_order' => (int) ($line['sort_order'] ?? 0),
                    'report_group' => $line['report_group'] ?? null,
                ]);
                continue;
            }
            $expr = MappingUtils::defaultExpression($line);
            try {
                $rawValue = Formula::evaluateExpression($expr, $fieldValues);
                $display = Formula::formatValue($rawValue, ($line['format_type'] ?? '') ?: 'usd');
            } catch (FormulaError $exc) {
                $rawValue = null;
                $display = '错误: ' . $exc->getMessage();
                $status = 'error';
                Database::updateById('report_runs', $runId, ['status' => 'error']);
            }

            Database::insert('report_values', [
                'report_run_id' => $runId,
                'mapping_id' => $line['id'],
                'line_code' => $code,
                'line_label' => $lbl,
                'expression' => $expr,
                'raw_value' => $rawValue,
                'computed_raw_value' => $rawValue,
                'display_value' => $display,
                'is_overridden' => 0,
                'sort_order' => (int) ($line['sort_order'] ?? 0),
                'report_group' => $line['report_group'] ?? null,
            ]);
        }

        $run = Database::fetchOne('SELECT * FROM report_runs WHERE id = ?', [$runId]);
        $run['_warnings'] = $warnings;
        return $run;
    }

    /** 为已生成的 run 补全新增字段的 ReportValue（导出前调用）。 */
    public static function syncRunMissingValues(array $run, int $dataSourceId): int
    {
        $runId = (int) $run['id'];
        $existing = [];
        foreach (Database::fetchAll('SELECT mapping_id FROM report_values WHERE report_run_id = ?', [$runId]) as $v) {
            if ($v['mapping_id']) {
                $existing[(int) $v['mapping_id']] = true;
            }
        }
        $allLines = MappingRepo::forDataSource($dataSourceId);
        $reportLines = self::reportDisplayLines($allLines);
        $missing = array_values(array_filter($reportLines, fn($line) => !isset($existing[(int) $line['id']])));
        if (!$missing) {
            return 0;
        }

        [$fieldValues] = self::aggregateFieldValues($dataSourceId, (string) $run['report_date'], (string) $run['store_name']);
        foreach ($reportLines as $line) {
            if (!MappingUtils::isManualLine($line)) {
                $expr = MappingUtils::defaultExpression($line);
                foreach (Formula::extractFieldCodes($expr) as $code) {
                    if (!array_key_exists($code, $fieldValues)) {
                        $fieldValues[$code] = 0.0;
                    }
                }
            }
        }

        $added = 0;
        foreach ($missing as $line) {
            $code = MappingUtils::mappingLineCode($line);
            $lbl = MappingUtils::mappingLabel($line);
            if (MappingUtils::isManualLine($line)) {
                Database::insert('report_values', [
                    'report_run_id' => $runId,
                    'mapping_id' => $line['id'],
                    'line_code' => $code,
                    'line_label' => $lbl,
                    'expression' => '',
                    'raw_value' => null,
                    'computed_raw_value' => null,
                    'display_value' => '',
                    'is_overridden' => 0,
                    'sort_order' => (int) ($line['sort_order'] ?? 0),
                    'report_group' => $line['report_group'] ?? null,
                ]);
                $added++;
                continue;
            }
            $expr = MappingUtils::defaultExpression($line);
            try {
                $rawValue = Formula::evaluateExpression($expr, $fieldValues);
                $display = Formula::formatValue($rawValue, ($line['format_type'] ?? '') ?: 'usd');
            } catch (FormulaError $exc) {
                $rawValue = null;
                $display = '错误: ' . $exc->getMessage();
            }
            Database::insert('report_values', [
                'report_run_id' => $runId,
                'mapping_id' => $line['id'],
                'line_code' => $code,
                'line_label' => $lbl,
                'expression' => $expr,
                'raw_value' => $rawValue,
                'computed_raw_value' => $rawValue,
                'display_value' => $display,
                'is_overridden' => 0,
                'sort_order' => (int) ($line['sort_order'] ?? 0),
                'report_group' => $line['report_group'] ?? null,
            ]);
            $added++;
        }
        return $added;
    }

    /**
     * 兼容旧模板出报；若数据源已有报表行配置则优先走新引擎。
     * $template 为 report_templates 行或 null。
     */
    public static function generateReport(?array $template, int $dataSourceId, string $reportDate, string $storeName, bool $isTest = true): array
    {
        $hasLines = (int) Database::fetchValue(
            'SELECT COUNT(*) FROM field_mappings WHERE data_source_id = ? AND sort_order > 0',
            [$dataSourceId]
        );
        if ($hasLines) {
            return self::generateReportForDataSource(
                $dataSourceId,
                $reportDate,
                $storeName,
                $isTest,
                $template ? (int) $template['id'] : null,
            );
        }

        [$fieldValues, $warnings] = self::aggregateFieldValues($dataSourceId, $reportDate, $storeName);

        $templateId = (int) $template['id'];
        $lines = Database::fetchAll(
            'SELECT * FROM template_lines WHERE template_id = ? ORDER BY sort_order',
            [$templateId]
        );
        foreach ($lines as $line) {
            foreach (Formula::extractFieldCodes((string) $line['expression']) as $code) {
                if (!array_key_exists($code, $fieldValues)) {
                    $fieldValues[$code] = 0.0;
                }
            }
        }

        $status = $warnings ? 'warning' : 'success';
        $runId = Database::insert('report_runs', [
            'template_id' => $templateId,
            'data_source_id' => $dataSourceId,
            'report_date' => $reportDate,
            'store_name' => $storeName,
            'is_test' => $isTest ? 1 : 0,
            'status' => $status,
            'created_at' => Database::utcNow(),
        ]);

        foreach ($lines as $line) {
            try {
                $rawValue = Formula::evaluateExpression((string) $line['expression'], $fieldValues);
                $display = Formula::formatValue($rawValue, (string) $line['format_type']);
            } catch (FormulaError $exc) {
                $rawValue = null;
                $display = '错误: ' . $exc->getMessage();
                Database::updateById('report_runs', $runId, ['status' => 'error']);
            }
            Database::insert('report_values', [
                'report_run_id' => $runId,
                'line_label' => $line['label'],
                'expression' => $line['expression'],
                'raw_value' => $rawValue,
                'display_value' => $display,
                'sort_order' => (int) $line['sort_order'],
            ]);
        }

        $run = Database::fetchOne('SELECT * FROM report_runs WHERE id = ?', [$runId]);
        $run['_warnings'] = $warnings;
        return $run;
    }
}
