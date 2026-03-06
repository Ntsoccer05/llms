以下は **現在の requirements.txt をベースに、このプロジェクト要件（Notion / Redis / DB / Worker / Git / LLM / Streamlit）を満たす形に整理した提案版**です。
既存のものを活かしつつ **不足分だけ追加**しています。

---

# requirements.txt（提案）

```txt
# ==========================================
# Web Framework & Server
# ==========================================
fastapi
uvicorn

# ==========================================
# UI
# ==========================================
streamlit

# ==========================================
# Validation / Settings
# ==========================================
pydantic
pydantic-settings
python-dotenv

# ==========================================
# HTTP Client
# ==========================================
httpx

# ==========================================
# Database
# ==========================================
sqlalchemy
asyncpg
alembic

# ==========================================
# Redis / Cache / Queue
# ==========================================
redis
arq

# ==========================================
# LLM / Agent Framework
# ==========================================
langchain
langchain-core
langgraph
langgraph-checkpoint
langgraph-prebuilt
langgraph-sdk

# ==========================================
# LLM Provider
# ==========================================
openai
tiktoken

# ==========================================
# Git operations
# ==========================================
gitpython

# ==========================================
# Diff generation
# ==========================================
unidiff

# ==========================================
# Markdown / HTML
# ==========================================
markdown-it-py
beautifulsoup4

# ==========================================
# Utilities
# ==========================================
python-slugify
orjson
loguru

# ==========================================
# Templates / Config
# ==========================================
Jinja2
json5
```

---

# 追加した主なライブラリと理由

## Streamlit

UI

用途

* タスクID入力
* HITLボタン
* requirement.mdダウンロード
* diff.patchダウンロード
* アコーディオンログ

---

## httpx

Notion API 呼び出し用

```python
async with httpx.AsyncClient() as client:
    await client.get(url)
```

FastAPIは async なので `requests` ではなく **httpx推奨**

---

## SQLAlchemy / asyncpg / alembic

DB

用途

* Folder
* Prefix
* Job
* Artifact
* Log

---

## Redis + arq

用途

* キャッシュ
* Worker queue
* debounce

`arq`は FastAPIと相性が良い async worker

---

## openai / tiktoken

LLM

用途

* slug生成
* requirement.md生成
* diff生成

---

## GitPython

Git操作

```python
Repo(path).git.checkout("-b", branch)
```

---

## unidiff

diff patch生成

---

## markdown-it-py

Notion blocks → Markdown

---

## python-slugify

branch slug生成

---

## orjson

高速JSON

FastAPIで `ORJSONResponse` に使える

---

## loguru

構造化ログ

---

# 現状の requirements と統合すると

あなたの現在のもの

```txt
fastapi
uvicorn
python-dotenv
pydantic-settings
Jinja2
json5

langchain
langchain-core
langgraph
langgraph-checkpoint
langgraph-prebuilt
langgraph-sdk
```

これは

**AIエージェント部分はすでにかなり良い構成**です。

不足しているのは主に

* UI
* DB
* Cache
* Worker
* Notion API通信
* Git
* Markdown
* Diff

の部分です。

---

# 最終おすすめ requirements.txt（シンプル版）

もし **AIエージェント用として最もバランスのいい構成**にするとこうなります。

```txt
fastapi
uvicorn
streamlit

pydantic
pydantic-settings
python-dotenv

httpx

sqlalchemy
asyncpg
alembic

redis
arq

langchain
langchain-core
langgraph
langgraph-checkpoint
langgraph-prebuilt
langgraph-sdk

openai
tiktoken

gitpython
unidiff

markdown-it-py
beautifulsoup4

python-slugify
orjson
loguru

Jinja2
json5
```

---

# もしさらにプロダクション寄りにするなら（おすすめ）

追加すると良いもの

```txt
# observability
prometheus-client
opentelemetry-api
opentelemetry-sdk

# retry
tenacity

# typing
typing-extensions
```

---

もし希望あれば次に **このプロジェクトで本当におすすめの構成（2026時点のAIエージェント標準）**として

* ディレクトリ構成
* FastAPI構成
* LangGraph構成
* Worker構成
* キャッシュ層
* Agent tool設計

まで含めた **フルアーキテクチャ図**を書きます。
今回の要件だと **LangGraphを中心に据えるとかなり綺麗な設計になります。**
