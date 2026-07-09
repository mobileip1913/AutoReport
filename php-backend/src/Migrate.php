<?php

declare(strict_types=1);

namespace App;

/**
 * 建表与增量迁移，与 Python 版 models.py + services/migrate.py 对等。
 * 表结构与 SQLAlchemy 生成的 DDL 兼容（可与 Python 后端共用同一 MySQL 库）。
 */
final class Migrate
{
    public static function runMigrations(): void
    {
        self::createTables();
        self::ensurePartColumns();
        self::ensureDataSourceColumns();
        self::ensureReportRunColumns();
        self::ensureFieldMappingReportColumns();
        self::ensureReportValueColumns();
        self::ensureStoreColumns();
    }

    private static function ddl(string $mysql, string $sqlite): string
    {
        return Database::isSqlite() ? $sqlite : $mysql;
    }

    private static function createTables(): void
    {
        $pk = self::ddl('INT NOT NULL AUTO_INCREMENT PRIMARY KEY', 'INTEGER PRIMARY KEY AUTOINCREMENT');
        $json = self::ddl('JSON', 'TEXT');
        $suffix = self::ddl(' ENGINE=InnoDB DEFAULT CHARSET=utf8mb4', '');
        $pdo = Database::pdo();

        $tables = [
            "CREATE TABLE IF NOT EXISTS data_sources (
                id $pk,
                name VARCHAR(100),
                platform VARCHAR(50),
                description TEXT,
                config $json,
                created_at DATETIME
            )$suffix",
            "CREATE TABLE IF NOT EXISTS accounts (
                id $pk,
                login_name VARCHAR(50) NOT NULL UNIQUE,
                display_name VARCHAR(100) NOT NULL,
                created_at DATETIME
            )$suffix",
            "CREATE TABLE IF NOT EXISTS stores (
                id $pk,
                name VARCHAR(100) NOT NULL,
                platform VARCHAR(50) NOT NULL,
                data_source_id INT NOT NULL UNIQUE,
                created_at DATETIME
            )$suffix",
            "CREATE TABLE IF NOT EXISTS account_stores (
                id $pk,
                account_id INT NOT NULL,
                store_id INT NOT NULL,
                UNIQUE (account_id, store_id)
            )$suffix",
            "CREATE TABLE IF NOT EXISTS data_imports (
                id $pk,
                data_source_id INT,
                file_name VARCHAR(255),
                report_date VARCHAR(10),
                store_name VARCHAR(100),
                status VARCHAR(20),
                row_count INT,
                created_at DATETIME
            )$suffix",
            "CREATE TABLE IF NOT EXISTS data_rows (
                id $pk,
                data_import_id INT,
                sheet_name VARCHAR(100),
                row_data $json
            )$suffix",
            "CREATE TABLE IF NOT EXISTS catalog_files (
                id $pk,
                data_source_id INT,
                keyword VARCHAR(100) NOT NULL,
                file_label VARCHAR(255) NOT NULL,
                file_name VARCHAR(255) NOT NULL,
                is_active BOOLEAN,
                created_at DATETIME
            )$suffix",
            "CREATE TABLE IF NOT EXISTS catalog_sheets (
                id $pk,
                file_id INT,
                sheet_name VARCHAR(100) NOT NULL,
                fact_table VARCHAR(100) NOT NULL,
                is_active BOOLEAN
            )$suffix",
            "CREATE TABLE IF NOT EXISTS catalog_columns (
                id $pk,
                sheet_id INT,
                header_name VARCHAR(200) NOT NULL,
                db_column VARCHAR(100) NOT NULL,
                column_aliases $json,
                data_type VARCHAR(20),
                is_active BOOLEAN
            )$suffix",
            "CREATE TABLE IF NOT EXISTS etl_batches (
                id $pk,
                data_source_id INT,
                store_name VARCHAR(100) NOT NULL,
                source_desc VARCHAR(255),
                row_counts $json,
                status VARCHAR(20),
                created_at DATETIME
            )$suffix",
            "CREATE TABLE IF NOT EXISTS logical_fields (
                id $pk,
                code VARCHAR(50) UNIQUE,
                name VARCHAR(100),
                data_type VARCHAR(20),
                description TEXT
            )$suffix",
            "CREATE TABLE IF NOT EXISTS field_mappings (
                id $pk,
                data_source_id INT,
                logical_field_id INT,
                line_type VARCHAR(10),
                label VARCHAR(100),
                line_code VARCHAR(50),
                report_group VARCHAR(100),
                sort_order INT,
                expression TEXT,
                format_type VARCHAR(20),
                is_highlight BOOLEAN,
                owner_id INT,
                description TEXT,
                sheet_name VARCHAR(100),
                column_header VARCHAR(100),
                aliases $json,
                aggregation VARCHAR(20),
                UNIQUE (data_source_id, line_code)
            )$suffix",
            "CREATE TABLE IF NOT EXISTS field_mapping_parts (
                id $pk,
                mapping_id INT,
                sort_order INT,
                label VARCHAR(100),
                source_file_keyword VARCHAR(100),
                sheet_name VARCHAR(100),
                column_header VARCHAR(100),
                aliases $json,
                combine_op VARCHAR(10),
                aggregation VARCHAR(20),
                dedup_keys $json,
                date_filter_column VARCHAR(100),
                date_format VARCHAR(10),
                row_filters $json,
                exclude_sample BOOLEAN,
                exclude_review BOOLEAN,
                join_to_orders BOOLEAN,
                join_keys $json,
                only_sample BOOLEAN,
                sources $json,
                ref_field_code VARCHAR(50)
            )$suffix",
            "CREATE TABLE IF NOT EXISTS mapping_logs (
                id $pk,
                data_import_id INT,
                level VARCHAR(10),
                message TEXT,
                context $json,
                created_at DATETIME
            )$suffix",
            "CREATE TABLE IF NOT EXISTS report_templates (
                id $pk,
                name VARCHAR(100),
                description TEXT,
                status VARCHAR(20),
                version INT,
                owner VARCHAR(50),
                published_at DATETIME,
                created_at DATETIME,
                updated_at DATETIME
            )$suffix",
            "CREATE TABLE IF NOT EXISTS template_lines (
                id $pk,
                template_id INT,
                sort_order INT,
                label VARCHAR(100),
                expression TEXT,
                format_type VARCHAR(20),
                is_highlight BOOLEAN
            )$suffix",
            "CREATE TABLE IF NOT EXISTS report_runs (
                id $pk,
                template_id INT,
                data_source_id INT,
                report_date VARCHAR(10),
                store_name VARCHAR(100),
                is_test BOOLEAN,
                status VARCHAR(20),
                created_at DATETIME
            )$suffix",
            "CREATE TABLE IF NOT EXISTS report_values (
                id $pk,
                report_run_id INT,
                mapping_id INT,
                line_code VARCHAR(50),
                line_label VARCHAR(100),
                expression TEXT,
                raw_value DOUBLE,
                computed_raw_value DOUBLE,
                display_value VARCHAR(50),
                is_overridden BOOLEAN,
                sort_order INT,
                report_group VARCHAR(100)
            )$suffix",
        ];
        foreach ($tables as $sql) {
            $pdo->exec($sql);
        }
    }

    private static function addColumnIfMissing(string $table, string $column, string $ddlType): void
    {
        if (!Database::tableExists($table)) {
            return;
        }
        $cols = Database::tableColumns($table);
        if (!in_array($column, $cols, true)) {
            Database::pdo()->exec("ALTER TABLE `$table` ADD COLUMN `$column` $ddlType");
        }
    }

    private static function ensurePartColumns(): void
    {
        $json = Database::isSqlite() ? 'TEXT' : 'JSON';
        self::addColumnIfMissing('field_mapping_parts', 'date_filter_column', 'VARCHAR(100)');
        self::addColumnIfMissing('field_mapping_parts', 'date_format', 'VARCHAR(10)');
        self::addColumnIfMissing('field_mapping_parts', 'row_filters', $json);
        self::addColumnIfMissing('field_mapping_parts', 'exclude_sample', 'BOOLEAN DEFAULT 0');
        self::addColumnIfMissing('field_mapping_parts', 'exclude_review', 'BOOLEAN DEFAULT 0');
        self::addColumnIfMissing('field_mapping_parts', 'join_to_orders', 'BOOLEAN DEFAULT 0');
        self::addColumnIfMissing('field_mapping_parts', 'sources', $json);
        self::addColumnIfMissing('field_mapping_parts', 'ref_field_code', 'VARCHAR(50)');
        self::addColumnIfMissing('field_mapping_parts', 'only_sample', 'BOOLEAN DEFAULT 0');
        self::addColumnIfMissing('field_mapping_parts', 'join_keys', $json);
        self::addColumnIfMissing('field_mapping_parts', 'benchmark_keys', $json);
        self::addColumnIfMissing('field_mapping_parts', 'exclude_same_day_refund', 'BOOLEAN DEFAULT 0');
    }

    private static function ensureDataSourceColumns(): void
    {
        $json = Database::isSqlite() ? 'TEXT' : 'JSON';
        self::addColumnIfMissing('data_sources', 'config', $json);
    }

    private static function ensureReportRunColumns(): void
    {
        self::addColumnIfMissing('report_runs', 'data_source_id', 'INTEGER');
        self::addColumnIfMissing('report_runs', 'template_id', 'INTEGER');
    }

    private static function ensureFieldMappingReportColumns(): void
    {
        self::addColumnIfMissing('field_mappings', 'description', 'TEXT');
        self::addColumnIfMissing('field_mappings', 'line_type', 'VARCHAR(10)');
        self::addColumnIfMissing('field_mappings', 'label', 'VARCHAR(100)');
        self::addColumnIfMissing('field_mappings', 'line_code', 'VARCHAR(50)');
        self::addColumnIfMissing('field_mappings', 'report_group', 'VARCHAR(100)');
        self::addColumnIfMissing('field_mappings', 'sort_order', 'INTEGER DEFAULT 0');
        self::addColumnIfMissing('field_mappings', 'expression', 'TEXT');
        self::addColumnIfMissing('field_mappings', 'format_type', 'VARCHAR(20)');
        self::addColumnIfMissing('field_mappings', 'is_highlight', 'BOOLEAN DEFAULT 0');
        self::addColumnIfMissing('field_mappings', 'owner_id', 'INTEGER');
    }

    private static function ensureReportValueColumns(): void
    {
        self::addColumnIfMissing('report_values', 'report_group', 'VARCHAR(100)');
        self::addColumnIfMissing('report_values', 'line_code', 'VARCHAR(50)');
        self::addColumnIfMissing('report_values', 'mapping_id', 'INTEGER');
        self::addColumnIfMissing('report_values', 'computed_raw_value', Database::isSqlite() ? 'FLOAT' : 'DOUBLE');
        self::addColumnIfMissing('report_values', 'is_overridden', 'BOOLEAN DEFAULT 0');
    }

    private static function ensureStoreColumns(): void
    {
        self::addColumnIfMissing('stores', 'production_store_id', 'INTEGER');
        self::addColumnIfMissing('stores', 'shop_code', 'VARCHAR(50)');
    }
}
