import { createWorkflow, createStep } from "@mastra/core/workflows";
import { confluenceSearchPagesTool, confluenceGetPageTool } from "../tools/confluenceTool";
import { githubCreateIssueTool } from "../tools/githubTool";
import { assistantAgent } from "../agents/assistantAgent";
import { z } from "zod"

// ツールからステップを作成
const confluenceSearchPagesStep = createStep(confluenceSearchPagesTool);
const confluenceGetPageStep = createStep(confluenceGetPageTool);
const githubCreateIssueStep = createStep(githubCreateIssueTool);

export const handsonWorkflow = createWorkflow({
  id: "handsonWorkflow",
  description: "自然言語の質問からConfluenceで要件書を検索し、GitHub Issueとして開発バックログを自動作成します。",
  inputSchema: z.object({
    query: z.string().describe("検索したい内容を自然言語で入力してください(例：「AIについての情報」「最新のプロジェクト情報」)"),
    owner: z.string().describe("リポジトリの所有者（ユーザ名またはorganization名）"),
    repo: z.string().describe("リポジトリ名"),
  }),
  // ツールから取得可能
  outputSchema: githubCreateIssueTool.outputSchema
}).then(
  createStep({
    id: "generate-cql-query",
    inputSchema: z.object({
      query: z.string(),
      owner: z.string(),
      repo: z.string()
    }),
    outputSchema: z.object({
      cql: z.string()
    }),
    execute: async ({ inputData }) => {
      const prompt = `
        以下の自然言語の検索要求をConfluence CQL（Confluence Query Language）に変換してください。
        CQLの基本的な構文：
        - text ~ "検索語"：全文検索
        - title ~ "タイトル"：タイトル検索
        - space = "スペースキー"：特定のスペース内検索
        - type = page：ページのみ検索
        - created >= "2024-01-01"：日付フィルタ
  
        検索要求：${inputData.query}
  
        重要：
        - 単純な単語検索の場合は、text ~ "単語"の形式を使用
        - 複数の単語を含む場合は AND で結合
        - 日本語の検索語もそのまま使用可能
        - レスポンスはCQLクエリのみを返してください
  
        CQLクエリ：`;
        try{
          const result = await assistantAgent.generate(prompt);
          const cql = result.text.trim();
          return { cql };
        }catch(error) {
          const fallbackCql = `text ~ "${inputData.query}"`
          return { cql: fallbackCql };
        }
      }
  })
).then(confluenceSearchPagesStep)
.then(
  createStep({
    id: "select-first-page",
    inputSchema: z.object({
      pages: z.array(
        z.object({
          id: z.string(),
          title: z.string(),
          url: z.string().optional()
        })
      ),
      total: z.number(),
      error: z.string().optional()
    }),
    outputSchema: z.object({
      pageId: z.string(),
      expand: z.string().optional()
    }),
    execute: async ({ inputData }) => {
      // ページの一覧取得
      const { pages, error } = inputData;
      if(error) {
        throw new Error(`検索エラー： ${error}`)
      }
      if(!pages || pages.length === 0) {
        throw new Error("検索結果が見つかりませんでした。")
      }

      // 最初のページを取得
      const firstPage = pages[0];
      return {
        pageId: firstPage.id,
        expand: "body.storage"
      };
    }
  })
)
.then(confluenceGetPageStep)
.then(
  createStep({
    id: "create-development-tasks",
    // Confluenceページ取得ツールのoutputSchemaをそのまま指定
    inputSchema: confluenceGetPageTool.outputSchema,
    // Github Issues作成ツールのoutputSchemaをそのまま指定
    outputSchema: githubCreateIssueTool.inputSchema,
    execute: async ({inputData, getInitData}) => {
      // 前のステップから受け渡されるConfluenceのページ情報
      const { page, error } = inputData;
      // GitHubのリポジトリ情報はワークフローの初期データから取得
      const { owner, repo, query } = getInitData();

      // いずれかの情報が取れない場合はエラーメッセージを送信
      if(error || !page || !page.content) {
        return {
          owner: owner || "",
          repo: repo || "",
          issues: [
            {
              title: "エラー： ページの内容が取得できませんでした。",
              body: "Confluenceページの内容を取得できませんでした。"
            }
          ]
        }
      }
      // エージェントからの出力フォーマットを規定
      const outputSchema = z.object({
        issues: z.array(
          z.object({
            title: z.string(),
            body: z.string(),
          })
        )
      });
      // プロンプト
      const analysisPrompt = `以下のConfluenceページの内容は要件書です。この要件書を分析して、開発バックログのGitHub Issue を複数作成するための情報を生成してください。
      ユーザーの質問： ${query}
      ページタイトル： ${page.title}
      ${page.content}
      重要：
      - 要件書の内容を機能やコンポーネント単位で分割
      - 各Issueのtitleは簡潔で分かりやすく
      - bodyはMarkdown形式で構造化
      - フォーマットはJSON配列形式で、必ず出力。枕詞は不要。トップの配列は必ず角括弧で囲む
      - \`\`\`jsonのようなコードブロックは不要
      - 2つIssueを作成
      - 曖昧な部分は「要確認」として記載`;

      try{
        const result = await assistantAgent.generate(analysisPrompt, {
          output: outputSchema, // エージェントからの出力フォーマットを指定
        });
        // JSONからIssueの配列を取り出す
        const parsedResult = JSON.parse(result.text);
        const issues = parsedResult.issues.map((issue: any) => ({
          title: issue.title,
          body: issue.body,
        }));
        return {
          owner: owner || "",
          repo: repo || "",
          issues: issues,
        };
      }catch (error) {
        return {
          owner: owner,
          repo: repo,
          issues: [
            {
              title: "エラー： Issue作成に失敗",
              body: "エラーが発生しました： " + String(error), 
            }
          ]
        }
      }
    }
  })
).then(githubCreateIssueStep)
.commit()
// Confluenceページを取得するステップを追加
// .then(confluenceGetPageStep)
// .then(
//   createStep({
//     id: "prepare-prompt",
//     inputSchema: z.object({
//       page: z.object({
//         id: z.string(),
//         title: z.string(),
//         url: z.string(),
//         content: z.string().optional(),
//       }),
//       error: z.string().optional()
//     }),
//     outputSchema: z.object({
//       prompt: z.string(),
//       originalQuery: z.string(),
//       pageTitle: z.string(),
//       pageUrl: z.string()
//     }),
//     execute: async({ inputData, getInitData }) => {
//       // ひとつ前のステップのoutputSchemaから渡されたデータ
//       const {page, error} = inputData;;
//       // ワークフローの最初に設定されたデータ（getInitData）
//       const initData = getInitData();

