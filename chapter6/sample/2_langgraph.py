# =============================================================================
# LangGraphを使ったエージェントネットワーク
# =============================================================================
# グラフ構造（ノードとエッジ）で複数のAIエージェントを繋げます。
# 各エージェントがサイコロを振って次の行き先を動的に決定する「すごろく」型の実装です。

from dotenv import load_dotenv
from langchain_core.messages import AIMessage
from langchain.chat_models import init_chat_model
from langgraph.types import Command
from langgraph.graph import StateGraph, MessagesState, START, END

load_dotenv()

# AIモデルの設定
model = init_chat_model(
    model="us.anthropic.claude-3-7-sonnet-20250219-v1:0",
    model_provider="bedrock_converse"
)

# =============================================================================
# エージェント作成関数（工場パターン）
# =============================================================================
def create_agent(name, odd_target, even_target):
    """
    サイコロを振って次の行き先を決定するエージェントを作成

    Args:
        name: エージェント名
        odd_target: サイコロが奇数のときの行き先
        even_target: サイコロが偶数のときの行き先
    """
    def agent(state):
        # AIにサイコロを振らせる
        dice = int(str(model.invoke("1から6のサイコロを1つ振って、数字だけ答えて").content).strip())

        # 奇数/偶数で次の行き先を決定
        is_odd = dice % 2 == 1
        next_agent = odd_target if is_odd else even_target

        # 進行状況を表示
        content = f"{name}: {dice}が出たので{next_agent}へ進みます！"
        print(content)

        # 次のノードへの移動指示を返す
        return Command(
            goto=next_agent,
            update={"messages": [AIMessage(content=content)]}
        )

    return agent

# 各エージェントを作成
agent_1 = create_agent("エージェント1", "agent_3", "agent_2")
agent_2 = create_agent("エージェント2", "agent_3", END)
agent_3 = create_agent("エージェント3", END, "agent_2")

# グラフを構築
builder = StateGraph(MessagesState)
builder.add_node("agent_1", agent_1)
builder.add_node("agent_2", agent_2)
builder.add_node("agent_3", agent_3)
builder.add_edge(START, "agent_1")
network = builder.compile()

# 実行
network.invoke({"messages": []})