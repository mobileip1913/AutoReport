<?php

declare(strict_types=1);

namespace App\Controllers;

use App\Database;
use App\HttpError;
use App\Services\AccountContext;
use App\Services\ConfigExport;
use App\Services\DsSettings;
use App\Services\Formula;
use App\Services\MappingRepo;
use App\Services\MappingUtils;
use App\Services\ReportEngine;
use App\Services\ReviewImport;
use App\Services\SchemaService;
use Psr\Http\Message\ResponseInterface as Response;
use Psr\Http\Message\ServerRequestInterface as Request;

/**
 * /api 路由，与 Python 版 routers/api.py 对等（响应结构一致）。
 */
final class ApiController
{
    private function json(Response $response, mixed $data, int $status = 200): Response
    {
        $response->getBody()->write(json_encode($data, JSON_UNESCAPED_UNICODE | JSON_UNESCAPED_SLASHES));
        return $response->withHeader('Content-Type', 'application/json; charset=utf-8')->withStatus($status);
    }

    private function body(Request $request): array
    {
        return (array) $request->getParsedBody();
    }

    private function cookies(Request $request): array
    {
        return $request->getCookieParams();
    }

    // ---------- 取数规则保存辅助（与 _apply_parts / _apply_report_fields 对等） ----------

    /** @param array[] $parts */
    private function applyParts(int $mappingId, array $parts): void
    {
        Database::execute('DELETE FROM field_mapping_parts WHERE mapping_id = ?', [$mappingId]);
        foreach ($parts as $idx => $part) {
            $refCode = trim((string) ($part['ref_field_code'] ?? ''));
            if ($refCode !== '') {
                $benchmarkKeys = [];
                foreach ((array) ($part['benchmark_keys'] ?? []) as $k) {
                    $k = trim((string) $k);
                    if ($k !== '') {
                        $benchmarkKeys[] = $k;
                    }
                }
                Database::insert('field_mapping_parts', [
                    'mapping_id' => $mappingId,
                    'sort_order' => $idx,
                    'label' => $part['label'] ?? null,
                    'ref_field_code' => $refCode,
                    'sheet_name' => '',
                    'column_header' => '',
                    'aliases' => Database::jsonEncode([]),
                    'sources' => Database::jsonEncode([]),
                    'combine_op' => ($part['combine_op'] ?? '') ?: 'add',
                    'aggregation' => 'sum',
                    'dedup_keys' => Database::jsonEncode([]),
                    'benchmark_keys' => Database::jsonEncode($benchmarkKeys),
                ]);
                continue;
            }
            $sources = array_values(array_map(fn($s) => [
                'source_file_keyword' => $s['source_file_keyword'] ?? null,
                'sheet_name' => (string) ($s['sheet_name'] ?? ''),
                'column_header' => (string) ($s['column_header'] ?? ''),
                'combine_op' => ($s['combine_op'] ?? '') ?: 'add',
            ], $part['sources'] ?? []));
            $first = $sources[0] ?? null;
            $sheetName = trim((string) ($first ? $first['sheet_name'] : ($part['sheet_name'] ?? '')));
            $columnHeader = trim((string) ($first ? $first['column_header'] : ($part['column_header'] ?? '')));
            $fileKw = trim((string) (($first['source_file_keyword'] ?? null) ?? ($part['source_file_keyword'] ?? '')));

            $rowFilters = array_values(array_map(fn($f) => [
                'column' => (string) ($f['column'] ?? ''),
                'op' => ($f['op'] ?? '') ?: 'eq',
                'values' => array_values(array_map('strval', (array) ($f['values'] ?? []))),
            ], $part['row_filters'] ?? []));

            $joinKeys = [];
            foreach ((array) ($part['join_keys'] ?? []) as $k) {
                $k = trim((string) $k);
                if ($k !== '') {
                    $joinKeys[] = $k;
                }
            }
            $benchmarkKeys = [];
            foreach ((array) ($part['benchmark_keys'] ?? []) as $k) {
                $k = trim((string) $k);
                if ($k !== '') {
                    $benchmarkKeys[] = $k;
                }
            }

            Database::insert('field_mapping_parts', [
                'mapping_id' => $mappingId,
                'sort_order' => $idx,
                'label' => $part['label'] ?? null,
                'source_file_keyword' => $fileKw !== '' ? $fileKw : null,
                'sheet_name' => $sheetName,
                'column_header' => $columnHeader,
                'aliases' => Database::jsonEncode(array_values((array) ($part['aliases'] ?? []))),
                'sources' => Database::jsonEncode($sources),
                'combine_op' => ($part['combine_op'] ?? '') ?: 'add',
                'aggregation' => ($part['aggregation'] ?? '') ?: 'sum',
                'dedup_keys' => Database::jsonEncode(array_values((array) ($part['dedup_keys'] ?? []))),
                'date_filter_column' => trim((string) ($part['date_filter_column'] ?? '')) ?: null,
                'date_format' => trim((string) ($part['date_format'] ?? '')) ?: null,
                'row_filters' => Database::jsonEncode($rowFilters),
                'exclude_sample' => !empty($part['exclude_sample']) ? 1 : 0,
                'exclude_review' => !empty($part['exclude_review']) ? 1 : 0,
                'exclude_same_day_refund' => !empty($part['exclude_same_day_refund']) ? 1 : 0,
                'join_to_orders' => !empty($part['join_to_orders']) ? 1 : 0,
                'join_keys' => Database::jsonEncode($joinKeys),
                'benchmark_keys' => Database::jsonEncode($benchmarkKeys),
                'only_sample' => !empty($part['only_sample']) ? 1 : 0,
            ]);
        }
    }

