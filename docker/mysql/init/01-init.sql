-- AutoReport MySQL 初始化（docker 首次启动时执行）
ALTER DATABASE autoreport CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;

GRANT ALL PRIVILEGES ON autoreport.* TO 'autoreport'@'%';
FLUSH PRIVILEGES;