//       if(error || !page || !page.content) {
//         return {
//           prompt: "ページの内容が取得できませんでした。",
//           originalQuery: initData.query || "",
//           pageTitle: page?.title || "不明",
//           pageUrl: page?.url || "",
//         };
//       }
//       // エージェントへの指示を作成
//       const prompt = `以下のConfluenceページの内容に基づいて、ユーザーの質問に答えてください。
//       ユーザーの質問： ${initData.query}

//       ページタイトル： ${page.title}
//       ページの内容：
//       ${page.content}

//       回答は簡潔で分かりやすく、必要に応じて箇条書きを使用してください。`;
//       return {
//         prompt,
//         originalQuery: initData.query || "",
//         pageTitle: page.title,
//         pageUrl: page.url
//       };
//     }
//   })
// )
// .then(
//   createStep({
//     id: "assistant-response",
//     inputSchema: z.object({
//       prompt: z.string(),
//       originalQuery: z.string(),
//       pageTitle: z.string(),
//       pageUrl: z.string()
//     }),
//     outputSchema: z.object({
//       // ワークフロー(createWorkflow)のoutputSchemaと一致させる
//       text: z.string()
//     }),
//     execute: async({ inputData }) => {
//       try{
//         // エージェントを実行しテキスト生成結果を受け取る(V2ではgenarateVNext()ではなくgenerate()を使用する)
//         const result = await assistantAgent.generate(inputData.prompt);
//         return {
//           text: result.text
//         }
//       } catch(error) {
//         return {text: "エラーが発生しました： " + String(error)}
//       }
//     }
//   })
// )
// ワークフローの最後であることを示すために.commit()を最後のステップのあとに設定
.commit();