    private function applyReportFields(array $mapping, array $body, int $dsId): void
    {
        $patch = [];
        if (array_key_exists('label', $body) && $body['label'] !== null) {
            $label = trim((string) $body['label']);
            $patch['label'] = $label !== '' ? $label : ($mapping['label'] ?? null);
        }
        if (array_key_exists('line_code', $body) && $body['line_code'] !== null) {
            $lineCode = trim((string) $body['line_code']);
            $patch['line_code'] = $lineCode !== '' ? $lineCode : ($mapping['line_code'] ?? null);
        }
        if (!empty($body['line_type'])) {
            $patch['line_type'] = (string) $body['line_type'];
        }
        if (array_key_exists('report_group', $body) && $body['report_group'] !== null) {
            $group = trim((string) $body['report_group']);
            $patch['report_group'] = $group !== '' ? $group : null;
        }
        if (array_key_exists('sort_order', $body) && $body['sort_order'] !== null) {
            $patch['sort_order'] = (int) $body['sort_order'];
        }
        if (array_key_exists('expression', $body) && $body['expression'] !== null) {
            $expr = trim((string) $body['expression']);
            $patch['expression'] = $expr !== '' ? $expr : null;
        }
        if (!empty($body['format_type'])) {
            $patch['format_type'] = (string) $body['format_type'];
        }
        $patch['is_highlight'] = !empty($body['is_highlight']) ? 1 : 0;
        if (array_key_exists('description', $body) && $body['description'] !== null) {
            $patch['description'] = (string) $body['description'];
        }

        $effectiveLineCode = $patch['line_code'] ?? $mapping['line_code'] ?? null;
        if (!$effectiveLineCode) {
            $used = [];
            foreach (MappingRepo::forDataSource($dsId, false) as $x) {
                if ((int) $x['id'] === (int) $mapping['id']) {
                    continue;
                }
                $c = MappingUtils::mappingLineCode($x);
                if ($c !== '') {
                    $used[$c] = true;
                }
            }
            $base = ($patch['label'] ?? $mapping['label'] ?? null) ?: 'line';
            $patch['line_code'] = MappingUtils::slugLineCode((string) $base, $used);
        }
        Database::updateById('field_mappings', (int) $mapping['id'], $patch);
    }

