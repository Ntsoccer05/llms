# LangGraph パターン集：よく使う処理テンプレート

このドキュメントは、LangGraph で繰り返し出てくる処理パターンを「テンプレート化」したものです。慣れるのではなく、パターンを覚えることで効率的に開発できます。

---

## パターン 1: 基本的なエージェント構造

### 用途
ユーザー入力 → LLM 呼び出し → ツール実行 → 結果返却

### テンプレート

```python
from langchain.chat_models import init_chat_model
from langchain_core.messages import AnyMessage, AIMessage, HumanMessage, SystemMessage
from langgraph.graph import StateGraph, START, END
from langgraph.prebuilt import ToolNode
from pydantic import BaseModel
from typing import Annotated, Dict, List, Union
import operator

# ① ステート定義
class AgentState(BaseModel):
    messages: Annotated[list[AnyMessage], operator.add]
    # ↑ operator.add により、メッセージが「追加」されていく

# ② LLM 初期化
llm_with_tools = init_chat_model(model="...").bind_tools(tools)

# ③ ノード関数定義
async def agent(state: AgentState) -> Dict[str, List[AIMessage]]:
    """LLM を呼び出すノード"""
    response = await llm_with_tools.ainvoke(
        [SystemMessage(system_prompt)] + state.messages
    )
    return {"messages": [response]}

def route_node(state: AgentState) -> Union[str]:
    """ツール呼び出しが必要かを判定"""
    last_message = state.messages[-1]
    if not isinstance(last_message, AIMessage):
        raise ValueError("AIMessage 以外が来たのでバグ")

    if not last_message.tool_calls:
        return END  # ツール呼び出しなし → 終了
    return "tools"  # ツール呼び出しあり → tools ノードへ

# ④ グラフ構築
builder = StateGraph(AgentState)
builder.add_node("agent", agent)
builder.add_node("tools", ToolNode(tools))

builder.add_edge(START, "agent")
builder.add_conditional_edges("agent", route_node)
builder.add_edge("tools", "agent")  # ツール結果で再度 LLM へ

graph = builder.compile(name="MyAgent")

# ⑤ グラフ実行
result = await graph.ainvoke({
    "messages": [HumanMessage("質問")]
})
```

### このテンプレートを理解するコツ

**覚えるべき 3 つのこと：**

1. **messages フィールドは「リスト連結」する**
   ```python
   messages: Annotated[list[AnyMessage], operator.add]
   #         ↑ これにより、return {"messages": [...]} は「追加」される
   ```

2. **agent 関数は必ず AIMessage を返す**
   ```python
   return {"messages": [response]}  # response = AIMessage
   ```

3. **route_node は次のノード名を返す**
   ```python
   if ツール呼び出し必要:
       return "tools"
   else:
       return END
   ```

---

## パターン 2: メッセージのトレース（デバッグ用）

### 用途
グラフの実行過程でメッセージがどう変わるか確認したい

### テンプレート

```python
def trace_messages(state: AgentState) -> None:
    """メッセージの履歴を表示（デバッグ用）"""
    print("\n========== メッセージ履歴 ==========")
    for i, msg in enumerate(state.messages):
        msg_type = type(msg).__name__
        content = msg.content[:50] if hasattr(msg, 'content') else str(msg)[:50]
        tool_calls = getattr(msg, 'tool_calls', None)

        print(f"{i}: [{msg_type}] {content}")
        if tool_calls:
            print(f"   → ツール呼び出し: {[t['function'] for t in tool_calls]}")

# グラフの各ステップ後に呼び出し
async def debug_main():
    # ... グラフ定義 ...

    result = await graph.ainvoke({
        "messages": [HumanMessage("質問")]
    })

    trace_messages(AgentState(**result))
```

**出力例：**
```
========== メッセージ履歴 ==========
0: [HumanMessage] 質問
1: [AIMessage] 検索します
   → ツール呼び出し: ['search_aws_docs']
2: [ToolMessage] 検索結果: Bedrock は ...
3: [AIMessage] 検索結果は...
```

---

## パターン 3: カスタムツール追加

### 用途
LLM が使える新しいツールを追加したい

### テンプレート

```python
from langchain_core.tools import tool

# ① ツール関数を @tool デコレータで定義
@tool
def my_custom_tool(query: str) -> str:
    """ツールの説明

    Args:
        query: 検索キーワード

    Returns:
        検索結果
    """
    # 実装
    result = f"'{query}' の検索結果"
    return result

# ② ツールリストに追加
tools = [existing_tool, my_custom_tool]

# ③ LLM にバインド
llm_with_tools = init_chat_model(model="...").bind_tools(tools)

# これで LLM が my_custom_tool を使えるようになる
```

