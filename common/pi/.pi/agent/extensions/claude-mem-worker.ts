/**
 * Runs the claude-mem worker only while pi needs it.
 *
 * On session start the worker is started if it is down, so pi-cmem (which
 * probes it once in its own session_start) finds it reachable. When the last pi
 * quits, a detached reaper waits for the worker's summary queue to drain and
 * stops it, but only if a pi started it and no interactive Claude Code session
 * is still using it. A worker Claude Code started is left alone.
 */

import { spawn } from "node:child_process";
import { existsSync, mkdirSync, readdirSync, readFileSync, rmSync, statSync, writeFileSync } from "node:fs";
import { homedir } from "node:os";
import { join } from "node:path";
import type { ExtensionAPI } from "@earendil-works/pi-coding-agent";

const HEALTH_TIMEOUT_MS = 500;
// `worker-service.cjs start` returns once the worker reports ready.
const START_TIMEOUT_MS = 20_000;
// Pending observations persist in claude-mem's database, so giving up on the
// drain only defers their summaries to the next worker start.
const DRAIN_POLL_MS = 2_000;
const DRAIN_MAX_MS = 5 * 60_000;

const CLAUDE_DIR = process.env.CLAUDE_CONFIG_DIR ?? join(homedir(), ".claude");
const PLUGIN_CACHE = join(CLAUDE_DIR, "plugins/cache/thedotmack/claude-mem");
const MARKETPLACE_PLUGIN = join(CLAUDE_DIR, "plugins/marketplaces/thedotmack/plugin");
const CLAUDE_MEM_SETTINGS = join(process.env.CLAUDE_MEM_DATA_DIR ?? join(homedir(), ".claude-mem"), "settings.json");

// Local runtime state, inside ~/.pi/agent but not in the dotfiles repo.
const STATE_DIR = join(homedir(), ".pi/agent/claude-mem-worker");
const CLIENTS_DIR = join(STATE_DIR, "clients");
const STARTED_BY_PI_MARKER = join(STATE_DIR, "started-by-pi");

// Same resolution claude-mem uses: env, then its settings file, then 37700 + uid % 100.
function workerPort(): string {
	if (process.env.CLAUDE_MEM_WORKER_PORT) return process.env.CLAUDE_MEM_WORKER_PORT;
	try {
		const settings = JSON.parse(readFileSync(CLAUDE_MEM_SETTINGS, "utf8"));
		if (settings.CLAUDE_MEM_WORKER_PORT) return String(settings.CLAUDE_MEM_WORKER_PORT);
	} catch {
		// No settings file means claude-mem's defaults apply.
	}
	return String(37700 + ((process.getuid?.() ?? 77) % 100));
}

// Newest installed plugin version first, as Claude Code's own hooks pick it.
function workerScript(): string | undefined {
	const versionDirs = existsSync(PLUGIN_CACHE)
		? readdirSync(PLUGIN_CACHE)
				.map((name) => join(PLUGIN_CACHE, name))
				.sort((a, b) => statSync(b).mtimeMs - statSync(a).mtimeMs)
		: [];
	return [...versionDirs, MARKETPLACE_PLUGIN]
		.map((dir) => join(dir, "scripts/worker-service.cjs"))
		.find((script) => existsSync(script));
}

function bunPath(): string {
	const userBun = join(homedir(), ".bun/bin/bun");
	return existsSync(userBun) ? userBun : "bun";
}

async function isWorkerHealthy(port: string): Promise<boolean> {
	try {
		const res = await fetch(`http://127.0.0.1:${port}/api/health`, {
			signal: AbortSignal.timeout(HEALTH_TIMEOUT_MS),
		});
		return res.ok;
	} catch {
		return false;
	}
}

async function ensureWorker(pi: ExtensionAPI, port: string, script: string): Promise<void> {
	if (await isWorkerHealthy(port)) return;

	const result = await pi.exec(bunPath(), [script, "start"], { timeout: START_TIMEOUT_MS });
	if (result.code !== 0 || !(await isWorkerHealthy(port))) {
		console.error(`claude-mem-worker: failed to start worker on port ${port}: ${result.stderr.trim() || `exit ${result.code}`}`);
		return;
	}
	writeFileSync(STARTED_BY_PI_MARKER, "");
}

function clientFile(): string {
	return join(CLIENTS_DIR, String(process.pid));
}

/**
 * Runs detached from pi so quitting is not delayed by the drain. It re-checks
 * for other users on every poll, because a new pi or Claude Code session may
 * start while it waits.
 */
const REAPER_SOURCE = String.raw`
const { existsSync, readdirSync, readFileSync, rmSync } = require("node:fs");
const { execFileSync } = require("node:child_process");
const [clientsDir, marker, port, bun, script, pollMs, maxMs] = process.argv.slice(1);
const base = "http://127.0.0.1:" + port;

const isAlive = (pid) => { try { process.kill(Number(pid), 0); return true; } catch { return false; } };

function hasLivePiClient() {
  return readdirSync(clientsDir).some((pid) => {
    if (isAlive(pid)) return true;
    rmSync(clientsDir + "/" + pid, { force: true });
    return false;
  });
}

const parentPid = (pid) => Number(readFileSync("/proc/" + pid + "/stat", "utf8").split(") ")[1].split(" ")[1]);

// The worker spawns its own claude processes for summarising; only count ones outside its tree.
function hasInteractiveClaude(workerPid) {
  return readdirSync("/proc").filter((p) => /^\d+$/.test(p)).some((pid) => {
    try {
      if (readFileSync("/proc/" + pid + "/comm", "utf8").trim() !== "claude") return false;
      for (let p = Number(pid); p > 1; p = parentPid(p)) if (p === workerPid) return false;
      return true;
    } catch { return false; }
  });
}

const getJson = async (path) => (await fetch(base + path, { signal: AbortSignal.timeout(2000) })).json();

(async () => {
  const deadline = Date.now() + Number(maxMs);
  for (;;) {
    if (!existsSync(marker) || hasLivePiClient()) return;
    let health;
    try { health = await getJson("/api/health"); } catch { rmSync(marker, { force: true }); return; }
    if (hasInteractiveClaude(health.pid)) return;
    const status = await getJson("/api/processing-status").catch(() => ({}));
    if ((status.queueDepth === 0 && !status.isProcessing) || Date.now() > deadline) break;
    await new Promise((r) => setTimeout(r, Number(pollMs)));
  }
  execFileSync(bun, [script, "stop"], { stdio: "ignore" });
  rmSync(marker, { force: true });
})();
`;

function spawnReaper(port: string, script: string): void {
	const reaper = spawn(
		process.execPath,
		["-e", REAPER_SOURCE, CLIENTS_DIR, STARTED_BY_PI_MARKER, port, bunPath(), script, String(DRAIN_POLL_MS), String(DRAIN_MAX_MS)],
		{ detached: true, stdio: "ignore" },
	);
	reaper.unref();
}

export default function (pi: ExtensionAPI) {
	const port = workerPort();

	pi.on("session_start", async () => {
		const script = workerScript();
		if (!script) {
			console.error("claude-mem-worker: claude-mem plugin not found; memory is unavailable");
			return;
		}
		mkdirSync(CLIENTS_DIR, { recursive: true });
		writeFileSync(clientFile(), "");
		await ensureWorker(pi, port, script);
	});

	// Reload, new, resume and fork are followed by another session_start in this process.
	pi.on("session_shutdown", (event) => {
		if (event.reason !== "quit") return;
		rmSync(clientFile(), { force: true });
		const script = workerScript();
		if (script && existsSync(STARTED_BY_PI_MARKER)) spawnReaper(port, script);
	});
}
