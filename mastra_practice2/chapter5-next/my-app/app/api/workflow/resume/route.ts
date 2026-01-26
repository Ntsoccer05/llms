import { NextResponse } from "next/server";
import { mastra } from "@/src/mastra";
import { success } from "zod";

type resumeRequest = {
  owner: string;
  repo: string;
  issues: [{
    title: string,
    body: string
  }],
  query: string;
  approved: boolean;
}

export async function POST(request: Request): Promise<NextResponse> {
  const {owner, repo, issues, query, approved}: resumeRequest = await request.json();

  if(!approved) {
    NextResponse.json({
      approved: false,
      message: "GitHubのIssues作成が禁止されました。再度実行するか、元に戻ってください"
    })
  }

  try{
    const githubCreateIssueTool = ((await import('@/src/mastra/tools/githubTool')).githubCreateIssueTool)
    const result = await githubCreateIssueTool.execute({
      context: {
        owner,
        repo,
        issues
      }
    } as any);
    console.log("result", result);
    let message;
    let isSuccess;

    if(result.success === true) {
      message = "ワークフローが正常に完了しました";
      isSuccess = true;
    }else{
      const detailErrorMsg = result.errors || "エラーが発生しました"
      message = detailErrorMsg
      isSuccess = false
    }

    const createdIssues = result.createdIssues || [];

    return NextResponse.json({
      success: isSuccess,
      message,
      confluencePages: [{
        title: query,
        message: "要件書の検索と取得を実行しました"
      }],
      githubIssues: createdIssues,

    })
  }catch(error) {
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