<?php

declare(strict_types=1);

namespace App\Services;

use App\Database;

/**
 * 美宠项目·TikTok 美国本土店日报规则的代码化配置。
 * 与 Python 版 services/meichong_rules.py 对等。
 */
final class MeichongRules
{
    public const ORDER_FILE = '订单';
    public const RETURN_FILE = '退货退款单';
    public const SETTLE_FILE = '结算表';
    public const CREATOR_FILE = '联盟达人佣金';
    public const PARTNER_FILE = '联盟服务商佣金';

    public const ORDER_SHEET = 'OrderSKUList';
    public const RETURN_SHEET = '0';
    public const SETTLE_SHEET = 'Order details';
    public const AFF_SHEET = 'Sheet1';

    public const SKU_TOTAL_COLS = ['SKU Subtotal After Discount', 'SKU Platform Discount'];

    public const MEICHONG_TEMPLATE_NAME = '美宠TK美国本土店日报';

    /** 导出 Excel 后由财务手工填写的行 */
    public const MANUAL_FILL_LABELS = ['利润', '总利润', '利润(估算)', '总利润(估算)'];
    public const LEGACY_MANUAL_LABELS = ['利润' => '利润(估算)', '总利润' => '总利润(估算)'];

    /** 尚无对应 Excel / Catalog 文件的占位指标（报表行保留，出报=0） */
    public const PENDING_FILE_CODES = [
        'mc_review_amount',
        'mc_review_commission',
        'mc_review_service_fee',
        'mc_review_logistics',
        'mc_review_cost',
        'mc_sample_cost',
        'mc_logistics_fee',
        'mc_product_cost',
        'mc_fixed_cost',
        'mc_frame_return',
    ];

    public static function meichongConfig(): array
    {
        return [
            'order_file' => self::ORDER_FILE,
            'order_sheet' => self::ORDER_SHEET,
            'order_id_col' => 'Order ID',
            'sku_id_col' => 'SKU ID',
            'order_date_col' => 'Created Time',
            'order_date_format' => 'us',
            'sample_rule' => ['sum_cols' => self::SKU_TOTAL_COLS, 'equals' => 0],
            'review_order_ids' => [],
            'meta' => ['项目' => '美宠', '平台' => 'TikTok', '区域' => '美国', '店铺名称' => '平衡贴美国本土店铺'],
        ];
    }

    /** 日报逻辑字段：[code, 名称, 说明] */
    public static function logicalFields(): array
    {
        return [
            ['mc_actual_payment', '实际支付金额', '订单表 Order Amount 按订单去重求和，当日、非样品、非刷单'],
            ['mc_sku_platform_discount', '日报有效SKU平台折扣', '订单表 SKU Platform Discount 求和'],
            ['mc_payment_platform_discount', '日报支付平台折扣', '订单表 Payment platform discount 去重求和'],
            ['mc_receivable_amount', '应收金额', 'SKU总额 = SKU Subtotal After Discount + SKU Platform Discount'],
            ['mc_cancelled_amount', '日报取消订单金额', 'SKU总额，Cancelled Time=日报日期'],
            ['mc_refunded_amount', '日报退款订单金额', '退货退款表，Refund Time=日报日期'],
            ['mc_actual_order_count', '实际订单数', '订单表 Order ID 去重计数，当日、非样品、非刷单'],
            ['mc_cancelled_order_count', '取消订单数', 'Cancelled Time=日报日期 的去重订单数'],
            ['mc_refunded_order_count', '退款订单数', '退货退款表 Refund Time=日报日期 的去重订单数'],
            ['mc_creator_commission', '联盟达人佣金', 'Est. standard + Est. Shop Ads commission，关联当日有效订单'],
            ['mc_partner_commission', '联盟服务商佣金', 'Est. Shop Ads + Est. Commission for Affiliate Partner，关联当日有效订单'],
            ['mc_shop_commission', '店铺佣金', '结算表 Fees（除达人佣金及运费外平台费用，近似）'],
            ['mc_ad_spend', '站内消耗(广告费)', '待开发广告费导入'],
            ['mc_logistics_fee', '物流费用', '预估操作费+预估尾程运费，待定=空'],
            ['mc_product_cost', '产品成本', '待定=空'],
            ['mc_review_amount', '刷单金额', '待导入刷单表'],
            ['mc_review_commission', '刷单佣金', '待导入刷单表'],
            ['mc_review_service_fee', '刷单服务费', '待导入刷单表'],
            ['mc_review_logistics', '刷单物流费用', '待导入刷单表'],
            ['mc_review_cost', '刷单成本', '待导入刷单表'],
            ['mc_sample_logistics', '样品单运费', '待定=空'],
            ['mc_sample_cost', '样品单成本', '待定=空'],
            ['mc_fixed_cost', '固定费用', '待定=空'],
            ['mc_frame_return', '框返', '待定=空'],
        ];
    }

