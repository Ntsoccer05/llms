# LangGraph Streamlit エージェント - 完全ガイド

このドキュメントでは、`4_streamlit_app.py` と `x_agent_core.py` の連携を詳しく説明します。

## 📚 ドキュメント構成

```
docs/
├── README.md                           # このファイル
├── 01_architecture/
│   ├── overview.md                     # システム全体図
│   ├── data_flow.md                    # データフロー図
│   └── component_interaction.md        # コンポーネント間の相互作用
├── 02_streamlit_app/
│   ├── entry_point.md                  # エントリーポイント
│   ├── session_management.md           # セッション管理
│   ├── ui_flow.md                      # UI フロー
│   └── streaming_handling.md           # ストリーミング処理
├── 03_agent_core/
│   ├── llm_initialization.md           # LLM 初期化
│   ├── tool_setup.md                   # ツール設定
│   ├── agent_loop.md                   # エージェントループ
│   └── tool_approval_flow.md           # ツール承認フロー
├── 04_integration/
│   ├── message_flow.md                 # メッセージフロー
│   ├── state_management.md             # 状態管理
│   └── error_handling.md               # エラーハンドリング
└── 05_quick_reference/
    ├── glossary.md                     # 用語集
    ├── code_snippets.md                # コードスニペット
    └── troubleshooting.md              # トラブルシューティング
```

## 🎯 クイックスタート

### これを読むべき人

- ✅ Streamlit 初心者
- ✅ LangGraph の基本を学びたい
- ✅ エージェント開発を始めたい

### 推奨読了順

1. **[01_architecture/overview.md](./01_architecture/overview.md)** - 全体像を理解
2. **[01_architecture/data_flow.md](./01_architecture/data_flow.md)** - データの流れを把握
3. **[02_streamlit_app/entry_point.md](./02_streamlit_app/entry_point.md)** - Streamlit から開始
4. **[03_agent_core/llm_initialization.md](./03_agent_core/llm_initialization.md)** - エージェント初期化
5. **[04_integration/message_flow.md](./04_integration/message_flow.md)** - 統合を理解

## 🔑 キーコンセプト

### 1. **Streamlit アプリ** (`4_streamlit_app.py`)
- **役割**: ユーザーインターフェース
- **責務**: ユーザー入力受け取り → エージェント実行 → 結果表示

### 2. **エージェントコア** (`x_agent_core.py`)
- **役割**: AI エージェントの実装
- **責務**: LLM 呼び出し → ツール実行 → ユーザー承認待ち

### 3. **連携ポイント**
```
Streamlit UI
    ↓
  入力受け取り
    ↓
エージェント実行（agent.stream()）
    ↓
リアルタイム更新
    ↓
結果表示
```

## 📖 詳細ドキュメント

各フォルダのドキュメントをクリックして詳細を確認してください。

- **[システムアーキテクチャ](./01_architecture/)** - 全体構造とコンポーネント
- **[Streamlit アプリケーション](./02_streamlit_app/)** - UI とユーザーインタラクション
- **[エージェントコア](./03_agent_core/)** - LLM とツール処理
- **[統合とメッセージング](./04_integration/)** - コンポーネント間通信
- **[クイックリファレンス](./05_quick_reference/)** - 用語と解決方法

---

**最終更新**: 2025年12月26日
