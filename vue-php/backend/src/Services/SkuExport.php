<?php

declare(strict_types=1);

namespace App\Services;

use PhpOffice\PhpSpreadsheet\Spreadsheet;
use PhpOffice\PhpSpreadsheet\Writer\Xlsx;

/**
 * 按报表日期导出 SKU 销量明细 Excel，与 Python 版 services/sku_export.py 对等。
 */
final class SkuExport
{
    public const EXPORT_COLUMNS = [
        ['order_id', 'Order ID'],
        ['sku_id', 'SKU ID'],
        ['seller_sku', 'Seller SKU'],
        ['product_name', 'Product Name'],
        ['quantity', 'Quantity'],
        ['sku_subtotal', 'SKU Subtotal After Discount'],
        ['sku_discount', 'SKU Platform Discount'],
        ['order_amount', 'Order Amount'],
    ];

    public const QTY_CANDIDATES = ['Quantity', 'SKU Quantity', 'Item Quantity'];
    public const SELLER_SKU_CANDIDATES = ['Seller SKU', 'Seller Sku', 'SKU'];
    public const PRODUCT_CANDIDATES = ['Product Name', 'Product', 'Item Name'];

    /** @param string[] $candidates */
    private static function pickNum(array $nd, array $candidates): float
    {
        foreach ($candidates as $c) {
            if (array_key_exists($c, $nd)) {
                return FieldAggregator::toNumber($nd[$c]);
            }
        }
        return 0.0;
    }

    /** @return array[] */
    public static function collectSkuRows(array $ds, string $reportDate, ?string $storeName = null): array
    {
        $cfg = DsSettings::getDsConfig($ds);
        $store = $storeName ?: (($cfg['meta'] ?? [])['店铺名称'] ?? null) ?: $ds['name'];
        $orderSheet = ($cfg['order_sheet'] ?? '') ?: 'OrderSKUList';
        $orderDateCol = ($cfg['order_date_col'] ?? '') ?: 'Created Time';
        $orderDateFmt = $cfg['order_date_format'] ?? null;
        $orderIdCol = ($cfg['order_id_col'] ?? '') ?: 'Order ID';
        $skuIdCol = ($cfg['sku_id_col'] ?? '') ?: 'SKU ID';
        $targetD = FieldAggregator::parseDate($reportDate, 'iso');

        [$rows] = FactProvider::loadFactRows((int) $ds['id'], (string) $store);
        $out = [];
        foreach ($rows as $r) {
            if ($r['sheet_name'] !== $orderSheet) {
                continue;
            }
            $nd = FieldAggregator::normalized($r['row_data']);
            if ($targetD !== null) {
                $d = FieldAggregator::parseDate($nd[$orderDateCol] ?? null, $orderDateFmt);
                if ($d !== $targetD) {
                    continue;
                }
            }
            $oid = FieldAggregator::extract($nd, [$orderIdCol, 'Order ID']);
            $sku = FieldAggregator::extract($nd, [$skuIdCol, 'SKU ID']);
            if ($oid === '' && $sku === '') {
                continue;
            }
            $out[] = [
                'order_id' => $oid,
                'sku_id' => $sku,
                'seller_sku' => FieldAggregator::extract($nd, self::SELLER_SKU_CANDIDATES),
                'product_name' => FieldAggregator::extract($nd, self::PRODUCT_CANDIDATES),
                'quantity' => self::pickNum($nd, self::QTY_CANDIDATES) ?: 1.0,
                'sku_subtotal' => self::pickNum($nd, ['SKU Subtotal After Discount']),
                'sku_discount' => self::pickNum($nd, ['SKU Platform Discount']),
                'order_amount' => self::pickNum($nd, ['Order Amount']),
            ];
        }
        return $out;
    }

    /** @return string 导出文件绝对路径 */
    public static function exportSkuExcel(array $ds, string $reportDate, ?string $storeName = null): string
    {
        $data = self::collectSkuRows($ds, $reportDate, $storeName);
        $spreadsheet = new Spreadsheet();
        $ws = $spreadsheet->getActiveSheet();
        $ws->setTitle('SKU明细');
        $ws->fromArray(array_map(fn($c) => $c[1], self::EXPORT_COLUMNS), null, 'A1');
        $rowNum = 2;
        foreach ($data as $row) {
            $ws->fromArray(array_map(fn($c) => $row[$c[0]], self::EXPORT_COLUMNS), null, "A{$rowNum}");
            $rowNum++;
        }

        $cfg = DsSettings::getDsConfig($ds);
        $store = $storeName ?: (($cfg['meta'] ?? [])['店铺名称'] ?? null) ?: $ds['name'];
        $safeStore = mb_substr(preg_replace('/[^\p{L}\p{N}\-_]/u', '_', (string) $store) ?? '', 0, 30);
        $fname = "SKU明细_{$safeStore}_{$reportDate}.xlsx";
        $path = rtrim(sys_get_temp_dir(), '/\\') . DIRECTORY_SEPARATOR . $fname;
        (new Xlsx($spreadsheet))->save($path);
        $spreadsheet->disconnectWorksheets();
        return $path;
    }

    public static function exportSkuForRun(array $run, array $ds): string
    {
        return self::exportSkuExcel($ds, (string) $run['report_date'], (string) $run['store_name']);
    }
}
