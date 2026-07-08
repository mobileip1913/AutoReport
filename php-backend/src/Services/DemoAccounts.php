<?php

declare(strict_types=1);

namespace App\Services;

use App\Database;

/**
 * Demo 账号 / 店铺种子：仅保留美宠真实店铺。
 * 与 Python 版 services/demo_accounts.py 对等。
 */
final class DemoAccounts
{
    private const LEGACY_DEMO_STORE_B_SOURCE = '美宠-欧洲区Demo店铺(TK-EU)';

    /** [login_name, display_name, store_names[]] */
    private static function demoAccounts(): array
    {
        return [
            ['zhang', '张财务', [Seed::MEICHONG_STORE]],
            ['li', '李运营', [Seed::MEICHONG_STORE]],
            ['wang', '王主管', [Seed::MEICHONG_STORE]],
        ];
    }

    private static function removeLegacyDemoStoreB(): void
    {
        $ds = Database::fetchOne('SELECT * FROM data_sources WHERE name = ?', [self::LEGACY_DEMO_STORE_B_SOURCE]);
        if (!$ds) {
            return;
        }
        $dsId = (int) $ds['id'];

        $mappings = Database::fetchAll('SELECT id FROM field_mappings WHERE data_source_id = ?', [$dsId]);
        foreach ($mappings as $m) {
            $mid = (int) $m['id'];
            Database::execute('UPDATE report_values SET mapping_id = NULL WHERE mapping_id = ?', [$mid]);
            Database::execute('DELETE FROM field_mapping_parts WHERE mapping_id = ?', [$mid]);
            Database::execute('DELETE FROM field_mappings WHERE id = ?', [$mid]);
        }

        $runs = Database::fetchAll('SELECT id FROM report_runs WHERE data_source_id = ?', [$dsId]);
        foreach ($runs as $run) {
            $rid = (int) $run['id'];
            Database::execute('DELETE FROM report_values WHERE report_run_id = ?', [$rid]);
            Database::execute('DELETE FROM report_runs WHERE id = ?', [$rid]);
        }

        $files = Database::fetchAll('SELECT id FROM catalog_files WHERE data_source_id = ?', [$dsId]);
        foreach ($files as $file) {
            $fid = (int) $file['id'];
            $sheets = Database::fetchAll('SELECT id FROM catalog_sheets WHERE file_id = ?', [$fid]);
            foreach ($sheets as $sheet) {
                $sid = (int) $sheet['id'];
                Database::execute('DELETE FROM catalog_columns WHERE sheet_id = ?', [$sid]);
                Database::execute('DELETE FROM catalog_sheets WHERE id = ?', [$sid]);
            }
            Database::execute('DELETE FROM catalog_files WHERE id = ?', [$fid]);
        }

        Database::execute('DELETE FROM etl_batches WHERE data_source_id = ?', [$dsId]);

        $imports = Database::fetchAll('SELECT id FROM data_imports WHERE data_source_id = ?', [$dsId]);
        foreach ($imports as $imp) {
            $iid = (int) $imp['id'];
            Database::execute('DELETE FROM data_rows WHERE data_import_id = ?', [$iid]);
            Database::execute('DELETE FROM mapping_logs WHERE data_import_id = ?', [$iid]);
            Database::execute('DELETE FROM data_imports WHERE id = ?', [$iid]);
        }

        $store = Database::fetchOne('SELECT id FROM stores WHERE data_source_id = ?', [$dsId]);
        if ($store) {
            $storeId = (int) $store['id'];
            Database::execute('DELETE FROM account_stores WHERE store_id = ?', [$storeId]);
            Database::execute('DELETE FROM stores WHERE id = ?', [$storeId]);
        }

        Database::execute('DELETE FROM data_sources WHERE id = ?', [$dsId]);
    }

    private static function ensureStoreRecord(string $name, string $platform, int $dataSourceId): array
    {
        $store = Database::fetchOne('SELECT * FROM stores WHERE data_source_id = ?', [$dataSourceId]);
        if ($store) {
            Database::updateById('stores', (int) $store['id'], ['name' => $name, 'platform' => $platform]);
            return Database::fetchOne('SELECT * FROM stores WHERE id = ?', [(int) $store['id']]);
        }
        $id = Database::insert('stores', [
            'name' => $name,
            'platform' => $platform,
            'data_source_id' => $dataSourceId,
            'created_at' => Database::utcNow(),
        ]);
        return Database::fetchOne('SELECT * FROM stores WHERE id = ?', [$id]);
    }

    private static function linkAccountStore(int $accountId, int $storeId): void
    {
        $exists = Database::fetchOne(
            'SELECT id FROM account_stores WHERE account_id = ? AND store_id = ?',
            [$accountId, $storeId]
        );
        if (!$exists) {
            Database::insert('account_stores', ['account_id' => $accountId, 'store_id' => $storeId]);
        }
    }

    public static function ensureDemoAccounts(): void
    {
        self::removeLegacyDemoStoreB();

        $srcDs = Seed::ensureMeichongDatasource();
        $store = self::ensureStoreRecord(Seed::MEICHONG_STORE, 'TikTok Shop', (int) $srcDs['id']);

        foreach (self::demoAccounts() as [$loginName, $displayName, $storeNames]) {
            $account = Database::fetchOne('SELECT * FROM accounts WHERE login_name = ?', [$loginName]);
            if (!$account) {
                $accId = Database::insert('accounts', [
                    'login_name' => $loginName,
                    'display_name' => $displayName,
                    'created_at' => Database::utcNow(),
                ]);
                $account = Database::fetchOne('SELECT * FROM accounts WHERE id = ?', [$accId]);
            } else {
                Database::updateById('accounts', (int) $account['id'], ['display_name' => $displayName]);
            }

            $allowedIds = [];
            foreach ($storeNames as $storeName) {
                if ($storeName === Seed::MEICHONG_STORE) {
                    $allowedIds[(int) $store['id']] = true;
                    self::linkAccountStore((int) $account['id'], (int) $store['id']);
                }
            }

            $links = Database::fetchAll('SELECT * FROM account_stores WHERE account_id = ?', [(int) $account['id']]);
            foreach ($links as $link) {
                if (!isset($allowedIds[(int) $link['store_id']])) {
                    Database::execute('DELETE FROM account_stores WHERE id = ?', [(int) $link['id']]);
                }
            }
        }
    }
}
