# =============================================================================
# AWSマスターエージェント - AWS知識検索の専門家
# =============================================================================
# MCP (Model Context Protocol) 経由でAWS公式ドキュメントを検索する専門エージェント。
# 読み取り専用で、実際のAWS操作は行いません。

import asyncio
import os
from strands import Agent, tool
from strands.tools.mcp import MCPClient
from mcp.client.streamable_http import streamable_http_client
from .agent_executor import invoke
from dotenv import load_dotenv

load_dotenv()

class AwsMasterState:
  """AWSマスターエージェントの状態を保持"""
  def __init__(self):
    self.client = None  # MCPクライアント
    self.queue = None   # 通信用キュー

_state = AwsMasterState()

def setup_aws_master(queue):
  """
  新規キューを受け取り、MCPクライアントを準備

  Args:
      queue: 監督者エージェントとの通信用キュー（Noneでクリーンアップ）
  """
  _state.queue = queue

  if queue and not _state.client:
    try:
      _state.client = MCPClient(
        # 接続方法を遅延実行する関数。必要になった時に初めて接続を開始する（効率的）
        lambda: streamable_http_client(
          "https://knowledge-mcp.global.api.aws"  # AWS公式MCPサーバー
        )
      )
    except Exception:
      _state.client = None

def _create_agent():
  """AWSマスターのサブエージェントを作成"""
  if not _state.client:
    return None

  return Agent(
    model=os.getenv("MODEL_ID"),
    tools=_state.client.list_tools_sync()  # MCPサーバーが提供するツール一覧
  )

@tool
async def aws_master(query):
  """
  AWSマスターエージェント - AWS知識検索の実行部分

  Args:
      query: ユーザーからの質問

  Returns:
      str: AWSドキュメントから検索した回答
  """
  if not _state.client:
    return "MCPクライアントが利用不可です"

  return await invoke("AWSマスター", query, _state.client, _create_agent, _state.queue)