    // ---------- 端点 ----------

    public function importExcel(Request $request, Response $response): Response
    {
        throw new HttpError(410, 'Web Excel 导入已停用。请使用离线 ETL：python scripts/import_meichong.py');
    }

    public function generate(Request $request, Response $response): Response
    {
        $body = $this->body($request);
        $dataSourceId = (int) ($body['data_source_id'] ?? 0);
        $reportDate = (string) ($body['report_date'] ?? '');
        $storeName = (string) ($body['store_name'] ?? '');
        $templateId = !empty($body['template_id']) ? (int) $body['template_id'] : null;
        $isTest = filter_var($body['is_test'] ?? false, FILTER_VALIDATE_BOOL);

        // 与 FastAPI Form(...) 必填行为一致
        if ($dataSourceId <= 0 || $reportDate === '' || $storeName === '') {
            throw new HttpError(422, 'data_source_id / report_date / store_name 均为必填');
        }

        if ($templateId) {
            $template = Database::fetchOne('SELECT * FROM report_templates WHERE id = ?', [$templateId]);
            if (!$template) {
                throw new HttpError(404, '模板不存在');
            }
            if (!$isTest && strtolower((string) $template['status']) !== 'published') {
                throw new HttpError(400, '正式生成需使用已发布模板');
            }
            $run = ReportEngine::generateReport($template, $dataSourceId, $reportDate, $storeName, $isTest);
        } else {
            $run = ReportEngine::generateReportForDataSource($dataSourceId, $reportDate, $storeName, $isTest);
        }
        return $this->json($response, ['run_id' => (int) $run['id'], 'status' => $run['status']]);
    }

    public function listReportLines(Request $request, Response $response, array $args): Response
    {
        $dataSourceId = (int) $args['data_source_id'];
        AccountContext::assertDataSourceAccess($this->cookies($request), $dataSourceId);
        $ds = Database::fetchOne('SELECT * FROM data_sources WHERE id = ?', [$dataSourceId]);
        if (!$ds) {
            throw new HttpError(404, '数据源不存在');
        }
        $rows = MappingRepo::forDataSource($dataSourceId);
        return $this->json($response, [
            'data_source_id' => $dataSourceId,
            'lines' => array_map(fn($m) => MappingRepo::serialize($m), $rows),
        ]);
    }

    public function mappedFields(Request $request, Response $response, array $args): Response
    {
        $dataSourceId = (int) $args['data_source_id'];
        AccountContext::assertDataSourceAccess($this->cookies($request), $dataSourceId);
        $exclude = $request->getQueryParams()['exclude'] ?? null;

        $fields = [];
        foreach (MappingRepo::forDataSource($dataSourceId) as $m) {
            if (MappingUtils::isFormulaLine($m) || MappingUtils::isManualLine($m)) {
                continue;
            }
            $code = MappingUtils::mappingLineCode($m);
            if ($exclude && $code === $exclude) {
                continue;
            }
            $fields[] = [
                'code' => $code,
                'name' => MappingUtils::mappingLabel($m),
                'mapping_id' => (int) $m['id'],
                'configured' => !empty($m['parts']) || (!empty($m['sheet_name']) && !empty($m['column_header'])),
            ];
        }
        return $this->json($response, ['data_source_id' => $dataSourceId, 'fields' => $fields]);
    }

    public function catalogTree(Request $request, Response $response, array $args): Response
    {
        $dataSourceId = (int) $args['data_source_id'];
        AccountContext::assertDataSourceAccess($this->cookies($request), $dataSourceId);
        $ds = Database::fetchOne('SELECT * FROM data_sources WHERE id = ?', [$dataSourceId]);
        if (!$ds) {
            throw new HttpError(404, '数据源不存在');
        }
        return $this->json($response, array_merge(
            ['data_source_id' => $dataSourceId],
            SchemaService::buildFullSchemaSnapshot($ds)
        ));
    }

