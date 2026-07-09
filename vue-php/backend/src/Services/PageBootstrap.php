<?php

declare(strict_types=1);

namespace App\Services;

use App\Database;

/**
 * SPA 页面 bootstrap 数据组装（与 Twig PagesController 共用逻辑，避免双份维护）。
 */
final class PageBootstrap
{
    /** @param array<string, string> $cookies */
    public static function session(array $cookies): array
    {
        $ctx = AccountContext::pageContext($cookies);
        return [
            'current_account' => $ctx['current_account'],
            'account_menu' => $ctx['account_menu'],
            'accessible_stores' => $ctx['accessible_stores'],
            'current_store' => $ctx['current_store'],
            'accessible_data_sources' => $ctx['accessible_data_sources'],
        ];
    }

    /** @param array<string, string> $cookies */
    public static function dashboard(array $cookies): array
    {
        $ctx = self::session($cookies);
        $templatesList = Database::fetchAll('SELECT * FROM report_templates ORDER BY updated_at DESC');
        foreach ($templatesList as &$t) {
            $t['status'] = strtolower((string) ($t['status'] ?? 'draft'));
        }
        unset($t);
        return array_merge($ctx, [
            'templates_list' => $templatesList,
            'recent_runs' => Database::fetchAll('SELECT * FROM report_runs ORDER BY created_at DESC LIMIT 8'),
            'data_sources' => Database::fetchAll('SELECT * FROM data_sources'),
        ]);
    }

    /** @param array<string, string> $cookies */
    public static function mappings(array $cookies): array
    {
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
                    'source_files' => MappingUtils::mappingSourceFileKeywords($m),
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
                'field_type' => MappingUtils::fieldDisplayType($m),
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

        $fileLabelsByDs = SchemaService::fileLabelsFromMeta($meta);
        $fieldLabelsByDs = [];
        foreach ($dataSources as $ds) {
            $dsId = (int) $ds['id'];
            $dsMappings = array_values(array_filter($mappings, fn($m) => (int) $m['data_source_id'] === $dsId));
            $fieldLabelsByDs[$dsId] = MappingUtils::buildFieldLabelsMap($dsMappings, $fields);
        }

        return array_merge($ctx, [
            'mappings' => $mappings,
            'grouped' => $grouped,
            'group_titles' => $groupTitles,
            'auxiliary' => $auxiliary,
            'excel_config' => $excelConfig,
            'fields' => $fields,
            'data_sources' => $dataSources,
            'store_by_ds_id' => $storeByDsId,
            'excel_templates' => DailyReport::listExcelTemplates(),
            'meta' => $meta,
            'file_labels_by_ds' => $fileLabelsByDs,
            'field_labels_by_ds' => $fieldLabelsByDs,
            'reuse_fields' => $reuseFields,
            'pending_file_codes' => MeichongRules::PENDING_FILE_CODES,
            'review_import_codes' => MeichongRules::REVIEW_IMPORT_CODES,
            'review_logistics_codes' => MeichongRules::REVIEW_LOGISTICS_CODES,
            'ds_settings' => $dsSettings,
            'modal_stores' => $accessibleStores,
        ]);
    }

    /**
     * @param array<string, string> $cookies
     * @param array<string, mixed> $query
     */
    public static function daily(array $cookies, array $query = []): array
    {
        $ctx = AccountContext::pageContext($cookies);
        $runId = isset($query['run_id']) && ctype_digit((string) $query['run_id']) ? (int) $query['run_id'] : null;

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
        $modalFields = Database::fetchAll('SELECT * FROM logical_fields');
        $modalDataSources = $dailySources;
        $reuseFields = [];

        if ($runId) {
            $run = Database::fetchOne('SELECT * FROM report_runs WHERE id = ?', [$runId]);
        }

        if ($run) {
            $activeDsId = $run['data_source_id'] ? (int) $run['data_source_id'] : self::runSourceId($run);
        } elseif (!empty($ctx['current_store']['data_source_id'])) {
            $activeDsId = (int) $ctx['current_store']['data_source_id'];
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
                $reuseFields[(string) $ds['id']] = $reuse;
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
        $dsSettings = [];
        if ($activeDsId) {
            $excelRows = DailyReport::buildDynamicReportRows($mappings, $run ? $values : null, MeichongRules::PENDING_FILE_CODES);
        }

        if ($activeDsId && $ds) {
            $dsSettings = [(int) $ds['id'] => DsSettings::serializeDsSettings($ds)];
        } elseif ($dailySources) {
            foreach ($dailySources as $d) {
                $dsSettings[(int) $d['id']] = DsSettings::serializeDsSettings($d);
            }
        }

        $defaultReportDate = $run
            ? (string) $run['report_date']
            : (new \DateTimeImmutable('yesterday', new \DateTimeZone('Asia/Shanghai')))->format('Y-m-d');

        $storeByDsId = [];
        foreach ($ctx['accessible_stores'] ?? [] as $store) {
            if (!empty($store['data_source_id'])) {
                $storeByDsId[(int) $store['data_source_id']] = $store;
            }
        }

        $metaAll = $ds ? SchemaService::getAllMeta([$ds]) : SchemaService::getAllMeta($dailySources);
        $fileLabelsByDs = [];
        try {
            $fileLabelsByDs = SchemaService::fileLabelsFromMeta($metaAll);
        } catch (\Throwable) {
            $fileLabelsByDs = [];
        }

        $fieldLabelsByDs = [];
        if ($activeDsId && $mappings) {
            $fieldLabelsByDs[$activeDsId] = MappingUtils::buildFieldLabelsMap($mappings, $modalFields);
        }

        return array_merge($ctx, [
            'template' => $template,
            'daily_sources' => $dailySources,
            'store_by_ds_id' => $storeByDsId,
            'run' => $run,
            'excel_rows' => $excelRows,
            'meta' => $meta,
            'active_ds_id' => $activeDsId,
            'default_report_date' => $defaultReportDate,
            'meta_all' => $metaAll,
            'file_labels_by_ds' => $fileLabelsByDs,
            'field_labels_by_ds' => $fieldLabelsByDs,
            'reuse_fields' => $reuseFields,
            'modal_data_sources' => $modalDataSources,
            'modal_fields' => $modalFields,
            'modal_stores' => $ctx['accessible_stores'] ?? [],
            'ds_settings' => $dsSettings,
            'pending_file_codes' => MeichongRules::PENDING_FILE_CODES,
            'review_import_codes' => MeichongRules::REVIEW_IMPORT_CODES,
            'review_logistics_codes' => MeichongRules::REVIEW_LOGISTICS_CODES,
        ]);
    }

    private static function runSourceId(array $run): int
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
}
