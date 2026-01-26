"use client";

import { useState } from 'react';
import { WorkflowForm } from '@/app/components/WorkflowForm';
import { WorkflowResults } from '@/app/components/WorkflowResults';
import { WorkflowFormData, WorkflowResult } from '@/app/types/workflow';

// ワークフローのコンテナコンポーネント（Client Component）
// 状態管理とAPI呼び出しを担当
export const WorkflowContainer = () => {
  // フォームの状態を管理するためのuseStateフック
  const [formData, setFormData] = useState<WorkflowFormData>({
    query: "",
    owner: "",
    repo: ""
  });
  // ワークフローの実行状態と結果を管理するためのuseStateフック
  const [isLoading, setIsLoading] = useState(false);
  // ワークフローの結果を管理するためのuseStateフック
  const [result, setResult] = useState<WorkflowResult | null>(null);

  // 入力フィールドの変更を処理する関数
  const handleInputChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    // 入力フィールドの名前と値を取得
    const { name, value } = e.target;
    // フォームデータの状態を更新
    setFormData(prev => ({
      ...prev,
      [name]: value
    }));
  };

  // フォームの送信を処理する関数
  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    // フォームが送信されたときにローディング状態を設定し、結果を初期化
    setIsLoading(true);
    // ワークフローの結果を初期化
    setResult({
      success: false,
      message: "ワークフローを実行中...",
      confluencePages: [],
      githubIssues: [],
      steps: []
    });

    try {
      // APIエンドポイントにPOSTリクエストを送信
      const response = await fetch("/api/workflow/execute", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify(formData),
      });

      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`);
      }

      // 結果をJSON形式で取得
      const data = await response.json();
      // レスポンスの結果をstateに設定
      setResult(data);
    } catch (error) {
      setResult({
        success: false,
        message: "ワークフローの実行中にエラーが発生しました",
        error: error instanceof Error ? error.message : "不明なエラー",
        confluencePages: [],
        githubIssues: [],
        steps: []
      });
    } finally {
      setIsLoading(false);
    }
  };

  const hundleResume = async () => {
    if (!result?.owner) return
    setIsLoading(true);
    try{

      const response = await fetch("/api/workflow/resume", {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json'
        },
        body: JSON.stringify(result)
      })
  
      if(!response.ok) {
        throw new Error('GitHub Issuesの作成に失敗しました')
      }
  
      const data = response.json();
      setResult(data);
    }catch(error) {
      setResult({
        success: false,
        message: "ワークフローの実行中にエラーが発生しました",
        error: error instanceof Error ? error.message : "不明なエラー",
        confluencePages: [],
        githubIssues: [],
        steps: []
      });
    }finally {
      setIsLoading(false);
    }
  }

  return (
    <>
      {/* ワークフローのフォームコンポーネント */}
      <WorkflowForm
        formData={formData}
        isLoading={isLoading}
        onInputChange={handleInputChange}
        onSubmit={handleSubmit}
      />

      {/* ワークフローの結果を表示するコンポーネント */}
      <WorkflowResults result={result} hundleResume={hundleResume} />
    </>
  );
};