    public function schema(Request $request, Response $response, array $args): Response
    {
        $dataSourceId = (int) $args['data_source_id'];
        AccountContext::assertDataSourceAccess($this->cookies($request), $dataSourceId);
        $ds = Database::fetchOne('SELECT * FROM data_sources WHERE id = ?', [$dataSourceId]);
        if (!$ds) {
            throw new HttpError(404, '数据源不存在');
        }
        $q = $request->getQueryParams();
        return $this->json($response, array_merge(
            ['data_source_id' => $dataSourceId],
            SchemaService::querySchema($ds, $q['file'] ?? null, $q['sheet'] ?? null)
        ));
    }

    public function getMapping(Request $request, Response $response, array $args): Response
    {
        $mapping = MappingRepo::byId((int) $args['mapping_id']);
        if (!$mapping) {
            throw new HttpError(404, '映射不存在');
        }
        AccountContext::assertMappingAccess($this->cookies($request), $mapping);
        return $this->json($response, MappingRepo::serialize($mapping));
    }

    public function saveMapping(Request $request, Response $response, array $args): Response
    {
        $mappingId = (int) $args['mapping_id'];
        $body = $this->body($request);
        $mapping = MappingRepo::byId($mappingId);
        if (!$mapping) {
            throw new HttpError(404, '映射不存在');
        }
        AccountContext::assertMappingAccess($this->cookies($request), $mapping);
        if (MappingUtils::isFormulaLine($mapping) || strtolower((string) ($body['line_type'] ?? '')) === 'formula') {
            throw new HttpError(400, '公式行请使用 /api/formula-lines 接口');
        }
        if (empty($body['parts'])) {
            throw new HttpError(400, '至少配置一条取数规则');
        }
        $this->applyReportFields($mapping, $body, (int) $mapping['data_source_id']);
        Database::updateById('field_mappings', $mappingId, ['line_type' => 'fetch']);
        $this->applyParts($mappingId, $body['parts']);
        return $this->json($response, MappingRepo::serialize(MappingRepo::byId($mappingId)));
    }

    public function createMapping(Request $request, Response $response): Response
    {
        $body = $this->body($request);
        $dataSourceId = (int) ($body['data_source_id'] ?? 0);
        AccountContext::assertDataSourceAccess($this->cookies($request), $dataSourceId);
        if (strtolower((string) (($body['line_type'] ?? '') ?: 'fetch')) === 'formula') {
            throw new HttpError(400, '公式行请使用 POST /api/formula-lines');
        }
        if (empty($body['parts'])) {
            throw new HttpError(400, '至少配置一条取数规则');
        }

        $lineCode = trim((string) ($body['line_code'] ?? ''));
        $logicalFieldId = !empty($body['logical_field_id']) ? (int) $body['logical_field_id'] : null;
        if ($lineCode === '' && $logicalFieldId) {
            $lf = Database::fetchOne('SELECT * FROM logical_fields WHERE id = ?', [$logicalFieldId]);
            $lineCode = $lf ? (string) $lf['code'] : '';
        }
        if ($lineCode !== '') {
            $exists = Database::fetchOne(
                'SELECT id FROM field_mappings WHERE data_source_id = ? AND line_code = ?',
                [$dataSourceId, $lineCode]
            );
            if ($exists) {
                throw new HttpError(400, "line_code {$lineCode} 已存在");
            }
        }

        $mappingId = Database::insert('field_mappings', [
            'data_source_id' => $dataSourceId,
            'logical_field_id' => $logicalFieldId,
            'line_type' => 'fetch',
            'sort_order' => 0,
            'is_highlight' => 0,
            'aggregation' => 'sum',
            'aliases' => Database::jsonEncode([]),
        ]);
        $mapping = MappingRepo::byId($mappingId);
        if ($lineCode !== '') {
            $body['line_code'] = $lineCode;
        }
        $this->applyReportFields($mapping, $body, $dataSourceId);
        $this->applyParts($mappingId, $body['parts']);
        return $this->json($response, MappingRepo::serialize(MappingRepo::byId($mappingId)));
    }

