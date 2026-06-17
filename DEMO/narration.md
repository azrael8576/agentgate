# AgentGate Demo Narration（中英雙語）

**Recording flow:** Slides **1–7** → **5 fixed report shots** → Slides **16–17**.

Slides 8–15 stay in the deck as reference art. **Do not show them while recording.**

Keep spoken lines short. Let the big type on each slide do the explaining.

**Recording style / 錄影原則:**

```text
Keynote, not README — short lines, pauses, let slide type carry the message.
Act 2 = evidence cards, not report tour — one proof per shot, overlay required.
Cut to browser: first frame = report hero, no mouse wandering.
```

```text
旁白像 keynote，不要像念 README — 短句、停頓、讓投影片大字承擔訊息。
Act 2 = 證據卡，不是報表導覽 — 每 shot 只證明一件事，overlay 一定要有。
切瀏覽器：第一格直接停 report hero，滑鼠不要亂動。
```

**Story spine / 故事主線:**

```text
2024: chatbot wrong answer → business consequence
2026: agents take actions → release risk
Agent releases need gates → AgentGate = release authority
Phoenix gives evidence. AgentGate enforces release policy.
Gemini suggests future regression tests.
The report proves it: DENY → EXECUTED, v2 BLOCKED, controls generated, v2.1 verified.
```

```text
2024：聊天機器人答錯 → 真實商業後果
2026：agent 能採取行動 → 上線風險
Agent 上線也需要 gate → AgentGate = release authority（上線裁決層）
Phoenix 提供證據。AgentGate 執行 release policy。
Gemini 建議未來的回歸測試。
Report 證明：DENY → EXECUTED、v2 BLOCKED、controls 生成、v2.1 驗證通過。
```

---

## Act 1 — Product architecture (Slides 1–7)

### Slide 1 — Opening（純 hook，不放品牌）

| EN | ZH（繁中） |
| --- | --- |
| In 2024, a chatbot's wrong refund guidance became a real business consequence. | 二〇二四年，一款聊天機器人給了錯誤的退款指引，造成了真實的商業後果。 |
| That was just a wrong answer. | 那還只是一次錯誤回答。 |
| The next risk is worse: | 下一個風險更大： |
| agents taking the wrong action. | agent 會採取錯誤的行動。 |

**錄音備註：** Air Canada 是 **chatbot 錯誤回答**（Devpost 可寫清楚，影片不必防禦性解釋）。約 5–8 秒，節奏 punchy。不放 AgentGate logo — 留給 Slide 4。不講 tools / workflows — 留給 Slide 2。

---

### Slide 2 — From chat to action（能力升級）

| EN | ZH（繁中） |
| --- | --- |
| Now agents are moving from answers to actions. | 現在，agent 正從「回答問題」走向「採取行動」。 |
| They call tools, trigger workflows, and touch internal systems. | 它們會呼叫工具、觸發工作流程、直接碰觸內部系統。 |
| Once an agent can act, wrong behavior becomes a release risk. | 一旦 agent 能夠行動，錯誤行為就變成了上線風險。 |

**錄音備註：** 承接 Slide 1 橋接：chatbot wrong answer → agent wrong action。第一句是整個 hook 的橋，第一秒加重語氣。讓四張卡片 carry the visual。

---

### Slide 3 — Release gap

| EN | ZH（繁中） |
| --- | --- |
| Software already has CI/CD gates. | 傳統軟體早就有了 CI/CD 放行關卡。 |
| But an agent version can change through its prompt, model, tools, and permissions. | 但 agent 版本可能因 prompt、模型、工具與權限改動而改變行為。 |
| That gap needs a release authority. | 這個缺口，需要一個上線裁決層。 |

**錄音備註：** 第二句念出 prompts / models / tools / permissions，與 GateRail 畫面對齊。

---

### Slide 4 — Product reveal（AgentGate 正式登場）

| EN | ZH（繁中） |
| --- | --- |
| That is where AgentGate sits. | AgentGate 就站在這個位置。 |
| Before production, it asks one question: | 在上線之前，它只問一個問題： |
| can this candidate ship from evidence? | 這個候選版本，能不能用證據放行？ |

---

### Slide 5 — Release check

| EN | ZH（繁中） |
| --- | --- |
| Submit a candidate. | 提交候選版本。 |
| Run a release check. | 執行 release check。 |
| Get an approve-or-block decision. | 取得放行或阻擋的決定。 |
| Then keep the audit trail for future regression coverage. | 並保留稽核軌跡。 |
| | 供未來的回歸驗證使用。 |

