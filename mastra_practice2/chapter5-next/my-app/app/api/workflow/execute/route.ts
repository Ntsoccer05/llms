// Next.jsのサーバーサイド機能をインポート
// NextRequest: リクエスト情報を扱うクラス
// NextResponse: レスポンスを返すクラス
import { NextRequest, NextResponse } from "next/server";

/**
 * Next.js App Router の API Route
 *
 * このファイルは `/api/workflow/execute` エンドポイントを定義します
 * POSTリクエストを受け取り、Mastraワークフローを実行して結果を返します
 *
 * 【処理の流れ】
 * 1. フロントエンドからPOSTリクエストを受け取る
 * 2. リクエストボディからパラメータを取得・検証
 * 3. Mastraワークフローを実行
 * 4. 実行結果をJSON形式で返す
 */
export async function POST(request: NextRequest){
  try{
    // 【ステップ1】リクエストボディを取得
    // クライアントから送信されたJSONデータを取得（非同期処理なのでawaitが必要）
    const body = await request.json();

    // 【ステップ2】必要なパラメータを分割代入で取り出す
    // query: Confluence検索クエリ（例: "AIについての情報"）
    // owner: GitHubリポジトリの所有者（例: "Ntsoccer05"）
    // repo: GitHubリポジトリ名（例: "llms"）
    const{query, owner, repo} = body;

    // 【ステップ3】バリデーション（入力値の検証）
    // 必須パラメータが全て存在するかチェック
    if(!query || !owner || !repo){
      // パラメータが不足している場合は400エラーを返す
      // 400 = Bad Request（クライアント側のエラー）
      return NextResponse.json(
        {error: "必要なパラメータが不足しています"},
        {status: 400}
      );
    }

    // 【ステップ4】Mastraワークフローインスタンスを取得
    // 動的インポート（必要な時だけ読み込む）でMastraインスタンスを取得
    // import("@/src/mastra") ← index.tsから、エージェント・ワークフローが登録されたMastraインスタンスをインポート
    const {mastra} = await import("@/src/mastra");

    // mastra.getWorkflow(): 登録済みのワークフローを取得
    // "handsonWorkflow" ← index.tsで登録したワークフローのキー名
    // このワークフローは @/src/mastra/workflows/handson.ts で定義されています
    const workflow = mastra.getWorkflow("handsonWorkflow");

    // ワークフローが見つからない場合はエラーを投げる
    if(!workflow) {
      throw new Error("ワークフローが見つかりません");
    }

    // 【ステップ5】ワークフローを実行
    // createRunAsync(): ワークフローの実行準備（非同期）
    const run = await workflow.createRunAsync();

    // start(): ワークフローを開始し、結果を待つ
    // inputData: ワークフローに渡す初期データ
    const result = await run.start({
      inputData: {query, owner, repo}
    });

    // 【ステップ6】ワークフロー実行結果を解析
    // 返却メッセージとステータスを作成
    let message;
    let isSuccess;

    if(result.status === "suspended") {
      // result.steps の構造を確認
      console.log("result.steps:", result.steps);
      console.log("result.steps type:", typeof result.steps);
      console.log("result.steps keys:", Object.keys(result.steps as Record<string, unknown>));

      // github-create-issue-step-human-in-the-loop のステップを取得
      const stepData = (result.steps as Record<string, unknown>)["github-create-issue-step-human-in-the-loop"] as Record<string, unknown> | undefined;
      console.log("stepData:", stepData);
      console.log("suspendPayload:", (stepData as Record<string, unknown>)?.suspendPayload);

      const payload = stepData?.['payload'] as Record<string, unknown> | undefined;
      const owner = payload?.['owner'] as string | undefined;
      const repo = payload?.['repo'] as string | undefined;
      const issues = payload?.['issues'] as unknown;

      return NextResponse.json({
        success: true,
        message: ((stepData as Record<string, unknown>)?.suspendPayload as Record<string, string> | undefined)?.message || "ユーザーの確認を待機中です",
        repo,
        owner,
        issues,
        steps: result.steps ? Object.keys(result.steps).map(stepId => ({
          stepId,
          status: (result.steps as any)[stepId].status
        })) : []
      })
    }

    // result.status: ワークフローの全体的なステータス（"success" or "error"）
    // result.result.success: 最終ステップ（GitHub Issue作成）の成功フラグ
    if(result.status === "success" && result.result?.success) {
      message = "ワークフローが正常に完了しました";
      isSuccess = true;
    } else {
      // エラーメッセージを結合
      // オプショナルチェーン(?.)を使って安全にエラー情報にアクセス
      const errorMsg = (result as any).error || "エラーが発生しました";
      const detailErrors = (result as any).result?.errors;
      message = detailErrors ? `${errorMsg}: ${detailErrors}` : errorMsg;
      isSuccess = false;
    }

    // Mastraワークフローの結果から必要な情報を抽出
    // 三項演算子: 成功時はresult.resultを、失敗時はnullを代入
    const workflowOutput = result.status === "success" ? result.result : null;

    // オプショナルチェーン(?.)とnullish coalescing(||)を使って安全に配列を取得
    // workflowOutputがnullの場合や、createdIssuesがundefinedの場合は空配列[]を使用
    const createdIssues = workflowOutput?.createdIssues || [];

    // 【ステップ7】結果をAPIレスポンスとして返却
    // NextResponse.json(): JSONレスポンスを生成
    return NextResponse.json({
      // 全体の成功/失敗フラグ
      success: isSuccess,

      // Confluenceページ情報（今回は検索クエリのみ）
      confluencePages: [{
        title: query,
        message: "要件書の検索と取得を実行しました"
      }],

      // 作成されたGitHub Issueの配列
      // 各issueには issueNumber, issueUrl, title が含まれる
      githubIssues: createdIssues,

      // ユーザー向けメッセージ
      message: message,

      // ワークフローの各ステップの実行状況
      // Object.keys(): オブジェクトのキー（ステップID）を配列に変換
      // map(): 各ステップの情報を整形
      steps: result.steps ? Object.keys(result.steps).map(stepId => ({
        stepId,
        status: (result.steps as any)[stepId].status
      })) : []
    })
  } catch(error) {
    // 【エラーハンドリング】
    // try-catchで捕捉されたエラーをAPIレスポンスとして返却
    // 500 = Internal Server Error（サーバー側のエラー）
    return NextResponse.json(
      {
        error: "ワークフローの実行中にエラーが発生しました",
        // instanceof: エラーオブジェクトの型チェック
        details: error instanceof Error ? error.message : "エラー"
      },
      {status: 500}
    )
  }
}