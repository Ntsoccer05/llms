# =============================================================================
# ストリームハンドラー - 複数のストリームをリアルタイムで統合
# =============================================================================
# 2つの異なるデータソース（監督者エージェントとサブエージェント）から
# 同時に届くデータを統合して、1つのストリームとしてユーザーに返します。

import asyncio

async def send_event(queue, message, state, tool_name=None):
  """
  サブエージェントのステータスメッセージをキューに送信

  Args:
      queue: 監督者エージェントとの通信用キュー
      message: 通知メッセージ
      state: イベントの状態（例: "start", "tool_use", "complete"）
      tool_name: ツール名（tool_use の場合のみ）
  """
  if not queue:
    return

  progress = {"message": message, "state": state}
  if tool_name:
    progress["tool_name"] = tool_name

  await queue.put({"event": {"subAgentProgress": progress}})

async def merge_streams(stream, queue):
  """
  親子エージェントのストリームを統合

  この関数は2つの異なるデータソースを同時に監視して、
  データが来た順にユーザーに届けます。

  Args:
      stream: 監督者エージェント（親）の応答ストリーム
      queue: サブエージェント（子）の進捗情報を受け取るキュー

  Yields:
      event: 親または子から届いたイベント（どちらか先に来た方）
  """
  create_task = asyncio.create_task

  # 2つのタスクを作成
  main = create_task(anext(stream, None))  # 親の次のデータを待つ
  sub = create_task(queue.get())           # 子の次のデータを待つ
  waiting = {main, sub}

  # メインループ: データが来るまで待ち続ける
  while waiting:
    # asyncio.wait(): 複数のタスクのうち、どれか1つでも完了したら返す
    ready_chunks, waiting = await asyncio.wait(
      waiting,
      return_when=asyncio.FIRST_COMPLETED
    )

    # 完了したタスクを処理
    for ready_chunk in ready_chunks:
      # パターン1: 監督者エージェント（親）のデータが来た
      if ready_chunk == main:
        event = ready_chunk.result()
        if event is not None:
          yield event  # データを外に返す（リアルタイム表示）
          main = create_task(anext(stream, None))
          waiting.add(main)
        else:
          main = None

      # パターン2: サブエージェント（子）のデータが来た
      if ready_chunk == sub:
        try:
          sub_event = ready_chunk.result()
          yield sub_event  # データを外に返す（リアルタイム表示）
          sub = create_task(queue.get())
          waiting.add(sub)
        except Exception:
          sub = None

    # 終了判定: 親が終了 AND キューが空
    if main is None and queue.empty():
      break
