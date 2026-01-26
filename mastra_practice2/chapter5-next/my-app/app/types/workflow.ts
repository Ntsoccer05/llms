type issues = Array<{
  issueNumber: number;
  issueUrl: string;
  title: string;
}>;

export interface WorkflowFormData {
  query: string;
  owner: string;
  repo: string;
}


export interface WorkflowResult {
  success: boolean;
  message: string;
  repo?: string;
  owner?: string;
  issues?: issues;
  confluencePages: Array<{
    title: string;
    message: string;
  }>;
  githubIssues: issues;
  steps: Array<{
    stepId: string;
    status?: 'success' | 'error';
  }>;
  error?: string;
}