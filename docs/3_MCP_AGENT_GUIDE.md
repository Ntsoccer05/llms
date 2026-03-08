# 3_mcp_agent.py 詳細解説ガイド

MCPサーバーを使用した LangGraph エージェントの詳しい解説です。

## 質問 1: "transport": "stdio" は何をしている？

### 答え
MCPサーバーとの**通信プロトコルを指定**します。

### 詳細

**stdio** = Standard Input/Output（標準入出力）を使ってMCPサーバーと通信

```
LangGraph アプリ ←→ MCPサーバープロセス
           (stdin/stdout で JSON-RPC メッセージ交換)
```

#### 通信フロー
1. MCPサーバーはプロセスとして起動される
2. LangGraphはそのプロセスの stdin に JSON-RPC リクエストを送信
3. MCPサーバーは stdout に JSON-RPC レスポンスを返す

#### その他の transport オプション
- **streamable_http**: HTTP通信（リモートサーバーに対して使用）
- **sse**: Server-Sent Events（リアルタイムストリーミング）

#### 例
```python
"transport": "stdio"
# → ローカルプロセスとして filesystem サーバーを起動、stdin/stdout で通信

"transport": "streamable_http"
# → リモートHTTPサーバー（AWS Knowledge MCP）とHTTPS通信
```

---

## 質問 2: await mcp_client.get_tools() では tools を全て取得？

### 答え
**はい、接続したすべての MCPサーバーから全ツール定義を取得します。**

### 詳細

```python
tools = await mcp_client.get_tools()
```

#### 戻り値
`List[Tool]` - LangChainの Tool オブジェクトのリスト

#### 取得されるツール
このコードの場合：
1. **Filesystem ツール** (`file-system` MCPサーバーから)
   - `read_file(path)` - ファイル読み込み
   - `write_file(path, content)` - ファイル書き込み
   - `list_directory(path)` - ディレクトリ一覧

2. **AWS Knowledge ツール** (`aws-knowledge-mcp-server` から)
   - `search_aws_docs(query)` - AWS ドキュメント検索
   - その他 AWS 関連ツール

#### ツール定義の構成
```python
{
    "name": "search_aws_docs",
    "description": "AWS ドキュメントを検索",
    "input_schema": {
        "type": "object",
        "properties": {
            "query": {"type": "string"}
        }
    }
}
```

#### 重要なポイント
- `get_tools()` は各MCPサーバーに接続してツール定義を取得
- ツール定義は「LLMが何ができるか」を記述したメタデータ
- LLMはこの定義を参考に、ツール呼び出しを決定する

---

## 質問 3: messages: Annotated[list[AnyMessage], operator.add] では任意のユーザーメッセージを追加している？

### 答え
**ユーザーメッセージに限定せず、すべてのメッセージが「追加」されていきます。**

### 詳細

#### Annotated[list[AnyMessage], operator.add] の意味

| 要素 | 説明 |
|------|------|
| `list[AnyMessage]` | メッセージのリスト型（どんなメッセージ型でもOK） |
| `operator.add` | リスト連結（追記）動作を指定 |

#### AnyMessage の種類
```python
# LangChain で定義されるメッセージ型
AnyMessage = Union[
    HumanMessage,        # ユーザー入力
    AIMessage,          # LLM の応答
    ToolMessage,        # ツール実行結果
    SystemMessage,      # システムプロンプト
    ...
]
```

#### 実行フロー例

**初期状態:**
```python
messages = [HumanMessage("AWS のモデル一覧をください")]
```

**1回目の agent ノード実行後:**
```python
messages = [
    HumanMessage("AWS のモデル一覧をください"),
    AIMessage(
        "検索してきます",
        tool_calls=[{"id": "call_1", "function": "search_aws_docs", ...}]
    )
]
```

**tools ノード実行後:**
```python
messages = [
    HumanMessage("AWS のモデル一覧をください"),
    AIMessage("検索してきます", tool_calls=[...]),
    ToolMessage("tool_use_id": "call_1", content="Bedrock は Claude, Llama, ... をサポート")
]
```

**2回目の agent ノード実行後:**
```python
messages = [
    HumanMessage("AWS のモデル一覧をください"),
    AIMessage("検索してきます", tool_calls=[...]),
    ToolMessage(...),
    AIMessage("Bedrock で利用可能なモデルは ...")  # 最終応答
]
```

#### operator.add の効果
- **上書きではなく追記**: 既存メッセージは残る
- **会話履歴が保持**: LLM が過去のやりとりを参照可能
- **状態の更新**: グラフの実行ループに対応