    private static function part(
        int $sortOrder,
        string $columnHeader,
        ?string $file = null,
        string $sheet = self::ORDER_SHEET,
        string $agg = 'sum',
        string $combine = 'add',
        array $dedupKeys = [],
        ?string $dateCol = null,
        ?string $dateFmt = null,
        array $rowFilters = [],
        bool $excludeSample = false,
        bool $excludeReview = false,
        bool $joinToOrders = false,
        bool $onlySample = false,
        ?string $label = null,
    ): array {
        return [
            'sort_order' => $sortOrder,
            'label' => $label,
            'source_file_keyword' => $file,
            'sheet_name' => $sheet,
            'column_header' => $columnHeader,
            'aliases' => [],
            'combine_op' => $combine,
            'aggregation' => $agg,
            'dedup_keys' => $dedupKeys,
            'date_filter_column' => $dateCol,
            'date_format' => $dateFmt,
            'row_filters' => $rowFilters,
            'exclude_sample' => $excludeSample,
            'exclude_review' => $excludeReview,
            'join_to_orders' => $joinToOrders,
            'only_sample' => $onlySample,
        ];
    }

    /** code => [描述, parts[]] */
    public static function mappings(): array
    {
        $orderValid = [
            'file' => self::ORDER_FILE, 'sheet' => self::ORDER_SHEET,
            'dateCol' => 'Created Time', 'dateFmt' => 'us',
            'excludeSample' => true, 'excludeReview' => true,
        ];
        return [
            'mc_actual_payment' => [
                '订单 Order Amount 按 Order ID 去重求和（当日/非样品/非刷单）',
                [self::part(0, 'Order Amount', ...$orderValid, agg: 'sum_dedup', dedupKeys: ['Order ID'])],
            ],
            'mc_sku_platform_discount' => [
                '订单 SKU Platform Discount 求和（当日/非样品/非刷单）',
                [self::part(0, 'SKU Platform Discount', ...$orderValid, agg: 'sum')],
            ],
            'mc_payment_platform_discount' => [
                '订单 Payment platform discount 按 Order ID 去重求和',
                [self::part(0, 'Payment platform discount', ...$orderValid, agg: 'sum_dedup', dedupKeys: ['Order ID'])],
            ],
            'mc_receivable_amount' => [
                '应收金额 = SKU Subtotal After Discount + SKU Platform Discount（当日/非样品/非刷单）',
                [
                    self::part(0, 'SKU Subtotal After Discount', ...$orderValid, agg: 'sum'),
                    self::part(1, 'SKU Platform Discount', ...$orderValid, agg: 'sum'),
                ],
            ],
            'mc_cancelled_amount' => [
                '取消订单 SKU总额，Cancelled Time=日报日期',
                [
                    self::part(0, 'SKU Subtotal After Discount', agg: 'sum', file: self::ORDER_FILE, sheet: self::ORDER_SHEET,
                        dateCol: 'Cancelled Time', dateFmt: 'us', excludeSample: true, excludeReview: true),
                    self::part(1, 'SKU Platform Discount', agg: 'sum', file: self::ORDER_FILE, sheet: self::ORDER_SHEET,
                        dateCol: 'Cancelled Time', dateFmt: 'us', excludeSample: true, excludeReview: true),
                ],
            ],
            'mc_refunded_amount' => [
                '退货退款表 Return unit price，Refund Time=日报日期（近似，未乘退货数量）',
                [self::part(0, 'Return unit price', agg: 'sum', file: self::RETURN_FILE, sheet: self::RETURN_SHEET,
                    dateCol: 'Refund Time', dateFmt: 'eu', excludeSample: true, excludeReview: true)],
            ],
            'mc_actual_order_count' => [
                '订单 Order ID 去重计数（当日/非样品/非刷单）',
                [self::part(0, 'Order ID', ...$orderValid, agg: 'count_distinct', dedupKeys: ['Order ID'])],
            ],
            'mc_cancelled_order_count' => [
                'Cancelled Time=日报日期 的去重订单数',
                [self::part(0, 'Order ID', agg: 'count_distinct', dedupKeys: ['Order ID'], file: self::ORDER_FILE,
                    sheet: self::ORDER_SHEET, dateCol: 'Cancelled Time', dateFmt: 'us',
                    excludeSample: true, excludeReview: true)],
            ],
            'mc_refunded_order_count' => [
                '退货退款表 Refund Time=日报日期 的去重订单数',
                [self::part(0, 'Order ID', agg: 'count_distinct', dedupKeys: ['Order ID'], file: self::RETURN_FILE,
                    sheet: self::RETURN_SHEET, dateCol: 'Refund Time', dateFmt: 'eu',
                    excludeSample: true, excludeReview: true)],
            ],
            'mc_creator_commission' => [
                '联盟达人佣金 = Est. standard commission payment + Est. Shop Ads commission payment（关联当日有效订单）',
                [
                    self::part(0, 'Est. standard commission payment', agg: 'sum', file: self::CREATOR_FILE,
                        sheet: self::AFF_SHEET, joinToOrders: true),
                    self::part(1, 'Est. Shop Ads commission payment', agg: 'sum', file: self::CREATOR_FILE,
                        sheet: self::AFF_SHEET, joinToOrders: true),
                ],
            ],
            'mc_partner_commission' => [
                '联盟服务商佣金 = Est. Shop Ads commission payment + Est. Commission for Affiliate Partner（关联当日有效订单）',
                [
                    self::part(0, 'Est. Shop Ads commission payment', agg: 'sum', file: self::PARTNER_FILE,
                        sheet: self::AFF_SHEET, joinToOrders: true),
                    self::part(1, 'Est. Commission for Affiliate Partner', agg: 'sum', file: self::PARTNER_FILE,
                        sheet: self::AFF_SHEET, joinToOrders: true),
                ],
            ],
            'mc_shop_commission' => [
                '结算表 Fees 求和（Order created date=日报日期，近似店铺费用）',
                [self::part(0, 'Fees', agg: 'sum', file: self::SETTLE_FILE, sheet: self::SETTLE_SHEET,
                    dateCol: 'Order created date', dateFmt: 'iso')],
            ],
            'mc_ad_spend' => [
                '结算表广告费（GMV Max ad fee + Smart Promotion campaign period fee，Order created date=日报日期）',
                [
                    self::part(0, 'GMV Max ad fee', agg: 'sum', file: self::SETTLE_FILE, sheet: self::SETTLE_SHEET,
                        dateCol: 'Order created date', dateFmt: 'iso'),
                    self::part(1, 'Smart Promotion campaign period fee', agg: 'sum', combine: 'add', file: self::SETTLE_FILE,
                        sheet: self::SETTLE_SHEET, dateCol: 'Order created date', dateFmt: 'iso'),
                ],
            ],
            'mc_sample_logistics' => [
                '样品单运费 = 订单 Shipping Fee After Discount，仅样品单、Created Time=日报日期',
                [self::part(0, 'Shipping Fee After Discount', agg: 'sum_dedup', dedupKeys: ['Order ID'],
                    file: self::ORDER_FILE, sheet: self::ORDER_SHEET, dateCol: 'Created Time', dateFmt: 'us',
                    onlySample: true)],
            ],
        ];
    }