**錄音備註：** 五句分開念，搭 pipeline 動畫；最後兩句可略放慢。

---

### Slide 6 — Evidence stack

| EN | ZH（繁中） |
| --- | --- |
| Phoenix records what happened. | Phoenix 記錄發生了什麼。 |
| AgentGate decides whether it can ship. | AgentGate 決定能不能上線。 |
| Gemini explains dangerous sessions | Gemini 解釋危險 session |
| and suggests candidates for future regression tests. | 並建議哪些案例可以成為未來的回歸測試。 |
| Advisory only. | 僅供參考。 |

**錄音備註：** 螢幕底部已有「LLMs explain. Policies decide.」— 旁白不重複念出。最後「Advisory only」獨立一句，對齊 Gemini 分工。

---

### Slide 7 — Advisory agents

| EN | ZH（繁中） |
| --- | --- |
| Two review agents help humans | 兩個 review agent 協助人類 |
| investigate dangerous traces and curate release controls. | 追查危險 trace、彙整 release 控制項。 |
| They are advisory only. | 它們僅供參考。 |
| Humans approve. | 由人把關。 |
| The gate still decides. | 放行仍由 gate 定奪。 |
| Let's look at a real release report for v2. | 接著看 v2 的真實 release report。 |

**錄音備註：** 動詞對齊畫面 headline（追查 / 把關 / 定奪）。念出「由人把關」— 信任邊界：Gemini / review agents 不是 release judge。停頓 0.5–1 秒，再切到瀏覽器。讓切換成為刻意的場景轉換，不是技術失誤。

**→ Cut to product. Leave the slide deck.**

---

## Act 2 — Live demo (fixed proof shots)

Switch to the AgentGate release report. **Do not free-scroll.** Hit each shot, say one line, move on.

**Act 2 不是帶人逛 report，是用 report 做證據展示。** 每張畫面只證明一件事；overlay 一定要有。第一格直接停在 report hero，不要滑鼠亂動。

If the report is dense, use a small overlay card so the audience sees what you are proving.

**Recommended overlay labels:**

| Shot | Overlay EN | Overlay ZH |
| --- | --- | --- |
| 1 | Release decision | 上線決定 |
| 2 | Deterministic, not LLM | 確定性，非 LLM 投票 |
| 3 | DENY → EXECUTED | DENY → EXECUTED |
| 4 | Failure → future requirements | 失敗 → 未來要求 |
| 5 | Verified against v2 controls | 對照 v2 控制項驗證 |

### v2 BLOCKED — Shots 1–4

Set `AGENTGATE_LATEST_ARTIFACT_DIR=artifacts/release/reference-v2`.

| Shot | Frame | EN | ZH（繁中） |
| --- | --- | --- | --- |
| **1 — Hero** | Report hero, verdict only | This is a real release check for candidate v2. | 這是候選版本 v2 的真實 release check。 |
| | | v2 is blocked. | v2 被阻擋。 |
| | | This is the release decision. | 這就是上線決定。 |
| **2 — Why blocked** | Blocker metrics highlighted | The decision is deterministic: | 決定是確定性的： |
| | | policy plus blocker metrics, | policy 加上 blocker 指標， |
| | | not an LLM opinion. | 不是 LLM 的意見。 |
| **3 — Dangerous evidence** | DENY → EXECUTED trace | The key trace: | 關鍵 trace： |
| | | policy denied the action, | policy 已 DENY 這個動作， |
| | | but the critical tool still ran. | 但高風險工具仍然 EXECUTED。 |
| **4 — Release controls** | Generated controls section | The failure becomes future release requirements, | 這次失敗會變成未來的 release 要求， |
| | | not just debug notes. | 不只是 debug 筆記。 |

**Shot 1 錄音備註：** 不要念「artifact directory」— 工程細節放 repo，旁白用產品語言。

**Shot 2 錄音備註：** 整支影片最重要的信任句之一。不要再加字、不要補 Gemini。Overlay 只要「Deterministic, not LLM」。

**Shot 3 錄音備註：** Demo 爆點。`DENY → EXECUTED` 畫面至少停 1 秒，不要一閃而過。念「policy denied the action —」後略停。

### v2.1 APPROVED — Shot 5 (required, ~8–10 s)

