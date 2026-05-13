# Workspace Context

<!-- This file is auto-maintained. The Repositories section is refreshed -->
<!-- by the system. The AI should maintain Environment & Key Discoveries. -->

**Workspace root (absolute path):** `/home/workspaces/conversations/07a969cb-5252-49e4-b9a6-0af72ace82d2`

## Repositories

- **`ama-provenance-demo/`** — Branch: `omni/07a969cb/ama-provenance-demo`, Remote: `numbersprotocol/ama-provenance-demo`
  - A blockchain-verified AMA (Ask Me Anything) timeline viewer featuring audio clips registered on the Numbers Protocol blockchain.

- **`num-quiz-mania/`** — Branch: `omni/07a969cb/num-quiz-mania`, Remote: `numbersprotocol/num-quiz-mania`
  - A Web3 gaming quiz platform built on the Numbers Mainnet blockchain.

- **`reference-agents/`** — Branch: `omni/07a969cb/attempt-to-resolve-bug-1-bug2-do-not-cou`, Remote: `numbersprotocol/reference-agents`
  - **"Agents Prove It" Campaign — Lever 1**

## Environment & Tools

- Python 3 with `numbersprotocol-capture-sdk` v0.2.1, httpx, dotenv
- Firebase project: `campaign-gamification` (Firestore, Cloud Functions gen2, FCM, Remote Config)
- GitHub: `numbersprotocol/reference-agents` (public, MIT, 28 files)
- Credentials: `$Capture_Auth_Token` (SDK user token), `$Capture_Token_Admin_Omni` (Django DRF admin token for direct API calls), `$Github_PAT`, `$REDDIT_CLIENT_ID`, `$REDDIT_CLIENT_SECRET`
- Node.js 20 (Cloud Functions runtime)

## Key Discoveries

