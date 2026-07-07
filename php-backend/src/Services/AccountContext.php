<?php

declare(strict_types=1);

namespace App\Services;

use App\Database;
use App\HttpError;

/**
 * Demo 账号上下文：Cookie 切换账号，按店铺过滤报表配置。
 * 与 Python 版 services/account_context.py 对等。
 */
final class AccountContext
{
    public const ACCOUNT_COOKIE = 'demo_account_id';
    public const STORE_COOKIE = 'demo_store_id';

    /** @return array[] */
    public static function listAccounts(): array
    {
        return Database::fetchAll('SELECT * FROM accounts ORDER BY id');
    }

    public static function getAccount(?int $accountId): ?array
    {
        if (!$accountId) {
            return null;
        }
        return Database::fetchOne('SELECT * FROM accounts WHERE id = ?', [$accountId]);
    }

    /** @param array<string, string> $cookies */
    public static function resolveCurrentAccount(array $cookies): array
    {
        $raw = $cookies[self::ACCOUNT_COOKIE] ?? '';
        $account = ctype_digit((string) $raw) ? self::getAccount((int) $raw) : null;
        if ($account) {
            return $account;
        }
        $account = Database::fetchOne('SELECT * FROM accounts ORDER BY id LIMIT 1');
        if (!$account) {
            throw new HttpError(503, '尚未初始化 Demo 账号，请重启服务');
        }
        return $account;
    }

    /** @return array[] store 行（含 data_source 子数组） */
    public static function storesForAccount(int $accountId): array
    {
        $stores = Database::fetchAll(
            'SELECT s.* FROM stores s
             JOIN account_stores ast ON ast.store_id = s.id
             WHERE ast.account_id = ?
             ORDER BY s.id',
            [$accountId]
        );
        foreach ($stores as &$store) {
            $store['data_source'] = Database::fetchOne(
                'SELECT * FROM data_sources WHERE id = ?',
                [(int) $store['data_source_id']]
            );
        }
        return $stores;
    }

    /** @param array<string, string> $cookies */
    public static function resolveCurrentStore(array $cookies, array $account): ?array
    {
        $stores = self::storesForAccount((int) $account['id']);
        if (!$stores) {
            return null;
        }
        $raw = $cookies[self::STORE_COOKIE] ?? '';
        if (ctype_digit((string) $raw)) {
            $storeId = (int) $raw;
            foreach ($stores as $store) {
                if ((int) $store['id'] === $storeId) {
                    return $store;
                }
            }
        }
        return $stores[0];
    }

    /** @return array[] */
    public static function dataSourcesForAccount(int $accountId): array
    {
        $out = [];
        foreach (self::storesForAccount($accountId) as $s) {
            if (!empty($s['data_source'])) {
                $out[] = $s['data_source'];
            }
        }
        return $out;
    }

    /** @return array<int, true> */
    public static function allowedDataSourceIds(int $accountId): array
    {
        $out = [];
        foreach (self::storesForAccount($accountId) as $s) {
            $out[(int) $s['data_source_id']] = true;
        }
        return $out;
    }

    /** @param array<string, string> $cookies */
    public static function assertDataSourceAccess(array $cookies, int $dataSourceId): void
    {
        $account = self::resolveCurrentAccount($cookies);
        $allowed = self::allowedDataSourceIds((int) $account['id']);
        if (!isset($allowed[$dataSourceId])) {
            throw new HttpError(403, '当前账号无权访问该店铺的报表配置');
        }
    }

    /** @param array<string, string> $cookies */
    public static function assertMappingAccess(array $cookies, array $mapping): void
    {
        self::assertDataSourceAccess($cookies, (int) $mapping['data_source_id']);
    }

    /** @param array<string, string> $cookies */
    public static function pageContext(array $cookies): array
    {
        $account = self::resolveCurrentAccount($cookies);
        $stores = self::storesForAccount((int) $account['id']);
        $currentStore = self::resolveCurrentStore($cookies, $account);
        $dataSources = [];
        foreach ($stores as $s) {
            if (!empty($s['data_source'])) {
                $dataSources[] = $s['data_source'];
            }
        }
        $accountMenu = [];
        foreach (self::listAccounts() as $acc) {
            $accStores = self::storesForAccount((int) $acc['id']);
            $names = array_map(fn($s) => (string) $s['name'], $accStores);
            if (count($names) === 0) {
                $hint = '暂无店铺';
            } elseif (count($names) === 1) {
                $hint = $names[0];
            } else {
                $hint = count($names) . ' 个店铺';
            }
            $accountMenu[] = [
                'id' => (int) $acc['id'],
                'display_name' => $acc['display_name'],
                'initial' => mb_substr((string) ($acc['display_name'] ?: '?'), 0, 1),
                'store_hint' => $hint,
            ];
        }
        return [
            'current_account' => $account,
            'demo_accounts' => self::listAccounts(),
            'account_menu' => $accountMenu,
            'accessible_stores' => $stores,
            'current_store' => $currentStore,
            'accessible_data_sources' => $dataSources,
        ];
    }
}