---

## 質問 4: async def agent(state: AgentState) -> Dict[str, List[AIMessage]] は何をしている？

### 答え
**ユーザーの質問（またはツール実行結果）を受け取り、LLMを呼び出して応答を生成するノード関数。**

### 詳細

#### 関数シグネチャの分解

```python
async def agent(state: AgentState) -> Dict[str, List[AIMessage]]:
```

| 要素 | 説明 |
|------|------|
| `async` | 非同期関数（await でき、他の操作と並列実行可能） |
| `state: AgentState` | 入力パラメータ |
| `-> Dict[str, List[AIMessage]]` | 戻り値の型 |

#### 入力パラメータ: state とその内容

```python
state: AgentState
  ├─ state.messages: メッセージリスト
  │   └─ [HumanMessage, AIMessage, ToolMessage, ...]
  │       （現在までの会話履歴）
  │
  # 例: グラフが複数回ループした場合
  # messages = [
  #     HumanMessage("Q1"),
  #     AIMessage("回答1", tool_calls=[...]),
  #     ToolMessage("検索結果"),
  #     AIMessage("修正版回答")
  # ]
```

#### 処理内容

```python
response = await llm_with_tools.ainvoke(
    [SystemMessage(system_prompt)] + state.messages
)
```

1. **システムプロンプト + メッセージ履歴を LLM に送信**
   ```
   LLM への入力 = [
       SystemMessage("あなたの責務はAWSドキュメントを検索し..."),
       HumanMessage("Q1"),
       AIMessage("..."),
       ToolMessage("検索結果"),
       ...
   ]
   ```

2. **LLM が応答を生成**
   ```python
   response = AIMessage(
       content="回答テキスト",
       tool_calls=[
           {
               "id": "call_123",
               "function": "search_aws_docs",
               "args": {"query": "bedrock models"}
           }
       ]
   )
   ```

3. **response は以下の情報を持つ**
   - `response.content`: テキスト応答
   - `response.tool_calls`: 呼び出すツール（リスト）
     - 空 = ツール呼び出しなし
     - 要素あり = ツール呼び出しあり

#### 戻り値: Dict[str, List[AIMessage]]

```python
return {"messages": [response]}
```

| 要素 | 説明 |
|------|------|
| `Dict[str, ...]` | 辞書型（キーと値）|
| `"messages"` | キー（AgentState のフィールド名と一致）|
| `[response]` | リスト形式（1つのAIMessageを含む）|

#### なぜ辞書で返すのか？
LangGraph の状態更新メカニズムと連携するため：
```python
# LangGraph は自動的にこう理解する：
# "messages フィールドに response を追加せよ"
# → operator.add により messages リストに AIMessage が追加される
state.messages = state.messages + [response]
```

#### 実行フロー図

```
agent ノード の処理フロー:

入力: AgentState {messages: [HumanMessage("Q1")]}
  ↓
SystemMessage + メッセージ履歴を LLM に送信
  ↓
LLM が応答を生成（AIMessage）
  ↓
{"messages": [AIMessage(...)]} を返す
  ↓
状態更新: messages = [HumanMessage("Q1"), AIMessage(...)]
  ↓
出力: 更新された AgentState
```

---

## 質問 5: route_node(state: AgentState) -> Union[str]: の Union[str]: はどういう型？

### 答え
**文字列型（またはその他の型）を返すことを示す型ヒント。ここでは実際には常に str が返される。**

### 詳細

#### Union[str] の意味

```python
from typing import Union

Union[str]  # 「str型 または他の型」を示す型ヒント
```

#### より一般的な Union の例

```python
Union[str, int]       # 文字列 または 整数を返す
Union[str, None]      # 文字列 または None を返す
Union[list, dict]     # リスト または 辞書を返す
```

#### このコードの場合

```python
def route_node(state: AgentState) -> Union[str]:
```

実際の戻り値：
```python
return END      # END は文字列定数（実際には "END" または "__end__"）
return "tools"  # 文字列
```

#### 型ヒントの実用性

```python
# Union[str] は比較的曖昧
# より明確な書き方：

def route_node(state: AgentState) -> Literal["tools", "__end__"]:
    # 返す値は厳密に "tools" か "__end__" のみ
    ...

# または

def route_node(state: AgentState) -> str:
    # 単純に str を返す
    ...
```

#### LangGraph での意味

LangGraph のルーティング関数の戻り値：
```python
def route_node(...) -> Union[str]:
    return END      # グラフ終了
    return "tools"  # "tools" ノードへ遷移
    return "agent"  # "agent" ノードへ遷移
```

