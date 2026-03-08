# データフロー図

## 📤 シーケンス図：ユーザーが質問を入力

```
ユーザー          Streamlit           エージェント          LLM          外部ツール
  │                 │                     │              │                │
  │─ 質問入力 ─→    │                     │              │                │
  │                 │─ セッション初期化 ─→               │                │
  │                 │─ agent.stream()呼び出し──────→    │                │
  │                 │                     │              │                │
  │                 │←─────── ストリーム開始 ─────────   │                │
  │                 │                     │              │                │
  │                 │     invoke_llm イベント           │                │
  │                 │←───────────────────┤              │                │
  │                 │     (LLM推論中...)  │              │                │
  │                 │                     │─ 質問送信 ─→│                │
  │                 │                     │              │                │
  │                 │                     │←─ 応答 ──────│                │
  │                 │     invoke_llm イベント            │                │
  │                 │←───────────────────┤              │                │
  │                 │  (ツール呼び出し判定)              │                │
  │                 │                     │              │                │
  │                 │    ツール呼び出し発見              │                │
  │                 │←───────────────────┤              │                │
  │                 │  (ask_human())                     │                │
  │                 │                     │              │                │
  │ ← ツール承認画面を表示                │              │                │
  │  (プレビュー付き)                      │              │                │
  │                 │                     │              │                │
  │─ APPROVE ─→    │                     │              │                │
  │                 │─ Command(resume)──→               │                │
  │                 │                     │              │                │
  │                 │    use_tool イベント               │                │
  │                 │←───────────────────┤              │                │
  │                 │                     │─ ツール実行 ──────────────→  │
  │                 │                     │              │                │
  │                 │                     │←──── 結果 ───────────────    │
  │                 │    use_tool イベント               │                │
  │                 │←───────────────────┤              │                │
  │                 │  (完了メッセージ)    │              │                │
  │                 │                     │              │                │
  │                 │    agent イベント    │              │                │
  │                 │←───────────────────┤              │                │
  │                 │  (最終結果)          │              │                │
  │                 │                     │              │                │
  │ ← 結果表示      │                     │              │                │
  │                 │                     │              │                │
```

## 🔄 ストリーム形式

### 1. `invoke_llm` イベント

```python
{
    "invoke_llm": AIMessage(
        content=[
            {"type": "text", "text": "検索してみます..."},
            ...
        ]
    )
}
```

**UI での処理**:
```python
if isinstance(chunk["invoke_llm"].content, list):
    for content in result.content:
        if content["type"] == "text":
            st.session_state.messages.append({
                "role": "assistant",
                "content": content["text"]
            })
```

### 2. `__interrupt__` イベント

```python
{
    "__interrupt__": [
        Interrupt(
            value={
                "name": "write_file",
                "args": "* ツール名\n ...",
                "html": "<html>...</html>"
            }
        )
    ]
}
```

**UI での処理**:
```python
if task_name == "__interrupt__":
    st.session_state.tool_info = result[0].value
    st.session_state.waiting_for_approval = True
    # ツール承認画面を表示
```

### 3. `use_tool` イベント

```python
{
    "use_tool": ToolMessage(
        content="ファイルが保存されました",
        tool_call_id="..."
    )
}
```

**UI での処理**:
```python
elif task_name == "use_tool":
    if "write_file" in str(result.tool_call_id):
        st.session_state.messages.append({
            "role": "assistant",
            "content": "✅ ファイル保存が完了しました"
        })
```

### 4. `agent` イベント

```python
{
    "agent": AIMessage(
        content="調査結果をファイルに保存しました。",
        tool_calls=[]  # ツール呼び出しなし = 終了
    )
}
```

**UI での処理**:
```python
elif task_name == "agent":
    st.session_state.final_result = result.content
    # 最終結果表示
```

## 📋 メッセージフロー詳細

### メッセージ型の説明

| 型 | 発信者 | 内容 | 例 |
|---|---|---|---|
| `HumanMessage` | ユーザー | ユーザーの質問 | "Bedrockについて調べて" |
| `AIMessage` | LLM | LLM の応答 | "検索します" + tool_calls |
| `ToolMessage` | ツール | ツール実行結果 | "ファイルが保存されました" |
| `SystemMessage` | システム | システムプロンプト | "あなたはアシスタントです" |

### エージェント内のメッセージリスト推移