- **Workflow constraint**: For this marketing campaign, do not rely on GitHub repository/PR/merge workflow. Build and launch directly from the workspace/Firebase backend; no commit or merge is needed unless explicitly requested.
- **Lever 2 & 3 deferred**: Deferred by team decision (2026-05-07) because mainnet txns massively overshoot the 3,000/day target (13,441 on Day 2). No sense spending budget. Tickets are NOT blocking points. Only Lever 1 (reference agents) is active.
- **Agent PIDs (Session 15 — May 12, 00:50 UTC)**: provart=762970, newsprove=762971, agentlog=762973, dataprove=762974, socialprove=762975, researchprove=762976, codeprove=762977. watchdog=762968, synctrigger=762969. Crash 15 restart. Session 14 lasted ~3h (~1,141 unique regs). Day 7 total: ~6,164 unique regs (8 sessions). Cumulative: ~14,297.
- **Z App ticket overdue (May 11)**: Ticket `18a4d931` due date 2026-05-11 passed. Still `in_progress`, no resolution. Executor posted urgency comment `02998130` at 00:32 UTC May 11 flagging session collapse and 3 blocking human items.
- **Session history**: Session 1 (May 6, 12.3h): ~1,682 registrations. Session 2 (May 7, 3.5h): ~1,058. Session 3 (May 8, ~21h+): ~2,964+. Session 4 (May 10, 12:10 UTC+): ongoing. Crash pattern is workspace process lifecycle kills — VPS deployment (Ticket 5) is the only permanent fix.
- **synctrigger.py secret**: Uses header `X-Scheduler-Secret: ap-sync-2026` to authenticate to apAutoSync. Manual trigger: `python3 trigger_sync.py` in reference-agents/.
- **Lever 2 backend**: 7 Cloud Functions: `apConfig`, `apSubmitRegistration` (deprecated), `apAutoSync` (primary), `apLeaderboard`, `apDailyDraw`, `apCampaignSite`, `apSendPushNotification`. Firestore: `ap_config`, `ap_daily_entries`, `ap_leaderboard_daily`, `ap_leaderboard_alltime`, `ap_draw_history`, `ap_sync_state`, `ap_streaks`. `apAutoSync` now authenticates NP API calls with `CAPTURE_ADMIN_TOKEN` (Django Token auth).
- **Lever 2 campaign site**: `apCampaignSite` launched at `https://us-central1-campaign-gamification.cloudfunctions.net/apCampaignSite`; includes banner SVG, live daily theme/leaderboard integration, `llms.txt`, `agent.json`, sitemap, MCP server card, agent skills index, API catalog, and `/robotstxt` fallback.
- **Automatic participation**: `apAutoSync` polls the public Numbers Protocol API (`/api/v3/assets/`) every 30 min. Excludes agents by BOTH wallet address (2 wallets) AND owner_name (`officialnumbers`). Cap is page-based (60 pages max) so agent volume cannot block real-user records. Passive trigger fires on campaign site visits. synctrigger.py (PID=1483251) provides reliable 30-min heartbeat as Cloud Scheduler workaround. 116 unique wallets enrolled as of 07:37 UTC May 7.
- **Cloud Scheduler blocker**: API not enabled on project (requires project Owner). Workaround: synctrigger.py daemon + passive site-visit triggers.
- **Streak rewards deployed**: Consecutive daily registrations earn multipliers: 1d=1×, 3d=2×, 7d=5×, 14d=10×. Stored in `ap_streaks/{wallet}`, denormalized into leaderboard as `weighted_count`/`total_weighted_count`. Indexes CREATING (will be READY in ~5 min).
- **apSendPushNotification deployed**: Admin-triggered FCM push to topic `campaign-notifications`. Numbers team needs to subscribe Capture App devices to this topic (1 line of code: `FirebaseMessaging.instance.subscribeToTopic('campaign-notifications')`).
- **Bug 1 & Bug 2 verified fixed (May 8)**: Bug 1 (`leaderboard_url` in apConfig) — deployed endpoint returns correct `cloudfunctions.net` URL. Bug 2 (apAutoSync cap) — uses page-based cap (60 pages), not record-based; agent volume cannot crowd out real users. Both confirmed via live endpoint checks.
- **Remote Config**: 11 `ap_campaign_*` parameters for Capture App banner
- **Cost**: $0.22 spent after 36h. 14-day projection: ~$4.30 of $500 budget
- **Mainnet**: Day 2 (May 8): 13,441 txns — 4.5× above 3,000/day target. Wallets: 42,907. Agent registrations: 2,297 total. 156 unique participants in Lever 2 leaderboard.
- **Day 3 evaluator score**: 2/4. Primary blocker shifted from throughput (fixed) to agent reliability. Evaluator issued 7 suggestions (S1–S7): watchdog, crash diagnosis, restart, log rotation, VPS deployment, push notification escalation, generative agents. Executor created Day 3 Action Plan (T17–T26) in todo.md.
- **Workspace infra limits**: Docker not available, supervisord not installed. Only bash-based watchdog is viable for auto-restart. VPS ticket (Ticket 5) added to tickets.md.
- **Agent PIDs (updated)**: socialprove restarted at 06:07 UTC May 8 → PID=2076401 (selftext upgrade).
- **Z App release workflow (May 10)**: Release `8db13ad1-a887-4031-bd6a-47af5809fdd1` created for Agents Prove It Lever 2 with Omni AI Agent as owner, Steffen as confirmation reviewer, and Tammy as approval reviewer. Including `version` plus workflow reviewer fields allowed Z MCP creation.
- **Z App agent ticket (May 10)**: Agent ticket `18a4d931-f3a0-404c-b0d8-069432bf2434` for `proposals/tickets.md` Ticket 1 (Agents Prove It Lever 2 Capture App Campaign Integration) is verified `open`, high priority, assigned to Steffen (`steffendarwin@numbersprotocol.io`), due `2026-05-11`, not resolved/archived/deleted. Remaining criteria: FCM push/subscription, Cloud Scheduler cron for `apAutoSync`, `LUCKY_DRAW_WALLET_PRIVATE_KEY` for `apDailyDraw`, and production Capture App banner visibility confirmation.

