// Sequential Reviewer — implement-then-review loop (Cursor CLI)
//
// Default: host mode (no Docker). Company laptops often block Docker.
//   npm run sandcastle
// Opt-in Docker only when available:
//   SANDCASTLE_USE_DOCKER=true npm run sandcastle
//
// Work branch: stays on your current branch unless SANDCASTLE_BRANCH is set.
// Issues: label open GitHub issues with Sandcastle (or SANDCASTLE_ISSUE_LABEL).

import * as sandcastle from "@ai-hero/sandcastle";
import { docker } from "@ai-hero/sandcastle/sandboxes/docker";
import { noSandbox } from "@ai-hero/sandcastle/sandboxes/no-sandbox";
import { execSync } from "node:child_process";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const MAX_ITERATIONS = 10;
const USE_DOCKER = process.env.SANDCASTLE_USE_DOCKER === "true";

const CURSOR_MODEL = process.env.CURSOR_MODEL ?? "auto";
const CURSOR_REVIEW_MODEL = process.env.CURSOR_REVIEW_MODEL ?? CURSOR_MODEL;

const sandcastleDir = dirname(fileURLToPath(import.meta.url));
const agentWrapperDir = join(sandcastleDir, "bin");

function gitCurrentBranch(): string {
  return execSync("git branch --show-current", { encoding: "utf8" }).trim();
}

const explicitBranch = process.env.SANDCASTLE_BRANCH?.trim();
const currentBranch = gitCurrentBranch();
const WORK_BRANCH = explicitBranch || currentBranch;

const CURSOR_ENV = {
  PATH: `${agentWrapperDir}:/opt/homebrew/bin:/usr/local/bin:${process.env.PATH ?? ""}`,
};

function cursorAgent(model: string) {
  return sandcastle.cursor(model, { env: CURSOR_ENV });
}

const hooks = {
  sandbox: {
    onSandboxReady: [
      {
        command: "uv sync --frozen 2>/dev/null || uv sync",
        timeoutMs: 300_000,
      },
    ],
  },
};

const sandboxProvider = USE_DOCKER ? docker() : noSandbox();

// Host mode: accumulate commits on the active branch (no per-iteration worktree).
const branchStrategy = { type: "head" as const };

if (explicitBranch && currentBranch !== explicitBranch) {
  console.log(`Checking out ${explicitBranch} (was ${currentBranch})...\n`);
  execSync(`git checkout ${explicitBranch}`, { stdio: "inherit" });
}

const issueLabel = process.env.SANDCASTLE_ISSUE_LABEL?.trim() || "Sandcastle";

if (USE_DOCKER) {
  console.log("SANDCASTLE_USE_DOCKER=true — using Docker sandbox.\n");
} else {
  console.log(
    `Host mode (no Docker): Cursor Agent runs on this machine.\n` +
      `  branch:    ${WORK_BRANCH} (head — in-place, no worktree)\n` +
      `  issues:    label "${issueLabel}"\n` +
      `  implement: ${CURSOR_MODEL}\n` +
      `  review:    ${CURSOR_REVIEW_MODEL}\n`,
  );
}

const runBase = {
  sandbox: sandboxProvider,
  branchStrategy,
  hooks,
} as const;

for (let iteration = 1; iteration <= MAX_ITERATIONS; iteration++) {
  console.log(`\n=== Iteration ${iteration}/${MAX_ITERATIONS} ===\n`);

  const implement = await sandcastle.run({
    ...runBase,
    name: "implementer",
    maxIterations: 1,
    agent: cursorAgent(CURSOR_MODEL),
    promptFile: "./.sandcastle/implement-prompt.md",
    promptArgs: {
      ISSUE_LABEL: issueLabel,
    },
  });

  if (!implement.commits.length) {
    console.log("Implementation agent made no commits. Stopping.");
    break;
  }

  console.log(`\nImplementation complete on branch: ${WORK_BRANCH}`);
  console.log(`Commits: ${implement.commits.length}`);

  if (process.env.SKIP_SANDCASTLE_REVIEW === "true") {
    console.log("SKIP_SANDCASTLE_REVIEW=true — skipping reviewer.\n");
    continue;
  }

  await sandcastle.run({
    ...runBase,
    name: "reviewer",
    maxIterations: 1,
    agent: cursorAgent(CURSOR_REVIEW_MODEL),
    promptFile: "./.sandcastle/review-prompt.md",
    promptArgs: {
      BRANCH: WORK_BRANCH,
    },
  });

  console.log("\nReview complete.");
}

console.log("\nAll done.");
