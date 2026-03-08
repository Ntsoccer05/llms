import { AuthFetchAuthSessionServer } from "./amplify-server-utils";


export async function getBedrockModel() {
  try {
    // Bedrockのクライアントをインポート
    const { createAmazonBedrock } = await import("@ai-sdk/amazon-bedrock");
    // BedrockモデルのIDとリージョンを設定
    const modelId = "claude-haiku-4-5-v1:0"; // プレフィックスなしのモデルID
    const region = process.env.AWS_REGION || "ap-northeast-1";
    // 認証セッションを取得
    const session = await AuthFetchAuthSessionServer();
    if (!session || !session.credentials) {
      throw new Error("Failed to get authentication session");
    }
    // Bedrockのクライアントを作成
    const bedrock = createAmazonBedrock({
      region,
      accessKeyId: session.credentials.accessKeyId,
      secretAccessKey: session.credentials.secretAccessKey,
      sessionToken: session.credentials.sessionToken,
    });
    // Anthropic専用のメソッドを使用（自動的にv2が使われる）
    const model = bedrock.anthropic(modelId);
    return model;
  } catch (error) {
    throw error;
  }
}