    public function createFormulaLine(Request $request, Response $response): Response
    {
        $body = $this->body($request);
        $dataSourceId = (int) ($body['data_source_id'] ?? 0);
        AccountContext::assertDataSourceAccess($this->cookies($request), $dataSourceId);
        $ds = Database::fetchOne('SELECT * FROM data_sources WHERE id = ?', [$dataSourceId]);
        if (!$ds) {
            throw new HttpError(404, '数据源不存在');
        }
        $lineCode = trim((string) ($body['line_code'] ?? ''));
        if ($lineCode === '') {
            $used = [];
            foreach (MappingRepo::forDataSource($dataSourceId, false) as $m) {
                $used[MappingUtils::mappingLineCode($m)] = true;
            }
            $lineCode = MappingUtils::slugLineCode((string) ($body['label'] ?? ''), $used);
        }
        $exists = Database::fetchOne(
            'SELECT id FROM field_mappings WHERE data_source_id = ? AND line_code = ?',
            [$dataSourceId, $lineCode]
        );
        if ($exists) {
            throw new HttpError(400, "line_code {$lineCode} 已存在");
        }

        $mappingId = Database::insert('field_mappings', [
            'data_source_id' => $dataSourceId,
            'line_type' => 'formula',
            'label' => trim((string) ($body['label'] ?? '')),
            'line_code' => $lineCode,
            'report_group' => trim((string) ($body['report_group'] ?? '')) ?: null,
            'sort_order' => (int) ($body['sort_order'] ?? 0),
            'expression' => trim((string) ($body['expression'] ?? '')),
            'format_type' => ($body['format_type'] ?? '') ?: 'usd',
            'is_highlight' => !empty($body['is_highlight']) ? 1 : 0,
            'description' => $body['description'] ?? null,
            'aggregation' => 'sum',
            'aliases' => Database::jsonEncode([]),
        ]);
        return $this->json($response, MappingRepo::serialize(MappingRepo::byId($mappingId)));
    }

    public function saveFormulaLine(Request $request, Response $response, array $args): Response
    {
        $mappingId = (int) $args['mapping_id'];
        $body = $this->body($request);
        $mapping = MappingRepo::byId($mappingId);
        if (!$mapping) {
            throw new HttpError(404, '公式行不存在');
        }
        AccountContext::assertMappingAccess($this->cookies($request), $mapping);
        $patch = [
            'line_type' => 'formula',
            'label' => trim((string) ($body['label'] ?? '')),
            'report_group' => trim((string) ($body['report_group'] ?? '')) ?: null,
            'sort_order' => (int) ($body['sort_order'] ?? 0),
            'expression' => trim((string) ($body['expression'] ?? '')),
            'format_type' => ($body['format_type'] ?? '') ?: 'usd',
            'is_highlight' => !empty($body['is_highlight']) ? 1 : 0,
            'description' => $body['description'] ?? null,
        ];
        if (!empty($body['line_code'])) {
            $patch['line_code'] = trim((string) $body['line_code']);
        }
        Database::updateById('field_mappings', $mappingId, $patch);
        return $this->json($response, MappingRepo::serialize(MappingRepo::byId($mappingId)));
    }

    public function deleteMapping(Request $request, Response $response, array $args): Response
    {
        $mappingId = (int) $args['mapping_id'];
        $mapping = MappingRepo::byId($mappingId);
        if (!$mapping) {
            throw new HttpError(404, '映射不存在');
        }
        AccountContext::assertMappingAccess($this->cookies($request), $mapping);
        Database::execute('DELETE FROM field_mapping_parts WHERE mapping_id = ?', [$mappingId]);
        Database::execute('DELETE FROM field_mappings WHERE id = ?', [$mappingId]);
        return $this->json($response, ['status' => 'deleted']);
    }

