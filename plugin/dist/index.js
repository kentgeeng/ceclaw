"use strict";
var __createBinding = (this && this.__createBinding) || (Object.create ? (function(o, m, k, k2) {
    if (k2 === undefined) k2 = k;
    var desc = Object.getOwnPropertyDescriptor(m, k);
    if (!desc || ("get" in desc ? !m.__esModule : desc.writable || desc.configurable)) {
      desc = { enumerable: true, get: function() { return m[k]; } };
    }
    Object.defineProperty(o, k2, desc);
}) : (function(o, m, k, k2) {
    if (k2 === undefined) k2 = k;
    o[k2] = m[k];
}));
var __setModuleDefault = (this && this.__setModuleDefault) || (Object.create ? (function(o, v) {
    Object.defineProperty(o, "default", { enumerable: true, value: v });
}) : function(o, v) {
    o["default"] = v;
});
var __importStar = (this && this.__importStar) || (function () {
    var ownKeys = function(o) {
        ownKeys = Object.getOwnPropertyNames || function (o) {
            var ar = [];
            for (var k in o) if (Object.prototype.hasOwnProperty.call(o, k)) ar[ar.length] = k;
            return ar;
        };
        return ownKeys(o);
    };
    return function (mod) {
        if (mod && mod.__esModule) return mod;
        var result = {};
        if (mod != null) for (var k = ownKeys(mod), i = 0; i < k.length; i++) if (k[i] !== "default") __createBinding(result, mod, k[i]);
        __setModuleDefault(result, mod);
        return result;
    };
})();
Object.defineProperty(exports, "__esModule", { value: true });
exports.register = register;
const fs = __importStar(require("fs"));
const path = __importStar(require("path"));
const os = __importStar(require("os"));
function loadCECLAWConfig() {
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
    }
    catch {
        return { router: { listen_host: "0.0.0.0", listen_port: 8000 }, inference: { strategy: "local-first" } };
    }
}
function getRouterBaseUrl(cfg) {
    const host = process.env.CECLAW_ROUTER_HOST || cfg.router?.listen_host || "0.0.0.0";
    const port = process.env.CECLAW_ROUTER_PORT || String(cfg.router?.listen_port || 8000);
    const resolvedHost = host === "0.0.0.0" ? "host.openshell.internal" : host;
    return `http://${resolvedHost}:${port}/v1`;
}
function register(api) {
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
