# Chapter 6: マルチエージェントシステム完全ガイド

このディレクトリでは、複数のAIエージェントを連携させる「マルチエージェントシステム」の実装方法を学びます。

## 📚 目次

- [全体構成](#全体構成)
- [yieldとは？（初心者向け）](#yieldとは初心者向け)
- [Sample編（学習用サンプル）](#sample編学習用サンプル)
- [Backend編（実践アプリケーション）](#backend編実践アプリケーション)
- [実行方法](#実行方法)
- [技術スタック](#技術スタック)

---

## 全体構成

```
chapter6/
├── sample/              # 学習用サンプルコード
│   ├── 1_stands.py     # マルチエージェントの基本
│   ├── 2_langgraph.py  # グラフ構造のエージェント
│   ├── 4_a2a_server.py # A2Aサーバー
│   └── 5_a2a_client.py # A2Aクライアント
└── backend/src/         # 実践的なAWS操作アプリ
    ├── main.py          # メインアプリケーション
    ├── aws_master.py    # AWS知識検索エージェント
    ├── api_master.py    # AWS API操作エージェント
    ├── agent_executor.py # エージェント実行処理
    └── stream_handler.py # ストリーム統合処理
```

---

## yieldとは？（初心者向け）

### ❌ returnの場合（従来型）

```python
def get_numbers():
    result = []
    for i in range(1000000):  # 100万個の数字
        result.append(i)
    return result  # 全部計算してから一度に返す（遅い＆メモリ大量消費）

numbers = get_numbers()  # 全部終わるまで待つ...
```

### ✅ yieldの場合（ストリーミング）

```python
def get_numbers():
    for i in range(1000000):
        yield i  # 1個作ったらすぐ返す（繰り返す）

for num in get_numbers():  # 1個ずつすぐ受け取れる
    print(num)  # 待たずに処理開始！
```

### 🤖 AIチャットでの使い道

```python
# ❌ 悪い例
def chat_bad(prompt):
    response = ai.get_full_response(prompt)  # 全部生成するまで待つ
    return response  # ユーザーは待たされる...

# ✅ 良い例（yieldを使う）
async def chat_good(prompt):
    async for chunk in ai.stream_response(prompt):  # 少しずつ生成
        yield chunk  # すぐユーザーに見せる（タイピング風）
```

**Chapter6での活用**: `stream_handler.py`と`main.py`で、複数のエージェントからのデータをリアルタイムでユーザーに表示するために使用しています。

---

## Sample編（学習用サンプル）

### 1. マルチエージェントの基本 - `1_stands.py`

#### 概要
2つのサブエージェント（計算AI、俳句AI）を監督者エージェントが統括するパターン。

#### アーキテクチャ
```
┌─────────────────┐
│ 監督者エージェント │
└────┬────────┬────┘
     │        │
     ▼        ▼
┌─────────┐ ┌─────────┐
│計算AI   │ │俳句AI   │
└─────────┘ └─────────┘
```

#### 実行例

```bash
$ python 1_stands.py
```

**出力:**
```
十円に
二十円足せば
三十円
```

#### 内部フロー

1. **監督者**: 質問を受け取る「十円持っている太郎くんが...」
2. **監督者**: 「計算が必要だ」と判断 → `math_agent`を呼び出し
3. **計算AI**: calculatorツールで計算 → "30円"
4. **監督者**: 「俳句にしよう」と判断 → `haiku_agent`を呼び出し
5. **俳句AI**: 俳句を生成 → "十円に 二十円足せば 三十円"
6. **監督者**: ユーザーに返す

#### 学習ポイント
- `@tool`デコレータで関数をツール化
- エージェントの階層構造
- サブエージェントの専門化

---

### 2. グラフ構造のエージェント - `2_langgraph.py`

#### 概要
LangGraphを使って、サイコロの目で次の行き先が変わる「すごろく」型のエージェントネットワークを実装。

#### グラフ構造
```
    START
      ↓
  [Agent 1]
   /      \
  奇      偶
 /          \
[Agent 3] [Agent 2]
 \        /  \
  奇偶   奇   偶
    ↘  ↙      ↘
    Agent2     END
```

#### 実行例

```bash
$ python 2_langgraph.py
```

**出力例:**
```
エージェント1: 3が出たのでagent_3へ進みます！
エージェント3: 2が出たのでagent_2へ進みます！
エージェント2: 4が出たのでENDへ進みます！
```

#### 学習ポイント
- ノードとエッジによるフロー制御
- `Command`で動的な分岐
- 状態管理（`MessagesState`）

---

### 3. A2A（Agent to Agent）通信 - `4_a2a_server.py` & `5_a2a_client.py`

#### 概要
AIエージェントをネットワーク経由で公開・利用する仕組み。

#### アーキテクチャ
```
┌──────────────────┐     HTTP      ┌──────────────────┐
│  クライアント     │ ←─────────→  │   サーバー       │
│ (5_a2a_client.py)│               │ (4_a2a_server.py)│
│                  │               │  俳句エージェント │
└──────────────────┘               └──────────────────┘
```

#### 実行例

**ターミナル1（サーバー起動）:**
```bash
$ python 4_a2a_server.py
A2A server running on http://localhost:9000
Waiting for requests...
```

**ターミナル2（クライアント実行）:**
```bash
$ python 5_a2a_client.py
コードの糸
AIが紡ぐ
未来かな
```

**ターミナル1（サーバー側のログ）:**
```
Received request: "Strandsにちなんだ俳句を詠んで"
Sending response: "コードの糸 AIが紡ぐ 未来かな"
```

#### 内部フロー

1. **サーバー起動**: 4_a2a_server.pyで俳句エージェントをHTTP公開
2. **クライアント起動**: 5_a2a_client.pyが起動
3. **ツール取得**: クライアントが`http://localhost:9000`に接続して利用可能なツールを取得
4. **リクエスト送信**: クライアントのAIが「俳句が必要」と判断 → サーバーにリクエスト
5. **俳句生成**: サーバーの俳句エージェントが俳句を生成
6. **レスポンス**: クライアントが俳句を受け取って表示

#### 学習ポイント
- エージェントのマイクロサービス化
- HTTP経由のツール利用
- 分散システムの基礎

---

## Backend編（実践アプリケーション）

### アプリケーション全体像

AWS操作AIアシスタント：ユーザーの質問に対して、AWSドキュメントを検索したり、実際にAWSリソースを操作したりできるシステム。

#### アーキテクチャ図

```
┌─────────────────┐
│  ユーザー        │
└────────┬────────┘
         │ HTTPリクエスト
         ▼
┌─────────────────┐
│ main.py         │ ← 監督者エージェント
│ (Webアプリ)      │
└────┬────────┬────┘
     │        │
     ▼        ▼
┌─────────┐ ┌─────────┐
│aws_master│ │api_master│
│(知識検索) │ │(API操作) │
└─────┬────┘ └────┬────┘
      │             │
      ▼             ▼
┌──────────┐  ┌──────────┐
│AWSドキュ  │  │AWS API   │
│メント     │  │(boto3等) │
└──────────┘  └──────────┘
```

---

### 1. メインアプリケーション - `main.py`

#### 概要
Webアプリケーションのエントリーポイント。監督者エージェントを管理し、ストリーミングでリアルタイム応答を実現。

#### キーコード解説

**1. `@app.entrypoint` デコレータ**

```python
@app.entrypoint
async def invoke(payload):
```

- **役割**: BedrockAgentCoteAppが「このinvoke関数がメイン処理の開始地点」と認識する
- **非同期関数**: `async def` で複数のリクエストを同時処理可能
- **呼ばれるタイミング**: ユーザーのHTTPリクエストを受け取った時

**2. `prompt = payload.get("input", {}).get("prompt", "")`**

ネストされた辞書から安全にデータを取り出す：

```
payload
  └─ "input" (辞書)
      └─ "prompt" (文字列)
```

| コード | 説明 |
|--------|------|
| `payload.get("input", {})` | payloadから "input" キーを取得。なければ空の辞書 `{}` |
| `.get("prompt", "")` | その結果から "prompt" キーを取得。なければ空文字列 `""` |

**具体例：**
```python
# リクエストデータ
payload = {
  "input": {
    "prompt": "S3バケットの料金について教えて"
  }
}

# 結果
prompt = "S3バケットの料金について教えて"

# 不完全なデータが来ても安全（エラーにならない）
payload = {"input": None}  # inputがNoneなら
prompt = payload.get("input", {}).get("prompt", "")  # → ""になる
```

**3. `queue = asyncio.Queue()`**

```python
queue = asyncio.Queue()
```

- **役割**: サブエージェント（aws_master, api_master）との通信用
- **Queue**: データを順番に格納・取り出しする「入れ物」
- **非同期対応**: `asyncio.Queue`で複数の処理間を効率的に連携

**4. `async for event in merge_streams(stream, queue):`**

```python
async for event in merge_streams(stream, queue):
    yield event  # データが来たらすぐ返す
```

- `merge_streams()`: 親エージェント（監督者）と子エージェント（サブ）のストリーム統合
- `async for`: 非同期イテレータから1個ずつデータを取り出す
- `yield`: データが届いたら即座にクライアントに送信（待たない）

#### 実行例

**起動:**
```bash
$ python backend/src/main.py
Server running on http://localhost:8000
Waiting for requests...
```

**リクエスト送信:**
```bash
$ curl -X POST http://localhost:8000/invoke \
  -H "Content-Type: application/json" \
  -d '{"input": {"prompt": "S3バケットの料金について教えて"}}'
```

**レスポンス（ストリーミング）:**
```
S3
バケット
の
料金
は...
（少しずつ文字が届く）
```

#### 内部フロー（詳細）

**ユーザー:** "S3バケットを作って"

| 時間 | イベント | 説明 |
|------|----------|------|
| t=0.0秒 | リクエスト受信 | `invoke()`関数が呼ばれる |
| t=0.1秒 | Queue初期化 | サブエージェント用のキュー作成 |
| t=0.2秒 | 監督者起動 | `orchestrator.stream_async(prompt)`開始 |
| t=0.3秒 | サブ選択 | 「APIマスターを使う」と判断 |
| t=0.4秒 | サブ通知 | queue経由で「APIマスター起動」通知 → yield → ユーザーに表示 |
| t=0.5秒 | 応答開始 | 監督者「S3」 → yield → ユーザーに表示 |
| t=0.6秒 | 応答継続 | 監督者「バケット」 → yield → ユーザーに表示 |
| t=1.5秒 | ツール実行 | APIマスターがAWS APIを呼び出し |
| t=1.6秒 | 完了通知 | 「APIマスター完了」 → yield → ユーザーに表示 |
| t=1.7秒 | 最終応答 | 監督者「作成しました」 → yield → ユーザーに表示 |

**ユーザーが見た画面:**
```
APIマスターが起動しました
S3バケットAPIマスターがツール「create_s3_bucket」を実行中
を作成しました
APIマスターが完了しました
```

#### キーコード解説

```python
async for event in merge_streams(stream, queue):
    yield event  # ← データが来たらすぐ返す（全部待たない）
```

- `merge_streams()`: 親（監督者）と子（サブエージェント）のストリームを統合
- `yield`: データを少しずつ返す = リアルタイム表示

---

### 2. AWS知識検索エージェント - `aws_master.py`

#### 概要
MCP（Model Context Protocol）経由でAWS公式ドキュメントを検索する専門エージェント。

#### キーコード解説

**1. `_state.client = MCPClient(...)`**

```python
_state.client = MCPClient(
  lambda: streamable_http_client(
    "https://knowledge-mcp.global.api.aws"  # AWS公式MCPサーバー
  )
)
```

| 部分 | 役割 |
|------|------|
| **MCPClient** | MCP (Model Context Protocol) でサーバーと通信するクライアント |
| **lambda: ...** | 接続方法を遅延実行関数にしてから初めて接続開始（効率的） |
| **streamable_http_client** | HTTP経由でストリーミング可能な接続を作成 |
| **"https://knowledge-mcp.global.api.aws"** | AWS公式のMCPサーバーURL |

**2. `tools=_state.client.list_tools_sync()`**

```python
return Agent(
  model=os.getenv("MODEL_ID"),
  tools=_state.client.list_tools_sync()  # ←ツール配列を取得
)
```

**返り値（例）:**
```python
[
  Tool(name="search_documentation", description="AWS公式ドキュメント検索"),
  Tool(name="get_service_info", description="AWSサービス情報取得"),
  Tool(name="get_pricing", description="料金情報取得"),
  ...
]
```

- `list_tools_sync()`: MCPサーバーに「利用可能なツール一覧をください」とリクエスト
- `_sync()`: 同期処理（`await` なしで結果を待つ）
- **返り値**: ツールオブジェクトの配列
- **用途**: エージェントがこのツール群を持つことで、AWS知識検索が可能に

#### 実行フロー

**質問:** "S3とは何ですか？"

1. **監督者エージェント（main.py）**: 質問を受け取る
2. **監督者**: 「AWS関連の質問だ」と判断
3. **監督者**: `aws_master("S3とは何ですか？")`を呼び出し
4. **AWSマスター起動**: MCPクライアントを起動
5. **ドキュメント検索**: `https://knowledge-mcp.global.api.aws`にリクエスト
   ```
   POST /search
   {"query": "S3とは"}
   ```
6. **結果取得**:
   ```json
   {"result": "Amazon S3 (Simple Storage Service) は、高い耐久性と..."}
   ```
7. **監督者に返却**: 検索結果を返す
8. **ユーザーに表示**: 監督者が結果を整形して表示

#### MCPの仕組み

```
[AIエージェント] ←→ [MCPクライアント] ←→ [MCPサーバー] ←→ [AWSドキュメント]
 (このファイル)      (strands.tools.mcp)   (AWS提供)      (ナレッジベース)
```

---

### 3. AWS API操作エージェント - `api_master.py`

#### 概要
実際にAWS APIを呼び出してリソースを操作する専門エージェント。

⚠️ **注意**: このエージェントは実際にAWSリソースを操作するため、料金が発生したり、重要なリソースを削除したりする可能性があります。

#### キーコード解説

**1. MCPサーバーの起動方法（`aws_master.py` との違い）**

```python
# aws_master.py: HTTP経由で外部のMCPサーバーに接続
_state.client = MCPClient(
  lambda: streamable_http_client(
    "https://knowledge-mcp.global.api.aws"  # AWS公式サーバー
  )
)

# api_master.py: ローカルでMCPサーバーを起動
_state.client = MCPClient(
  lambda: stdio_client(
    StdioServerParameters(
      command="uvx",  # Python パッケージを一時実行
      args=["awslabs.aws-api-mcp-server==0.2.1"],  # AWS API MCP サーバー
      env=os.environ.copy()  # AWS認証情報を引き継ぐ
    )
  )
)
```

**2. `env=os.environ.copy()` の役割**

```python
env=os.environ.copy()  # AWS認証情報を引き継ぐ
```

| コード | 説明 |
|--------|------|
| **os.environ** | 現在のプロセスの環境変数（辞書） |
| **.copy()** | 環境変数を **コピー** して新規プロセスに渡す |
| **理由** | 子プロセスが環境変数を変更しても、親プロセスに影響しない（安全性） |

**必須な環境変数：**
```bash
AWS_ACCESS_KEY_ID         # AWSアクセスキー
AWS_SECRET_ACCESS_KEY     # AWSシークレットキー
AWS_REGION                # AWSリージョン（例：us-east-1）
AWS_PROFILE               # AWSプロファイル（オプション）
```

**3. `tools=_state.client.list_tools_sync()`**

```python
return Agent(
  model=os.getenv("MODEL_ID"),
  tools=_state.client.list_tools_sync()  # ←AWS API操作ツール配列を取得
)
```

**返り値（例）:**
```python
[
  Tool(name="ec2:describe_instances", description="EC2インスタンス一覧取得"),
  Tool(name="ec2:start_instances", description="EC2インスタンス開始"),
  Tool(name="ec2:stop_instances", description="EC2インスタンス停止"),
  Tool(name="ec2:terminate_instances", description="EC2インスタンス削除"),
  Tool(name="s3:create_bucket", description="S3バケット作成"),
  Tool(name="s3:delete_bucket", description="S3バケット削除"),
  Tool(name="rds:describe_db_instances", description="RDSインスタンス一覧"),
  ...
]
```

- `list_tools_sync()`: aws-api-mcp-serverから利用可能なAWS APIツール一覧を取得
- **実装**: boto3経由で実際のAWS APIを呼び出す
- **危険性**: リソース削除・料金発生の可能性がある

**処理の流れ:**
```
1. MCPサーバー起動（uvx経由）
2. ツール一覧取得（list_tools_sync）
3. エージェント作成（ツール群を装備）
4. ユーザーの指示に従ってツール実行
5. AWS APIが実際に動作
6. 結果をユーザーに返却
```

#### 実行フロー

**指示:** "my-bucket という名前のS3バケットを作って"

1. **監督者**: 「AWS操作が必要だ」と判断
2. **監督者**: `api_master("my-bucket という名前のS3バケットを作って")`を呼び出し
3. **APIマスター起動**: ローカルでMCPサーバーを起動
   ```bash
   $ uvx awslabs.aws-api-mcp-server==0.2.1
   ```
4. **ツール取得**: 利用可能なツール一覧を取得
   - `create_s3_bucket`
   - `delete_s3_bucket`
   - `list_s3_buckets`
   - etc.
5. **ツール選択**: `create_s3_bucket`を選択
6. **AWS API呼び出し**:
   ```python
   import boto3
   s3 = boto3.client('s3')
   s3.create_bucket(Bucket='my-bucket')
   ```
7. **結果返却**: "S3バケット 'my-bucket' を us-east-1 リージョンに作成しました"
8. **監督者に返却** → **ユーザーに表示**

#### セキュリティベストプラクティス

1. **IAM権限を最小限に**
   ```json
   {
     "Version": "2012-10-17",
     "Statement": [{
       "Effect": "Allow",
       "Action": ["s3:CreateBucket", "s3:ListBucket"],
       "Resource": "*"
     }]
   }
   ```

2. **確認ステップを追加**
   ```python
   if "delete" in query.lower():
       confirm = input("本当に削除しますか？ (y/n): ")
       if confirm != "y":
           return "削除をキャンセルしました"
   ```

3. **タグ付け**
   ```python
   s3.put_bucket_tagging(
       Bucket='my-bucket',
       Tagging={'TagSet': [
           {'Key': 'CreatedBy', 'Value': 'AI-Agent'},
           {'Key': 'Date', 'Value': '2025-01-15'}
       ]}
   )
   ```

---

### 4. エージェント実行処理 - `agent_executor.py`

#### 概要
サブエージェントを実行し、ストリームからデータを抽出してキューに送信する処理。

このファイルには **2つの関数** があります：

1. **`extract()`**: イベントを解析してキューに送信
2. **`invoke()`**: サブエージェント全体を実行制御

---

#### 関数1: `extract()` - イベント解析処理

**役割**: AIのストリーム出力を解析し、2つのパターンを処理

```python
async def extract(queue, agent, event, state):
```

**処理するイベントの2パターン:**

**パターン1: 文字列イベント（テキストの断片）**
```python
if isinstance(event, str):
    state["text"] += event                    # ① 累積テキストに追加
    if queue:
      delta = {"delta": {"text": event}}      # ② キューに送信用にフォーマット
      await queue.put({"event": {"contentBlockDelta": delta}})  # ③ キューに送信
```

**具体例:**
```
AIのストリーム出力
  ↓
event = "S3"
  ↓
extract() で処理：
  ├─ state["text"] = "S3"（蓄積）
  └─ キューに {"event": {"contentBlockDelta": {"delta": {"text": "S3"}}}} を送信
       ↓
       main.py の merge_streams() で受け取り
       ↓
       yield → ユーザーに "S3" と表示
```

**パターン2: 辞書イベント（メタデータ）**
```python
elif isinstance(event, dict) and "event" in event:
    event_data = event["event"]

    # ツール使用を検出
    if "contentBlockDelta" in event_data:
      block = event_data["contentBlockStart"]
      start_data = block.get("start", {})
      if "toolUse" in start_data:
        tool_use = start_data["toolUse"]
        tool = tool_use.get("name", "unknown")
        await send_event(queue, f"「{agent}」がツール「{tool}」を実行中", "tool_use", tool)

    # テキスト増分を処理
    if "contentBlockDelta" in event_data:
      block = event_data["contentBlockDelta"]
      delta = block.get("delta", {})
      if "text" in delta:
        state["text"] += delta["text"]
```

**具体例1：ツール実行検出**
```
AIがツール実行判断
  ↓
event = {"event": {"contentBlockStart": {"start": {"toolUse": {"name": "create_s3_bucket"}}}}}
  ↓
extract() で処理：
  ├─ ネストを掘り進む
  ├─ contentBlockStart → start → toolUse → name を抽出
  └─ キューに "「APIマスター」がツール「create_s3_bucket」を実行中" を送信
       ↓
       main.py で受け取り
       ↓
       yield → ユーザーに表示
```

**具体例2：テキスト増分の抽出（ネストされた辞書から段階的に取得）**
```
AWS Bedrockの詳細なイベント形式
  ↓
event = {
  "event": {
    "contentBlockDelta": {
      "delta": {
        "text": "S3"
      }
    }
  }
}
  ↓
extract() で処理：
  1️⃣ event_data = event["event"]
     → {"contentBlockDelta": {...}}

  2️⃣ block = event_data["contentBlockDelta"]
     → {"delta": {"text": "S3"}}

  3️⃣ delta = block.get("delta", {})
     → {"text": "S3"}

  4️⃣ if "text" in delta:
     → True

  5️⃣ state["text"] += delta["text"]
     → state["text"] = "S3"（蓄積）
```

**ネストされた辞書の階層図**
```
event
  └─ "event" (辞書)
      ├─ "contentBlockStart" (ツール実行情報)
      │   └─ "start" (辞書)
      │       └─ "toolUse" (ツール情報)
      │           └─ "name" (ツール名)
      │
      └─ "contentBlockDelta" (テキスト増分)
          └─ "delta" (増分情報)
              └─ "text" (テキスト) ← 抽出対象
```

**段階的な安全な取得**

| ステップ | コード | 結果 | 目的 |
|---------|--------|------|------|
| ① | `event_data = event["event"]` | 1階層掘り進む | event配下の"event"を取得 |
| ② | `block = event_data["contentBlockDelta"]` | 2階層掘り進む | contentBlockDelta配下の辞書を取得 |
| ③ | `delta = block.get("delta", {})` | 3階層掘り進む | deltaキーを取得（なければ空辞書） |
| ④ | `if "text" in delta:` | キー確認 | "text"キーが存在するか確認 |
| ⑤ | `state["text"] += delta["text"]` | テキスト抽出 | 最終的なテキスト値を蓄積 |

**なぜ2つのパターンがあるのか？**

AWS Bedrockは同じテキスト情報を複数の形式で送信：

| パターン | 形式 | 用途 |
|---------|------|------|
| **パターン1（シンプル）** | `event = "S3"` | 高速ストリーミング向け |
| **パターン2（詳細）** | `event = {"event": {"contentBlockDelta": {"delta": {"text": "S3"}}}}` | メタデータ付き（ツール情報など含む） |

両パターンに対応することで **どちらの形式でも対応できる堅牢な実装** を実現

---

#### 関数2: `invoke()` - エージェント実行制御

**役割**: サブエージェント全体のライフサイクル管理

```python
async def invoke(agent, query, mcp, create_agent, queue):
```

**処理フロー（詳細）:**

1. **状態初期化**
   ```python
   state = {"text": ""}
   ```
   蓄積テキスト用の辞書を作成

2. **開始通知**
   ```python
   await send_event(queue, f"サブエージェント「{agent}」が呼び出されました", "start")
   ```
   キューに「起動した」という通知を送信

3. **MCPクライアント起動**
   ```python
   with mcp:  # MCPコンテキストマネージャー
   ```
   MCPを起動。`with`の終了時に自動でクリーンアップ

4. **エージェント作成**
   ```python
   agent_obj = create_agent()
   ```
   aws_master.py や api_master.py の `_create_agent()` を呼び出し

5. **ストリーミング開始 + イベント処理ループ**
   ```python
   async for event in agent_obj.stream_async(query):
     await extract(queue, agent, event, state)
   ```
   - AIが出力する1個のイベントを受け取る度に `extract()` を呼び出す
   - `extract()` がテキストを蓄積し、キューに送信

6. **完了通知**
   ```python
   await send_event(queue, f"「{agent}」が対応を完了しました", "complete")
   ```

7. **結果返却**
   ```python
   return state["text"]
   ```
   蓄積したテキスト全体を監督者エージェント（main.py）に返す

---

#### 実行例：タイムライン

**シナリオ:** APIマスターがS3バケット作成

| 時間 | 関数 | 処理 | キューに送信 | state["text"] |
|------|------|------|------------|----------------|
| t=0.0秒 | `invoke()` | 開始 | "APIマスター起動" | "" |
| t=0.1秒 | `invoke()` | MCP起動 | (なし) | "" |
| t=0.2秒 | `invoke()` | エージェント作成 | (なし) | "" |
| t=0.3秒 | `extract()` | event="S3" (文字列) | `{"delta": {"text": "S3"}}` | "S3" |
| t=0.4秒 | `extract()` | event="バケット" | `{"delta": {"text": "バケット"}}` | "S3バケット" |
| t=0.5秒 | `extract()` | event=ツール実行辞書 | "ツール「create_s3_bucket」実行中" | "S3バケット" |
| t=1.0秒 | `extract()` | event="を" | `{"delta": {"text": "を"}}` | "S3バケットを" |
| t=1.1秒 | `extract()` | event="作成" | `{"delta": {"text": "作成"}}` | "S3バケットを作成" |
| t=1.2秒 | `invoke()` | ストリーム終了 | "APIマスター完了" | "S3バケットを作成しました" |
| t=1.3秒 | `invoke()` | return | (なし) | 全テキストを返却 |

---

#### 2つの関数の役割分担

| 関数 | 責務 | 非同期か |
|------|------|---------|
| **`extract()`** | イベント1個を処理。テキスト蓄積 + キュー送信 | 非同期 (`async`) |
| **`invoke()`** | サブエージェント全体のライフサイクル管理。複数の `extract()` を呼び出す | 非同期 (`async`) |

**比喩：**
- `invoke()` = 図書館の窓口係（来館者を記録して、貸出カウンターへ）
- `extract()` = 貸出カウンター（本1冊を処理）

---

#### キーポイント

1. **`state["text"]`**: 最終的に返すテキストの蓄積
2. **キュー送信**: リアルタイムでユーザーに表示
3. **イベント2パターン**: 文字列（テキスト）と辞書（メタデータ）を別々に処理
4. **非同期**: `await` で複数処理を効率的に連携
5. **with文**: MCPの自動クリーンアップを保証

---

### 5. ストリーム統合処理 - `stream_handler.py`（最重要！）

#### 概要
親エージェント（監督者）と子エージェント（サブ）のストリームを**同時に**監視し、データが来た順に`yield`で返す。

#### 並行処理の仕組み

```python
async def merge_streams(stream, queue):
    # 2つのタスクを作成
    main = create_task(anext(stream, None))  # 親の次のデータを待つ
    sub = create_task(queue.get())           # 子の次のデータを待つ

    while True:
        # どちらか先に完了した方を取得
        ready_chunks, waiting = await asyncio.wait(
            {main, sub},
            return_when=asyncio.FIRST_COMPLETED
        )

        for chunk in ready_chunks:
            if chunk == main:
                yield main.result()  # 親のデータを即座に返す
                main = create_task(anext(stream, None))  # 次を待つ準備
            elif chunk == sub:
                yield sub.result()   # 子のデータを即座に返す
                sub = create_task(queue.get())  # 次を待つ準備
```

#### タイムライン（実例）

**質問:** "S3バケットを作って"

| 時間 | タスク | データ | 処理 |
|------|--------|--------|------|
| t=0.0秒 | - | - | `merge_streams()`開始 |
| t=0.1秒 | **sub完了** | `{"subAgentProgress": "APIマスター起動"}` | **yield** → main.pyに渡される |
| t=0.2秒 | **main完了** | `"S3"` | **yield** → main.pyに渡される |
| t=0.3秒 | **main完了** | `"バケット"` | **yield** → main.pyに渡される |
| t=0.4秒 | **sub完了** | `{"subAgentProgress": "ツール実行中"}` | **yield** → main.pyに渡される |
| t=0.5秒 | **main完了** | `"を"` | **yield** → main.pyに渡される |
| t=1.5秒 | **sub完了** | `{"subAgentProgress": "完了"}` | **yield** → main.pyに渡される |
| t=1.6秒 | **main完了** | `"作成しました"` | **yield** → main.pyに渡される |
| t=1.7秒 | **main完了** | `None` (終了) | main = None |
| t=1.8秒 | - | - | `queue.empty() == True` → break |

#### asyncio.wait()の内部動作

```python
# 簡略版の動作イメージ
while True:
    for task in {main, sub}:
        if task.done():  # 完了しているか？
            return task  # 完了したタスクを返す
    await asyncio.sleep(0)  # 少し待つ
```

---

## 実行方法

### Sample編

```bash
# 1. マルチエージェント基本
cd chapter6/sample
python 1_stands.py

# 2. LangGraph
python 2_langgraph.py

# 3. A2A通信（2つのターミナルが必要）
# ターミナル1
python 4_a2a_server.py

# ターミナル2
python 5_a2a_client.py
```

### Backend編

```bash
# .envファイルを設定（MODEL_ID、AWS認証情報など）
# 例: MODEL_ID=us.anthropic.claude-3-7-sonnet-20250219-v1:0

# サーバー起動
cd chapter6/backend/src
python main.py

# 別のターミナルでリクエスト送信
curl -X POST http://localhost:8000/invoke \
  -H "Content-Type: application/json" \
  -d '{"input": {"prompt": "S3とは何ですか？"}}'
```

---

## 技術スタック

### ライブラリ

| ライブラリ | 用途 | 使用箇所 |
|-----------|------|----------|
| `strands` | AIエージェント作成 | 全ファイル |
| `strands_tools` | ツール提供（calculator等） | 1_stands.py |
| `langgraph` | グラフ構造のワークフロー | 2_langgraph.py |
| `mcp` | Model Context Protocol | aws_master.py, api_master.py |
| `bedrock_agentcore` | AWS Bedrock統合 | main.py |
| `asyncio` | 非同期処理 | Backend全体 |

### 重要な概念

| 概念 | 説明 | 学習難易度 |
|------|------|-----------|
| **デコレータ（@tool）** | 関数をツール化 | ⭐ |
| **マルチエージェント** | 複数のAIを連携 | ⭐⭐ |
| **グラフ構造** | ノードとエッジでフロー制御 | ⭐⭐⭐ |
| **A2A通信** | エージェント間通信 | ⭐⭐ |
| **async/await** | 非同期処理 | ⭐⭐⭐⭐ |
| **yield** | データストリーミング | ⭐⭐⭐⭐ |
| **asyncio.wait()** | 複数タスクの並行監視 | ⭐⭐⭐⭐⭐ |
| **MCP** | AI用通信規格 | ⭐⭐⭐ |

---

## 学習ロードマップ

### 初級（Python少しわかる）

1. ✅ `1_stands.py` - マルチエージェント基本
2. ✅ `4_a2a_server.py` + `5_a2a_client.py` - A2A通信
3. ✅ `yield`の基本概念を理解

### 中級

4. ✅ `2_langgraph.py` - グラフ構造
5. ✅ `main.py` - async/awaitの基本
6. ✅ `aws_master.py` - MCPの仕組み

### 上級

7. ✅ `agent_executor.py` - ストリーム処理
8. ✅ `stream_handler.py` - 並行処理とyield
9. ✅ 自分でマルチエージェントシステムを設計

---

## トラブルシューティング

### Q1: A2Aサーバーに接続できない

**エラー:**
```
Error: Failed to connect to http://localhost:9000
```

**解決策:**
1. `4_a2a_server.py`が起動しているか確認
2. ポート9000が使用中でないか確認: `lsof -i :9000`（Mac/Linux）

### Q2: AWS APIエラー

**エラー:**
```
botocore.exceptions.NoCredentialsError
```

**解決策:**
1. AWS認証情報を設定: `aws configure`
2. `.env`ファイルに認証情報を追加
3. IAMロールが正しいか確認

### Q3: MCPクライアントが利用不可

**エラー:**
```
MCPクライアントが利用不可です
```

**解決策:**
1. ネットワーク接続を確認
2. `uvx`コマンドがインストールされているか確認: `pip install uvx`
3. ファイアウォール設定を確認

---

## まとめ

### Sample編で学べること
- マルチエージェントの基本パターン
- グラフ構造のフロー制御
- エージェント間通信（A2A）

### Backend編で学べること
- 実践的なWebアプリケーション構築
- ストリーミングレスポンスの実装
- 非同期処理の活用
- 複数のストリームの統合

### 最重要ポイント
1. **yield**: データを少しずつ返す = リアルタイム表示
2. **async/await**: 並行処理で効率化
3. **asyncio.wait()**: 複数のタスクを同時監視
4. **マルチエージェント**: 専門化されたAIを組み合わせる

---

## 参考リンク

- [Strands公式ドキュメント](https://github.com/anthropics/strands)
- [LangGraph公式ドキュメント](https://langchain-ai.github.io/langgraph/)
- [MCP仕様](https://github.com/modelcontextprotocol)
- [AWS Bedrock](https://aws.amazon.com/bedrock/)

---

**Happy Coding! 🚀**
