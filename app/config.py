from typing import Optional
from pydantic_settings import BaseSettings, SettingsConfigDict
from functools import lru_cache


class Settings(BaseSettings):
  NOTION_API_KEY: str
  NOTION_API_URL: str
  NOTION_DATABASE_ID: str
  NOTION_DATASOURCE_ID: str
  MODEL_ID: str
  AWS_ACCESS_KEY_ID: str
  AWS_SECRET_ACCESS_KEY: str
  AWS_DEFAULT_REGION: str
  GITHUB_TOKEN: str = ""  # 未設定時はブランチ作成・チェックアウトはスキップまたはエラー
  GITHUB_REPO: Optional[str] = None  # owner/repo（例: myorg/my-repo）。ブランチ作成時に使用
  REPO_PATH: Optional[str] = None    # ローカルリポジトリのパス。チェックアウト時に使用
  BACKEND_URL: Optional[str] = None  # Streamlit から API を叩くときのベース URL（例: http://localhost:8000）
  BACKEND_HOST: Optional[str] = None # Docker 用。指定時は http://{BACKEND_HOST}:{BACKEND_PORT} で接続（例: backend）
  BACKEND_PORT: int = 8000          # バックエンドの待ち受けポート（BACKEND_HOST と組み合わせて URL を組むとき用）
  NOTIFY_DIR: Optional[str] = None  # 通知 JSON の書き出し先（watcher が win11toast で表示）。Docker では /notify 等
  NOTIFY_BACKEND_URL: Optional[str] = None  # watcher がトーストから API を叩くときの URL（例: http://localhost:8000）

  model_config = SettingsConfigDict(
    env_file=".env",
    extra="ignore",  # .env の未定義キーを無視（大文字/小文字の差で extra エラーになるのを防ぐ）
  )

@lru_cache()
def get_settings():
  return Settings()