    public function quickAddReportField(Request $request, Response $response, array $args): Response
    {
        $dataSourceId = (int) $args['data_source_id'];
        $body = $this->body($request);
        AccountContext::assertDataSourceAccess($this->cookies($request), $dataSourceId);
        $label = trim((string) ($body['label'] ?? ''));
        if ($label === '') {
            throw new HttpError(400, '请填写字段名称');
        }

        $used = [];
        foreach (MappingRepo::forDataSource($dataSourceId, false) as $m) {
            $used[MappingUtils::mappingLineCode($m)] = true;
        }
        $maxSort = (int) (Database::fetchValue(
            'SELECT sort_order FROM field_mappings WHERE data_source_id = ? ORDER BY sort_order DESC LIMIT 1',
            [$dataSourceId]
        ) ?? 0);

        $mappingId = Database::insert('field_mappings', [
            'data_source_id' => $dataSourceId,
            'line_type' => 'fetch',
            'label' => $label,
            'line_code' => MappingUtils::slugLineCode($label, $used),
            'sort_order' => $maxSort + 10,
            'report_group' => '报表字段',
            'format_type' => ($body['format_type'] ?? '') ?: 'usd',
            'is_highlight' => 0,
            'aggregation' => 'sum',
            'aliases' => Database::jsonEncode([]),
        ]);
        $mapping = MappingRepo::byId($mappingId);

        if (!empty($body['run_id'])) {
            $run = Database::fetchOne('SELECT * FROM report_runs WHERE id = ?', [(int) $body['run_id']]);
            if ($run && ((int) ($run['data_source_id'] ?? 0) === $dataSourceId || !$run['data_source_id'])) {
                $fmt = ($mapping['format_type'] ?? '') ?: 'usd';
                Database::insert('report_values', [
                    'report_run_id' => (int) $run['id'],
                    'mapping_id' => $mappingId,
                    'line_code' => $mapping['line_code'],
                    'line_label' => $label,
                    'expression' => MappingUtils::defaultExpression($mapping),
                    'raw_value' => 0.0,
                    'computed_raw_value' => 0.0,
                    'display_value' => Formula::formatValue(0.0, $fmt),
                    'is_overridden' => 0,
                    'sort_order' => (int) ($mapping['sort_order'] ?? 0),
                    'report_group' => $mapping['report_group'] ?? null,
                ]);
            }
        }

        return $this->json($response, MappingRepo::serialize($mapping));
    }

    public function reorderReportFields(Request $request, Response $response, array $args): Response
    {
        $dataSourceId = (int) $args['data_source_id'];
        $body = $this->body($request);
        AccountContext::assertDataSourceAccess($this->cookies($request), $dataSourceId);
        $mappingIds = array_map('intval', (array) ($body['mapping_ids'] ?? []));
        if (!$mappingIds) {
            throw new HttpError(400, '排序列表为空');
        }

        $byId = [];
        foreach (Database::fetchAll('SELECT id FROM field_mappings WHERE data_source_id = ?', [$dataSourceId]) as $m) {
            $byId[(int) $m['id']] = true;
        }
        foreach ($mappingIds as $i => $mid) {
            if (!isset($byId[$mid])) {
                throw new HttpError(400, "字段 {$mid} 不存在");
            }
            Database::updateById('field_mappings', $mid, ['sort_order' => ($i + 1) * 10]);
        }
        return $this->json($response, ['status' => 'ok', 'count' => count($mappingIds)]);
    }

