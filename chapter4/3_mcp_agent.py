import asyncio
import operator
import os
from langchain.chat_models import init_chat_model
from langchain_core.messages import AnyMessage, AIMessage, HumanMessage, SystemMessage
from langchain_mcp_adapters.client import MultiServerMCPClient
from langgraph.graph import StateGraph, START, END
from langgraph.prebuilt import ToolNode
from pydantic import BaseModel
from typing import Annotated, Dict, List, Union

from dotenv import load_dotenv
load_dotenv()

mcp_client = None
tools = None
llm_with_tools = None

MODEL_ID = "jp.anthropic.claude-haiku-4-5-20251001-v1:0"

async def initialize_llm():
  """MCP クライアントとツールを初期化する"""
  global mcp_client, tools, llm_with_tools

  try:
    mcp_client = MultiServerMCPClient(
      {
        # Filesystem MCPサーバー
        "file-system": {
          "command": "npx",
          "args": [
            "-y",
            "@modelcontextprotocol/server-filesystem",
            "./"
          ],
          # "transport": "stdio"は通信プロトコルを指定
          # stdio = 標準入出力(stdin/stdout)を使ってMCPサーバーと通信
          # MCPサーバーはプロセスとして起動され、JSON-RPCメッセージを stdin/stdout でやり取りする
          # 他のオプション: "streamable_http" (HTTP通信), "sse" (Server-Sent Events) など
          "transport": "stdio"
        },
        # AWS Knowledge MCPサーバー
        "aws-knowledge-mcp-server": {
          "url": "https://knowledge-mcp.global.api.aws",
          "transport": "streamable_http"
        }
      }
    )

    print("[初期化中] MCPクライアントを起動しています...")

    # MCPサーバーをLangChainツールとして取得
    # get_tools()は接続したすべてのMCPサーバーから全ツール定義を取得
    # 戻り値: LangChainの Tool オブジェクトのリスト
    # ここでは filesystem ツール（ファイル操作）と aws-knowledge ツール（AWS検索）が取得される
    tools = await mcp_client.get_tools()
    print(f"[初期化完了] {len(tools)}個のツールを取得しました")

    # LLMの初期化
    llm_with_tools = init_chat_model(
      model=MODEL_ID,
      model_provider="bedrock_converse"
    ).bind_tools(tools)

    print("[LLM初期化] Claude Haiku 4.5をbedrock_converseで初期化しました")

  except Exception as e:
    print(f"[エラー] MCP初期化に失敗しました: {e}")
    import traceback
    traceback.print_exc()
    raise


# ステートの定義
class AgentState(BaseModel):
    # messages フィールド:
    # - list[AnyMessage]: メッセージのリスト（HumanMessage, AIMessage, ToolMessage など任意のメッセージ型）
    # - Annotated[..., operator.add]: LangGraphの特別な指定
    #   → グラフを実行するたびにメッセージが「追加」されていく（上書きではなく追記）
    #   例: messages=[HumanMessage("Q1")] → messages=[HumanMessage("Q1"), AIMessage("A1")] → ...
    # このため、会話履歴が保持され、エージェントが過去のやりとりを参照できる
    messages: Annotated[list[AnyMessage], operator.add]

system_prompt = """
あなたの責務はAWSドキュメントを検索し、Markdown形式としてファイル出力することです。
- 検索後、Markdown形式に変換してください。
- 検索は最大で２回までとし、その時点での情報を出力してください。

【重要：ファイルパスについて】
ファイルを保存する場合は、必ず相対パス（ドットスラッシュで始まるパス）を使用してください。
正しい例：./bedrock_models.md  ./results/output.md
間違った例：C:\\tmp\\file.md  /tmp/file.md  ../../../tmp/file.md
必ず ./ で始まるパスを使用してください。
"""

# エージェントノード（LLM実行部分）
# 役割: ユーザーの質問に対してLLMを呼び出し、ツール呼び出しが必要かを判定する
async def agent(state: AgentState) -> Dict[str, List[AIMessage]]:
  # 引数 state: AgentState
  #   └─ state.messages: 過去のメッセージ履歴（HumanMessage, AIMessage, ToolMessage）
  #
  # 処理:
  # 1. SystemMessage(system_prompt) + state.messages を LLM に送信
  #    → システムプロンプト + 全メッセージ履歴をLLMに与える
  # 2. LLMが応答を生成（AIMessage）
  # 3. AIMessage内のtool_callsプロパティにツール呼び出し情報が含まれる場合がある
  #
  # 戻り値: Dict[str, List[AIMessage]]
  #   └─ {"messages": [response]}
  #   response は AIMessage （LLMの応答）
  #   辞書形式で返すことで、LangGraphの状態更新メカニズムと連携
  try:
    response = await llm_with_tools.ainvoke(
      [SystemMessage(system_prompt)] + state.messages
    )
    return {"messages": [response]}
  except Exception as e:
    print(f"[エージェントエラー] LLM実行に失敗しました: {e}")
    # エラーメッセージをAIMessageとして返す（グラフが停止しないように）
    error_msg = AIMessage(content=f"申し訳ありません。処理中にエラーが発生しました: {str(e)}")
    return {"messages": [error_msg]}

