# AI-Agent（Notion × GitHub HITL）

Notion のタスクからブランチ名を取得し、Human-in-the-loop（HITL）で GitHub ブランチ作成・チェックアウトと requirement.md の LLM 生成を行うアプリケーションです。

---

## 概要

- **Streamlit** で GUI を提供し、**FastAPI** が Notion API・GitHub API・LLM（AWS Bedrock）を呼び出す構成です。
- タスクID（例: ES-1）を入力すると Notion からページ詳細と提案ブランチ名を取得。**承認**後に GitHub にブランチを作成し、ローカルでチェックアウト。続けて **requirement.md** を LLM で生成できます。
- ブラウザを閉じていても **Windows デスクトップ通知（トースト）** で承認・却下できるよう、通知 watcher（`scripts/win_notify_watcher.py`）を併用できます。

---

## 主な機能・仕様

| 機能 | 説明 |
|------|------|
| ページ詳細＋ブランチ名取得 | Notion のタスクIDからページ本文（マークダウン）を取得し、タスク名・バグタグ等から GitHub 用ブランチ名（例: `feature/1/slug`）を生成 |
| ブランチ作成・チェックアウト | ユーザーが「承認」すると、GitHub にブランチを作成し、指定リポジトリで `git checkout` を実行（HITL） |
| requirement.md 生成 | Notion 本文と対象フォルダ構成を LLM（雛形ベース）に渡し、requirement.md を生成。ストリーミング対応（思考過程＋本文） |
| デスクトップ通知連携 | Streamlit が `NOTIFY_DIR` に JSON を書き出し、Windows 上の watcher が win11toast で表示。トーストの「承認」「却下」でバックエンド API を呼び、Streamlit がポーリングで結果を反映 |

---

## アーキテクチャ

```
[Streamlit GUI]  ←→  [FastAPI バックエンド]  ←→  Notion API / GitHub API / AWS Bedrock
       │                        │
       └── NOTIFY_DIR (JSON) ───┴──→ [win_notify_watcher] → Windows トースト
```

- **バックエンド**: FastAPI。ルートは `api/routers` で notion / branch / requirement に分割。
- **フロント**: Streamlit。`ui/workflows/hitl` で HITL ワークフローを実装。
- **通知**: Streamlit が `NOTIFY_DIR` に JSON を出力。Windows で `scripts/win_notify_watcher.py` が監視し、win11toast で表示。トーストのボタンでバックエンドの `/branch/checkout` や `/requirement/ready/ack` を呼ぶ。

---

## 必要環境

- Python 3.x（3.10 以上推奨）
- Notion API キー・データベースID・データソースID
- AWS 認証情報（Bedrock 用）・モデルID（例: Claude）
- （ブランチ作成・チェックアウトを使う場合）GitHub トークン・リポジトリ（owner/repo）
- （デスクトップ通知を使う場合）Windows + `pip install win11toast`

---

## セットアップ

### 1. リポジトリと依存関係

```bash
git clone <this-repo>
cd AI-Agent
pip install -r requirements.txt
```

### 2. 環境変数

プロジェクトルートに `.env` を用意します。`.env.example` をコピーして編集してください。

```bash
cp .env.example .env
# .env を編集して NOTION_*, AWS_*, MODEL_ID 等を設定
```

必須の主な項目:

| 変数 | 説明 |
|------|------|
| NOTION_API_KEY | Notion の API キー |
| NOTION_API_URL | 例: `https://api.notion.com/v1` |
| NOTION_DATABASE_ID / NOTION_DATASOURCE_ID | 使用する DB・データソース |
| MODEL_ID | Bedrock のモデル ID（例: Claude） |
| AWS_ACCESS_KEY_ID / AWS_SECRET_ACCESS_KEY / AWS_DEFAULT_REGION | AWS 認証 |

オプション（ブランチ作成・チェックアウト）:

- GITHUB_TOKEN / GITHUB_REPO（例: `owner/repo`）
- REPO_PATH（git リポジトリの絶対パス。Docker 時は compose で `/workspace` を渡す想定）

オプション（通知・接続先）:

- NOTIFY_DIR / NOTIFY_BACKEND_URL（通知用。Docker では NOTIFY_DIR=/notify 等）
- BACKEND_URL（Streamlit から見たバックエンド URL。ローカル: `http://localhost:8000`）
- BACKEND_HOST / BACKEND_PORT（Docker 内で Streamlit がバックエンドに繋ぐときのホスト名・ポート）

### 3. Docker で起動（推奨）

```bash
docker compose up -d
```

- バックエンド: `http://localhost:8000`（デフォルト）
- Streamlit: `http://localhost:8501`（デフォルト）

ルートの `.env` が `env_file` で読み込まれ、コンテナに渡されます。ポートや NOTIFY_* 等は `.env` で上書き可能です。

### 4. ローカルで起動

