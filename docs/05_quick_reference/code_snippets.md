# クイックリファレンス - コードスニペット集

## 🔧 よく使うコード例

### 1. Streamlit - ユーザー入力を受け取る

```python
user_input = st.chat_input("メッセージを入力してください")
if user_input:
    st.session_state.messages.append({
        "role": "user",
        "content": user_input
    })
```

### 2. Streamlit - メッセージを表示

```python
for msg in st.session_state.messages:
    if msg["role"] == "user":
        st.chat_message("user").write(msg["content"])
    else:
        st.chat_message("assistant").write(msg["content"])
```

### 3. Streamlit - セッション状態の操作

```python
# 状態を設定
st.session_state.my_state = "value"

# 状態を読み込み
current_value = st.session_state.my_state

# 状態を確認
if "my_state" in st.session_state:
    print(st.session_state.my_state)

# 状態をリセット
del st.session_state.my_state
```

### 4. Streamlit - UI コンポーネント

```python
# ボタン
if st.button("クリック"):
    st.write("ボタンが押されました")

# テキスト入力
name = st.text_input("名前を入力:")

# チェックボックス
agree = st.checkbox("同意します")

# 選択ボックス
option = st.selectbox("選択してください", ["Option 1", "Option 2"])

# スライダー
value = st.slider("値を選択", 0, 100)

# 警告・情報メッセージ
st.warning("警告メッセージ")
st.info("情報メッセージ")
st.success("成功メッセージ")
st.error("エラーメッセージ")
```

### 5. LangChain - メッセージの作成

```python
from langchain_core.messages import (
    HumanMessage,
    AIMessage,
    SystemMessage,
    ToolMessage
)

# ユーザーメッセージ
user_msg = HumanMessage(content="こんにちは")

# AI メッセージ（ツール呼び出し付き）
ai_msg = AIMessage(
    content="検索します",
    tool_calls=[
        {
            "name": "web_search",
            "args": {"query": "Python"},
            "id": "call_123"
        }
    ]
)

# ツール結果メッセージ
tool_msg = ToolMessage(
    content="検索結果: ...",
    tool_call_id="call_123"
)

# システムプロンプト
sys_msg = SystemMessage(content="あなたはアシスタントです")
```

### 6. LangGraph - エージェント実行

```python
# 単一実行
response = agent.invoke({"messages": [HumanMessage("質問")]})

# ストリーミング実行
config = {
    "configurable": {
        "thread_id": "thread_123"
    }
}

for chunk in agent.stream(
    {"messages": [HumanMessage("質問")]},
    stream_mode="updates",
    config=config
):
    print(chunk)

# エージェントの再開（ユーザー入力後）
from langgraph.types import Command
response = agent.invoke(
    Command(resume="APPROVE")
)
```

### 7. ツール定義 - カスタムツール

```python
from langchain_core.tools import tool

@tool
def my_function(input_text: str) -> str:
    """ツールの説明

    Args:
        input_text: 入力テキスト

    Returns:
        処理結果
    """
    # 処理
    return f"結果: {input_text}"

# 使用
tools = [my_function, other_tool]
```

### 8. ツール定義 - Tool クラス

```python
from langchain_core.tools import Tool

def my_function(x: int) -> int:
    return x * 2

tool = Tool(
    name="double_number",
    func=my_function,
    description="数字を 2 倍にします"
)

tools = [tool, ...]
```

### 9. エラーハンドリング

```python
try:
    response = agent.invoke(input_data)
except Exception as e:
    st.error(f"エラー: {str(e)}")
    print(f"詳細: {type(e).__name__}")
```

### 10. ロギング

```python
import logging

# ログレベル設定
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ログ出力
logger.info("処理開始")
logger.warning("警告")
logger.error("エラー発生")
```

## 📊 データ構造リファレンス

### AIMessage with tool_calls

```python
{
    "content": "検索します",
    "tool_calls": [
        {
            "name": "write_file",
            "args": {
                "file_path": "output.html",
                "text": "<html>...</html>"
            },
            "id": "call_abc123",
            "type": "tool_call"
        }
    ]
}
```

