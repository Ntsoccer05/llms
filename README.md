# LangGraph Agent with Tavily Search & AWS SNS

LangGraph を使用した AI エージェント。Tavily Web検索と AWS SNS 統合、LangGraph Studio GUI サポート。

## 機能

- **LangGraph ベースエージェント**: ステートフルなグラフベース設計
- **Tavily Web 検索**: リアルタイム Web 検索
- **AWS SNS 統合**: 結果を AWS SNS に送信
- **AWS Bedrock**: Claude Haiku 4.5 を使用
- **LangGraph Studio**: Web UI でのグラフ可視化・実行

## プロジェクト構成

```
llms/
├── src/agent/
│   └── graph.py              # LangGraph エージェント定義
├── chapter4/                 # 学習用サンプル
├── .env                      # 環境変数（要設定）
├── .env.example              # 環境変数のテンプレート
├── pyproject.toml            # Python パッケージ設定
└── langgraph.json            # LangGraph Studio 設定
```

## セットアップ

### 1. 仮想環境と依存パッケージ

```bash
# 仮想環境の作成
python -m venv dev-llm
source ./dev-llm/Scripts/activate  # Windows Git Bash
# または .\dev-llm\Scripts\Activate.ps1  # Windows PowerShell

# パッケージインストール
pip install -e .
```

### 2. 環境変数設定

`.env.example` をコピーして `.env` を作成：

```bash
cp .env.example .env
```

`.env` に以下を設定：

```env
AWS_ACCESS_KEY_ID=your_key
AWS_SECRET_ACCESS_KEY=your_secret
AWS_DEFAULT_REGION=ap-northeast-1
SNS_TOPIC_ARN=arn:aws:sns:ap-northeast-1:ACCOUNT_ID:TOPIC_NAME
TAVILY_API_KEY=tvly-xxxxxxxx
LANGSMITH_API_KEY=lsv2_pt_xxxxxxxx  # オプション
```

## 使用方法

### LangGraph Studio（推奨）

```bash
langgraph up
# ブラウザで http://localhost:8000 にアクセス
```

- グラフの可視化
- 入力テキストでエージェント実行
- 実行フローのリアルタイム監視

### Python スクリプト実行

```bash
python chapter4/2_graph_agent.py
```

## エージェント動作フロー

```
START
  → [Agent] LLM にユーザー質問を送信
  → [Router] ツール呼び出し判定
    ├─ ツール必要 → [Tools] 検索/SNS送信
    └─ 不要 → END
  → [Agent] 結果を再処理
  → END
```

## 主要コンポーネント

| ファイル | 説明 |
|---------|------|
| `src/agent/graph.py` | LangGraph エージェント定義 |
| `langgraph.json` | Studio 設定・グラフパス定義 |
| `pyproject.toml` | パッケージ依存関係 |

### graph.py の主要関数

- `send_aws_sns(text)`: AWS SNS にメッセージ送信
- `agent(state)`: LLM ノード
- `route_node(state)`: ツール呼び出し判定

### ツール

- **TavilySearch**: Web 検索（最大 2 件）
- **send_aws_sns**: SNS メッセージ送信

## トラブルシューティング

### "You must specify a region"

→ `.env` の `AWS_DEFAULT_REGION` を確認（形式: `AWS_DEFAULT_REGION=ap-northeast-1`）

### "Tavily API key not found"

→ `.env` に `TAVILY_API_KEY=tvly-xxxxxxxx` を追加

### Docker 接続エラー

→ Docker Desktop を起動

### Unicode エラー（Windows）

→ `chcp 65001` を実行、または Git Bash で `export PYTHONIOENCODING=utf-8`

## 開発ガイド

### ノードを追加

```python
async def new_node(state: AgentState) -> Dict:
    # 処理
    return {"messages": [result]}

builder.add_node("new_node", new_node)
builder.add_edge("previous_node", "new_node")
```

### カスタムツール追加

```python
from langchain_core.tools import tool

@tool
def custom_tool(input_text: str):
    """ツールの説明"""
    return result

tools = [web_search, send_aws_sns, custom_tool]
```

### LLM モデル変更

`src/agent/graph.py` の `MODEL_ID` を変更：

```python
MODEL_ID = "jp.anthropic.claude-sonnet-4-20250514-v1:0"
```

## API 入出力

### 入力例

```python
from langchain_core.messages import HumanMessage

input_data = {
    "messages": [HumanMessage(content="ユーザーの質問")]
}
result = graph.invoke(input_data)
```

## セキュリティ

- `.env` は `.gitignore` に含まれています
- 本番環境では AWS Secrets Manager 使用を推奨
- API キーを Git にコミットしないでください

## 参考リンク

- [LangGraph ドキュメント](https://langchain-ai.github.io/langgraph/)
- [LangChain ドキュメント](https://python.langchain.com/)
- [AWS SNS](https://aws.amazon.com/sns/)
- [Tavily API](https://docs.tavily.com/)
- [AWS Bedrock](https://aws.amazon.com/bedrock/)

---

**最終更新**: 2025年12月22日