**バックエンド**

```bash
cd app
uvicorn main:app --host 0.0.0.0 --port 8000
```

**Streamlit**

別ターミナルで:

```bash
cd app
streamlit run streamlit_app.py --server.port 8501
```

`.env` は `app/` に置くか、プロジェクトルートに置いて `cd app` で起動する場合はパスを調整してください。

### 5. デスクトップ通知（Windows）

Docker の `notify_data` をマウントしている場合、Windows 側で watcher を起動すると、ブラウザを閉じていてもトーストで承認・却下できます。

```bash
pip install win11toast
python scripts/win_notify_watcher.py notify_data
```

または環境変数で監視フォルダを指定:

```bash
set NOTIFY_DIR=C:\path\to\notify_data
python scripts/win_notify_watcher.py
```

Docker でバックエンドに接続するときは、watcher からは `localhost` で届くように `.env` の `NOTIFY_BACKEND_URL=http://localhost:8000` を設定してください。

---

## 使い方（HITL フロー）

1. Streamlit を開き、**「ページ詳細＋ブランチ名取得」** を選択。
2. **ベースブランチ**（例: main）・**タスクID**（例: ES-1）・**リポジトリのパス**（またはフォルダ選択）を入力。
3. **「実行（ブランチ名を取得）」** を押す。バックエンドが Notion からページ詳細を取得し、ブランチ名を表示。デスクトップ通知も出る（watcher 起動時）。
4. **承認** または **却下** を選択。
   - 承認: バックエンドが GitHub にブランチを作成し、`REPO_PATH` で `git checkout`。完了後「requirement.md を生成しますか？」通知が出る。
   - 却下: チェックアウトは行わないが、requirement.md 生成は手動で可能。
5. **requirement.md を生成**: 画面上のボタン、またはトーストの「承認」で生成開始。LLM の思考過程と本文がストリーミング表示され、完了後にダウンロード可能。
6. **「クリアして最初から」** で状態とバックエンド側の承認・チェックアウト結果をリセット。

---

## API 一覧（バックエンド）

| メソッド | パス | 説明 |
|----------|------|------|
| POST | /search/datasource | タスクIDで Notion データソースを検索（内部用） |
| GET | /page/detail | タスクIDからページ詳細・マークダウン・ブランチ名を取得 |
| GET | /branch/checkout/status | 直近のチェックアウト結果（Streamlit 連携） |
| POST | /branch/checkout/status/clear | チェックアウト結果をクリア（「クリアして最初から」用） |
| POST | /branch/checkout | ブランチ作成＋ローカル checkout |
| POST | /requirement/ready/ack | トースト「requirement.md を生成しますか？」の承認・却下を記録 |
| GET | /requirement/ready/ack | 直近の承認・却下を返す |
| POST | /requirement/ready/ack/clear | 承認・却下をクリア |
| POST | /requirement/generate | requirement.md を一括生成 |
| POST | /requirement/generate/stream | requirement.md をストリーミング生成（SSE） |

---

## 環境変数一覧

`.env.example` を参照してください。主なものは次のとおりです。

- **アプリ必須**: NOTION_API_KEY, NOTION_API_URL, NOTION_DATABASE_ID, NOTION_DATASOURCE_ID, MODEL_ID, AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY, AWS_DEFAULT_REGION
- **オプション**: GITHUB_TOKEN, GITHUB_REPO, REPO_PATH, BACKEND_URL, BACKEND_HOST, BACKEND_PORT, NOTIFY_DIR, NOTIFY_BACKEND_URL
- **Docker Compose**: APP_ENV, APP_HOST_PORT, STREAMLIT_HOST_PORT, STREAMLIT_PORT, STREAMLIT_ADDRESS

---

## プロジェクト構成（抜粋）

```
AI-Agent/
├── app/
│   ├── main.py              # FastAPI アプリ（ルーター登録のみ）
│   ├── config.py            # 設定（pydantic-settings）
│   ├── streamlit_app.py     # Streamlit エントリ
│   ├── api/
│   │   ├── schemas.py       # リクエスト/レスポンス型
│   │   ├── state.py         # HITL 用インメモリ状態
│   │   └── routers/        # notion, branch, requirement
│   ├── services/            # Notion 取得・ブランチ checkout ロジック
│   ├── ui/
│   │   ├── workflows/       # hitl ワークフロー＋ヘルパー
│   │   ├── config.py        # バックエンド URL 取得
│   │   └── notifications.py # 通知 JSON 出力
│   ├── utils/               # requirement 生成・ブランチ名・フォーマット等
│   └── prompts/             # requirement 雛形
├── docker/
│   ├── Dockerfile
│   └── entrypoint.sh
├── scripts/
│   └── win_notify_watcher.py # Windows トースト通知 watcher
├── docker-compose.yaml
├── .env.example
└── requirements.txt
```
