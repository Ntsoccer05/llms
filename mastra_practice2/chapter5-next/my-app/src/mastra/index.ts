
import { Mastra } from '@mastra/core/mastra';
import { assistantAgent } from './agents/assistantAgent';
import { handsonWorkflow } from './workflows/handson';

export const mastra = new Mastra({
  agents: { assistantAgent },
  workflows: { handsonWorkflow }
})
