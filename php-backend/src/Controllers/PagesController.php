<?php

declare(strict_types=1);

namespace App\Controllers;

use App\Database;
use App\HttpError;
use App\Services\AccountContext;
use App\Services\DailyReport;
use App\Services\DsSettings;
use App\Services\MappingRepo;
use App\Services\MappingUtils;
use App\Services\MeichongRules;
use App\Services\ReportEngine;
use App\Services\SchemaService;
use App\Services\SkuExport;
use App\Views;
use Psr\Http\Message\ResponseInterface as Response;
use Psr\Http\Message\ServerRequestInterface as Request;

/**
 * 页面路由，与 Python 版 routers/pages.py 对等。
 */
final class PagesController
{
    private function render(string $name, Request $request, array $ctx = []): string
    {
        $cookies = $request->getCookieParams();
        return Views::render($name, array_merge(
            ['path' => $request->getUri()->getPath()],
            AccountContext::pageContext($cookies),
            $ctx
        ));
    }

    private function html(Response $response, string $body): Response
    {
        $response->getBody()->write($body);
        return $response->withHeader('Content-Type', 'text/html; charset=utf-8');
    }

    private function redirect(Response $response, string $url, int $status = 303): Response
    {
        return $response->withHeader('Location', $url)->withStatus($status);
    }

    private function withCookie(Response $response, string $name, string $value, int $maxAge): Response
    {
        $cookie = sprintf('%s=%s; Max-Age=%d; Path=/; HttpOnly; SameSite=Lax', $name, urlencode($value), $maxAge);
        return $response->withAddedHeader('Set-Cookie', $cookie);
    }

    public function switchAccount(Request $request, Response $response): Response
    {
        $body = (array) $request->getParsedBody();
        $accountId = (int) ($body['account_id'] ?? 0);
        $nextUrl = (string) ($body['next_url'] ?? '/mappings');

        $account = Database::fetchOne('SELECT * FROM accounts WHERE id = ?', [$accountId]);
        if (!$account) {
            throw new HttpError(404, '账号不存在');
        }
        $stores = AccountContext::storesForAccount($accountId);
        $target = str_starts_with($nextUrl, '/') ? $nextUrl : '/mappings';
        $resp = $this->redirect($response, $target);
        $resp = $this->withCookie($resp, AccountContext::ACCOUNT_COOKIE, (string) $accountId, 60 * 60 * 24 * 30);
        if ($stores) {
            $resp = $this->withCookie($resp, AccountContext::STORE_COOKIE, (string) $stores[0]['id'], 60 * 60 * 24 * 30);
        }
        return $resp;
    }

    public function switchStore(Request $request, Response $response): Response
    {
        $body = (array) $request->getParsedBody();
        $storeId = (int) ($body['store_id'] ?? 0);
        $nextUrl = (string) ($body['next_url'] ?? '/mappings');

        $account = AccountContext::resolveCurrentAccount($request->getCookieParams());
        $store = Database::fetchOne(
            'SELECT s.* FROM stores s JOIN account_stores ast ON ast.store_id = s.id
             WHERE s.id = ? AND ast.account_id = ?',
            [$storeId, (int) $account['id']]
        );
        if (!$store) {
            throw new HttpError(403, '当前账号无权访问该店铺');
        }
        $target = str_starts_with($nextUrl, '/') ? $nextUrl : '/mappings';
        $resp = $this->redirect($response, $target);
        return $this->withCookie($resp, AccountContext::STORE_COOKIE, (string) $storeId, 60 * 60 * 24 * 30);
    }

    public function dashboard(Request $request, Response $response): Response
    {
        $templatesList = Database::fetchAll('SELECT * FROM report_templates ORDER BY updated_at DESC');
        foreach ($templatesList as &$t) {
            $t['status'] = strtolower((string) ($t['status'] ?? 'draft'));
        }
        $recentRuns = Database::fetchAll('SELECT * FROM report_runs ORDER BY created_at DESC LIMIT 8');
        $dataSources = Database::fetchAll('SELECT * FROM data_sources');
        return $this->html($response, $this->render('dashboard.html.twig', $request, [
            'templates_list' => $templatesList,
            'recent_runs' => $recentRuns,
            'data_sources' => $dataSources,
        ]));
    }

    public function templatesRedirect(Request $request, Response $response): Response
    {
        return $this->redirect($response, '/mappings');
    }

    public function testTemplate(Request $request, Response $response, array $args): Response
    {
        $templateId = (int) $args['template_id'];
        $body = (array) $request->getParsedBody();
        $template = Database::fetchOne('SELECT * FROM report_templates WHERE id = ?', [$templateId]);
        if (!$template) {
            throw new HttpError(404, '模板不存在');
        }
        ReportEngine::generateReport(
            $template,
            (int) ($body['data_source_id'] ?? 0),
            (string) ($body['report_date'] ?? ''),
            (string) ($body['store_name'] ?? ''),
            true
        );
        return $this->redirect($response, "/templates/{$templateId}?tested=1");
    }

