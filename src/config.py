from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    qdrant_host: str = "http://localhost:6333"
    collection_name: str = "my_thoughts"
    api_key: str = ""

    class Config:
        env_file = ".env"


settings = Settings()
