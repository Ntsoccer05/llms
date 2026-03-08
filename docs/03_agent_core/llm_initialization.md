# エージェントコア - LLM 初期化

## 📄 ファイル位置

```
chapter4/x_agent_core.py (行 1-68)
```

## 🚀 初期化フロー

```
1. 環境変数読み込み (.env)
        ↓
2. ツール定義
   - TavilySearch (Web 検索)
   - FileManagementToolkit (ファイル操作)
        ↓
3. ツール辞書作成 (tool_by_name)
        ↓
4. LLM 初期化 (init_chat_model)
        ↓
5. LLM にツールをバインド (bind_tools)
        ↓
6. システムプロンプト設定
        ↓
7. エージェント開始
```

## 📋 コード詳細

### 1. 環境変数の読み込み

```python
from dotenv import load_dotenv
load_dotenv()
```

**読み込まれる環境変数** (`.env` ファイルから):

```env
AWS_ACCESS_KEY_ID=your_key
AWS_SECRET_ACCESS_KEY=your_secret
AWS_DEFAULT_REGION=ap-northeast-1
TAVILY_API_KEY=your_tavily_key
```

**用途**:
- `AWS_*`: AWS Bedrock 認証
- `TAVILY_API_KEY`: Tavily Web 検索 API

### 2. ツール定義

#### 2.1 Web 検索ツール

```python
from langchain_tavily import TavilySearch

web_search = TavilySearch(max_results=2, topic="general")
```

**パラメータ**:
- `max_results=2`: 最大 2 件の検索結果を返す
- `topic="general"`: 一般的なトピック検索

**機能**: キーワードから Web ページを検索

#### 2.2 ファイル操作ツール

```python
from langchain_community.agent_toolkits import FileManagementToolkit

working_directory = "report"
file_toolkit = FileManagementToolkit(
  root_dir=str(working_directory),
  selected_tools=["write_file"]
)
write_file = file_toolkit.get_tools()[0]
```

**ポイント**:
- `root_dir="report"`: ファイル操作可能な場所は `report/` フォルダのみ
- `selected_tools=["write_file"]`: ファイル書き込みのみ許可（削除・読み込みなし）
- `get_tools()[0]`: ツールキットから最初のツール（write_file）を抽出

**機能**: HTML ファイルをディスクに保存

### 3. ツール辞書の作成

```python
tools = [web_search, write_file]

# ツール名をキーにしたディクショナリ
tool_by_name = {tool.name: tool for tool in tools}
```

**例**:
```python
tool_by_name = {
    "tavily_search_results_json": TavilySearch(...),
    "write_file": Tool(...)
}
```

**用途**: 実行時に ツール名から素早くツールを取得
```python
tool = tool_by_name["write_file"]
tool.invoke({"file_path": "output.html", "text": "<html>..."})
```

### 4. LLM 初期化

```python
from botocore.config import Config
from langchain.chat_models import init_chat_model

MODEL_ID = "jp.anthropic.claude-haiku-4-5-20251001-v1:0"

cfg = Config(
  read_timeout=300  # 5 分のタイムアウト
)

llm_with_tools = init_chat_model(
  model=MODEL_ID,
  model_provider="bedrock_converse",
  config=cfg
).bind_tools(tools)
```

**パラメータ解説**:

| パラメータ | 値 | 意味 |
|---|---|---|
| `model` | `jp.anthropic.claude-haiku-4-5-...` | AWS Bedrock 上の Claude Haiku 4.5 |
| `model_provider` | `bedrock_converse` | AWS Bedrock API を使用 |
| `config.read_timeout` | `300` | 5 分以上かかる処理のタイムアウト時間 |

**`.bind_tools(tools)`**: LLM にツール情報を教え、ツール呼び出しを可能にする

**結果**: `llm_with_tools` は ツール呼び出し機能を持つ LLM になる

### 5. システムプロンプト

```python
system_prompt = """
あなたの責務はユーザーからのリクエストを調査し、調査結果をファイルに出力することです。
- ユーザーのリクエスト調査にWeb検索が必要であれば、Web検索ツールを使ってください。
- 必要な情報が集まったと判断したら検索は終了してください。
- 検索は最大2回までとしてください。
- ファイル出力はHTML形式(.html)に変換して保存してください。
  * Web検索が拒否された場合、Web検索を中止してください。
  * レポート保存を拒否された場合、レポート作成を中止し、内容をユーザーに直接伝えてください。
"""
```

**役割**: LLM の振る舞いを定義

**ポイント**:
- 検索は最大 2 回まで（コスト削減）
- HTML 形式での出力を指定
- ユーザー承認の尊重（拒否された場合の対応）

## 🔗 LLM と ツールの連携

### ツール呼び出しの仕組み

```python
# 1. ツール情報をバインド
llm_with_tools = init_chat_model(...).bind_tools(tools)

# 2. ユーザーメッセージを送信
response = llm_with_tools.invoke([SystemMessage(...)] + messages)

# 3. LLM がツール呼び出しを生成
# response は AIMessage で、tool_calls プロパティを持つ
response.tool_calls = [
    {
        "name": "write_file",
        "args": {"file_path": "output.html", "text": "<html>..."},
        "id": "call_abc123"
    }
]

# 4. エージェントがツール呼び出しを実行
tool = tool_by_name["write_file"]
result = tool.invoke(response.tool_calls[0]["args"])
```

## 📊 初期化後の状態

```
llm_with_tools
├── model: Claude Haiku 4.5 (AWS Bedrock)
├── tools: [
│   ├── TavilySearch (Web 検索)
│   └── write_file (ファイル保存)
├── system_prompt: "あなたの責務は..."
└── configuration:
    └── read_timeout: 300s
```

## 🔐 セキュリティ設定

### AWS Bedrock 認証

AWS Bedrock へのアクセスには、以下の認証方法がサポートされています：

1. **環境変数** （推奨）
```bash
export AWS_ACCESS_KEY_ID=...
export AWS_SECRET_ACCESS_KEY=...
export AWS_DEFAULT_REGION=ap-northeast-1
```

2. **IAM ロール** （EC2/ECS で推奨）
   - インスタンスに Bedrock アクセス権限を持つ IAM ロールをアタッチ

3. **AWS CLI 設定** （ローカル開発）
```bash
aws configure
```

### Tavily API キー

```bash
export TAVILY_API_KEY=tvly_...
```

## 💡 クイックリファレンス

### モデル ID 変更

```python
# Claude Sonnet に変更
MODEL_ID = "jp.anthropic.claude-sonnet-4-20250514-v1:0"

# 利用可能なモデルを確認
aws bedrock list-foundation-models --region ap-northeast-1
```

### タイムアウト調整

```python
cfg = Config(
  read_timeout=600  # 10 分に延長
)
```

### ツール追加

```python
from langchain_core.tools import tool

@tool
def custom_tool(input_text: str):
    """カスタムツールの説明"""
    return f"処理結果: {input_text}"

tools = [web_search, write_file, custom_tool]
```

## 📚 参考資料

- [AWS Bedrock ドキュメント](https://docs.aws.amazon.com/bedrock/latest/userguide/)
- [Claude モデル リスト](https://docs.anthropic.com/claude/reference/models-overview)
- [Tavily Search API](https://tavily.com/docs/python-sdk)
- [LangChain init_chat_model](https://python.langchain.com/api_reference/langchain/chat_models/init_chat_model.html)
- [LangChain Tools](https://python.langchain.com/docs/modules/tools/)

---

**次のステップ**: [ツール設定の詳細](./tool_setup.md)
