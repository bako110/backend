from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    POSTGRES_URL: str
    MONGO_URL: str
    MONGO_DB: str

    JWT_SECRET: str
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60

    mail_username: str
    mail_password: str
    mail_from: str
    mail_port: int
    mail_server: str

    class Config:
        env_file = ".env"

settings = Settings()