    public function publishTemplate(Request $request, Response $response, array $args): Response
    {
        $templateId = (int) $args['template_id'];
        $template = Database::fetchOne('SELECT * FROM report_templates WHERE id = ?', [$templateId]);
        if (!$template) {
            throw new HttpError(404, '模板不存在');
        }
        Database::updateById('report_templates', $templateId, [
            'status' => 'PUBLISHED',
            'published_at' => Database::utcNow(),
            'version' => (int) $template['version'] + 1,
        ]);
        return $this->redirect($response, "/templates/{$templateId}?published=1");
    }

    public function unpublishTemplate(Request $request, Response $response, array $args): Response
    {
        $templateId = (int) $args['template_id'];
        $template = Database::fetchOne('SELECT * FROM report_templates WHERE id = ?', [$templateId]);
        if (!$template) {
            throw new HttpError(404, '模板不存在');
        }
        Database::updateById('report_templates', $templateId, ['status' => 'DRAFT']);
        return $this->redirect($response, "/templates/{$templateId}");
    }

    public function mappings(Request $request, Response $response): Response
    {
        $cookies = $request->getCookieParams();
        $ctx = AccountContext::pageContext($cookies);
        $currentStore = $ctx['current_store'];
        $accessibleStores = $ctx['accessible_stores'];
        $dataSources = $currentStore && !empty($currentStore['data_source'])
            ? [$currentStore['data_source']]
            : $ctx['accessible_data_sources'];

        $storeByDsId = [];
        foreach ($accessibleStores as $store) {
            if (!empty($store['data_source_id'])) {
                $storeByDsId[(int) $store['data_source_id']] = $store;
            }
        }

        $dsIds = array_map(fn($ds) => (int) $ds['id'], $dataSources);
        $mappings = MappingRepo::forDataSources($dsIds ?: [0]);
        $fields = Database::fetchAll('SELECT * FROM logical_fields');
        $meta = SchemaService::getAllMeta($dataSources);

        $reuseFields = [];
        foreach ($dataSources as $ds) {
            $dsId = (int) $ds['id'];
            $reuseFields[$dsId] = [];
            foreach ($mappings as $m) {
                if ((int) $m['data_source_id'] !== $dsId
                    || MappingUtils::isFormulaLine($m)
                    || MappingUtils::isManualLine($m)) {
                    continue;
                }
                $reuseFields[$dsId][] = [
                    'code' => MappingUtils::mappingLineCode($m),
                    'name' => MappingUtils::mappingLabel($m),
                    'mapping_id' => (int) $m['id'],
                    'configured' => !empty($m['parts']) || (!empty($m['sheet_name']) && !empty($m['column_header'])),
                ];
            }
        }

        $grouped = [];
        $groupTitles = [];
        $auxiliary = [];
        $excelConfig = [];
        foreach ($dataSources as $ds) {
            $dsId = (int) $ds['id'];
            $grouped[$dsId] = [];
            $groupTitles[$dsId] = [];
            $auxiliary[$dsId] = [];
            $excelConfig[$dsId] = [];
        }
        foreach ($mappings as $m) {
            $dsId = (int) $m['data_source_id'];
            $item = [
                'mapping' => $m,
                'is_formula' => MappingUtils::isFormulaLine($m),
                'is_manual' => MappingUtils::isManualLine($m),
                'label' => MappingUtils::mappingLabel($m),
                'line_code' => MappingUtils::mappingLineCode($m),
            ];
            if ((int) ($m['sort_order'] ?? 0) <= 0 && empty($m['report_group'])) {
                $auxiliary[$dsId][] = $item;
                continue;
            }
            $title = ($m['report_group'] ?? '') ?: '未分组';
            if (!in_array($title, $groupTitles[$dsId] ?? [], true)) {
                $groupTitles[$dsId][] = $title;
            }
            $item['group'] = $title;
            $grouped[$dsId][] = $item;
        }

        $dsSettings = [];
        foreach ($dataSources as $ds) {
            $dsId = (int) $ds['id'];
            $dsMappings = array_values(array_filter($mappings, fn($m) => (int) $m['data_source_id'] === $dsId));
            $excelConfig[$dsId] = DailyReport::buildDynamicReportRows($dsMappings, null, MeichongRules::PENDING_FILE_CODES);
            $dsSettings[$dsId] = DsSettings::serializeDsSettings($ds);
        }

        return $this->html($response, $this->render('mappings.html.twig', $request, [
            'mappings' => $mappings,
            'grouped' => $grouped,
            'group_titles' => $groupTitles,
            'auxiliary' => $auxiliary,
            'excel_config' => $excelConfig,
            'fields' => $fields,
            'data_sources' => $dataSources,
            'accessible_stores' => $accessibleStores,
            'store_by_ds_id' => $storeByDsId,
            'excel_templates' => DailyReport::listExcelTemplates(),
            'meta_json' => json_encode($meta, JSON_UNESCAPED_UNICODE),
            'reuse_fields_json' => json_encode($reuseFields, JSON_UNESCAPED_UNICODE),
            'pending_file_codes' => MeichongRules::PENDING_FILE_CODES,
            'ds_settings_json' => json_encode($dsSettings, JSON_UNESCAPED_UNICODE),
            'ds_settings' => $dsSettings,
        ]));
    }

