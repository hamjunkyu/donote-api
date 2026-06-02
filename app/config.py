"""환경변수 기반 애플리케이션 설정."""

from pydantic import model_validator
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """.env 파일에서 로딩하는 애플리케이션 설정."""

    DATABASE_URL: str
    TEST_DATABASE_URL: str = ""
    SECRET_KEY: str
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7
    CORS_ORIGINS: str = (
        "http://localhost:5173,http://127.0.0.1:5173,https://donote-frontend.vercel.app"
    )

    model_config = {"env_file": ".env"}

    @model_validator(mode="after")
    def _default_test_database_url(self):
        """TEST_DATABASE_URL 미지정 시 DATABASE_URL 의 DB 이름에 _test 를 붙여 파생한다."""
        if not self.TEST_DATABASE_URL:
            base, sep, name = self.DATABASE_URL.rstrip("/").rpartition("/")
            if sep and name:
                self.TEST_DATABASE_URL = f"{base}/{name}_test"
        return self

    @property
    def cors_origins_list(self) -> list[str]:
        """쉼표로 구분된 CORS_ORIGINS 를 리스트로 변환한다."""
        return [origin.strip() for origin in self.CORS_ORIGINS.split(",") if origin.strip()]


settings = Settings()
