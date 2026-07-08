<?php

declare(strict_types=1);

namespace App\Services;

/**
 * 日报上下文：样品/刷单订单集合、当日有效订单键，与 Python 版 DailyContext 对等。
 * 日期统一用 'Y-m-d' 字符串表示（Python date 对象的等价物）。
 */
final class DailyContext
{
    /** @param array<string, true> $sampleOrderIds 等均为 set（key => true） */
    public function __construct(
        public ?string $reportDate = null,
        public array $sampleOrderIds = [],
        public array $reviewOrderIds = [],
        public array $orderKeys = [],
        public array $orderIdSet = [],
        public array $validOrderKeys = [],
        public array $validOrderIds = [],
        /** @var array<string, array<string, true>> 关联键列头(JSON) → 有效值元组(JSON)集合 */
        public array $validJoinMap = [],
        /** @var array[] 当日有效订单行（normalized row_data） */
        public array $validMasterRows = [],
        /** @var array<string, true> 当日下单且当日退款的 Order ID */
        public array $sameDayRefundOrderIds = [],
    ) {
    }
}
