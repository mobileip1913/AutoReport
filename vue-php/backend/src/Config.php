<?php

declare(strict_types=1);

namespace App;

/**
 * 应用配置。生产环境通过环境变量或 .env 注入，勿将密码提交到仓库。
 * 与 Python 版 app/config.py 对等。
 */
final class Config
{
    private static ?Config $instance = null;

    public string $databaseUrl;
    public string $uploadDir;
    public string $filesDir;

    public string $mysqlHost;
    public int $mysqlPort;
    public string $mysqlUser;
    public string $mysqlPassword;
    public string $mysqlDatabase;

    private function __construct()
    {
        $root = self::rootDir();
        if (is_file($root . '/.env')) {
            $dotenv = \Dotenv\Dotenv::createImmutable($root);
            $dotenv->safeLoad();
        }

        $env = fn(string $key, string $default = '') => $_ENV[$key] ?? getenv($key) ?: $default;

        $this->databaseUrl = $env('DATABASE_URL', 'sqlite:///./data/autoreport.db');
        $this->uploadDir = $env('UPLOAD_DIR', $root . '/data/uploads');
        $this->filesDir = $env('FILES_DIR', dirname($root) . '/files');
        $this->mysqlHost = $env('MYSQL_HOST', '127.0.0.1');
        $this->mysqlPort = (int) $env('MYSQL_PORT', '3306');
        $this->mysqlUser = $env('MYSQL_USER', 'autoreport');
        $this->mysqlPassword = $env('MYSQL_PASSWORD', '');
        $this->mysqlDatabase = $env('MYSQL_DATABASE', 'autoreport');
    }

    public static function get(): Config
    {
        return self::$instance ??= new Config();
    }

    /** php-backend 目录绝对路径 */
    public static function rootDir(): string
    {
        return dirname(__DIR__);
    }
}
