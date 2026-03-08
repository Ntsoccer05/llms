# LangGraph Studio で実行可能なグラフAPI
import boto3
import operator
import os

from langchain.chat_models import init_chat_model
from langchain_core.messages import AnyMessage, AIMessage, HumanMessage, SystemMessage
from langchain_core.tools import tool
from langgraph.graph import StateGraph, START, END
from langgraph.prebuilt import ToolNode
from pydantic import BaseModel
from typing import Annotated, Dict, List, Union

from dotenv import load_dotenv
load_dotenv()

# Tavily検索ツールをインポート（Web検索機能）
try:
    from langchain_tavily import TavilySearch
    tavily_api_key = os.getenv("TAVILY_API_KEY")
    if tavily_api_key:
        web_search = TavilySearch(max_results=2)
    else:
        web_search = None
except ImportError:
    web_search = None

# AWS SNSにメッセージを送信するカスタムツール
@tool
def send_aws_sns(text: str):
    """テキストをAWS SNSのトピックにPublishするツール"""
    topic_arn = os.getenv("SNS_TOPIC_ARN")
    if topic_arn:
        try:
            sns_client = boto3.client('sns')
            sns_client.publish(TopicArn=topic_arn, Message=text)
            return f"Message published to SNS: {text}"
        except Exception as e:
            return f"Error publishing to SNS: {str(e)}"
    else:
        print(f"SNS Message (no topic configured): {text}")
        return text

# エージェントが使用できるツールリストを構築
if web_search is not None:
    tools = [web_search, send_aws_sns]
else:
    tools = [send_aws_sns]

# Bedrockで使用するモデルID
MODEL_ID = "jp.anthropic.claude-haiku-4-5-20251001-v1:0"

# LLMモデルを初期化してツールにバインド
llm_with_tools = init_chat_model(
    model=MODEL_ID,
    model_provider="bedrock_converse"
).bind_tools(tools)

# エージェント状態を定義
class AgentState(BaseModel):
    messages: Annotated[list[AnyMessage], operator.add]

# グラフビルダーを作成
builder = StateGraph(AgentState)

# エージェントに与えるシステムプロンプト
system_prompt = """
あなたの業務はユーザーからの質問を調査し、結果を要約してAWS SNSに送ることです。
検索は１回のみとしてください。
必ず send_aws_sns ツールを使用して、調査結果をSNSに送信してください。
"""

# エージェントノードの処理
async def agent(state: AgentState) -> Dict[str, List[AIMessage]]:
    response = await llm_with_tools.ainvoke(
        [SystemMessage(system_prompt)] + state.messages
    )
    return {"messages": [response]}

# グラフにノードを追加
builder.add_node("agent", agent)
builder.add_node("tools", ToolNode(tools))

# グラフのエッジ（遷移ルール）を定義する関数
def route_node(state: AgentState) -> Union[str]:
    last_message = state.messages[-1]
    if not hasattr(last_message, 'tool_calls') or not last_message.tool_calls:
        return END
    return "tools"

# グラフの構造を定義
builder.add_edge(START, "agent")
builder.add_conditional_edges("agent", route_node)
builder.add_edge("tools", "agent")

# グラフをコンパイル
graph = builder.compile()

# LangGraph Studioで使用するためのエクスポート
__all__ = ["graph"]
