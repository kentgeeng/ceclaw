// index.ts
import { Type } from "@sinclair/typebox";
function register(api) {
  const cfg = api.pluginConfig ?? {};
  const baseUrl = cfg.baseUrl?.trim() || process.env.SEARXNG_URL || "http://localhost:8080";
  const timeoutMs = cfg.timeoutMs ?? 15e3;
  const defaultCount = cfg.defaultCount ?? 5;
  api.registerTool({
    name: "searxng_search",
    description: "Search the web via self-hosted SearXNG. Returns titles, URLs, and snippets. Privacy-preserving, aggregated results from 70+ engines. Use for web searches, especially when privacy matters or as an alternative to Brave.",
    parameters: Type.Object({
      query: Type.String({ description: "Search query string." }),
      count: Type.Optional(
        Type.Number({
          description: "Number of results (1-20, default 5).",
          minimum: 1,
          maximum: 20
        })
      ),
      categories: Type.Optional(
        Type.String({
          description: "Comma-separated categories: general, images, news, videos, it, science, files, music, social media."
        })
      ),
      language: Type.Optional(
        Type.String({
          description: "Language code (e.g. en, de, fr)."
        })
      ),
      time_range: Type.Optional(
        Type.String({
          description: "Time range: day, week, month, year."
        })
      )
    }),
    async execute(_toolCallId, args) {
      const query = args.query;
      const count = args.count ?? defaultCount;
      const params = new URLSearchParams({
        q: query,
        format: "json"
      });
      if (args.categories) params.set("categories", args.categories);
      if (args.language) params.set("language", args.language);
      if (args.time_range) params.set("time_range", args.time_range);
      try {
        const res = await fetch(`${baseUrl}/search?${params}`, {
          signal: AbortSignal.timeout(timeoutMs)
        });
        if (!res.ok) {
          const detail = await res.text().catch(() => "");
          return {
            content: [
              {
                type: "text",
                text: JSON.stringify({
                  error: `SearXNG error (${res.status}): ${detail || res.statusText}`
                })
              }
            ]
          };
        }
        const data = await res.json();
        const results = (data.results ?? []).slice(0, count).map((r) => ({
          title: r.title ?? "",
          url: r.url ?? "",
          description: r.content ?? "",
          published: r.publishedDate ?? void 0,
          engines: r.engines?.join(", ") ?? void 0,
          score: r.score ?? void 0,
          category: r.category ?? void 0
        }));
        return {
          content: [
            {
              type: "text",
              text: JSON.stringify({
                query,
                provider: "searxng",
                count: results.length,
                results
              })
            }
          ]
        };
      } catch (err) {
        const message = err instanceof Error ? err.message : "Unknown error";
        return {
          content: [
            {
              type: "text",
              text: JSON.stringify({
                error: `SearXNG request failed: ${message}`
              })
            }
          ]
        };
      }
    }
  });
}
export {
  register as default
};
