# 3_mcp_agent.py エラー対応ガイド

`python ./chapter4/3_mcp_agent.py` 実行時に発生するエラーと対応方法をまとめました。

---

## エラー 1: "Connection closed" (MCP接続エラー)

### エラーメッセージ
```
mcp.shared.exceptions.McpError: Connection closed
During task with name 'tools' and id '...'
```

### 原因
- AWS Knowledge MCP サーバーへの接続がタイムアウトしている
- ネットワークが不安定
- リモートサーバーが応答していない

### 対応方法

#### 方法 1: Filesystem のみを使用（推奨）
```python
# AWS Knowledge MCP を削除し、Filesystem のみを使用

mcp_client = MultiServerMCPClient(
    {
        # Filesystem MCPサーバーのみ
        "file-system": {
            "command": "npx",
            "args": [
                "-y",
                "@modelcontextprotocol/server-filesystem",
                "./"
            ],
            "transport": "stdio"
        }
        # AWS Knowledge MCP を削除 ↓
        # "aws-knowledge-mcp-server": { ... }
    }
)
```

#### 方法 2: タイムアウト設定を追加
```python
# MCP初期化時にタイムアウトを設定

mcp_client = MultiServerMCPClient(
    {...},
    timeout=10  # 10秒でタイムアウト
)
```

#### 方法 3: エラーハンドリングを追加
```python
from langgraph.prebuilt import ToolNode

# ToolNode でエラーを無視する設定
tool_node = ToolNode(
    tools,
    handle_tool_errors=True  # エラーをメッセージに変換
)

builder.add_node("tools", tool_node)
```

---

## エラー 2: "Access denied - path outside allowed directories"

### エラーメッセージ
```
langchain_core.tools.base.ToolException: Access denied - path outside allowed directories:
C:\tmp\bedrock_model_providers.md not in C:\WorkSpace\llms
```

### 原因
LLM が許可されたディレクトリ外（C:\tmp など）にファイルを保存しようとしている

### 対応方法

**system_prompt を修正して、相対パスを使うように指示：**

```python
system_prompt = """
あなたの責務はAWSドキュメントを検索し、Markdown形式としてファイル出力することです。

【重要：ファイル保存時の指示】
- ファイルパスは相対パス "./" から始めてください
- 例："./" や "./bedrock_models.md" や "./output/models.md"
- 絶対パス（C:\\tmp など）は使わないでください

【検索と出力】
- 検索語をMarkdown形式に変換してください。
- 検索は最大で２回までとし、その時点での情報を出力してください。
- ファイルに出力した後、その旨を報告してください。
"""
```

---

## エラー 3: "UnicodeEncodeError: 'cp932' codec can't encode character"

### エラーメッセージ
```
UnicodeEncodeError: 'cp932' codec can't encode character '\xe3' in position 17371
```

### 原因
Windows のターミナルエンコーディング（cp932）が日本語を含むテキストを表示できない

### 対応方法

**UTF-8 で安全に出力：**

```python
import sys

# 日本語を含むテキストを UTF-8 で出力
response = await graph.ainvoke({...})

for msg in response['messages']:
    if hasattr(msg, 'content'):
        # UTF-8 でバイナリ出力
        sys.stdout.buffer.write(f"{msg.content}\n".encode('utf-8'))
```

または **PowerShell で実行：**

```bash
chcp 65001  # UTF-8 に変更
python ./chapter4/3_mcp_agent.py
```

---

## エラー 4: "Model not found" または "Invalid API key"

### エラーメッセージ
```
ValidationError: bedrock_converse provider not found
# または
Access Denied: Invalid AWS credentials
```

### 原因
- AWS Bedrock へのアクセス権がない
- AWS認証情報が正しくない
- モデルIDが誤っている

### 対応方法

**1. AWS 認証情報を確認：**

```bash
# .env ファイルを確認
cat .env | grep AWS

# 出力例：
# AWS_ACCESS_KEY_ID=AKIA...
# AWS_SECRET_ACCESS_KEY=...
# AWS_DEFAULT_REGION=ap-northeast-1
```

**2. モデルID を確認：**

```python
# 正しいモデルID を使用
MODEL_ID = "jp.anthropic.claude-haiku-4-5-20251001-v1:0"
# または
MODEL_ID = "us.anthropic.claude-opus-4-1-20250805-v1:0"
```

