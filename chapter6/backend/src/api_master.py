# =============================================================================
# APIマスターエージェント - AWS API操作の専門家
# =============================================================================
# 実際にAWS APIを呼び出してリソースを操作する専門エージェント。
# ⚠️ 注意: 実際にAWSリソースを操作するため、料金が発生したり、
#          重要なリソースを削除したりする可能性があります。

import os
import asyncio
from strands import Agent, tool
from strands.tools.mcp import MCPClient
from mcp import stdio_client, StdioServerParameters
from.agent_executor import invoke

class ApiMasterState:
  """APIマスターエージェントの状態を保持"""
  def __init__(self):
    self.client = None  # MCPクライアント
    self.queue = None   # 通信用キュー

_state = ApiMasterState()

def setup_api_master(queue):
  """
  新規キューを受け取り、MCPクライアントを準備

  Args:
      queue: 監督者エージェントとの通信用キュー（Noneでクリーンアップ）
  """
  _state.queue = queue

  if queue and not _state.client:
    try:
      # ローカルでMCPサーバーを起動（標準入出力経由）
      _state.client = MCPClient(
        lambda: stdio_client(
          StdioServerParameters(
            command="uvx",  # uvx: Pythonパッケージを一時的に実行
            args=["awslabs.aws-api-mcp-server==0.2.1"],
            env=os.environ.copy()  # AWS認証情報を引き継ぐ
          )
        )
      )
    except Exception:
      _state.client = None

def _create_agent():
  """APIマスターのサブエージェントを作成"""
  if not _state.client:
    return None

  return Agent(
    model=os.getenv("MODEL_ID"),
    tools=_state.client.list_tools_sync() # ←ここにツール一覧配列が渡される
  )

@tool
async def api_master(query):
  """
  APIマスターエージェント - AWS API操作の実行部分

  Args:
      query: ユーザーからの操作指示

  Returns:
      str: 操作結果のメッセージ
  """
  if not _state.client:
    return "MCPクライアントが利用不可です"

  return await invoke("APIマスター", query, _state.client, _create_agent, _state.queue)