戻り値がノード名またはEND（グラフ終了）の指示になる。

---

## 質問 6: isinstance(last_message, AIMessage) は何を判定している？またAIMessageとは何？

### 答え
**メッセージが AIMessage 型であるかを判定。AIMessage は LLM（AI）が生成したメッセージ。**

### 重要な補足：なぜ「エージェントノード直後なので AIMessage であるべき」？

これは**グラフの構造と実行フロー**から自動的に保証される条件です。

#### グラフの遷移フローを見る

```python
# グラフの定義
builder.add_edge(START, "agent")              # ① START → agent
builder.add_conditional_edges("agent", route_node)  # ② agent → route_node
builder.add_edge("tools", "agent")            # ③ tools → agent
```

#### 実行フロー図

```
グラフ実行時の流れ:

START
  ↓
┌─────────────────────────────┐
│ agent ノード実行             │
│ 戻り値: {"messages": [AIMessage]}
└──────────────┬──────────────┘
               ↓
┌──────────────────────────────────────────┐
│ route_node 実行 ← route_node が呼ばれる時点
│ last_message = state.messages[-1]        │
│ この last_message は絶対に AIMessage     │
│ （理由：agent が AIMessage を追加したから）
└──────────┬──────────────────┬───────────┘
           ↓                  ↓
    tools 呼び出し      END（終了）
    あり             なし
           ↓
    ┌────────────────┐
    │ tools ノード   │
    │ (ツール実行)   │
    │ ToolMessage を追加
    └────────────────┘
           ↓
        agent へ戻る
```

#### なぜ AIMessage が保証されるのか？

```python
# 1. agent ノードの定義を見ると：

async def agent(state: AgentState) -> Dict[str, List[AIMessage]]:
    # 戻り値の型: Dict[str, List[AIMessage]]
    # つまり、返すメッセージは「必ず AIMessage である」
    response = await llm_with_tools.ainvoke(...)
    return {"messages": [response]}
    # response は LLM の出力なので AIMessage
```

```python
# 2. 状態更新の流れ：

初期状態:
  messages = [HumanMessage("質問")]

agent ノード実行後:
  messages = messages + [AIMessage(...)]
  # Annotated[..., operator.add] により「追加」される

route_node が実行される時点:
  last_message = state.messages[-1]
  # = messages[-1]
  # = AIMessage (agent が追加した最後のメッセージ)
```

#### もし AIMessage 以外が来たら？

```python
# 考えられるシナリオ：
# 1. グラフの設定が壊れている
#    例: START → tools → route_node という順序になっている
# 2. 誰かが state を手動で不正に変更した
# 3. LangGraph のバグ

# だから isinstance チェックでエラーを早期に発見できる
if not isinstance(last_message, AIMessage):
    raise ValueError("グラフ設計が壊れています")
```

#### 実例：各ステップでのメッセージ型

```
ステップ 1:
  messages = [HumanMessage("AWS のモデルは？")]
  next_node = "agent"

ステップ 2: agent 実行
  agent が LLM を呼び出す
  response = AIMessage("検索します", tool_calls=[...])
  messages = messages + [response]
  = [
      HumanMessage("AWS のモデルは？"),
      AIMessage("検索します", tool_calls=[...])
    ]
  last_message = AIMessage (← route_node がここで判定)
  next_node = route_node() → "tools"

ステップ 3: tools 実行
  messages = messages + [ToolMessage("検索結果: ...")]
  = [
      HumanMessage("AWS のモデルは？"),
      AIMessage("検索します", ...),
      ToolMessage("検索結果: ...")
    ]
  next_node = "agent"

ステップ 4: 再度 agent 実行
  agent が LLM を呼び出す
  response = AIMessage("検索結果は...")
  messages = messages + [response]
  = [
      HumanMessage("AWS のモデルは？"),
      AIMessage("検索します", ...),
      ToolMessage("検索結果: ..."),
      AIMessage("検索結果は...", tool_calls=[])  ← ツール呼び出しなし
    ]
  last_message = AIMessage (← また route_node で判定)
  next_node = route_node() → END

グラフ終了
```

### 詳細

#### isinstance() 関数

```python
isinstance(last_message, AIMessage)
```

| 要素 | 説明 |
|------|------|
| `last_message` | 検査する対象（変数） |
| `AIMessage` | 期待する型 |
| 戻り値 | `True` または `False` |

#### 判定例

```python
from langchain_core.messages import AIMessage, HumanMessage

msg1 = HumanMessage("ユーザーの質問")
msg2 = AIMessage("LLMの応答")

isinstance(msg1, AIMessage)  # False（HumanMessageだから）
isinstance(msg2, AIMessage)  # True（AIMessageだから）
```

