import { Agent } from "@mastra/core/agent";
import { bedrock } from "@ai-sdk/amazon-bedrock";

const MODEL_ID = "jp.anthropic.claude-haiku-4-5-20251001-v1:0";

// V2モデルとして強制的に設定（Claude Haiku 4.5はV2 APIを使用）
const model = bedrock(MODEL_ID);
// haiku-4-5が自動的にv2となるため独自に指定が必要。そうでないとv1が使用されエラーが出る
model.specificationVersion = "v2";

export const assistantAgent = new Agent({
  name: "assistant",
  instructions: "あなたは親切で知識豊富なAIアシスタントです。ユーザーの質問に対して、分かりやすく丁寧に回答してください。",
  model: model,
});