**3. AWS IAM 権限を確認：**

Bedrock へのアクセス権があるか確認
```bash
aws bedrock list-foundation-models --region ap-northeast-1
```

---

## 推奨される実行方法

### シンプル版：Filesystem のみ使用

以下のコードを `3_mcp_agent_simple.py` として作成：

```python
import asyncio
import operator
import os
from langchain.chat_models import init_chat_model
from langchain_core.messages import AnyMessage, AIMessage, HumanMessage, SystemMessage
from langchain_mcp_adapters.client import MultiServerMCPClient
from langgraph.graph import StateGraph, START, END
from langgraph.prebuilt import ToolNode
from pydantic import BaseModel
from typing import Annotated, Dict, List, Union
from dotenv import load_dotenv

load_dotenv()

# グローバル変数
mcp_client = None
tools = None
llm_with_tools = None

MODEL_ID = "jp.anthropic.claude-haiku-4-5-20251001-v1:0"

async def initialize_llm():
    """MCP クライアントとツールを初期化する"""
    global mcp_client, tools, llm_with_tools

    # Filesystem のみを使用（AWS Knowledge MCP を削除）
    mcp_client = MultiServerMCPClient(
        {
            "file-system": {
                "command": "npx",
                "args": [
                    "-y",
                    "@modelcontextprotocol/server-filesystem",
                    "./"
                ],
                "transport": "stdio"
            }
        }
    )

    # ツール取得
    tools = await mcp_client.get_tools()

    # LLM 初期化
    llm_with_tools = init_chat_model(
        model=MODEL_ID,
        model_provider="bedrock_converse"
    ).bind_tools(tools)


class AgentState(BaseModel):
    messages: Annotated[list[AnyMessage], operator.add]


system_prompt = """
ファイル操作のテストをしてください。
- "./test.md" という Markdown ファイルを作成してください
- ファイルに以下の内容を書き込んでください：

# テストファイル

これは LangGraph + MCP による Filesystem テストです。

ツール：
- write_file: ファイル書き込み
- read_file: ファイル読み込み
- list_directory: ディレクトリ一覧
"""

async def agent(state: AgentState) -> Dict[str, List[AIMessage]]:
    response = await llm_with_tools.ainvoke(
        [SystemMessage(system_prompt)] + state.messages
    )
    return {"messages": [response]}


def route_node(state: AgentState) -> Union[str]:
    last_message = state.messages[-1]
    if not isinstance(last_message, AIMessage):
        raise ValueError("AIMessage 以外が来た")
    if not last_message.tool_calls:
        return END
    return "tools"


async def main():
    await initialize_llm()

    builder = StateGraph(AgentState)
    builder.add_node("agent", agent)
    builder.add_node("tools", ToolNode(tools))

    builder.add_edge(START, "agent")
    builder.add_conditional_edges("agent", route_node)
    builder.add_edge("tools", "agent")

    graph = builder.compile(name="FileSystem Agent")

    # グラフ実行
    response = await graph.ainvoke({
        "messages": [HumanMessage("ファイル操作のテストをしてください")]
    })

    # 結果表示
    import sys
    print("\n========== 実行完了 ==========\n")
    print(f"メッセージ数: {len(response['messages'])}")
    for i, msg in enumerate(response['messages']):
        print(f"[{i}] {type(msg).__name__}")


asyncio.run(main())
```

実行：
```bash
python ./chapter4/3_mcp_agent_simple.py
```

---

## まとめ：3_mcp_agent.py を使う前に

| 項目 | 確認内容 |
|------|--------|
| **AWS 認証情報** | `.env` に `AWS_ACCESS_KEY_ID` 等が設定されているか |
| **モデルアクセス** | AWS Bedrock でモデルへのアクセス権があるか |
| **ネットワーク** | AWS リモートサーバーに接続できるか |
| **MCP サーバー** | `npx @modelcontextprotocol/server-filesystem` が動作するか |
| **Python 環境** | 必要なパッケージが全てインストールされているか |

---

## デバッグ用コマンド

```bash
# 1. AWS 認証情報の確認
aws sts get-caller-identity

# 2. Bedrock モデルリストの確認
aws bedrock list-foundation-models --region ap-northeast-1

# 3. MCP Filesystem サーバーの動作確認
npx @modelcontextprotocol/server-filesystem ./
```

---

**最終更新**: 2025年12月22日
