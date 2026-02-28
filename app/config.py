from pydantic_settings import BaseSettings, SettingsConfigDict
from functools import lru_cache

class Settings(BaseSettings):
  NOTION_API_KEY: str
  NOTION_API_URL: str
  NOTION_DATABASE_ID: str
  NOTION_DATASOURCE_ID: str

  model_config = SettingsConfigDict(env_file=".env")

@lru_cache()
def get_settings():
  return Settings()