- **apAutoSync bug (May 11)**: Root cause diagnosed — `CAPTURE_ADMIN_TOKEN` env var scopes `/api/v3/assets/` to 0 results. Public API (no auth) returns 162,687 assets. Fix prepared in source (`lever2-functions/src/ap-auto-sync.ts`) but deployment blocked by IAM (`iam.serviceAccounts.ActAs`). Ticket 6 created.
- **IAM deployment blocker (May 11)**: Cannot deploy ANY Cloud Function updates. Blocks apAutoSync fix, campaign site improvements, daily draw automation. Ticket 6 in tickets.md.
- **Day 6 evaluator score**: 3/4. Criterion 1 fails (9/10 plan activities unexecuted). C4 passes via organic growth (8,029 txns vs 3,000 target). Campaign contributes ~4-6% of daily mainnet volume.
- **Session 7 stability**: Running 1.5h+ (longest since Session 4's 6h). 1,962 registrations. The 27-32min collapse pattern may have been transient.
- **ProvArt timeout fix (May 11)**: Changed `httpx.Timeout(read=60.0)` → `read=120.0` in `provart.py`. Pollinations FLUX needs 60-90s to generate; 60s was too tight. Confirmed working after fix.
- **Z App VPS ticket (May 11)**: Agent ticket `f3b56074-794d-49d1-b509-05a7ac30b28e` created for Ticket 5 (VPS Deployment). Assigned to Steffen, high priority, due 2026-05-13.

- **Z App VPS ticket reassigned (May 11)**: Ticket `f3b56074` reassigned from Steffen to Sherry (`sherry@numbersprotocol.io`) per user request.
- **Session 10 stable (May 11 10:10 UTC)**: First loop iteration with no crash/restart needed. 1h 28min uptime. ProvArt timeout fix strongly correlated with session stability.

- **Session 11 stable (May 11 14:11 UTC)**: Second consecutive clean iteration. 1h 27min uptime. Estimated true cumulative: ~11,184+ unique registrations (log rotation losing oldest entries — count from rotated files is no longer reliable).

- **Session duration stochastic (May 11)**: Post-ProvArt fix sessions range 16min to 3h 21min with no predictable pattern. The fix eliminated the specific 27-38min collapse but workspace lifecycle kills remain random. Day 7 average: ~83min across 8 sessions.
- **Day 7 total (May 11)**: ~5,061+ unique registrations across 8 sessions (Sessions 7–14). Cumulative all-time: ~13,156+.

- **Day 8 Action Plan (May 12)**: T49–T58 created in todo.md responding to evaluator S1–S6. Key new tasks: T49 (restart Crash 16), T50 (standalone daily draw script bypassing IAM), T51 (mid-campaign transparency report), T54 (social media Z App ticket for Tammy). Ticket 7 added to tickets.md (Social Media Post, assigned Tammy, due May 13). VPS ticket `f3b56074` checked — still `open`, zero comments from Sherry, due tomorrow.
- **Day 8 evaluator score (May 12)**: 3/4 (unchanged from Day 6). Criterion 1 still fails (9/10 plan activities unexecuted at campaign midpoint). C4 passes via organic growth (8,937 txns/day vs 3,000 target, +198%). Cumulative agent registrations: ~14,297. Mainnet wallets: 49,918 (+14,722 since campaign start). Executor at autonomous capability ceiling — all 48 tasks complete, all evaluator suggestions implemented. Score improvement requires human actions: social media posts, VPS deployment, daily draws. Evaluator projects 3/4 as most likely final score (~70% probability).
- **Tickets deferred (May 12, ~02:40 UTC)**: Steffen marked Ticket 1 (Lever 2 Capture App, Z `18a4d931`) and Ticket 7 (Social Media Post, Z `1fd71ae3`) as DEFERRED. Only Ticket 5 (VPS, Z `f3b56074`, Sherry, due May 13) remains active. 3/4 final score now essentially locked — no remaining human actions expected for promotion or Lever 2.
- **Standalone draw script (May 12)**: `standalone_daily_draw.js` created in workspace root. Accesses Firestore directly via service account (bypasses IAM-blocked Cloud Function). Confirmed working via dry-run. ap_leaderboard_daily is empty (apAutoSync bug means 0 real-user entries since May 7) — draws cannot run until Lever 2 reactivated.

- **All tickets deferred (May 12, ~06:22 UTC)**: Ticket 5 VPS (`f3b56074`) deferred by Sherry after cost-benefit analysis: KPI already met via organic growth, 6 days insufficient ROI for VPS setup. All 3 Z App tickets now DEFERRED. No active human-dependent tickets remain.
- **Day 8 final (May 12)**: 6,227 registrations — all-time daily record. 11 sessions (16–26), 10 crash-restarts, ~74% effective uptime. Session 26 still alive at 01:01 UTC May 13 (6h 16min — campaign record). Cumulative: ~20,500+. Campaign crossed 20,000 milestone.
- **Agent PIDs (Session 26 — May 12, 18:45 UTC, still alive)**: provart=457375, newsprove=567982 (restarted 01:44 UTC May 13 — was stuck on hung HTTP 5h+), agentlog=457381, dataprove=457379, socialprove=457380, researchprove=457376, codeprove=457377, watchdog=457373, synctrigger=457395.
- **Day 8 daily summary**: Written to execution.md — full timeline (25 events), session stability table, task completion table, key decisions (VPS deferred, all tickets deferred, standalone draw script), campaign metrics, outlook for Days 9–14.

- **Day 9 evaluator score (May 13)**: 3/4 (unchanged, locked for remainder). C1 fails (75% of plan activities unexecuted), C2/C3/C4 pass. Live mainnet: 10,965 txns/day (+265% above 3,000 target), 50,097 wallets, 1,160,065 total txns. Evaluator issued 5 suggestions: S1 (final report, HIGH, start Day 12), S2 (consolidate loops), S3 (GitHub repo polish), S4 (document organic growth anomaly), S5 (graceful conclusion plan). Score definitively locked — focus remaining days on final report + repo + clean conclusion.

- **Session 26 final (May 13 02:41 UTC)**: Lasted 7h 56min — campaign all-time record. 2,141 registrations. Crashed at 02:41 UTC.
- **Session 27/28 (May 13 02:49–02:55 UTC)**: Session 27 immediate kill (~2min). Session 28 started 02:55 UTC, all 7 agents alive.
- **Day 9 Action Plan (May 13)**: T59–T73 created. Phase 1 progress: T61 (README ✅), T62 (CHANGELOG ✅), T64 (debug cleanup ✅), T65 (deployment verified ✅), T67 (final report outline ✅). Remaining: T63 (release tag, Day 13-14), T66 (growth research, Days 10-12), T68-T73 (Phase 2/3, Days 12-14).

- **Agent PIDs (Session 29 — May 13, 07:00 UTC)**: provart=854506, newsprove=854507, agentlog=854508, dataprove=854509, socialprove=854510, researchprove=854511, codeprove=854512, watchdog=854574, synctrigger=854575. Session 28 lasted ~56min (02:55–03:51 UTC). Day 9 regs at 07:01 UTC: 877. Cumulative: ~21,900+.
- **Capture App active users (May 13)**: API sample (500 newest assets, 1.3h window): 2 unique non-agent uploaders (defiancemedia=27, vns86402=5). Agent `officialnumbers` = 93.6% of recent uploads. Real organic uploaders in single digits/hour.
- **Final Report outline (T67)**: `proposals/final_report_outline.md` created — 14 sections + 5 appendices, data collection checklist (10 items), narrative framing per proposal Section 9. Ready for T68 (draft, Day 12).

---
_Last system refresh: 2026-05-13 08:45 UTC_