### ストリーム イベント

```python
# invoke_llm イベント
{
    "invoke_llm": AIMessage(content="...")
}

# __interrupt__ イベント
{
    "__interrupt__": [
        Interrupt(value={
            "name": "write_file",
            "args": "...",
            "html": "..."
        })
    ]
}

# use_tool イベント
{
    "use_tool": ToolMessage(content="...")
}

# agent イベント
{
    "agent": AIMessage(content="完了")
}
```

### セッション状態

```python
st.session_state = {
    "messages": [
        {"role": "user", "content": "..."},
        {"role": "assistant", "content": "..."}
    ],
    "waiting_for_approval": False,
    "tool_info": {
        "name": "write_file",
        "args": "...",
        "html": "..."
    },
    "final_result": "完了しました",
    "thread_id": "uuid-string"
}
```

## 🎯 一般的なタスク

### タスク 1: エージェント実行結果を全て表示

```python
response = agent.invoke(input_data)

# 全メッセージを表示
for msg in response["messages"]:
    print(f"{type(msg).__name__}: {msg.content}")
    if hasattr(msg, "tool_calls") and msg.tool_calls:
        print(f"  ツール呼び出し: {[tc['name'] for tc in msg.tool_calls]}")
```

### タスク 2: ツール呼び出しを判定

```python
if isinstance(message, AIMessage) and message.tool_calls:
    print(f"ツール呼び出しあり: {len(message.tool_calls)}件")
    for tool_call in message.tool_calls:
        print(f"  - {tool_call['name']}")
else:
    print("ツール呼び出しなし（エージェント終了）")
```

### タスク 3: 特定のツールのみ実行

```python
for tool_call in ai_message.tool_calls:
    if tool_call["name"] == "write_file":
        # ユーザー承認を待つ
        approval = get_user_approval()
        if approval:
            result = tool_by_name["write_file"].invoke(tool_call["args"])
```

### タスク 4: メッセージ履歴から特定の内容を抽出

```python
# 最後の LLM 応答を取得
last_response = None
for msg in messages[::-1]:  # 逆順でループ
    if isinstance(msg, AIMessage):
        last_response = msg
        break

# 全ツール呼び出しを集める
all_tool_calls = []
for msg in messages:
    if isinstance(msg, AIMessage) and msg.tool_calls:
        all_tool_calls.extend(msg.tool_calls)

# ツール実行結果を集める
tool_results = []
for msg in messages:
    if isinstance(msg, ToolMessage):
        tool_results.append(msg.content)
```

## 🔍 デバッグ技法

### デバッグ 1: ストリーム イベントを全て表示

```python
for chunk in agent.stream(input_data, stream_mode="updates", config=config):
    print(f"イベント: {list(chunk.keys())}")
    for task_name, result in chunk.items():
        print(f"  {task_name}: {type(result).__name__}")
```

### デバッグ 2: メッセージの詳細情報を表示

```python
for msg in messages:
    print(f"\n{type(msg).__name__}:")
    print(f"  content: {msg.content[:100]}...")
    if hasattr(msg, "tool_calls"):
        print(f"  tool_calls: {msg.tool_calls}")
    if hasattr(msg, "tool_call_id"):
        print(f"  tool_call_id: {msg.tool_call_id}")
```

### デバッグ 3: セッション状態を表示

```python
print("=== セッション状態 ===")
for key, value in st.session_state.items():
    if isinstance(value, list):
        print(f"{key}: リスト (長さ={len(value)})")
    elif isinstance(value, dict):
        print(f"{key}: 辞書 (キー={list(value.keys())})")
    else:
        print(f"{key}: {value}")
```

## 📚 参考リンク

- [Streamlit API](https://docs.streamlit.io/develop/api-reference)
- [LangChain ドキュメント](https://python.langchain.com/docs/)
- [LangGraph ドキュメント](https://langchain-ai.github.io/langgraph/)
- [AWS Bedrock API](https://docs.aws.amazon.com/bedrock/latest/APIReference/)

---

**その他のガイド**: [トラブルシューティング](./troubleshooting.md)