Switch to `AGENTGATE_LATEST_ARTIFACT_DIR=artifacts/release/reference-v21`.

| Shot | Frame | EN | ZH（繁中） |
| --- | --- | --- | --- |
| **5 — Future verification** | Inherited controls panel | v2.1 is verified against the controls from v2. | v2.1 對照 v2 產生的控制項完成驗證。 |
| | | Four inherited controls loaded. | 載入四項繼承控制項。 |
| | | Four passed. | 四項全數通過。 |
| | | Zero blocking failures. | 零 blocking 失敗。 |
| | | Warnings remain. | 警告仍保留。 |
| | | *(pause 0.5s)* | *（停頓 0.5 秒）* |
| | | Approved, not perfect. | 通過，但不完美。 |

**錄音備註：** Shot 5 整段放慢。畫面必須真的看到 yellow warning / warnings remain，否則「Approved, not perfect」只是口號。「Warnings remain」與「Approved, not perfect」之間停 0.5 秒 — 整支 Demo 最誠實的一刻。

Without Shot 5, the improvement loop stops at generated controls — no proof the loop closes.

**→ Return to slide deck on slide 16.**

---

## Act 3 — Close (Slides 16–17)

### Slide 16 — System loop

| EN | ZH（繁中） |
| --- | --- |
| Phoenix provides evidence. | Phoenix 提供證據。 |
| AgentGate enforces release policy. | AgentGate 執行 release policy。 |
| Gemini suggests future regression tests. | Gemini 建議未來的回歸測試。 |
| That is the loop. | 這就是閉環。 |

### Slide 17 — Closing

| EN | ZH（繁中） |
| --- | --- |
| Ship with evidence, not vibes. | 用證據上線，不靠感覺。 |
| Blocked failures become future release requirements. | 被阻擋的失敗，會變成未來的 release 要求。 |

---

## 完整旁白稿（依錄影順序，可直接給配音）

> **最終錄音版** — 評審自然化修正已套用。短句 + 空行 = 停頓點。

### English — full read-through

```
[Slide 1]
In 2024, a chatbot's wrong refund guidance became a real business consequence.

That was just a wrong answer.

The next risk is worse:
agents taking the wrong action.

[Slide 2]
Now agents are moving from answers to actions.

They call tools, trigger workflows, and touch internal systems.

Once an agent can act, wrong behavior becomes a release risk.

[Slide 3]
Software already has CI/CD gates.

But an agent version can change through its prompt, model, tools, and permissions.

That gap needs a release authority.

[Slide 4]
That is where AgentGate sits.

Before production, it asks one question:

can this candidate ship from evidence?

[Slide 5]
Submit a candidate.

Run a release check.

Get an approve-or-block decision.

Then keep the audit trail for future regression coverage.

[Slide 6]
Phoenix records what happened.

AgentGate decides whether it can ship.

Gemini explains dangerous sessions
and suggests candidates for future regression tests.

Advisory only.

[Slide 7]
Two review agents help humans investigate dangerous traces
and curate release controls.

They are advisory only.

Humans approve.

The gate still decides.

Let's look at a real release report for v2.

(pause 0.5–1s → cut to browser; first frame = report hero)

[Shot 1]
This is a real release check for candidate v2.

v2 is blocked.

This is the release decision.

[Shot 2]
The decision is deterministic:

policy plus blocker metrics,

not an LLM opinion.

[Shot 3]
The key trace:

policy denied the action,

but the critical tool still ran.

(hold DENY → EXECUTED on screen ≥1s)

[Shot 4]
The failure becomes future release requirements,

not just debug notes.

[Shot 5 — slow]
v2.1 is verified against the controls from v2.

Four inherited controls loaded.

Four passed.

Zero blocking failures.

Warnings remain.

(pause 0.5s — show yellow warnings on screen)

Approved, not perfect.

[Slide 16]
Phoenix provides evidence.

AgentGate enforces release policy.

Gemini suggests future regression tests.

That is the loop.

[Slide 17]
Ship with evidence, not vibes.

Blocked failures become future release requirements.
```

### 繁體中文 — 完整朗讀稿

