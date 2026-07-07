<?php

declare(strict_types=1);

namespace App\Services;

use App\Database;

/**
 * Demo 账号 / 店铺种子：报表配置按店铺隔离，账号可绑定多店铺。
 * 与 Python 版 services/demo_accounts.py 对等。
 */
final class DemoAccounts
{
    public const DEMO_STORE_B_NAME = '美宠Demo-欧洲区店铺';
    public const DEMO_STORE_B_SOURCE = '美宠-欧洲区Demo店铺(TK-EU)';

    /** [login_name, display_name, store_names[]] */
    private static function demoAccounts(): array
    {
        return [
            ['zhang', '张财务', [Seed::MEICHONG_STORE]],
            ['li', '李运营', [self::DEMO_STORE_B_NAME]],
            ['wang', '王主管', [Seed::MEICHONG_STORE, self::DEMO_STORE_B_NAME]],
        ];
    }

    private static function ensureStoreBDatasource(array $srcDs): array
    {
        $existing = Database::fetchOne('SELECT * FROM data_sources WHERE name = ?', [self::DEMO_STORE_B_SOURCE]);
        if ($existing) {
            return $existing;
        }

        $cfg = MeichongRules::meichongConfig();
        $cfg['meta'] = array_merge($cfg['meta'] ?? [], [
            '项目' => '美宠',
            '平台' => 'TikTok',
            '区域' => '欧洲',
            '店铺名称' => self::DEMO_STORE_B_NAME,
        ]);
        $dsId = Database::insert('data_sources', [
            'name' => self::DEMO_STORE_B_SOURCE,
            'platform' => 'TikTok Shop',
            'description' => 'Demo 第二店铺：欧洲区独立报表配置（Catalog/映射从美宠美区克隆，便于对比权限）',
            'config' => Database::jsonEncode($cfg),
            'created_at' => Database::utcNow(),
        ]);

        StoreClone::cloneCatalog((int) $srcDs['id'], $dsId);
        StoreClone::cloneFieldMappings((int) $srcDs['id'], $dsId);

        // 标记差异：欧区店铺用不同指标名，便于 Demo 区分
        $payLine = Database::fetchOne(
            'SELECT * FROM field_mappings WHERE data_source_id = ? AND label = ?',
            [$dsId, '应支付金额']
        );
        if ($payLine) {
            Database::updateById('field_mappings', (int) $payLine['id'], [
                'label' => '应支付金额(欧区口径)',
                'description' => 'Demo：欧区店铺独立报表配置',
            ]);
        }
        return Database::fetchOne('SELECT * FROM data_sources WHERE id = ?', [$dsId]);
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
        $srcDs = Seed::ensureMeichongDatasource();
        $storeA = self::ensureStoreRecord(Seed::MEICHONG_STORE, 'TikTok Shop', (int) $srcDs['id']);
        $storeBDs = self::ensureStoreBDatasource($srcDs);
        $storeB = self::ensureStoreRecord(self::DEMO_STORE_B_NAME, 'TikTok Shop', (int) $storeBDs['id']);

        $storesByName = [
            (string) $storeA['name'] => $storeA,
            (string) $storeB['name'] => $storeB,
        ];

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
                $store = $storesByName[$storeName] ?? null;
                if ($store) {
                    $allowedIds[(int) $store['id']] = true;
                    self::linkAccountStore((int) $account['id'], (int) $store['id']);
                }
            }

            // 移除 Demo 账号不再绑定的店铺
            $links = Database::fetchAll('SELECT * FROM account_stores WHERE account_id = ?', [(int) $account['id']]);
            foreach ($links as $link) {
                if (!isset($allowedIds[(int) $link['store_id']])) {
                    Database::execute('DELETE FROM account_stores WHERE id = ?', [(int) $link['id']]);
                }
            }
        }
    }
}
