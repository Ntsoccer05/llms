# =============================================================================
# メインアプリケーション - AWS操作AIアシスタント
# =============================================================================
# AWS（Amazon Web Services）を操作できるAIアシスタントの中核部分です。
# 2つのサブエージェント（AWSマスター、APIマスター）を使って、
# AWSの質問に答えたり、実際にAWSリソースを操作します。

import asyncio
import os
from strands import Agent
from bedrock_agentcore.runtime import BedrockAgentCoteApp
from .aws_master import aws_master, setup_aws_master
from .api_master import api_master, setup_api_master
from .stream_handler import merge_streams
from dotenv import load_dotenv

load_dotenv()

def _create_orchestrator():
  """監督者エージェントを作成"""
  return Agent(
    model=os.getenv("MODEL_ID"),
    tools=[aws_master, api_master],
    system_prompt="""2体のサブエージェントを使って日本語で応対して。
1. AWSマスター：AWSドキュメントなどを参照できます。
2. APIマスター：AWSアカウントをAPIで操作できます。"""
  )

# アプリケーションの初期化
app = BedrockAgentCoteApp()
orchestrator = _create_orchestrator()

# BedrockAgentCoteAppというフレームワークが「このinvoke関数がメインの処理開始地点ですよ」と認識する
@app.entrypoint
async def invoke(payload):
  """
  呼び出し処理の開始地点（非同期関数）

  Args:
      payload: HTTPリクエストから受け取ったデータ
  """

#   ネストされた辞書（辞書の中の辞書）から、安全にデータを取り出しています：


# payload
#   └─ "input" (辞書)
#       └─ "prompt" (文字列)

# payload.get("input", {})	payloadから "input" キーの値を取得。なければ空の辞書 {} をデフォルト値として使う
# .get("prompt", "")	その結果から "prompt" キーの値を取得。なければ空文字列 "" をデフォルト値として使う
  prompt = payload.get("input", {}).get("prompt", "")

  # サブエージェント用のキューを初期化
  # Queue: データを順番に格納する入れ物（複数の処理間でデータをやり取り）
  queue = asyncio.Queue()
  setup_aws_master(queue)
  setup_api_master(queue)

  try:
    # 監督者エージェントを呼び出し、ストリームを統合
    stream = orchestrator.stream_async(prompt)

    # merge_streams(): 親と子のストリームを統合
    # async for: 非同期イテレータから1つずつデータを取り出す
    # yield: データが来たらすぐ返す（リアルタイム表示）
    async for event in merge_streams(stream, queue):
      yield event

  finally:
    # キューをクリーンアップ
    setup_aws_master(None)
    setup_api_master(None)

# APIサーバーを起動
if __name__ == "__main__":
  app.run()
