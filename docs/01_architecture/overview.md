# システムアーキテクチャ概要

## 🏗️ システム全体図

```
┌─────────────────────────────────────────────────────────────┐
│                   Streamlit UI (4_streamlit_app.py)          │
│  ┌──────────────────────────────────────────────────────┐  │
│  │  入力フォーム → メッセージ表示 → ツール承認画面      │  │
│  │  (st.chat_input) (st.chat_message) (st.button)       │  │
│  └──────────────────────────────────────────────────────┘  │
│                          ↓                                    │
│                    agent.stream()                             │
│                          ↓                                    │
│  ┌──────────────────────────────────────────────────────┐  │
│  │  セッション状態管理 (st.session_state)               │  │
│  │  - messages                                           │  │
│  │  - waiting_for_approval                              │  │
│  │  - tool_info                                         │  │
│  │  - final_result                                      │  │
│  └──────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────┘
                          ↓↑
              ＿＿＿＿＿＿＿＿＿＿＿＿＿＿
             │      LangGraph      │
             │   エージェント実行  │
             │  (x_agent_core.py)  │
             ＿＿＿＿＿＿＿＿＿＿＿＿＿＿
                          ↓
┌─────────────────────────────────────────────────────────────┐
│                    エージェント層                             │
│  ┌──────────────────────────────────────────────────────┐  │
│  │  LLM 初期化 (init_chat_model)                         │  │
│  │  - Claude Haiku 4.5                                  │  │
│  │  - Bedrock Converse                                  │  │
│  └──────────────────────────────────────────────────────┘  │
│                          ↓                                    │
│  ┌──────────────────────────────────────────────────────┐  │
│  │  ツール設定 (tool_by_name)                           │  │
│  │  - TavilySearch (Web 検索)                           │  │
│  │  - write_file (ファイル保存)                         │  │
│  └──────────────────────────────────────────────────────┘  │
│                          ↓                                    │
│  ┌──────────────────────────────────────────────────────┐  │
│  │  エージェントループ (@entrypoint)                    │  │
│  │  1. LLM を呼び出し                                   │  │
│  │  2. ツール呼び出し判定                               │  │
│  │  3. ユーザー承認を待つ (interrupt)                   │  │
│  │  4. ツール実行                                       │  │
│  │  5. 結果を返す                                       │  │
│  └──────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────┘
                          ↓
┌─────────────────────────────────────────────────────────────┐
│                    外部サービス層                            │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐    │
│  │ AWS Bedrock  │  │ Tavily API   │  │ ファイル     │    │
│  │ (LLM)        │  │ (Web 検索)   │  │ システム     │    │
│  └──────────────┘  └──────────────┘  └──────────────┘    │
└─────────────────────────────────────────────────────────────┘
```

## 🔄 データフロー

### 基本的なフロー

1. **ユーザー入力** → Streamlit UI で質問を入力
2. **セッション保存** → `st.session_state` に保存
3. **エージェント実行** → `agent.stream()` で実行開始
4. **リアルタイム更新** → ストリーム結果を受信して UI 更新
5. **ツール承認** → ユーザーが承認 / 拒否
6. **ツール実行** → 承認されたツールを実行
7. **結果表示** → 最終結果を表示

## 🧩 主要コンポーネント

| コンポーネント | ファイル | 役割 |
|---|---|---|
| UI フレームワーク | `4_streamlit_app.py` | ユーザーインターフェース |
| エージェント実装 | `x_agent_core.py` | AI エージェント実行 |
| LLM | AWS Bedrock | Claude Haiku 4.5 |
| 検索ツール | Tavily | Web 検索 |
| ファイルツール | FileManagementToolkit | ファイル操作 |

## 📊 状態管理

### Streamlit セッション状態

```python
st.session_state = {
    "messages": [],                    # チャット履歴
    "waiting_for_approval": False,     # ツール承認待ちフラグ
    "tool_info": None,                 # 実行予定のツール情報
    "final_result": None,              # 最終結果
    "thread_id": None                  # エージェントスレッド ID
}
```

## 🔌 連携ポイント

### 1. メッセージング
- **Streamlit → Agent**: `HumanMessage(content=user_input)`
- **Agent → Streamlit**: `agent.stream()` のストリームイベント

### 2. ツール実行承認
- **Agent → Streamlit**: `interrupt(tool_data)` でユーザー承認を待つ
- **Streamlit → Agent**: `Command(resume=feedback_result)` で再開

### 3. 結果通知
- **Agent → Streamlit**: 最終 `AIMessage` を返す
- **Streamlit**: `final_result` にセット

## 🎯 処理フロー詳細

### ユーザーが質問を入力した場合

```
1. Streamlit: st.chat_input() で入力受け取り
2. Streamlit: セッション初期化 (reset_session)
3. Streamlit: HumanMessage を作成
4. Streamlit: agent.stream() を呼び出し
5. Agent: LLM に質問を送信
6. Agent: ツール呼び出しが必要か判定
7. Agent: ツール実行が必要な場合、interrupt() で一時停止
8. Streamlit: interrupt イベントを受信
9. Streamlit: ツール承認画面を表示
10. ユーザー: APPROVE / DENY を選択
11. Streamlit: Command(resume=feedback) でエージェント再開
12. Agent: ツール実行 / スキップ
13. Agent: 最終結果を返す
14. Streamlit: 結果を表示
```

## 📚 参考資料

- [LangGraph ドキュメント](https://langchain-ai.github.io/langgraph/)
- [Streamlit ドキュメント](https://docs.streamlit.io/)
- [AWS Bedrock API](https://docs.aws.amazon.com/bedrock/latest/userguide/)
- [Tavily Search API](https://tavily.com/)

---

**次のステップ**: [データフロー図を詳しく見る](./data_flow.md)