```
初期状態:
  messages = [HumanMessage("Bedrockについて調べて")]

LLM 呼び出し後:
  messages = [
      HumanMessage("Bedrockについて調べて"),
      AIMessage("検索します", tool_calls=[...])
  ]

ツール実行後:
  messages = [
      HumanMessage("Bedrockについて調べて"),
      AIMessage("検索します", tool_calls=[...]),
      ToolMessage("検索結果: ...", tool_call_id="..."),
      AIMessage("結果をファイルに保存します", tool_calls=[...])
  ]

最終状態:
  messages = [
      HumanMessage("Bedrockについて調べて"),
      AIMessage("検索します", tool_calls=[...]),
      ToolMessage("検索結果: ...", tool_call_id="..."),
      AIMessage("結果をファイルに保存します", tool_calls=[...]),
      ToolMessage("ファイル保存完了", tool_call_id="..."),
      AIMessage("完了しました")  # tool_calls = [] (終了)
  ]
```

## 🔀 分岐フロー

### ツール呼び出しの判定

```
LLM 応答を受信
    ↓
tool_calls が空か?
    ├─ YES → 終了 (END)
    └─ NO → ツール実行へ
             ↓
        ユーザー承認が必要か?
             ├─ YES (write_file) → interrupt で一時停止
             │                      ↓
             │                   ユーザーが APPROVE?
             │                      ├─ YES → ツール実行
             │                      └─ NO → スキップ
             └─ NO (search) → 自動実行
                              ↓
                          結果を messages に追加
                              ↓
                          LLM を再度呼び出し
```

## 📊 状態遷移図

```
初期状態
    ↓
[ユーザー入力待機]
    ↓
ユーザー が入力 → [入力受け取り]
    ↓
[エージェント実行]
    ├─ LLM 推論
    ├─ ツール呼び出し判定
    │   ├─ なし → [終了]
    │   └─ あり → [ツール承認待機]
    │              ↓
    │          ユーザーが応答
    │              └─ [ツール実行]
    │                  ↓
    └─────── [メッセージ追加] ──→ LLM を再度呼び出し

[結果表示]
    ↓
[ユーザー入力待機]
```

## 🔍 例：完全なデータフロー

### シナリオ：「Python について調べて、HTML ファイルに保存」

```
1. ユーザー入力
   Input: "Python について調べて、HTML ファイルに保存"

2. Streamlit: セッション初期化
   reset_session() を実行

3. Streamlit: エージェント実行開始
   run_agent([HumanMessage("Python について調べて...")])

4. ストリーム: invoke_llm イベント
   chunk = {
       "invoke_llm": AIMessage(content=[{"type": "text", "text": "検索します"}])
   }
   → st.session_state.messages に追加

5. ストリーム: __interrupt__ イベント
   chunk = {
       "__interrupt__": [Interrupt(value={
           "name": "tavily_search_results_json",
           "args": "query: 'Python'"
       })]
   }
   → ツール承認画面を表示（自動実行なので即座に実行）

6. ストリーム: use_tool イベント
   chunk = {
       "use_tool": ToolMessage(content="[{'title': '...', 'url': '...'}]")
   }
   → "✅ ツール実行が完了しました" をメッセージに追加

7. ストリーム: invoke_llm イベント (2回目)
   LLM が検索結果を見て、write_file を呼び出す判定

8. ストリーム: __interrupt__ イベント (write_file)
   chunk = {
       "__interrupt__": [Interrupt(value={
           "name": "write_file",
           "args": "* ツール名\n ...",
           "html": "<html>...</html>"
       })]
   }
   → ツール承認画面を表示（HTML プレビュー付き）

9. ユーザー: APPROVE ボタンをクリック

10. Streamlit: Command(resume="APPROVE") でエージェント再開

11. ストリーム: use_tool イベント (write_file)
    chunk = {
        "use_tool": ToolMessage(content="python_guide.html に保存しました")
    }
    → "✅ ファイル保存が完了しました" をメッセージに追加

12. ストリーム: agent イベント
    chunk = {
        "agent": AIMessage(content="完了しました", tool_calls=[])
    }
    → st.session_state.final_result = "完了しました"

13. Streamlit: st.rerun() でページ再表示

14. UI: 最終結果を表示
    "✅ 処理が完了しました"
    "結果: 完了しました"
```

## 📚 参考資料

- [LangGraph Streaming](https://langchain-ai.github.io/langgraph/concepts/streaming/)
- [Streamlit Data Flow](https://docs.streamlit.io/develop/concepts/architecture/data-flow)
- [LangChain Message Types](https://python.langchain.com/api_reference/core/messages.html)

---

**次のステップ**: [Streamlit アプリの詳細](../02_streamlit_app/entry_point.md)