    /** 报表指标行：[sort, label, expression, format, highlight] */
    public static function templateLines(): array
    {
        return [
            [1, '实际支付金额', '{field:mc_actual_payment}', 'usd', false],
            [2, '应支付金额', '={field:mc_actual_payment}+{field:mc_payment_platform_discount}+{field:mc_sku_platform_discount}', 'usd', false],
            [3, '应收金额', '{field:mc_receivable_amount}', 'usd', true],
            [4, '退单金额', '={field:mc_cancelled_amount}+{field:mc_refunded_amount}', 'usd', false],
            [5, '刷单金额', '{field:mc_review_amount}', 'usd', false],
            [6, '刷单佣金', '{field:mc_review_commission}', 'usd', false],
            [7, '刷单服务费', '{field:mc_review_service_fee}', 'usd', false],
            [8, '刷单物流费用', '{field:mc_review_logistics}', 'usd', false],
            [9, '刷单成本', '{field:mc_review_cost}', 'usd', false],
            [10, '样品单运费', '{field:mc_sample_logistics}', 'usd', false],
            [11, '样品单成本', '{field:mc_sample_cost}', 'usd', false],
            [12, '达人佣金', '={field:mc_creator_commission}+{field:mc_partner_commission}', 'usd', false],
            [13, '店铺佣金', '{field:mc_shop_commission}', 'usd', false],
            [14, '站内消耗', '{field:mc_ad_spend}', 'usd', false],
            [15, '物流费用', '{field:mc_logistics_fee}', 'usd', false],
            [16, '产品成本', '{field:mc_product_cost}', 'usd', false],
            [17, '固定费用', '{field:mc_fixed_cost}', 'usd', false],
            [18, '框返', '{field:mc_frame_return}', 'usd', false],
            [19, '下单数', '={field:mc_actual_order_count}-{field:mc_cancelled_order_count}-{field:mc_refunded_order_count}', 'integer', false],
            [20, '利润', '', 'usd', true],
            [21, '总利润', '', 'usd', true],
        ];
    }

