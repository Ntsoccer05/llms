# 必要なライブラリをインポート
import asyncio  # 非同期処理用
import boto3  # AWS SDK
import operator  # 状態のメッセージをリストに追加するために使用
import os  # 環境変数の読み込み用

from langchain.chat_models import init_chat_model  # LLMモデルの初期化
from langchain_core.messages import AnyMessage, AIMessage, HumanMessage, SystemMessage  # メッセージタイプ
from langchain_core.tools import tool  # ツール定義用デコレータ
from langgraph.graph import StateGraph, START, END  # グラフの構築用
from langgraph.prebuilt import ToolNode  # ツール実行ノード
from pydantic import BaseModel  # データ型定義用
from typing import Annotated, Dict, List, Union  # 型ヒント用

# 環境変数ファイル(.env)を読み込む
from dotenv import load_dotenv
load_dotenv()

# Tavily検索ツールをインポート（Web検索機能）
# TAVILY_API_KEYが設定されている場合のみ初期化
try:
    from langchain_tavily import TavilySearch
    tavily_api_key = os.getenv("TAVILY_API_KEY")
    if tavily_api_key:
        web_search = TavilySearch(max_results=2)
    else:
        web_search = None
        print("Warning: TAVILY_API_KEY not set, web search not available")
except ImportError:
    web_search = None
    print("Warning: langchain-tavily not installed, web search not available")

# AWS SNSにメッセージを送信するカスタムツール
@tool
def send_aws_sns(text: str):
    """テキストをAWS SNSのトピックにPublishするツール"""
    topic_arn = os.getenv("SNS_TOPIC_ARN")
    if topic_arn:
        try:
            # SNSクライアントを作成してメッセージをパブリッシュ
            sns_client = boto3.client('sns')
            sns_client.publish(TopicArn=topic_arn, Message=text)
            return f"Message published to SNS: {text}"
        except Exception as e:
            return f"Error publishing to SNS: {str(e)}"
    else:
        # SNS_TOPIC_ARNが設定されていない場合はコンソールに出力
        print(f"SNS Message (no topic configured): {text}")
        return text

# エージェントが使用できるツールリストを構築
# web_searchが利用可能な場合は追加、そうでない場合はSNS送信ツールのみ
if web_search is not None:
    tools = [web_search, send_aws_sns]
else:
    tools = [send_aws_sns]

# Bedrockで使用するモデルID
MODEL_ID = "jp.anthropic.claude-haiku-4-5-20251001-v1:0"

# LLMモデルを初期化してツールにバインド
# init_chat_modelでBedrockからモデルを取得し、bind_toolsで上記のツールを付与
llm_with_tools = init_chat_model(
    model=MODEL_ID,
    model_provider="bedrock_converse"
).bind_tools(tools)

# エージェント状態を定義
# messagesは複数のメッセージを蓄積できるリスト（operator.addで追加される）
class AgentState(BaseModel):
    messages: Annotated[list[AnyMessage], operator.add]

# グラフビルダーを作成（AgentStateを状態管理オブジェクトとして使用）
builder = StateGraph(AgentState)

# エージェントに与えるシステムプロンプト（動作指示）
system_prompt = """
あなたの業務はユーザーからの質問を調査し、結果を要約してAWS SNSに送ることです。
検索は１回のみとしてください。
必ず send_aws_sns ツールを使用して、調査結果をSNSに送信してください。
"""

# エージェントノードの処理：LLMにメッセージを送信して応答を得る
# @toolでマークされた関数を自動的に認識してツールとして利用可能にする
async def agent(state: AgentState) -> Dict[str, List[AIMessage]]:
    # システムプロンプトと履歴メッセージをLLMに送信
    response = await llm_with_tools.ainvoke(
        [SystemMessage(system_prompt)] + state.messages
    )
    # LLMの応答をメッセージリストに追加
    return {"messages": [response]}

# グラフにノードを追加
# agentノード：LLMの推論処理を実行
builder.add_node("agent", agent)
# toolsノード：ツール呼び出しを実行（自動的にツールを実行して結果を返す）
builder.add_node("tools", ToolNode(tools))

# グラフのエッジ（遷移ルール）を定義する関数
# agent の出力に基づいて、次はtools ノードに遷移するか END に遷移するか判定
def route_node(state: AgentState) -> Union[str]:
    last_message = state.messages[-1]
    # 最後のメッセージにツール呼び出しがなければ終了
    if not hasattr(last_message, 'tool_calls') or not last_message.tool_calls:
        return END  # ENDノードへ遷移（処理終了）
    # ツール呼び出しがあれば tools ノードへ遷移
    return "tools"  # ツールノードへ遷移（ツール実行）

# グラフの構造を定義
# START → agent ノード（LLMの推論）
builder.add_edge(START, "agent")
# agent ノード → route_node で判定 → tools or END
builder.add_conditional_edges("agent", route_node)
# tools ノード → agent ノード（ツール実行後、再度LLMで処理）
builder.add_edge("tools", "agent")

# グラフをコンパイル（実行可能な形に変換）
graph = builder.compile()

# メイン処理：グラフを実行してエージェントの応答を取得
async def main():
    # ユーザーの質問を定義
    question = "LangGraphの基本をやさしく解説して"
    # グラフを非同期実行
    # 初期状態：HumanMessageとしてユーザー質問をメッセージリストに設定
    response = await graph.ainvoke(
        {"messages": [HumanMessage(question)]}
    )
    return response

# asyncio.runで非同期処理を実行
response = asyncio.run(main())
# 最終的なメッセージ履歴と応答結果を表示
print(response)