**ツール定義のコツ：**

```python
@tool
def tool_name(param1: str, param2: int) -> str:
    """ツールの説明（LLM が参照する）

    Args:
        param1: パラメータ 1 の説明
        param2: パラメータ 2 の説明

    Returns:
        戻り値の説明
    """
    # 実装
    return result
```

LLM は docstring を読んで、ツールの使い方を判断する。

---

## パターン 4: 条件分岐（複数の結果処理）

### 用途
LLM の応答に応じて異なる処理をしたい（例：検索 → ファイル保存 → メール送信）

### テンプレート

```python
def route_node(state: AgentState) -> Union[str]:
    """複数の分岐を持つルーティング"""
    last_message = state.messages[-1]

    if not isinstance(last_message, AIMessage):
        raise ValueError("バグ")

    # tool_calls の内容で分岐
    if not last_message.tool_calls:
        return END

    # 複数の分岐パターン
    tool_name = last_message.tool_calls[0]['function']

    if tool_name == "search":
        return "search_node"
    elif tool_name == "save_file":
        return "save_node"
    elif tool_name == "send_email":
        return "email_node"
    else:
        return "default_node"

# グラフに複数のノードを追加
builder.add_node("agent", agent)
builder.add_node("search_node", search_node)
builder.add_node("save_node", save_node)
builder.add_node("email_node", email_node)

# 条件付きエッジで分岐
builder.add_conditional_edges("agent", route_node)
```

---

## パターン 5: ループ制御（無限ループ防止）

### 用途
ツールが何度も呼ばれるのを制限したい

### テンプレート

```python
class AgentState(BaseModel):
    messages: Annotated[list[AnyMessage], operator.add]
    tool_call_count: int = 0  # ← ツール呼び出し回数を追跡

def route_node(state: AgentState) -> Union[str]:
    last_message = state.messages[-1]

    if not isinstance(last_message, AIMessage):
        raise ValueError("バグ")

    # ツール呼び出し回数をチェック
    MAX_TOOL_CALLS = 3
    if state.tool_call_count >= MAX_TOOL_CALLS:
        print("ツール呼び出し回数の上限に達しました")
        return END

    if not last_message.tool_calls:
        return END

    return "tools"

def tools_node(state: AgentState) -> Dict:
    """tools ノードから戻る時に call_count を増やす"""
    # ... ツール実行 ...
    return {
        "messages": [tool_result],
        "tool_call_count": state.tool_call_count + 1
    }

builder.add_node("tools", tools_node)
```

---

## パターン 6: 状態フィルタリング（クリーンアップ）

### 用途
不要なメッセージを削除したい、またはメッセージ数を制限したい

### テンプレート

```python
def cleanup_node(state: AgentState) -> Dict:
    """古いメッセージを削除し、最新 N 件だけ保持"""
    KEEP_MESSAGES = 5

    # 最新 N 件だけ保持
    if len(state.messages) > KEEP_MESSAGES:
        # システムメッセージは保持、古いメッセージを削除
        system_msgs = [m for m in state.messages if isinstance(m, SystemMessage)]
        recent_msgs = state.messages[-KEEP_MESSAGES:]
        filtered = system_msgs + recent_msgs
        return {"messages": filtered}

    return {}  # 変更なし

# グラフの最後に追加
builder.add_node("cleanup", cleanup_node)
builder.add_edge("agent", "cleanup")
builder.add_edge("cleanup", "...)
```

---

## パターン 7: 並列処理（複数ツール同時実行）

### 用途
複数のツールを同時に実行したい

### テンプレート

```python
import asyncio

async def parallel_tools_node(state: AgentState) -> Dict:
    """複数のツールを並列実行"""
    last_message = state.messages[-1]

    if not last_message.tool_calls:
        return {}

    # tool_calls を実行（並列化）
    tasks = []
    for tool_call in last_message.tool_calls:
        task = execute_tool(
            tool_call['function'],
            tool_call['args']
        )
        tasks.append(task)

    # すべてのツール実行を待つ
    results = await asyncio.gather(*tasks)

    # 結果をメッセージに変換
    tool_messages = [
        ToolMessage(content=str(r), tool_use_id=tc['id'])
        for r, tc in zip(results, last_message.tool_calls)
    ]

    return {"messages": tool_messages}

async def execute_tool(tool_name: str, args: dict):
    """ツール実行（非同期）"""
    # 実装
    return result
```

