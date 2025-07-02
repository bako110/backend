from pydantic_settings import BaseSettings
from pydantic import Field

class Settings(BaseSettings):
    POSTGRES_URL: str = Field(..., env="POSTGRES_URL")
    MONGO_URL: str = Field(..., env="MONGO_URL")
    MONGO_DB: str = Field(..., env="MONGO_DB")
    JWT_SECRET: str = Field(..., env="JWT_SECRET")
    ALGORITHM: str = Field(default="HS256", env="ALGORITHM")
    ACCESS_TOKEN_EXPIRE_MINUTES: int = Field(default=60, env="ACCESS_TOKEN_EXPIRE_MINUTES")
    MAIL_USERNAME: str = Field(..., env="MAIL_USERNAME")
    MAIL_PASSWORD: str = Field(..., env="MAIL_PASSWORD")
    MAIL_FROM: str = Field(..., env="MAIL_FROM")
    MAIL_PORT: int = Field(..., env="MAIL_PORT")
    MAIL_SERVER: str = Field(..., env="MAIL_SERVER")

    class Config:
        env_file = ".env"

settings = Settings()