    public function logs(Request $request, Response $response): Response
    {
        return $this->redirect($response, '/mappings');
    }

    public function reports(Request $request, Response $response): Response
    {
        return $this->redirect($response, '/daily');
    }

    public function reportDetail(Request $request, Response $response, array $args): Response
    {
        $runId = (int) $args['run_id'];
        return $this->redirect($response, '/daily?run_id=' . $runId);
    }

    public function daily(Request $request, Response $response): Response
    {
        $cookies = $request->getCookieParams();
        $query = $request->getQueryParams();
        $runId = isset($query['run_id']) && ctype_digit((string) $query['run_id']) ? (int) $query['run_id'] : null;

        $ctx = AccountContext::pageContext($cookies);
        $dailySources = array_values(array_filter(
            $ctx['accessible_data_sources'],
            fn($ds) => !empty(DsSettings::getDsConfig($ds))
        ));

        $template = Database::fetchOne(
            'SELECT * FROM report_templates WHERE name = ?',
            [MeichongRules::MEICHONG_TEMPLATE_NAME]
        );

        $run = null;
        $meta = null;
        $activeDsId = null;
        $metaJson = json_encode(SchemaService::getAllMeta($dailySources), JSON_UNESCAPED_UNICODE);
        $reuseFieldsJson = '{}';
        $modalDataSources = $dailySources;
        $modalFields = Database::fetchAll('SELECT * FROM logical_fields');

        if ($runId) {
            $run = Database::fetchOne('SELECT * FROM report_runs WHERE id = ?', [$runId]);
        }

        if ($run) {
            $activeDsId = $run['data_source_id'] ? (int) $run['data_source_id'] : $this->runSourceId($run);
        } elseif ($dailySources) {
            $activeDsId = (int) $dailySources[0]['id'];
        }

        $values = [];
        $mappings = [];
        $ds = null;
        if ($activeDsId) {
            $mappings = MappingRepo::forDataSource($activeDsId, false);
            $ds = Database::fetchOne('SELECT * FROM data_sources WHERE id = ?', [$activeDsId]);
            if ($ds) {
                $modalDataSources = [$ds];
                $metaJson = json_encode(SchemaService::getAllMeta([$ds]), JSON_UNESCAPED_UNICODE);
                $reuse = [];
                foreach ($mappings as $m) {
                    if (MappingUtils::isFormulaLine($m) || MappingUtils::isManualLine($m)) {
                        continue;
                    }
                    $reuse[] = [
                        'code' => MappingUtils::mappingLineCode($m),
                        'name' => MappingUtils::mappingLabel($m),
                        'mapping_id' => (int) $m['id'],
                        'configured' => !empty($m['parts']) || (!empty($m['sheet_name']) && !empty($m['column_header'])),
                    ];
                }
                $reuseFieldsJson = json_encode([(string) $ds['id'] => $reuse], JSON_UNESCAPED_UNICODE);
            }
        }

        if ($run) {
            $values = Database::fetchAll(
                'SELECT * FROM report_values WHERE report_run_id = ? ORDER BY sort_order',
                [(int) $run['id']]
            );
            $meta = $ds ? DailyReport::reportMeta($ds, $run) : null;
        }

        $excelRows = null;
        if ($activeDsId) {
            $excelRows = DailyReport::buildDynamicReportRows($mappings, $run ? $values : null);
        }

        return $this->html($response, $this->render('daily.html.twig', $request, [
            'template' => $template,
            'daily_sources' => $dailySources,
            'run' => $run,
            'excel_rows' => $excelRows,
            'meta' => $meta,
            'active_ds_id' => $activeDsId,
            'meta_json' => $metaJson,
            'reuse_fields_json' => $reuseFieldsJson,
            'modal_data_sources' => $modalDataSources,
            'modal_fields' => $modalFields,
        ]));
    }

