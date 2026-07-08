<?php

/**
 * 定时出报脚本（对等 Python 版 APScheduler）。
 *
 * PHP-FPM 没有常驻后台任务，改为由系统计划任务每分钟调用一次本脚本：
 *   Windows 任务计划程序 / cron:  * * * * *  php /path/to/php-backend/bin/scheduler.php
 *
 * 脚本读取每个数据源 config.daily_generate_at（hh:mm，Asia/Shanghai），
 * 到点时为「昨日」生成正式日报。data/scheduler_state.json 记录已执行标记，避免同日重复出报。
 */

declare(strict_types=1);

require dirname(__DIR__) . '/vendor/autoload.php';

use App\Config;
use App\Database;
use App\Services\DsSettings;
use App\Services\ReportEngine;

$tz = new DateTimeZone('Asia/Shanghai');
$now = new DateTimeImmutable('now', $tz);
$today = $now->format('Y-m-d');
$currentMinutes = (int) $now->format('H') * 60 + (int) $now->format('i');
$reportDate = $now->modify('-1 day')->format('Y-m-d');

$stateFile = Config::rootDir() . '/data/scheduler_state.json';
@mkdir(dirname($stateFile), 0777, true);
$state = is_file($stateFile) ? (json_decode((string) file_get_contents($stateFile), true) ?: []) : [];

function parseHhmm(string $text): ?int
{
    $text = trim($text);
    if ($text === '' || !str_contains($text, ':')) {
        return null;
    }
    [$h, $m] = explode(':', $text, 2);
    if (!ctype_digit($h) || !ctype_digit($m)) {
        return null;
    }
    $hour = (int) $h;
    $minute = (int) $m;
    if ($hour < 0 || $hour > 23 || $minute < 0 || $minute > 59) {
        return null;
    }
    return $hour * 60 + $minute;
}

$ran = 0;
foreach (Database::fetchAll('SELECT * FROM data_sources WHERE config IS NOT NULL') as $ds) {
    $cfg = DsSettings::getDsConfig($ds);
    $scheduled = parseHhmm((string) ($cfg['daily_generate_at'] ?? ''));
    if ($scheduled === null) {
        continue;
    }
    // 到点（含错过的分钟，脚本可能不是恰好整分触发）且今天尚未执行
    if ($currentMinutes < $scheduled) {
        continue;
    }
    $key = 'ds_' . $ds['id'];
    if (($state[$key] ?? '') === $today) {
        continue;
    }
    try {
        $storeName = (($cfg['meta'] ?? [])['店铺名称'] ?? null) ?: $ds['name'];
        $run = ReportEngine::generateReportForDataSource((int) $ds['id'], $reportDate, (string) $storeName, false);
        $state[$key] = $today;
        $ran++;
        echo sprintf("[scheduler] 定时出报完成 ds=%s date=%s run_id=%s\n", $ds['id'], $reportDate, $run['id']);
    } catch (Throwable $e) {
        echo sprintf("[scheduler] 定时出报失败 ds=%s: %s\n", $ds['id'], $e->getMessage());
    }
}

file_put_contents($stateFile, json_encode($state, JSON_PRETTY_PRINT | JSON_UNESCAPED_UNICODE));
if ($ran === 0) {
    echo "[scheduler] 无到点任务。\n";
}
