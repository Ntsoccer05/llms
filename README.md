# LangGraph Agent - LLM + MCP Integration

LangGraph を使用した AI エージェント実装。Model Context Protocol (MCP)、AWS Bedrock、LangGraph Studio に対応。

## 機能

- **LangGraph**: ステートフルなグラフベース設計
- **MCP統合**: Filesystem と AWS Knowledge MCP サーバー
- **AWS Bedrock**: Claude Haiku 4.5 モデル
- **Web検索**: Tavily 統合
- **AWS SNS**: メッセージ送信機能

## プロジェクト構成

```
llms/
├── chapter4/                              # LangGraph + MCP 学習モジュール
├── .env                                   # 環境変数（要設定）
├── pyproject.toml                         # 依存関係
├── requirements.txt                       # pip用依存関係
└── README.md                              # このファイル
```

## セットアップ

### 1. 環境構築

```bash
# 仮想環境の作成
python -m venv dev-llm
source ./dev-llm/Scripts/activate  # Windows Git Bash
# または .\dev-llm\Scripts\Activate.ps1  # Windows PowerShell

# パッケージインストール
pip install -e .
# または
pip install -r requirements.txt

# Node.js 確認（Filesystem MCP用）
npm --version
```

### 2. 環境変数設定

`.env` ファイルを作成して以下を設定：

```env
AWS_ACCESS_KEY_ID=your_key
AWS_SECRET_ACCESS_KEY=your_secret
AWS_DEFAULT_REGION=ap-northeast-1
TAVILY_API_KEY=tvly-xxxxxxxx
LANGSMITH_API_KEY=lsv2_pt_xxxxxxxx  # オプション
```

## 使用方法

### MCP エージェント実行（推奨）

```bash
# シンプル版（エラーハンドリング機能付き）
python chapter4/3_mcp_agent_simple.py

# または詳細コメント付き版
python chapter4/3_mcp_agent.py
```

**機能:**
- Filesystem MCP: ローカルファイル読み書き（相対パスのみ）
- AWS Knowledge MCP: AWS ドキュメント検索
- 自動エラーハンドリング: ツール実行エラー時も処理継続

### LangGraph Studio（グラフ可視化）

```bash
langgraph up
# ブラウザで http://localhost:8000
```

## 主要コンポーネント

| ファイル | 説明 |
|---------|------|
| `3_mcp_agent.py` | MCP統合エージェント（詳細コメント） |
| `3_mcp_agent_simple.py` | MCP統合エージェント（シンプル版） |
| `3_MCP_AGENT_GUIDE.md` | LangGraph と MCP の詳細解説 |
| `3_MCP_AGENT_ERROR_SOLUTIONS.md` | エラー解決ガイド |
| `LANGGRAPH_PATTERNS.md` | 再利用可能な10個のパターン |

## トラブルシューティング

### MCP 関連

**Connection closed（AWS Knowledge MCP）**
- インターネット接続確認
- 詳細: `3_MCP_AGENT_ERROR_SOLUTIONS.md` 参照

**Access denied - path outside allowed directories**
- LLM が絶対パスを生成している
- システムプロンプトで相対パス（./）使用を強制
- 詳細: `3_MCP_AGENT_ERROR_SOLUTIONS.md` 参照

### AWS 関連

**"You must specify a region"**
```
AWS_DEFAULT_REGION=ap-northeast-1
```

**"No credentials found"**
```
AWS_ACCESS_KEY_ID=your_key
AWS_SECRET_ACCESS_KEY=your_secret
```

### その他

**Unicode エラー（Windows）**
```bash
chcp 65001
# または Git Bash で
export PYTHONIOENCODING=utf-8
```

## セキュリティ

- `.env` は `.gitignore` に含まれています
- 本番環境では AWS Secrets Manager 使用を推奨
- API キーを Git にコミットしないでください

## 開発ガイド

### ノード追加

```python
async def new_node(state: AgentState) -> Dict:
    return {"messages": [result]}

builder.add_node("new_node", new_node)
builder.add_edge("previous_node", "new_node")
```

### カスタムツール追加

```python
from langchain_core.tools import tool

@tool
def custom_tool(input_text: str):
    """ツール説明"""
    return result

tools = [custom_tool, ...]
```

## 参考リソース

- [LangGraph ドキュメント](https://langchain-ai.github.io/langgraph/)
- [LangChain ドキュメント](https://python.langchain.com/)
- [Model Context Protocol](https://modelcontextprotocol.io/)
- [AWS Bedrock](https://aws.amazon.com/bedrock/)
- [Tavily API](https://docs.tavily.com/)

---

**最終更新**: 2025年12月24日
