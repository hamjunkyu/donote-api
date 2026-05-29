"""환경변수 기반 애플리케이션 설정."""

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """.env 파일에서 로딩하는 애플리케이션 설정."""

    DATABASE_URL: str
    TEST_DATABASE_URL: str = "postgresql://postgres:1234@localhost:5432/donote_test"
    SECRET_KEY: str
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7

    model_config = {"env_file": ".env"}


settings = Settings()