    /** 推断报表对应的数据源：优先 run 记录，其次 config 店铺名，最后 legacy 导入表。 */
    private function runSourceId(array $run): int
    {
        if (!empty($run['data_source_id'])) {
            return (int) $run['data_source_id'];
        }

        foreach (Database::fetchAll("SELECT * FROM data_sources WHERE config IS NOT NULL AND config != ''") as $ds) {
            $cfg = DsSettings::getDsConfig($ds);
            $store = ($cfg['meta'] ?? [])['店铺名称'] ?? null;
            if ($store === $run['store_name'] || $ds['name'] === $run['store_name']) {
                return (int) $ds['id'];
            }
        }

        $imp = Database::fetchOne(
            'SELECT * FROM data_imports WHERE store_name = ? ORDER BY created_at DESC LIMIT 1',
            [(string) $run['store_name']]
        );
        if ($imp) {
            return (int) $imp['data_source_id'];
        }

        $first = Database::fetchOne("SELECT * FROM data_sources WHERE config IS NOT NULL AND config != '' LIMIT 1");
        return $first ? (int) $first['id'] : 0;
    }

    public function dailyGenerate(Request $request, Response $response): Response
    {
        $body = (array) $request->getParsedBody();
        $dataSourceId = (int) ($body['data_source_id'] ?? 0);
        $reportDate = (string) ($body['report_date'] ?? '');

        AccountContext::assertDataSourceAccess($request->getCookieParams(), $dataSourceId);
        $ds = Database::fetchOne('SELECT * FROM data_sources WHERE id = ?', [$dataSourceId]);
        if (!$ds) {
            throw new HttpError(404, '数据源不存在');
        }

        $cfg = DsSettings::getDsConfig($ds);
        $storeName = (($cfg['meta'] ?? [])['店铺名称'] ?? null) ?: $ds['name'];
        $run = ReportEngine::generateReportForDataSource($dataSourceId, $reportDate, (string) $storeName, true);
        return $this->redirect($response, '/daily?run_id=' . $run['id']);
    }

    public function dailyReviewTemplate(Request $request, Response $response): Response
    {
        $query = $request->getQueryParams();
        $dataSourceId = (int) ($query['data_source_id'] ?? 0);
        AccountContext::assertDataSourceAccess($request->getCookieParams(), $dataSourceId);
        $content = \App\Services\ReviewImport::buildReviewTemplateBytes();
        $response->getBody()->write($content);
        return $response
            ->withHeader('Content-Type', 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
            ->withHeader('Content-Disposition', 'attachment; filename="review_orders_template.xlsx"');
    }

    public function dailyExportSku(Request $request, Response $response, array $args): Response
    {
        $runId = (int) $args['run_id'];
        $run = Database::fetchOne('SELECT * FROM report_runs WHERE id = ?', [$runId]);
        if (!$run) {
            throw new HttpError(404, '报表不存在');
        }
        $dsId = $run['data_source_id'] ? (int) $run['data_source_id'] : $this->runSourceId($run);
        $ds = Database::fetchOne('SELECT * FROM data_sources WHERE id = ?', [$dsId]);
        if (!$ds) {
            throw new HttpError(404, '未找到报表对应的数据源');
        }
        AccountContext::assertDataSourceAccess($request->getCookieParams(), (int) $ds['id']);
        $path = SkuExport::exportSkuForRun($run, $ds);
        return $this->fileResponse($response, $path);
    }

    public function dailyExport(Request $request, Response $response, array $args): Response
    {
        $runId = (int) $args['run_id'];
        $run = Database::fetchOne('SELECT * FROM report_runs WHERE id = ?', [$runId]);
        if (!$run) {
            throw new HttpError(404, '报表不存在');
        }
        $ds = Database::fetchOne('SELECT * FROM data_sources WHERE id = ?', [$this->runSourceId($run)]);
        if (!$ds) {
            throw new HttpError(404, '未找到报表对应的数据源');
        }
        ReportEngine::syncRunMissingValues($run, (int) $ds['id']);
        $values = Database::fetchAll(
            'SELECT * FROM report_values WHERE report_run_id = ? ORDER BY sort_order',
            [$runId]
        );
        $mappings = MappingRepo::forDataSource((int) $ds['id'], false);
        $path = DailyReport::exportDailyExcel($ds, $run, $values, $mappings);
        return $this->fileResponse($response, $path);
    }

    public function importsRedirect(Request $request, Response $response): Response
    {
        return $this->redirect($response, '/mappings');
    }

    private function fileResponse(Response $response, string $path): Response
    {
        $response->getBody()->write((string) file_get_contents($path));
        $filename = rawurlencode(basename($path));
        return $response
            ->withHeader('Content-Type', 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
            ->withHeader('Content-Disposition', "attachment; filename*=UTF-8''{$filename}");
    }
}
