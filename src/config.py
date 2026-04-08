from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    qdrant_host: str = "http://localhost:6333"
    collection_name: str = "my_thoughts"
    api_key: str = ""

    couchdb_url: str = "http://couchdb:5984"
    couchdb_user: str = ""
    couchdb_password: str = ""
    couchdb_db: str = "obsidian"

    class Config:
        env_file = ".env"


settings = Settings()
