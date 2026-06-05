// Sequential Reviewer — implement-then-review loop (Codex CLI + Docker)
//
// Default: Docker sandbox with Codex CLI inside the container.
//   npm run sandcastle
// Host mode (no Docker):
//   npm run sandcastle:host
//
// Work branch: stays on your current branch unless SANDCASTLE_BRANCH is set.
// Issues: label open GitHub issues with Sandcastle (or SANDCASTLE_ISSUE_LABEL).

import * as sandcastle from "@ai-hero/sandcastle";
import { docker } from "@ai-hero/sandcastle/sandboxes/docker";
import { noSandbox } from "@ai-hero/sandcastle/sandboxes/no-sandbox";
import { execSync } from "node:child_process";
import { homedir } from "node:os";
import { join } from "node:path";

const MAX_ITERATIONS = 10;
const USE_DOCKER = process.env.SANDCASTLE_USE_DOCKER !== "false";

const CODEX_MODEL = process.env.CODEX_MODEL ?? "gpt-5.4";
const CODEX_REVIEW_MODEL = process.env.CODEX_REVIEW_MODEL ?? CODEX_MODEL;
const IMAGE_NAME = process.env.SANDCASTLE_IMAGE_NAME ?? "sandcastle:agentgate";

function gitCurrentBranch(): string {
  return execSync("git branch --show-current", { encoding: "utf8" }).trim();
}

const explicitBranch = process.env.SANDCASTLE_BRANCH?.trim();
const currentBranch = gitCurrentBranch();
const WORK_BRANCH = explicitBranch || currentBranch;

function codexAgent(model: string) {
  return sandcastle.codex(model);
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

const sandboxProvider = USE_DOCKER
  ? docker({
      imageName: IMAGE_NAME,
      mounts: [
        {
          hostPath: join(homedir(), ".codex"),
          sandboxPath: "/home/agent/.codex",
        },
      ],
    })
  : noSandbox();

// Bind-mount head: commits land on the active branch (no per-iteration worktree).
const branchStrategy = { type: "head" as const };

if (explicitBranch && currentBranch !== explicitBranch) {
  console.log(`Checking out ${explicitBranch} (was ${currentBranch})...\n`);
  execSync(`git checkout ${explicitBranch}`, { stdio: "inherit" });
}

const issueLabel = process.env.SANDCASTLE_ISSUE_LABEL?.trim() || "Sandcastle";

if (USE_DOCKER) {
  console.log(
    `Docker + Codex CLI\n` +
      `  image:     ${IMAGE_NAME}\n` +
      `  branch:    ${WORK_BRANCH} (head — in-place)\n` +
      `  issues:    label "${issueLabel}"\n` +
      `  implement: ${CODEX_MODEL}\n` +
      `  review:    ${CODEX_REVIEW_MODEL}\n`,
  );
} else {
  console.log(
    `Host mode (no Docker): Codex runs on this machine.\n` +
      `  branch:    ${WORK_BRANCH}\n` +
      `  implement: ${CODEX_MODEL}\n` +
      `  review:    ${CODEX_REVIEW_MODEL}\n`,
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
    agent: codexAgent(CODEX_MODEL),
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
    agent: codexAgent(CODEX_REVIEW_MODEL),
    promptFile: "./.sandcastle/review-prompt.md",
    promptArgs: {
      BRANCH: WORK_BRANCH,
    },
  });

  console.log("\nReview complete.");
}

console.log("\nAll done.");
