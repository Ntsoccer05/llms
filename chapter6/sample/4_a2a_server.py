# =============================================================================
# A2A（Agent to Agent）サーバー
# =============================================================================
# AIエージェントをHTTPサーバーとしてネットワーク経由で公開します。
# デフォルトで http://localhost:9000 で起動し、他のプログラムから利用可能になります。

from dotenv import load_dotenv
from strands import Agent
from strands.multiagent.a2a import A2AServer

load_dotenv()

# リモートエージェントを作成
agent = Agent(
    name="俳句エージェント",
    description="お題に沿った俳句を読みます。"
)

# A2Aサーバーとして起動（ブロッキング処理）
a2a_server = A2AServer(agent=agent)
a2a_server.serve()