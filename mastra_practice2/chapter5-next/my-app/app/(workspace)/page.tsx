import { WorkflowContainer } from '@/app/components/WorkflowContainer';
import { WorkflowInstructions } from '@/app/components/WorkflowInstructions';

// ワークフローのメインページコンポーネント（Server Component）
const Page = () => {
  return (
    <div className="min-h-screen bg-gradient-to-br
     from-blue-50 via-white to-purple-50">
      <div className="container mx-auto px-4 py-8">
        <div className="max-w-4xl mx-auto">
          <div className="bg-white/90 backdrop-blur-sm
           rounded-2xl shadow-xl border border-gray-100
            p-8 transition-all hover:shadow-2xl">
            <h1 className="text-3xl font-bold
             bg-gradient-to-r from-blue-600
              to-purple-600 bg-clip-text
               text-transparent mb-8">
              要件書→プロダクトバックログ ワークフロー
            </h1>

            {/* Server Component：静的なワークフロー説明 */}
            <div className="mb-8">
              <WorkflowInstructions />
            </div>

            {/* Client Component：状態管理が必要な部分 */}
            <WorkflowContainer />
          </div>
        </div>
      </div>
    </div>
  );
};

export default Page;