#### AIMessage とは？

LangChain で定義されたメッセージクラス：
```python
class AIMessage:
    content: str              # LLMの応答テキスト
    tool_calls: List[Dict]    # ツール呼び出し情報
    additional_kwargs: Dict   # メタデータ
```

#### メッセージ型の比較

| メッセージ型 | 生成元 | 用途 |
|-------------|------|------|
| `HumanMessage` | ユーザー | 質問や指示 |
| `AIMessage` | LLM | AI の応答・判断 |
| `ToolMessage` | ツール | ツール実行結果 |
| `SystemMessage` | 開発者 | システムプロンプト |

#### なぜ型チェックが必要？

```python
def route_node(state: AgentState) -> Union[str]:
    last_message = state.messages[-1]

    # agent ノード直後なので AIMessage であるべき
    # もし HumanMessage や ToolMessage が来たら異常
    if not isinstance(last_message, AIMessage):
        raise ValueError("不正な遷移")

    # AIMessage であることを確認したら、tool_calls を安全にアクセス可能
    if last_message.tool_calls:
        return "tools"
    else:
        return END
```

#### 型チェックなしだと？

```python
# 型チェックなし（危険）
def route_node_unsafe(state):
    last_message = state.messages[-1]
    if last_message.tool_calls:  # ← AttributeError が発生する可能性
        return "tools"
    return END
```

---

## 質問 7: builder.add_edge("tools", "agent") は何を表している？

### 答え
**tools ノード実行後、再び agent ノードへ遷移することを指定。つまり、ループ構造を作る。**

### 詳細

#### エッジ（遷移）の種類

```python
# 1. 無条件エッジ（常に同じ先へ遷移）
builder.add_edge("tools", "agent")
# tools ノード実行後、必ず agent ノードへ

# 2. 条件付きエッジ（条件に応じて遷移先を変更）
builder.add_conditional_edges("agent", route_node)
# route_node の戻り値に応じて "tools" または END へ
```

#### グラフの構造図

```
add_edge(START, "agent")
    ↓
    START
    ↓
    agent (LLM呼び出し)
    ↓
add_conditional_edges("agent", route_node)
    ↓
    route_node で判定
    ├─ True (ツール呼び出しあり) → "tools"
    └─ False (ツール呼び出しなし) → END (終了)
    ↓
add_edge("tools", "agent") ← ここでループ形成
    ↓
    tools (ツール実行)
    ↓
    agent (再度LLMを呼び出し)
    ↓
    (ループ継続...)
```

#### なぜループが必要？

**ReAct パターン**（Reasoning + Acting）：
1. **Reasoning**: LLMが考える（ツール呼び出し判定）
2. **Acting**: ツールを実行
3. **Reasoning**: LLMが結果を受け取り、再度考える
4. (繰り返し)

#### 実行例

```
Q: "AWS のモデル一覧を教えて、ファイルに保存してください"

ループ 1 回目:
  → agent: "AWS のモデルを検索する必要があります"
  → route_node: ツール呼び出しあり → "tools" へ
  → tools: search_aws_docs() を実行 → "Bedrock は Claude, Llama,..."

ループ 2 回目:
  → agent: "検索結果をファイルに保存します"
  → route_node: ツール呼び出しあり → "tools" へ
  → tools: write_file() を実行 → "ファイル保存完了"

ループ 3 回目:
  → agent: "完了しました"
  → route_node: ツール呼び出しなし → END

グラフ終了
```

#### add_edge vs add_conditional_edges

```python
# add_edge: 常に同じ先
builder.add_edge("A", "B")      # A の後は常に B

# add_conditional_edges: 条件により異なる先
builder.add_conditional_edges("A", route_func)
# route_func の戻り値に応じて遷移先を決定
```

---

## 質問 8: graph.ainvoke() は何をしている？

### 答え
**グラフを非同期で実行し、入力に対する最終的な出力（state）を返す。**

### 詳細

#### ainvoke vs invoke

| メソッド | 実行方式 | 用途 |
|---------|--------|------|
| `invoke()` | 同期実行 | シンプルな処理、ブロッキングOK |
| `ainvoke()` | 非同期実行 | 複数の I/O 操作を並列化 |

#### ainvoke() の処理フロー

```python
response = await graph.ainvoke(
    {
        "messages": [HumanMessage(question)]
    }
)
```

