import type { Schemas } from "../../../api/contract";

/**
 * A literal copy of the "What each plug-in reads" table under [Source plug-ins]
 * (/features/signal-pipeline.md#source-plug-ins) (D3), tied to it by `pluginWords.test.ts`.
 */
export const WHAT_IT_READS: Record<Schemas["SourcePluginCode"], string> = {
  GDELT: "News articles worldwide that name the account, found through the GDELT Project",
  RSS: "The news and blog feeds listed among the account's sources",
  WEBSITE: "The account's own website, newsroom and investor pages, and the reports they link",
  CAREERS: "Job postings on the account's career pages and job boards",
  CRUNCHBASE: "The company's profile, key people, funding and acquisitions",
  NEWSAPI: "News articles that name the account, found through NewsAPI",
  SERPAPI: "Google News and web search results for the account, found through SerpAPI",
};
