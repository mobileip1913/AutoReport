<?php

declare(strict_types=1);

namespace App;

use PDO;

/**
 * PDO 封装：MySQL / SQLite 双支持，与 Python 版 app/database.py 对等。
 */
final class Database
{
    private static ?PDO $pdo = null;
    private static string $driver = 'mysql';

    public static function pdo(): PDO
    {
        if (self::$pdo !== null) {
            return self::$pdo;
        }
        $cfg = Config::get();

        if ($cfg->mysqlHost !== '' && $cfg->mysqlPassword !== '') {
            self::$driver = 'mysql';
            $dsn = sprintf(
                'mysql:host=%s;port=%d;dbname=%s;charset=utf8mb4',
                $cfg->mysqlHost,
                $cfg->mysqlPort,
                $cfg->mysqlDatabase
            );
            self::$pdo = new PDO($dsn, $cfg->mysqlUser, $cfg->mysqlPassword, [
                PDO::ATTR_ERRMODE => PDO::ERRMODE_EXCEPTION,
                PDO::ATTR_DEFAULT_FETCH_MODE => PDO::FETCH_ASSOC,
                PDO::ATTR_EMULATE_PREPARES => false,
            ]);
        } else {
            self::$driver = 'sqlite';
            $path = Config::rootDir() . '/data/autoreport.db';
            if (str_starts_with($cfg->databaseUrl, 'sqlite')) {
                $rel = preg_replace('#^sqlite:///#', '', $cfg->databaseUrl);
                if ($rel !== '' && $rel !== $cfg->databaseUrl) {
                    $path = str_starts_with($rel, './') ? Config::rootDir() . substr($rel, 1) : $rel;
                }
            }
            @mkdir(dirname($path), 0777, true);
            self::$pdo = new PDO('sqlite:' . $path, null, null, [
                PDO::ATTR_ERRMODE => PDO::ERRMODE_EXCEPTION,
                PDO::ATTR_DEFAULT_FETCH_MODE => PDO::FETCH_ASSOC,
            ]);
        }
        return self::$pdo;
    }

    public static function driver(): string
    {
        self::pdo();
        return self::$driver;
    }

    public static function isSqlite(): bool
    {
        return self::driver() === 'sqlite';
    }

    /** @return array<int, array<string, mixed>> */
    public static function fetchAll(string $sql, array $params = []): array
    {
        $stmt = self::pdo()->prepare($sql);
        $stmt->execute($params);
        return $stmt->fetchAll();
    }

    /** @return array<string, mixed>|null */
    public static function fetchOne(string $sql, array $params = []): ?array
    {
        $stmt = self::pdo()->prepare($sql);
        $stmt->execute($params);
        $row = $stmt->fetch();
        return $row === false ? null : $row;
    }

    public static function fetchValue(string $sql, array $params = []): mixed
    {
        $stmt = self::pdo()->prepare($sql);
        $stmt->execute($params);
        $val = $stmt->fetchColumn();
        return $val === false ? null : $val;
    }

    public static function execute(string $sql, array $params = []): int
    {
        $stmt = self::pdo()->prepare($sql);
        $stmt->execute($params);
        return $stmt->rowCount();
    }

    /** 插入一行并返回自增 id */
    public static function insert(string $table, array $data): int
    {
        $cols = array_keys($data);
        $colSql = implode(', ', array_map(fn($c) => "`$c`", $cols));
        $ph = implode(', ', array_map(fn($c) => ":$c", $cols));
        $stmt = self::pdo()->prepare("INSERT INTO `$table` ($colSql) VALUES ($ph)");
        $stmt->execute($data);
        return (int) self::pdo()->lastInsertId();
    }

    /** 按 id 更新一行 */
    public static function updateById(string $table, int $id, array $data): void
    {
        if (!$data) {
            return;
        }
        $sets = implode(', ', array_map(fn($c) => "`$c` = :$c", array_keys($data)));
        $data['__id'] = $id;
        $stmt = self::pdo()->prepare("UPDATE `$table` SET $sets WHERE id = :__id");
        $stmt->execute($data);
    }

    public static function tableExists(string $table): bool
    {
        if (self::isSqlite()) {
            return (bool) self::fetchValue(
                "SELECT name FROM sqlite_master WHERE type='table' AND name = ?",
                [$table]
            );
        }
        return (bool) self::fetchValue(
            'SELECT table_name FROM information_schema.tables WHERE table_schema = DATABASE() AND table_name = ?',
            [$table]
        );
    }

    /** @return string[] */
    public static function tableColumns(string $table): array
    {
        if (!self::tableExists($table)) {
            return [];
        }
        if (self::isSqlite()) {
            $rows = self::fetchAll("PRAGMA table_info(`$table`)");
            return array_map(fn($r) => (string) $r['name'], $rows);
        }
        $rows = self::fetchAll(
            'SELECT column_name AS name FROM information_schema.columns WHERE table_schema = DATABASE() AND table_name = ?',
            [$table]
        );
        return array_map(fn($r) => (string) $r['name'], $rows);
    }

    /** JSON 列解码（DB 中存 JSON/TEXT） */
    public static function jsonDecode(mixed $value, mixed $default = null): mixed
    {
        if ($value === null || $value === '') {
            return $default;
        }
        if (is_array($value)) {
            return $value;
        }
        $decoded = json_decode((string) $value, true);
        return $decoded === null && trim((string) $value) !== 'null' ? $default : $decoded;
    }

    public static function jsonEncode(mixed $value): ?string
    {
        if ($value === null) {
            return null;
        }
        return json_encode($value, JSON_UNESCAPED_UNICODE);
    }

    /** UTC 当前时间（与 SQLAlchemy datetime.utcnow 存储格式一致） */
    public static function utcNow(): string
    {
        return gmdate('Y-m-d H:i:s');
    }
}