    public function patchMappingLabel(Request $request, Response $response, array $args): Response
    {
        $mappingId = (int) $args['mapping_id'];
        $body = $this->body($request);
        $mapping = MappingRepo::byId($mappingId);
        if (!$mapping) {
            throw new HttpError(404, '映射不存在');
        }
        AccountContext::assertMappingAccess($this->cookies($request), $mapping);
        $label = trim((string) ($body['label'] ?? ''));
        if ($label === '') {
            throw new HttpError(400, '名称不能为空');
        }
        Database::updateById('field_mappings', $mappingId, ['label' => $label]);
        if (!empty($body['run_id'])) {
            Database::execute(
                'UPDATE report_values SET line_label = ? WHERE report_run_id = ? AND mapping_id = ?',
                [$label, (int) $body['run_id'], $mappingId]
            );
        }
        $mapping = MappingRepo::byId($mappingId);
        return $this->json($response, [
            'id' => (int) $mapping['id'],
            'label' => $mapping['label'],
            'line_code' => MappingUtils::mappingLineCode($mapping),
        ]);
    }

    public function patchReportValue(Request $request, Response $response, array $args): Response
    {
        $runId = (int) $args['run_id'];
        $valueId = (int) $args['value_id'];
        $body = $this->body($request);

        $run = Database::fetchOne('SELECT * FROM report_runs WHERE id = ?', [$runId]);
        if (!$run) {
            throw new HttpError(404, '报表不存在');
        }
        if (!empty($run['data_source_id'])) {
            AccountContext::assertDataSourceAccess($this->cookies($request), (int) $run['data_source_id']);
        }

        $rv = Database::fetchOne(
            'SELECT * FROM report_values WHERE id = ? AND report_run_id = ?',
            [$valueId, $runId]
        );
        if (!$rv) {
            throw new HttpError(404, '字段不存在');
        }

        $mapping = null;
        if (!empty($rv['mapping_id'])) {
            $mapping = MappingRepo::byId((int) $rv['mapping_id']);
        }
        $fmt = ($mapping ? ($mapping['format_type'] ?? null) : 'usd') ?: 'usd';
        $isManual = $mapping
            ? MappingUtils::isManualLine($mapping)
            : in_array((string) $rv['line_label'], ['利润', '总利润', '利润(估算)', '总利润(估算)'], true);

        $clearOverride = !empty($body['clear_override']);
        $rawValueInput = array_key_exists('raw_value', $body) ? $body['raw_value'] : null;

        $patch = [];
        if ($clearOverride) {
            if ($rv['computed_raw_value'] !== null) {
                $patch['raw_value'] = (float) $rv['computed_raw_value'];
                $patch['display_value'] = Formula::formatValue((float) $rv['computed_raw_value'], $fmt);
            } else {
                $patch['raw_value'] = null;
                $patch['display_value'] = '';
            }
            $patch['is_overridden'] = 0;
        } elseif ($rawValueInput !== null) {
            $rawValue = (float) $rawValueInput;
            $patch['raw_value'] = $rawValue;
            $patch['display_value'] = Formula::formatValue($rawValue, $fmt);
            $computed = $rv['computed_raw_value'];
            if ($isManual) {
                $patch['is_overridden'] = 0;
            } else {
                $patch['is_overridden'] = ($computed === null || abs((float) $computed - $rawValue) > 1e-9) ? 1 : 0;
            }
        } else {
            $patch['raw_value'] = null;
            $patch['display_value'] = '';
            $patch['is_overridden'] = $isManual ? 0 : ($rv['computed_raw_value'] !== null ? 1 : 0);
        }

        Database::updateById('report_values', $valueId, $patch);
        $rv = Database::fetchOne('SELECT * FROM report_values WHERE id = ?', [$valueId]);
        return $this->json($response, [
            'id' => (int) $rv['id'],
            'raw_value' => $rv['raw_value'] !== null ? (float) $rv['raw_value'] : null,
            'display_value' => $rv['display_value'],
            'is_overridden' => (bool) $rv['is_overridden'],
            'computed_display' => $rv['computed_raw_value'] !== null
                ? Formula::formatValue((float) $rv['computed_raw_value'], $fmt)
                : '',
        ]);
    }