```
【Slide 1】
二〇二四年，一款聊天機器人給了錯誤的退款指引，造成了真實的商業後果。

那還只是一次錯誤回答。

下一個風險更大：
agent 會採取錯誤的行動。

【Slide 2】
現在，agent 正從「回答問題」走向「採取行動」。

它們會呼叫工具、觸發工作流程、直接碰觸內部系統。

一旦 agent 能夠行動，錯誤行為就變成了上線風險。

【Slide 3】
傳統軟體早就有了 CI/CD 放行關卡。

但 agent 版本可能因 prompt、模型、工具與權限改動而改變行為。

這個缺口，需要一個上線裁決層。

【Slide 4】
AgentGate 就站在這個位置。

在上線之前，它只問一個問題：

這個候選版本，能不能用證據放行？

【Slide 5】
提交候選版本。

執行 release check。

取得放行或阻擋的決定。

並保留稽核軌跡。

供未來的回歸驗證使用。

【Slide 6】
Phoenix 記錄發生了什麼。

AgentGate 決定能不能上線。

Gemini 解釋危險 session，
並建議哪些案例可以成為未來的回歸測試。

僅供參考。

【Slide 7】
兩個 review agent 協助人類
追查危險 trace、彙整 release 控制項。

它們僅供參考。

由人把關。

放行仍由 gate 定奪。

接著看 v2 的真實 release report。

（停頓 0.5–1 秒 → 切到瀏覽器；第一格直接停 report hero）

【Shot 1】
這是候選版本 v2 的真實 release check。

v2 被阻擋。

這就是上線決定。

【Shot 2】
決定是確定性的：

policy 加上 blocker 指標，

不是 LLM 的意見。

【Shot 3】
關鍵 trace：

policy 已 DENY 這個動作，

但高風險工具仍然 EXECUTED。

（畫面 DENY → EXECUTED 至少停 1 秒）

【Shot 4】
這次失敗會變成未來的 release 要求，

不只是 debug 筆記。

【Shot 5 — 放慢】
v2.1 對照 v2 產生的控制項完成驗證。

載入四項繼承控制項。

四項全數通過。

零 blocking 失敗。

警告仍保留。

（停頓 0.5 秒 — 畫面需可見 yellow warning）

通過，但不完美。

【Slide 16】
Phoenix 提供證據。

AgentGate 執行 release policy。

Gemini 建議未來的回歸測試。

這就是閉環。

【Slide 17】
用證據上線，不靠感覺。

被阻擋的失敗，會變成未來的 release 要求。
```

---

## 評審要記住的線（Takeaway spine）

```text
Wrong answer was only the beginning.
Agents now take actions.
AgentGate decides whether an agent version can ship.
Phoenix provides evidence.
Policies decide.
Gemini suggests future regression tests.
Blocked failures become future release requirements.
```

```text
錯誤回答只是開始。
Agent 現在能採取行動。
AgentGate 決定 agent 版本能不能上線。
Phoenix 提供證據。
Policy 裁決。
Gemini 建議未來的回歸測試。
被阻擋的失敗，會變成未來的 release 要求。
```

---

## 中文配音用語備註

| 英文原文 | 中文建議 | 說明 |
| --- | --- | --- |
| release authority | 上線裁決層 | Slide 3 概念句；口語可簡化為「上線把關」 |
| ship / no-ship | 放行 / 阻擋 | 與螢幕 APPROVE/BLOCK 對齊 |
| release check | release check | 產品術語，可保留英文或念「上線檢查」 |
| advisory only | 僅供參考 | 強調 LLM 不裁決 |
| Humans approve | 由人把關 | Slide 7 信任邊界；對齊畫面 headline |
| The gate still decides | 放行仍由 gate 定奪 | 與「由人把關」呼應 |
| deterministic | 確定性的 | 強調非 LLM 投票 |
| blocker metrics | blocker 指標 | 與 report UI 一致 |
| inherited controls | 繼承控制項 | Shot 5 核心 |
| Approved, not perfect | 通過，但不完美 | 整支 Demo 最誠實的一句，需留停頓 |
| Ship with evidence, not vibes | 用證據上線，不靠感覺 | 收束 tagline；「vibes」不直譯為「氛圍」 |
| regression coverage / candidates | 回歸驗證 / 回歸測試 | 中文旁白用口語詞，避免直譯「regression 覆蓋」 |
| future regression tests | 未來的回歸測試 | Slide 6 / 16 Gemini 分工句 |

**螢幕仍是英文時：** 中文旁白不必逐字對應 slide 大標，以「補充語意、不重复螢幕已寫清楚的字」為原則。