    /** 输出分组（对应日报模板.xlsx 的列分组） */
    public static function templateGroups(): array
    {
        return [
            ['订单情况', ['实际支付金额', '应支付金额', '应收金额', '退单金额']],
            ['刷单情况', ['刷单金额', '刷单佣金', '刷单服务费', '刷单物流费用', '刷单成本']],
            ['样品情况', ['样品单运费', '样品单成本']],
            ['佣金', ['达人佣金', '店铺佣金']],
            ['成本/费用', ['站内消耗', '物流费用', '产品成本', '固定费用', '框返']],
            ['订单数 / 利润', ['下单数', '利润', '总利润']],
        ];
    }

    public static function seedMeichongTemplate(): array
    {
        $tpl = Database::fetchOne('SELECT * FROM report_templates WHERE name = ?', [self::MEICHONG_TEMPLATE_NAME]);
        if ($tpl) {
            Database::execute('DELETE FROM template_lines WHERE template_id = ?', [(int) $tpl['id']]);
            $tplId = (int) $tpl['id'];
        } else {
            $tplId = Database::insert('report_templates', [
                'name' => self::MEICHONG_TEMPLATE_NAME,
                'description' => '按《美宠日报规则-TK》生成；占位指标（刷单/样品/广告/成本/固定费用/框返）待接入对应数据。利润为透明估算口径。',
                'status' => 'DRAFT',
                'version' => 1,
                'owner' => '财务',
                'created_at' => Database::utcNow(),
                'updated_at' => Database::utcNow(),
            ]);
        }
        foreach (self::templateLines() as [$sortOrder, $label, $expr, $fmt, $highlight]) {
            Database::insert('template_lines', [
                'template_id' => $tplId,
                'sort_order' => $sortOrder,
                'label' => $label,
                'expression' => $expr,
                'format_type' => $fmt,
                'is_highlight' => $highlight ? 1 : 0,
            ]);
        }
        return Database::fetchOne('SELECT * FROM report_templates WHERE id = ?', [$tplId]);
    }

    public static function ensureMeichongTemplate(): void
    {
        if (!Database::fetchOne('SELECT id FROM report_templates WHERE name = ?', [self::MEICHONG_TEMPLATE_NAME])) {
            self::seedMeichongTemplate();
        }
    }

