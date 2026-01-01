
import { Mastra } from '@mastra/core/mastra';
import { assistantAgent } from './agents/assistantAgent';

export const mastra = new Mastra({
  agents: { assistantAgent },
})
