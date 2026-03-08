# =============================================================================
# エージェント実行処理 - サブエージェントの起動と監視
# =============================================================================
# サブエージェント（AWSマスター、APIマスター）を実際に実行し、
# その進捗状況をリアルタイムで監視する処理を担当します。

import asyncio
from .stream_handler import send_event

async def extract(queue, agent, event, state):
  """
  AIの応答ストリームから内容を抽出し、キューに送信

  Args:
      queue: 監督者エージェントとの通信用キュー
      agent: エージェント名
      event: ストリームから届いた1つのイベント（文字列 or 辞書）
      state: 状態を保持する辞書（テキストを蓄積）
  """
  # パターン1: 文字列イベント（テキストの断片）
  if isinstance(event, str):
    state["text"] += event
    if queue:
      delta = {"delta": {"text": event}}
      await queue.put({"event": {"contentBlockDelta": delta}})

  # パターン2: 辞書イベント（メタデータ）
  elif isinstance(event, dict) and "event" in event:
    event_data = event["event"]

    # ツール使用を検出
    if "contentBlockDelta" in event_data:
      block = event_data["contentBlockStart"]
      start_data = block.get("start", {})
      if "toolUse" in start_data:
        tool_use = start_data["toolUse"]
        tool = tool_use.get("name", "unknown")
        await send_event(queue, f"「{agent}」がツール「{tool}」を実行中", "tool_use", tool)

    # テキスト増分を処理
    if "contentBlockDelta" in event_data:
      block = event_data["contentBlockDelta"]
      delta = block.get("delta", {})
      if "text" in delta:
        state["text"] += delta["text"]

async def invoke(agent, query, mcp, create_agent, queue):
  """
  サブエージェントを呼び出して実行

  Args:
      agent: エージェント名
      query: ユーザーの質問・指示
      mcp: MCPクライアント
      create_agent: エージェント作成関数
      queue: 監督者エージェントとの通信用キュー

  Returns:
      str: サブエージェントの最終応答テキスト
  """
  state = {"text": ""}
  await send_event(queue, f"サブエージェント「{agent}」が呼び出されました", "start")

  try:
    # MCPクライアントを起動しながら、エージェントを呼び出し
    # with文: 終了時に自動でクリーンアップ
    with mcp:
      agent_obj = create_agent()

      # async for: 非同期イテレータから1つずつデータを取り出す
      # stream_async() は内部的に yield でデータを返している
      async for event in agent_obj.stream_async(query):
        await extract(queue, agent, event, state)

    await send_event(queue, f"「{agent}」が対応を完了しました", "complete")
    return state["text"]

  except Exception:
    return f"{agent}エージェントの処理に失敗しました"