    /** 启动时调用：仅当数据源尚未配置（config 为空）时写入规则，避免覆盖用户的 Web 编辑。 */
    public static function ensureMeichongRules(): void
    {
        $ds = Database::fetchOne('SELECT * FROM data_sources WHERE name = ?', [Seed::MEICHONG_SOURCE_NAME]);
        if ($ds && empty(DsSettings::getDsConfig($ds))) {
            self::applyMeichongRules(true);
        }
        self::ensureMeichongTemplate();
    }

    public static function applyMeichongRules(bool $reset = true): void
    {
        $ds = Database::fetchOne('SELECT * FROM data_sources WHERE name = ?', [Seed::MEICHONG_SOURCE_NAME]);
        if (!$ds) {
            throw new \RuntimeException('美宠数据源不存在，请先运行 ensureMeichongDatasource / 导入数据');
        }
        $dsId = (int) $ds['id'];

        Database::updateById('data_sources', $dsId, ['config' => Database::jsonEncode(self::meichongConfig())]);

        foreach (self::logicalFields() as [$code, $name, $desc]) {
            $lf = Database::fetchOne('SELECT * FROM logical_fields WHERE code = ?', [$code]);
            if (!$lf) {
                Database::insert('logical_fields', [
                    'code' => $code,
                    'name' => $name,
                    'data_type' => 'number',
                    'description' => $desc,
                ]);
            } else {
                Database::updateById('logical_fields', (int) $lf['id'], ['name' => $name, 'description' => $desc]);
            }
        }

        $fieldMap = [];
        foreach (Database::fetchAll('SELECT * FROM logical_fields') as $f) {
            $fieldMap[(string) $f['code']] = $f;
        }

        foreach (self::mappings() as $code => [$desc, $parts]) {
            $lf = $fieldMap[$code];
            $mapping = Database::fetchOne(
                'SELECT * FROM field_mappings WHERE data_source_id = ? AND line_code = ?',
                [$dsId, $code]
            ) ?: Database::fetchOne(
                'SELECT * FROM field_mappings WHERE data_source_id = ? AND logical_field_id = ?',
                [$dsId, (int) $lf['id']]
            );
            if ($mapping && $reset) {
                Database::execute('DELETE FROM field_mapping_parts WHERE mapping_id = ?', [(int) $mapping['id']]);
            }
            if (!$mapping) {
                $mid = Database::insert('field_mappings', [
                    'data_source_id' => $dsId,
                    'logical_field_id' => (int) $lf['id'],
                    'line_type' => 'fetch',
                    'sort_order' => 0,
                    'format_type' => 'usd',
                    'is_highlight' => 0,
                    'aggregation' => 'sum',
                    'aliases' => Database::jsonEncode([]),
                ]);
                $mapping = Database::fetchOne('SELECT * FROM field_mappings WHERE id = ?', [$mid]);
            }
            Database::updateById('field_mappings', (int) $mapping['id'], ['description' => $desc]);
            foreach ($parts as $p) {
                Database::insert('field_mapping_parts', [
                    'mapping_id' => (int) $mapping['id'],
                    'sort_order' => $p['sort_order'],
                    'label' => $p['label'],
                    'source_file_keyword' => $p['source_file_keyword'],
                    'sheet_name' => $p['sheet_name'],
                    'column_header' => $p['column_header'],
                    'aliases' => Database::jsonEncode($p['aliases']),
                    'combine_op' => $p['combine_op'],
                    'aggregation' => $p['aggregation'],
                    'dedup_keys' => Database::jsonEncode($p['dedup_keys']),
                    'date_filter_column' => $p['date_filter_column'],
                    'date_format' => $p['date_format'],
                    'row_filters' => Database::jsonEncode($p['row_filters']),
                    'exclude_sample' => $p['exclude_sample'] ? 1 : 0,
                    'exclude_review' => $p['exclude_review'] ? 1 : 0,
                    'join_to_orders' => $p['join_to_orders'] ? 1 : 0,
                    'only_sample' => $p['only_sample'] ? 1 : 0,
                ]);
            }
        }

        ReportLineSync::syncReportLines($dsId, self::templateLines(), self::templateGroups(), true);
    }
}
