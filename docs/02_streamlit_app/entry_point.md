# Streamlit アプリケーション - エントリーポイント

## 📄 ファイル位置

```
chapter4/4_streamlit_app.py
```

## 🚀 実行コマンド

```bash
streamlit run ./chapter4/4_streamlit_app.py
```

ブラウザで自動的に開きます（デフォルト: `http://localhost:8501`）

## 📋 コード構造

### 1. インポート

```python
import uuid                         # スレッド ID 生成用
import streamlit as st             # Streamlit フレームワーク
from langchain_core.messages import HumanMessage  # LangChain メッセージ
from langgraph.types import Command # LangGraph コマンド
from x_agent_core import agent      # エージェント実装をインポート
```

**用途**:
- `uuid`: 各エージェント実行に一意な ID を割り当て
- `streamlit`: UI コンポーネント提供
- `HumanMessage`: ユーザー入力をエージェントに渡す形式
- `Command`: エージェント実行の制御（resume など）
- `agent`: 実際のエージェント実装（`x_agent_core.py` から）

### 2. セッション状態の初期化

```python
def init_session_state():
  """セッション状態を初期化する"""
  if 'messages' not in st.session_state:
    st.session_state.messages = []              # チャット履歴
  if 'waiting_for_approval' not in st.session_state:
    st.session_state.waiting_for_approval = False  # ツール承認待機フラグ
  if 'final_result' not in st.session_state:
    st.session_state.final_result = None        # 最終結果
  if 'thread_id' not in st.session_state:
    st.session_state.thread_id = None           # エージェントスレッド ID
  if 'tool_info' not in st.session_state:
    st.session_state.tool_info = None           # 実行予定のツール情報
```

**重要**: Streamlit は ページをリロードするたびに スクリプト全体を再実行します。
そのため、`st.session_state` を使用してデータを保持します。

**各状態変数の役割**:

| 変数 | 型 | 用途 |
|---|---|---|
| `messages` | リスト | UI に表示するチャット履歴 |
| `waiting_for_approval` | bool | ツール実行待機時に True |
| `final_result` | str \| None | エージェントの最終応答 |
| `thread_id` | str \| None | エージェント実行のスレッド ID |
| `tool_info` | dict \| None | 実行待機中のツール情報 |

### 3. セッション リセット関数

```python
def reset_session():
  """セッション状態をリセットする"""
  st.session_state.messages = []
  st.session_state.waiting_for_approval = False
  st.session_state.final_result = None
  st.session_state.thread_id = None
```

**いつ呼ぶ**: 新しい質問を入力したとき

**理由**: 前の会話の状態を綺麗にするため

## 🔄 主要関数フロー

### `run_agent(input_data)`

ユーザー入力を受け取り、エージェントを実行する メイン関数。

```python
def run_agent(input_data):
  """エージェントを実行し、結果を処理する"""
  # 1. エージェント実行用の設定を作成
  config = {
    "configurable": {
      "thread_id": st.session_state.thread_id  # エージェントのスレッド ID
    }
  }

  # 2. エージェント実行開始（ストリーミング）
  with st.spinner("処理中...", show_time=True):
    for chunk in agent.stream(input_data, stream_mode="updates", config=config):
      # 3. ストリーム イベントを処理
      for task_name, result in chunk.items():
        ...
```

**ストリーム イベント処理**:

```python
if task_name == "__interrupt__":
    # ツール承認待機
    st.session_state.tool_info = result[0].value
    st.session_state.waiting_for_approval = True

elif task_name == "agent":
    # エージェント応答
    st.session_state.final_result = result.content

elif task_name == "invoke_llm":
    # LLM 推論結果
    if isinstance(chunk["invoke_llm"].content, list):
        for content in result.content:
            if content["type"] == "text":
                st.session_state.messages.append({
                    "role": "assistant",
                    "content": content["text"]
                })

elif task_name == "use_tool":
    # ツール実行完了
    if "write_file" in str(result.tool_call_id):
        st.session_state.messages.append({
            "role": "assistant",
            "content": "✅ ファイル保存が完了しました"
        })
```

### `feedback()`

ユーザーの承認 / 拒否 ボタンを表示します。

