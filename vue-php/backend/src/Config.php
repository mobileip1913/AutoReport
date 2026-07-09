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
        $filesFromEnv = trim($env('FILES_DIR', ''));
        $this->filesDir = $filesFromEnv !== '' ? $filesFromEnv : self::defaultFilesDir($root);
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

    /**
     * 默认模板目录：优先含 日报模板.xlsx 的路径。
     * vue-php/backend → 先试 vue-php/files，再回退仓库根 files/（与 Python ./files 一致）。
     */
    private static function defaultFilesDir(string $root): string
    {
        $template = '日报模板.xlsx';
        $candidates = [
            dirname($root) . '/files',
            dirname(dirname($root)) . '/files',
        ];
        foreach ($candidates as $dir) {
            if (is_file($dir . DIRECTORY_SEPARATOR . $template)) {
                return $dir;
            }
        }
        return $candidates[0];
    }
}
