<?php

/**
 * 初始化脚本：建表迁移 + 种子数据 + 规则同步。
 * 对等 Python 版 FastAPI 的 on_startup 逻辑，部署后运行一次即可：
 *   php bin/init.php
 */

declare(strict_types=1);

require dirname(__DIR__) . '/vendor/autoload.php';

use App\Bootstrap;

echo "[init] 开始初始化数据库与种子数据...\n";
Bootstrap::startup();
echo "[init] 完成。\n";