```python
def feedback():
  """フィードバックを取得し、エージェントに通知する関数"""
  approve_column, deny_column = st.columns(2)  # 2 列に分割

  feedback_result = None
  with approve_column:
    if st.button("APPROVE", width="stretch"):
      feedback_result = "APPROVE"
  with deny_column:
    if st.button("DENY", width="stretch"):
      feedback_result = "DENY"

  return feedback_result
```

**ボタンの動作**:
- **APPROVE**: ツールを実行する（エージェント再開）
- **DENY**: ツールをスキップする（エージェント再開）

### `app()`

メイン UI 関数。すべての UI ロジックを統合します。

## 📺 UI フロー詳細

### 1. 初期状態

```
┌─────────────────────────────────────────┐
│  Webリサーチエージェント                 │
├─────────────────────────────────────────┤
│                                         │
│  (メッセージ表示エリア - 空)             │
│                                         │
├─────────────────────────────────────────┤
│  [メッセージを入力してください]  ←─ 入力フォーム
│                                         │
└─────────────────────────────────────────┘
```

### 2. ユーザーが質問を入力

```python
user_input = st.chat_input("メッセージを入力してください")
if user_input:
    reset_session()  # セッションをリセット
    st.session_state.thread_id = str(uuid.uuid4())  # スレッド ID 生成
    st.chat_message("user").write(user_input)  # ユーザーメッセージを表示
    st.session_state.messages.append({
        "role": "user",
        "content": user_input
    })
    messages = [HumanMessage(content=user_input)]
    run_agent(messages)  # エージェント実行
```

### 3. エージェント実行中

```
┌─────────────────────────────────────────┐
│  処理中... (X秒)                        │
│  LLMが応答を生成しています...           │
└─────────────────────────────────────────┘
```

### 4. ツール承認画面

```
┌─────────────────────────────────────────┐
│ ⚠️ ツール実行の確認が必要です            │
├─────────────────────────────────────────┤
│ * ツール名                              │
│  ・write_file                           │
│ * 保存ファイル名                        │
│  * output.html                          │
│                                         │
│ プレビュー:                             │
│ ┌─────────────────────────────────────┐ │
│ │ <html>...</html>  (HTML表示)        │ │
│ └─────────────────────────────────────┘ │
│                                         │
│ [APPROVE]  [DENY]                       │
└─────────────────────────────────────────┘
```

### 5. 完了画面

```
┌─────────────────────────────────────────┐
│ ✅ 処理が完了しました                   │
├─────────────────────────────────────────┤
│ 結果: Bedrockについて調べました...      │
│                                         │
│ チャット履歴:                           │
│ あなた:                                 │
│ Bedrockについて調べて                   │
│                                         │
│ アシスタント:                           │
│ 検索します...                           │
│ ✅ ツール実行が完了しました             │
│ ✅ ファイル保存が完了しました           │
│                                         │
├─────────────────────────────────────────┤
│ [メッセージを入力してください]          │
└─────────────────────────────────────────┘
```

## 🔗 x_agent_core.py との連携

### インポート

```python
from x_agent_core import agent
```

このインポートで、`x_agent_core.py` の `agent` 関数を取得します。

### 呼び出し

```python
for chunk in agent.stream(input_data, stream_mode="updates", config=config):
    ...
```

**パラメータ**:
- `input_data`: 入力（`HumanMessage` のリスト）
- `stream_mode="updates"`: ストリーミング モード（各タスクの更新を受け取る）
- `config`: 設定（スレッド ID など）

### 戻り値

ストリーム イベント:
```python
chunk = {
    "task_name": result_object
}
```

**task_name の種類**:
- `invoke_llm`: LLM 推論
- `use_tool`: ツール実行
- `agent`: エージェント完了
- `__interrupt__`: 中断（ユーザー承認待機）

## 📚 参考資料

- [Streamlit API Reference](https://docs.streamlit.io/develop/api-reference)
- [Streamlit Session State](https://docs.streamlit.io/develop/concepts/design/session-state)
- [LangGraph Streaming](https://langchain-ai.github.io/langgraph/concepts/streaming/)
- [LangChain Message Types](https://python.langchain.com/api_reference/core/messages.html)

---

**次のステップ**: [セッション管理の詳細](./session_management.md)
