import operator
from pydantic import BaseModel
from typing import Annotated, Literal, Dict, Any
from langgraph.graph import StateGraph, START, END


# 100,101ページ
class State(BaseModel):
    id: int
    messages: Annotated[list[str], operator.add]

# ノード関数の定義
def search_web(state: State) -> Dict[str, Any]:
    return {"id": 123, "messages": ["WebSearch"]}

def summarize(state: State) -> Dict[str, Any]:
    return {"id": 123, "messages": ["Summarizer"]}

def save_record(state: State) -> Dict[str, Any]:
    return {"id": 123, "messages": ["Recoder"]}

# ルーティング関数の定義
def routing_function(state: State) -> Literal["Summarizer", "Recoder"]:
    if state.id == 123:
        return "Summarizer"  # Summarizerに遷移する
    else:
        return "Recoder"  # Recoderに遷移する

# グラフビルダーの作成
builder = StateGraph(State)

# ノードの定義
builder.add_node("WebSearch", search_web)
builder.add_node("Summarizer", summarize)
builder.add_node("Recoder", save_record)

# エッジの定義
builder.add_edge(START, "WebSearch")
builder.add_conditional_edges("WebSearch", routing_function)
builder.add_edge("Summarizer", END)
builder.add_edge("Recoder", END)

# グラフのコンパイル
graph = builder.compile()

# グラフの同期実行
response = graph.invoke({"id": 123, "messages": ["start"]})
print(response)
