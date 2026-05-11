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
- **Agent PIDs (Session 8 — May 11, 04:35 UTC)**: provart=71209, newsprove=71210, agentlog=71211, dataprove=71212, socialprove=71213, researchprove=71215, codeprove=71217. watchdog=71282, synctrigger=71283. Crash 8 restart (8th crash total). Session durations: 6h → 27min → 32min → 1h46min → ongoing. Cumulative registrations: ~9,649.
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

---
_Last system refresh: 2026-05-11 04:43 UTC_