# ルーティング関数：toolsノードかENDノードへ遷移する
# 役割: LLMの応答を判定し、ツール呼び出しが必要かどうかを決める
# 戻り値の型: Union[str] = 文字列型の値を返す（"tools" または END）
#   - Union[str] は「文字列またはその他の型」を表す型ヒント
#   - ここでは返す値は常に str 型 ("tools" または END定数)
def route_node(state: AgentState) -> Union[str]:
  last_message = state.messages[-1]

  # isinstance(last_message, AIMessage) で、メッセージが AIMessage型 かを判定
  # AIMessage = AI（LLM）が生成したメッセージ
  # 他の型: HumanMessage（ユーザー入力）, ToolMessage（ツール実行結果）など
  #
  # なぜ「エージェントノード直後なので AIMessage であるべき」？
  # グラフの遷移を見ると：
  #   1. START → agent ノード         (agent が必ず AIMessage を返す)
  #   2. agent → route_node で判定
  #   3. tools → agent (ここで再び agent が実行される)
  #
  # つまり route_node が実行されるのは、常に agent ノードの直後
  # agent ノードは必ず {"messages": [AIMessage]} を返す
  # （agent 関数の戻り値型を見ると -> Dict[str, List[AIMessage]]）
  # だから route_node に来る時点での last_message は必ず AIMessage のはず
  #
  # もし AIMessage 以外が来たら、グラフの設計が壊れている（バグ）
  if not isinstance(last_message, AIMessage):
      raise ValueError("「AIMessage」以外のメッセージです。遷移が不正な可能性があります。")

  # last_message.tool_calls を確認
  # tool_calls = LLMがツール呼び出しを指定したかどうか
  # - リストが空 → ツール呼び出しなし → END（処理終了）
  # - リストに要素あり → ツール呼び出しあり → "tools" ノードで実行
  if not last_message.tool_calls:
      return END  # ENDノードへ遷移（エージェント処理終了）
  return "tools"  # toolsノードへ遷移（ツール実行）

async def main():
  try:
    #  MCPクライアントとツールを初期化
    await initialize_llm()

    #  グラフを構築
    builder = StateGraph(AgentState)
    builder.add_node("agent", agent)
    # ToolNode に handle_tool_errors=True を指定してエラーハンドリングを有効化
    # これにより、ツール実行エラーが発生してもグラフが停止せず、エラーメッセージが返される
    builder.add_node("tools", ToolNode(tools, handle_tool_errors=True))

    # グラフの遷移ルール（エッジ）を定義
    builder.add_edge(START, "agent")  # START → agent ノードへ
    builder.add_conditional_edges(
       "agent",
       route_node
       # route_node の戻り値に応じて遷移先を決定
       # "tools" → tools ノードへ
       # END → グラフ終了
    )
    # builder.add_edge("tools", "agent") は何を表しているか？
    # 「tools ノード実行後、再び agent ノードへ遷移」を意味する
    # つまり、ツール実行結果を含むメッセージで LLM を再度呼び出す（ループ）
    # 流れ: START → agent（LLM） → tools（ツール実行） → agent（再度LLM） → ...
    builder.add_edge("tools", "agent")

    # graph = builder.compile(name="ReAct Agent") は何をしている？
    # name="ReAct Agent" は単なる名前付け（任意の名前をつけられる）
    # グラフの ID や UI表示用に使われる（処理ロジックに影響しない）
    # compile() は StateGraph を実行可能な CompiledStateGraph に変換
    graph = builder.compile(name="ReAct Agent")

    question = "Bedrockで利用可能なモデルプロバイダーを教えて！"

    # graph.ainvoke() は非同期でグラフを実行する関数
    # invoke() = 同期実行, ainvoke() = 非同期実行（並列処理に対応）
    # 入力: {"messages": [HumanMessage(...)]}
    # 処理フロー:
    #   1. START → agent ノード（LLM呼び出し）
    #   2. route_node で判定
    #      - ツール呼び出し必要 → tools ノード → agent ノード（ループ）
    #      - 不要 → END
    # 出力: 最終的な state （全メッセージ履歴を含む）
    response = await graph.ainvoke(
       {
          "messages": [HumanMessage(question)]
       }
    )

    # ================================================================================
    # Unicode エンコーディング対応
    # ================================================================================
    # Windows の cp932 では日本語を含むテキストが出力できないため、
    # 以下の対応をしている：
    #
    # 1. JSON形式で出力（日本語も正しく表示）
    # 2. またはテキストを処理しやすい形に加工
    #
    # エラー例：
    #   UnicodeEncodeError: 'cp932' codec can't encode character '\xe3'
    # ================================================================================

    import sys

    print("\n========== グラフ実行完了 ==========\n")

    # メッセージの数を表示
    print(f"メッセージ数: {len(response['messages'])}\n")

    # 各メッセージを見やすく表示
    for i, msg in enumerate(response['messages']):
      msg_type = type(msg).__name__
      print(f"[{i}] メッセージタイプ: {msg_type}")

      if hasattr(msg, 'content'):
        # content を UTF-8 で出力（cp932 の問題を回避）
        content = msg.content[:200] if len(msg.content) > 200 else msg.content
        # 日本語を含むテキストの安全な出力
        sys.stdout.buffer.write(f"    内容: {content}\n".encode('utf-8'))

      if hasattr(msg, 'tool_calls') and msg.tool_calls:
        print(f"    ツール呼び出し数: {len(msg.tool_calls)}")
        for tool_call in msg.tool_calls:
          print(f"      - {tool_call['function']}")

      print()

    return response

  except Exception as e:
    print(f"\n[致命的エラー] 実行に失敗しました: {e}")
    import traceback
    traceback.print_exc()
    return None

asyncio.run(main())