**ステップ:**
1. **入力を受け取る**
   ```python
   {
       "messages": [HumanMessage("Bedrockで利用可能なモデルプロバイダーを教えて！")]
   }
   ```

2. **START から グラフを開始**
   ```
   START → agent ノード
   ```

3. **agent ノード実行**
   ```python
   await llm_with_tools.ainvoke([SystemMessage(...)] + messages)
   # → AIMessage が返される
   ```

4. **route_node で判定**
   ```python
   if last_message.tool_calls:
       return "tools"
   else:
       return END
   ```

5. **ツール呼び出しあり → tools ノード実行**
   ```python
   ToolNode が各ツール実行
   # → ToolMessage が返される
   ```

6. **tools → agent へループ**
   ```python
   再び agent ノード実行
   ```

7. **ツール呼び出しなし → END**
   ```python
   return END  # グラフ終了
   ```

8. **最終的な state を返す**
   ```python
   {
       "messages": [
           HumanMessage("..."),
           AIMessage("..."),
           ToolMessage("..."),
           AIMessage("最終応答")
       ]
   }
   ```

#### 戻り値の内容

```python
response = {
    "messages": [
        HumanMessage("Bedrockで利用可能なモデルプロバイダーを教えて！"),
        AIMessage(
            content="検索します",
            tool_calls=[{"id": "...", "function": "search_aws_docs", ...}]
        ),
        ToolMessage(
            tool_use_id="...",
            content="Bedrock は Claude, Llama, Mistral をサポート"
        ),
        AIMessage(
            content="Bedrock で利用可能なモデルプロバイダーは..."
        )
    ]
}
```

#### なぜ非同期（ainvoke）を使うのか？

- **I/O 待機時間の有効活用**：
  - LLM API 呼び出し（ネットワーク待機）
  - ツール実行（データベース、ファイルI/O 待機）
  - これらを並列化

- **パフォーマンス向上**：
  ```python
  # 同期（invoke）: 5秒 + 3秒 + 2秒 = 10秒
  # 非同期（ainvoke）: max(5秒, 3秒, 2秒) = 5秒
  ```

---

## 質問 9: graph = builder.compile(name="ReAct Agent") の name="ReAct Agent" は任意の名前を付けているだけ？

### 答え
**はい、name は単なる識別用の名前付けです。処理ロジックに影響しません。**

### 詳細

#### compile() 関数の役割

```python
graph = builder.compile(name="ReAct Agent")
```

| 処理 | 説明 |
|-----|------|
| `builder.compile()` | StateGraph を実行可能な CompiledStateGraph に変換 |
| `name="ReAct Agent"` | グラフの識別名（UI表示、デバッグ用） |

#### name の用途

1. **LangGraph Studio の表示**
   ```
   UI に "ReAct Agent" というタイトルで表示
   ```

2. **ログ・デバッグ**
   ```python
   print(graph.get_name())  # "ReAct Agent"
   ```

3. **トレーシング・分析**
   ```python
   LangSmith でのグラフ実行履歴に表示
   ```

#### name の変更例

```python
# 任意の名前に変更可能
graph1 = builder.compile(name="MyAwesomeAgent")
graph2 = builder.compile(name="検索エージェント")
graph3 = builder.compile(name="ReAct-2024")
graph4 = builder.compile()  # name 省略時は自動生成
```

#### compile() 後の処理

```python
# compile() の戻り値は CompiledStateGraph
graph: CompiledStateGraph

# これで以下が使える：
graph.invoke(...)      # 同期実行
graph.ainvoke(...)     # 非同期実行
graph.get_name()       # グラフ名取得
graph.get_graph()      # グラフ構造取得
```

#### compile() がなぜ必要？

```python
# compile() 前
builder: StateGraph  # グラフの定義のみ

# compile() 後
graph: CompiledStateGraph  # 実行可能な状態に変換
```

内部では：
- ノード・エッジの検証
- 実行フローの最適化
- メモリ・ストレージの初期化

---

## まとめ

| 項目 | 説明 |
|------|------|
| **transport** | MCP通信プロトコル（stdio = 標準入出力） |
| **get_tools()** | すべてのMCPサーバーから全ツール取得 |
| **Annotated[..., operator.add]** | メッセージを「追記」（上書き不可） |
| **agent()** | LLM呼び出しノード、AIMessage返す |
| **Union[str]** | 文字列型の型ヒント |
| **isinstance()** | メッセージ型チェック |
| **add_edge()** | グラフのループ構造形成 |
| **ainvoke()** | グラフの非同期実行 |
| **name** | グラフの識別名（処理ロジックに無関係） |

---

**作成日**: 2025年12月22日
