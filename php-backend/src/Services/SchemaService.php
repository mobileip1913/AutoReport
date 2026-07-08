<?php

declare(strict_types=1);

namespace App\Services;

/**
 * 字段映射下拉：从 Catalog 目录表按需加载 文件 → Sheet → 列头。
 * 与 Python 版 services/schema.py 对等。
 */
final class SchemaService
{
    public static function querySchema(array $ds, ?string $fileKeyword = null, ?string $sheetName = null): array
    {
        $dsId = (int) $ds['id'];
        if ($fileKeyword && $sheetName) {
            return ['columns' => CatalogResolver::listCatalogColumns($dsId, $fileKeyword, $sheetName)];
        }
        if ($fileKeyword) {
            return ['sheets' => CatalogResolver::listCatalogSheets($dsId, $fileKeyword)];
        }
        return ['files' => CatalogResolver::listCatalogFiles($dsId)];
    }

    public static function getDataSourceMeta(array $ds): array
    {
        return ['files' => CatalogResolver::listCatalogFiles((int) $ds['id'])];
    }

    /** @param array[] $dataSources @return array<int, array> */
    public static function getAllMeta(array $dataSources): array
    {
        $out = [];
        foreach ($dataSources as $ds) {
            $out[(int) $ds['id']] = self::getDataSourceMeta($ds);
        }
        return $out;
    }

    /**
     * 数据源 catalog 关键字 → UI 短名，供规则摘要展示。
     * @param array<int, array> $meta
     * @return array<int, array<string, string>>
     */
    public static function fileLabelsFromMeta(array $meta): array
    {
        $out = [];
        foreach ($meta as $dsId => $m) {
            $labels = [];
            foreach ($m['files'] ?? [] as $f) {
                $kw = trim((string) ($f['keyword'] ?? ''));
                if ($kw === '') {
                    continue;
                }
                $labels[$kw] = trim((string) ($f['label'] ?? $f['file_label'] ?? $kw));
            }
            $out[(int) $dsId] = $labels;
        }
        return $out;
    }

    /** 完整 Catalog 目录：文件 → Sheet → 列头。 */
    public static function buildFullSchemaSnapshot(array $ds): array
    {
        $dsId = (int) $ds['id'];
        $filesOut = [];
        $merged = [];
        foreach (CatalogResolver::listCatalogFiles($dsId) as $f) {
            $kw = $f['keyword'];
            $sheetsOut = [];
            foreach (CatalogResolver::listCatalogSheets($dsId, $kw) as $sh) {
                $cols = CatalogResolver::listCatalogColumns($dsId, $kw, $sh);
                $sheetsOut[$sh] = $cols;
                foreach ($cols as $c) {
                    $merged[$sh][$c] = true;
                }
            }
            $filesOut[] = array_merge($f, ['sheets' => $sheetsOut ?: new \stdClass()]);
        }
        $sheets = [];
        foreach ($merged as $k => $set) {
            $names = array_keys($set);
            sort($names);
            $sheets[$k] = $names;
        }
        return ['sheets' => $sheets ?: new \stdClass(), 'files' => $filesOut];
    }
}
