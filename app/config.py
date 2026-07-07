from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """应用配置。生产环境通过环境变量或 .env 注入，勿将密码提交到仓库。"""

    database_url: str = "sqlite:///./data/autoreport.db"
    upload_dir: str = "./data/uploads"
    sample_dir: str = "./sample_data"
    files_dir: str = "./files"
    schemas_dir: str = "./data/schemas"

    mysql_host: str = "127.0.0.1"
    mysql_port: int = 3306
    mysql_user: str = "autoreport"
    mysql_password: str = ""
    mysql_database: str = "autoreport"

    class Config:
        env_file = ".env"
        extra = "ignore"


settings = Settings()
