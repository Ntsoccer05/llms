# =============================================================================
# A2A（Agent to Agent）クライアント
# =============================================================================
# ネットワーク上のAIエージェント（A2Aサーバー）をツールとして利用します。
# 4_a2a_server.py を先に起動してから、このファイルを実行してください。

from strands import Agent
from strands_tools.a2a_client import A2AClientToolProvider

# A2Aサーバーをツールに変換
provider = A2AClientToolProvider(
    known_agent_urls=["http://localhost:9000"]  # 4_a2a_server.pyのアドレス
)

# クライアントエージェントを作成
# リモートの「俳句エージェント」をツールとして利用可能
agent = Agent(tools=provider.tools)

# リモートエージェントを使って処理を実行
response = agent("Strandsにちなんだ俳句を詠んで")