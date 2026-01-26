import { NextResponse } from "next/server";
import { mastra } from "@/src/mastra";

type resumeRequest = {
  owner: string,
  repo: string,
  issues: [{
    title: string,
    body: string
  }],
  approved: boolean
}

export async function POST(request: Request) {
  const {owner, repo, issues, approved}: resumeRequest = await request.json();

  if(!approved) {
    NextResponse.json({
      approved: false,
      message: "GitHubのIssues作成が禁止されました。再度実行するか、元に戻ってください"
    })
  }

  const githubCreateIssueTool = ((await import('@/src/mastra/tools/githubTool')).githubCreateIssueTool)
  const result = await githubCreateIssueTool.execute({
    context: {
      owner,
      repo,
      issues
    }
  } as any);

  console.log(result);
}