---

## パターン 8: エラーハンドリング

### 用途
ツール実行時のエラーを処理したい

### テンプレート

```python
def safe_tools_node(state: AgentState) -> Dict:
    """エラーハンドリング付きツール実行"""
    last_message = state.messages[-1]

    if not last_message.tool_calls:
        return {}

    tool_messages = []
    for tool_call in last_message.tool_calls:
        try:
            result = execute_tool(
                tool_call['function'],
                tool_call['args']
            )
            tool_messages.append(
                ToolMessage(content=result, tool_use_id=tool_call['id'])
            )
        except Exception as e:
            # エラーメッセージを返す
            tool_messages.append(
                ToolMessage(
                    content=f"エラー: {str(e)}",
                    tool_use_id=tool_call['id']
                )
            )

    return {"messages": tool_messages}
```

---

## パターン 9: 入力検証

### 用途
ユーザー入力を検証してから処理したい

### テンプレート

```python
class AgentState(BaseModel):
    messages: Annotated[list[AnyMessage], operator.add]
    is_valid: bool = True  # 入力の妥当性
    error_message: str = ""  # エラーメッセージ

async def validate_node(state: AgentState) -> Dict:
    """入力を検証"""
    last_message = state.messages[-1]

    if not isinstance(last_message, HumanMessage):
        return {}

    # 入力検証ロジック
    query = last_message.content

    if len(query) < 3:
        return {
            "is_valid": False,
            "error_message": "3文字以上入力してください"
        }

    if len(query) > 500:
        return {
            "is_valid": False,
            "error_message": "500文字以内にしてください"
        }

    return {"is_valid": True, "error_message": ""}

def route_after_validation(state: AgentState) -> Union[str]:
    """検証結果に応じてルーティング"""
    if not state.is_valid:
        # エラーメッセージを返して終了
        return END
    return "agent"

builder.add_edge(START, "validate")
builder.add_node("validate", validate_node)
builder.add_conditional_edges("validate", route_after_validation)
```

---

## パターン 10: グラフの可視化・デバッグ

### 用途
グラフの構造を確認したい

### テンプレート

```python
# ① グラフ構造を図で表示
import json

def visualize_graph(graph):
    """グラフの構造を JSON で表示"""
    graph_dict = graph.get_graph().to_dict()
    print(json.dumps(graph_dict, indent=2, ensure_ascii=False))

visualize_graph(graph)

# ② ステップごとの実行を見る
async def debug_invoke():
    """ステップバイステップで実行"""
    input_state = {"messages": [HumanMessage("質問")]}

    # stream() で各ステップの出力を見る
    async for event in graph.astream(input_state):
        print(f"ノード出力: {event}")

await debug_invoke()

# ③ メッセージの履歴を表示
def show_result(result: Dict):
    """最終結果を見やすく表示"""
    print("\n=== 実行結果 ===")
    for i, msg in enumerate(result['messages']):
        print(f"\n{i}. {type(msg).__name__}")
        if hasattr(msg, 'content'):
            print(f"   {msg.content[:100]}")
        if hasattr(msg, 'tool_calls') and msg.tool_calls:
            print(f"   ツール: {msg.tool_calls}")

show_result(result)
```

---

## まとめ：速く習得するコツ

### 1. テンプレートを暗記する（丸暗記でOK）
```python
# 必ずこの構造
class State(BaseModel):
    messages: Annotated[list[AnyMessage], operator.add]

async def agent(state: State) -> Dict[str, List[AIMessage]]:
    response = await llm.ainvoke([SystemMessage(...)] + state.messages)
    return {"messages": [response]}

def route(state: State) -> Union[str]:
    last = state.messages[-1]
    if not isinstance(last, AIMessage):
        raise ValueError()
    if last.tool_calls:
        return "tools"
    return END
```

### 2. 実際に書いて試す
- 完璧に理解しようとしない
- テンプレートを使って簡単なエージェントを作る
- エラーが出たら、エラーメッセージから学ぶ

### 3. 1つずつ改造する
```
基本テンプレート
  ↓
ツール追加
  ↓
ループ制限追加
  ↓
エラーハンドリング追加
```

### 4. LangGraph のドキュメントをテンプレートとして使う
- 「パターンAはこう書く」「パターンBはこう書く」と覚える
- 「なぜこう書くのか」は後から理解でOK

---

**慣れるのではなく、パターンを覚える。これが効率的です！**

最終更新: 2025年12月22日