    public function getDataSourceSettings(Request $request, Response $response, array $args): Response
    {
        $dataSourceId = (int) $args['data_source_id'];
        AccountContext::assertDataSourceAccess($this->cookies($request), $dataSourceId);
        $ds = Database::fetchOne('SELECT * FROM data_sources WHERE id = ?', [$dataSourceId]);
        if (!$ds) {
            throw new HttpError(404, '数据源不存在');
        }
        return $this->json($response, DsSettings::serializeDsSettings($ds));
    }

    public function updateDataSourceSettings(Request $request, Response $response, array $args): Response
    {
        $dataSourceId = (int) $args['data_source_id'];
        $body = $this->body($request);
        AccountContext::assertDataSourceAccess($this->cookies($request), $dataSourceId);
        $ds = Database::fetchOne('SELECT * FROM data_sources WHERE id = ?', [$dataSourceId]);
        if (!$ds) {
            throw new HttpError(404, '数据源不存在');
        }
        DsSettings::saveDsConfig($ds, $body);
        $ds = Database::fetchOne('SELECT * FROM data_sources WHERE id = ?', [$dataSourceId]);
        return $this->json($response, DsSettings::serializeDsSettings($ds));
    }

    public function exportDataSourceConfig(Request $request, Response $response, array $args): Response
    {
        $dataSourceId = (int) $args['data_source_id'];
        $query = $request->getQueryParams();
        $includeReviewOrders = !isset($query['include_review_orders'])
            || filter_var($query['include_review_orders'], FILTER_VALIDATE_BOOL, FILTER_NULL_ON_FAILURE) !== false;
        AccountContext::assertDataSourceAccess($this->cookies($request), $dataSourceId);
        $ds = Database::fetchOne('SELECT * FROM data_sources WHERE id = ?', [$dataSourceId]);
        if (!$ds) {
            throw new HttpError(404, '数据源不存在');
        }
        $bundle = ConfigExport::buildConfigExport($ds, $includeReviewOrders);
        $content = json_encode($bundle, JSON_UNESCAPED_UNICODE | JSON_PRETTY_PRINT);
        $filename = ConfigExport::exportFilename($ds);
        $response->getBody()->write($content);
        return $response
            ->withHeader('Content-Type', 'application/json; charset=utf-8')
            ->withHeader('Content-Disposition', 'attachment; filename="' . $filename . '"');
    }

    public function downloadReviewTemplate(Request $request, Response $response, array $args): Response
    {
        $dataSourceId = (int) $args['data_source_id'];
        AccountContext::assertDataSourceAccess($this->cookies($request), $dataSourceId);
        $content = ReviewImport::buildReviewTemplateBytes();
        $response->getBody()->write($content);
        $filename = rawurlencode('刷单清单模板.xlsx');
        return $response
            ->withHeader('Content-Type', 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
            ->withHeader('Content-Disposition', "attachment; filename*=UTF-8''{$filename}");
    }

    public function importReviewOrders(Request $request, Response $response, array $args): Response
    {
        $dataSourceId = (int) $args['data_source_id'];
        AccountContext::assertDataSourceAccess($this->cookies($request), $dataSourceId);
        $ds = Database::fetchOne('SELECT * FROM data_sources WHERE id = ?', [$dataSourceId]);
        if (!$ds) {
            throw new HttpError(404, '数据源不存在');
        }
        $files = $request->getUploadedFiles();
        $file = $files['file'] ?? null;
        if (!$file || $file->getError() !== UPLOAD_ERR_OK) {
            throw new HttpError(400, '缺少上传文件');
        }
        $content = (string) $file->getStream();
        $result = ReviewImport::importReviewOrders($ds, $content, true);
        if (empty($result['ok'])) {
            throw new HttpError(400, implode('; ', $result['errors'] ?? ['导入失败']));
        }
        return $this->json($response, $result);
    }
}
