import * as fs from "fs";
import * as path from "path";
import * as os from "os";

interface CECLAWConfig {
  router?: { listen_host?: string; listen_port?: number };
  inference?: { strategy?: string };
}

function loadCECLAWConfig(): CECLAWConfig {
  const configPath = process.env.CECLAW_CONFIG ||
    path.join(os.homedir(), ".ceclaw", "ceclaw.yaml");
  try {
    const raw = fs.readFileSync(configPath, "utf-8");
    const port = raw.match(/listen_port:\s*(\d+)/)?.[1];
    const host = raw.match(/listen_host:\s*"?([^"\n]+)"?/)?.[1]?.trim();
    const strategy = raw.match(/strategy:\s*(\S+)/)?.[1];
    return {
      router: { listen_host: host || "0.0.0.0", listen_port: port ? parseInt(port) : 8000 },
      inference: { strategy: strategy || "local-first" },
    };
  } catch {
    return { router: { listen_host: "0.0.0.0", listen_port: 8000 }, inference: { strategy: "local-first" } };
  }
}

function getRouterBaseUrl(cfg: CECLAWConfig): string {
  const host = process.env.CECLAW_ROUTER_HOST || cfg.router?.listen_host || "0.0.0.0";
  const port = process.env.CECLAW_ROUTER_PORT || String(cfg.router?.listen_port || 8000);
  const resolvedHost = host === "0.0.0.0" ? "host.openshell.internal" : host;
  return `http://${resolvedHost}:${port}/v1`;
}

export function register(api: any) {
  const cfg = loadCECLAWConfig();
  const baseUrl = getRouterBaseUrl(cfg);
  const strategy = cfg.inference?.strategy || "local-first";

  api.onGatewayStart?.(() => {
    console.log("");
    console.log("  ┌─────────────────────────────────────────────┐");
    console.log("  │  CECLAW registered                          │");
    console.log("  │                                             │");
    console.log(`  │  Router:    ${baseUrl.padEnd(31)}│`);
    console.log(`  │  Strategy:  ${strategy.padEnd(31)}│`);
    console.log("  │  Commands:  openclaw ceclaw <command>       │");
    console.log("  └─────────────────────────────────────────────┘");
    console.log("");
  });

  api.configureProvider?.({ id: "local", baseUrl, apiKey: "ceclaw-local", api: "openai-completions" });

  /* TEMP DISABLED
  api.registerCommand?.("ceclaw", {
    description: "CECLAW management commands",
    subcommands: {
      status: {
        description: "Show CECLAW Router status",
        handler: async () => {
          try {
            const resp = await fetch(baseUrl.replace("/v1", "/ceclaw/status"));
            const data = await resp.json();
            console.log(JSON.stringify(data, null, 2));
          } catch (e) {
            console.error("Cannot reach CECLAW Router:", e);
          }
        },
      },
    },
  });
  */
}
