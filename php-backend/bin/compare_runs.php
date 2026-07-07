<?php

/** 临时验证：对比同一 report_date 的最近两个 run 的取数结果是否一致。 */

declare(strict_types=1);

require dirname(__DIR__) . '/vendor/autoload.php';

use App\Database;

$date = $argv[1] ?? '2026-06-22';
$runs = Database::fetchAll(
    'SELECT id, report_date, status, is_test, data_source_id, created_at FROM report_runs WHERE report_date = ? ORDER BY id DESC LIMIT 8',
    [$date]
);
foreach ($runs as $r) {
    echo json_encode($r, JSON_UNESCAPED_UNICODE), PHP_EOL;
}

if (count($argv) >= 4) {
    $a = (int) $argv[2];
    $b = (int) $argv[3];
    $va = Database::fetchAll('SELECT line_label, display_value FROM report_values WHERE report_run_id = ? ORDER BY sort_order', [$a]);
    $vb = Database::fetchAll('SELECT line_label, display_value FROM report_values WHERE report_run_id = ? ORDER BY sort_order', [$b]);
    $mapB = [];
    foreach ($vb as $v) {
        $mapB[$v['line_label']] = $v;
    }
    $diff = 0;
    foreach ($va as $v) {
        $other = $mapB[$v['line_label']] ?? null;
        if (!$other) {
            echo "仅 run{$a} 有: {$v['line_label']} = {$v['display_value']}\n";
            $diff++;
            continue;
        }
        if ((string) $v['display_value'] !== (string) $other['display_value']) {
            echo "不一致: {$v['line_label']}  run{$a}={$v['display_value']}  run{$b}={$other['display_value']}\n";
            $diff++;
        }
        unset($mapB[$v['line_label']]);
    }
    foreach ($mapB as $label => $v) {
        echo "仅 run{$b} 有: {$label} = {$v['display_value']}\n";
        $diff++;
    }
    echo $diff === 0 ? "两个 run 数值完全一致\n" : "共 {$diff} 处差异\n";
}
