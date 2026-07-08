<?php

declare(strict_types=1);

namespace App\Services;

/**
 * 时区工具：数据库统一存 UTC，展示时转东八区（UTC+8 / 北京时间）。
 */
final class Timezone
{
    public static function toCst(?string $value, string $fmt = 'Y-m-d H:i'): string
    {
        if ($value === null || $value === '') {
            return '';
        }
        try {
            $dt = new \DateTimeImmutable($value, new \DateTimeZone('UTC'));
        } catch (\Exception) {
            return (string) $value;
        }
        return $dt->setTimezone(new \DateTimeZone('Asia/Shanghai'))->format($fmt);
    }
}
