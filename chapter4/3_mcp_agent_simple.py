import asyncio
import operator
import os
import sys
from langchain.chat_models import init_chat_model
from langchain_core.messages import AnyMessage, AIMessage, HumanMessage, SystemMessage, ToolMessage
from langchain_mcp_adapters.client import MultiServerMCPClient
from langgraph.graph import StateGraph, START, END
from langgraph.prebuilt import ToolNode
from pydantic import BaseModel
from typing import Annotated, Dict, List, Union

from dotenv import load_dotenv
load_dotenv()

mcp_client = None
tools = None
llm_with_tools = None

MODEL_ID = "jp.anthropic.claude-haiku-4-5-20251001-v1:0"

async def initialize_llm():
  """MCP クライアントとツールを初期化する"""
  global mcp_client, tools, llm_with_tools

  try:
    mcp_client = MultiServerMCPClient(
      {
        # Filesystem MCPサーバー
        "file-system": {
          "command": "npx",
          "args": [
            "-y",
            "@modelcontextprotocol/server-filesystem",
            "./"
          ],
          "transport": "stdio"
        },
        # AWS Knowledge MCPサーバー
        "aws-knowledge-mcp-server": {
          "url": "https://knowledge-mcp.global.api.aws",
          "transport": "streamable_http"
        }
      }
    )

    print("[初期化中] MCPクライアントを起動しています...")
    tools = await mcp_client.get_tools()
    print(f"[初期化完了] {len(tools)}個のツールを取得しました")

    # LLMの初期化
    llm_with_tools = init_chat_model(
      model=MODEL_ID,
      model_provider="bedrock_converse"
    ).bind_tools(tools)

    print("[LLM初期化] Claude Haiku 4.5をbedrock_converseで初期化しました")
  except Exception as e:
    print(f"[エラー] MCP初期化に失敗しました: {e}")
    raise


# ステートの定義
class AgentState(BaseModel):
    messages: Annotated[list[AnyMessage], operator.add]

system_prompt = """
あなたの責務はAWSドキュメントを検索し、Markdown形式としてファイル出力することです。
- 検索後、Markdown形式に変換してください。
- 検索は最大で２回までとし、その時点での情報を出力してください。

【重要：ファイルパスについて】
ファイルを保存する場合は、必ず相対パス（ドットスラッシュで始まるパス）を使用してください。
正しい例：./bedrock_models.md  ./results/output.md
間違った例：C:\\tmp\\file.md  /tmp/file.md  ../../../tmp/file.md
必ず ./ で始まるパスを使用してください。
"""

# エージェントノード（LLM実行部分）
# 役割: ユーザーの質問に対してLLMを呼び出し、ツール呼び出しが必要かを判定する
async def agent(state: AgentState) -> Dict[str, List[AIMessage]]:
  response = await llm_with_tools.ainvoke(
    [SystemMessage(system_prompt)] + state.messages
  )

  return {"messages": [response]}

def route_node(state: AgentState) -> Union[str]:
  last_message = state.messages[-1]

  if not isinstance(last_message, AIMessage):
    raise ValueError("「AIMessage」以外のメッセージです。遷移が不正な可能性があります。")

  if not last_message.tool_calls:
    return END  # ENDノードへ遷移（エージェント処理終了）
  return "tools"  # toolsノードへ遷移（ツール実行）

async def main():
  #  MCPクライアントとツールを初期化
  await initialize_llm()

  #  グラフを構築
  builder = StateGraph(AgentState)
  builder.add_node("agent", agent)
  builder.add_node("tools", ToolNode(tools))

  # グラフの遷移ルール（エッジ）を定義
  builder.add_edge(START, "agent")
  builder.add_conditional_edges(
     "agent",
     route_node
  )

  builder.add_edge("tools", "agent")

  graph = builder.compile(name="ReAct Agent")

  question = "Bedrockで利用可能なモデルプロバイダーを教えて！"

  response = await graph.ainvoke(
     {
        "messages": [HumanMessage(question)]
     }
  )
  print(response)
  return response

asyncio.run(main())