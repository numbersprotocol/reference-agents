# Workspace Context

<!-- This file is auto-maintained. The Repositories section is refreshed -->
<!-- by the system. The AI should maintain Environment & Key Discoveries. -->

**Workspace root (absolute path):** `/home/workspaces/conversations/07a969cb-5252-49e4-b9a6-0af72ace82d2`

## Repositories

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
- **Lever 2 & 3 deferred**: Tickets 1–3 in tickets.md are marked DEFERRED by team decision (2026-05-07). Executor loop should skip these until explicitly re-activated. Only Lever 1 (reference agents) is active.
- **Agent PIDs (Session 3)**: provart=1994238, newsprove=1994242, agentlog=1994245, dataprove=1994248, socialprove=1994251, researchprove=1994254, codeprove=1994258. synctrigger=1994261. watchdog.sh=1994597. All restarted 03:49 UTC May 8 after ~21h downtime. **Watchdog deployed** — checks all 8 processes every 5 min, auto-restarts any that die. gc.collect and log rotation added to all agents in common.py.
- **Session history**: Session 1 (May 6, 12.3h): ~1,682 registrations. Session 2 (May 7, 3.5h): ~1,058. Session 3 (May 8, ongoing): 224+ in first 6 min. Grand total: ~2,964+.
- **Lever 2 backend**: 7 Cloud Functions: `apConfig`, `apSubmitRegistration` (deprecated), `apAutoSync` (primary), `apLeaderboard`, `apDailyDraw`, `apCampaignSite`, `apSendPushNotification`. Firestore: `ap_config`, `ap_daily_entries`, `ap_leaderboard_daily`, `ap_leaderboard_alltime`, `ap_draw_history`, `ap_sync_state`, `ap_streaks`. `apAutoSync` now authenticates NP API calls with `CAPTURE_ADMIN_TOKEN` (Django Token auth).
- **Lever 2 campaign site**: `apCampaignSite` launched at `https://us-central1-campaign-gamification.cloudfunctions.net/apCampaignSite`; includes banner SVG, live daily theme/leaderboard integration, `llms.txt`, `agent.json`, sitemap, MCP server card, agent skills index, API catalog, and `/robotstxt` fallback.
- **Automatic participation**: `apAutoSync` polls the public Numbers Protocol API (`/api/v3/assets/`) every 30 min. Excludes agents by BOTH wallet address (2 wallets) AND owner_name (`officialnumbers`). Cap is page-based (60 pages max) so agent volume cannot block real-user records. Passive trigger fires on campaign site visits. synctrigger.py (PID=1483251) provides reliable 30-min heartbeat as Cloud Scheduler workaround. 116 unique wallets enrolled as of 07:37 UTC May 7.
- **Cloud Scheduler blocker**: API not enabled on project (requires project Owner). Workaround: synctrigger.py daemon + passive site-visit triggers.
- **Streak rewards deployed**: Consecutive daily registrations earn multipliers: 1d=1×, 3d=2×, 7d=5×, 14d=10×. Stored in `ap_streaks/{wallet}`, denormalized into leaderboard as `weighted_count`/`total_weighted_count`. Indexes CREATING (will be READY in ~5 min).
- **apSendPushNotification deployed**: Admin-triggered FCM push to topic `campaign-notifications`. Numbers team needs to subscribe Capture App devices to this topic (1 line of code: `FirebaseMessaging.instance.subscribeToTopic('campaign-notifications')`).
- **Remote Config**: 11 `ap_campaign_*` parameters for Capture App banner
- **Cost**: $0.22 spent after 36h. 14-day projection: ~$4.30 of $500 budget
- **Mainnet**: 3,044 txns on Day 2 (above 3,000 target). Day 3 at risk due to agent downtime. Wallets: 36,245
- **Day 3 evaluator score**: 2/4. Primary blocker shifted from throughput (fixed) to agent reliability. Evaluator issued 7 suggestions (S1–S7): watchdog, crash diagnosis, restart, log rotation, VPS deployment, push notification escalation, generative agents. Executor created Day 3 Action Plan (T17–T26) in todo.md.
- **Workspace infra limits**: Docker not available, supervisord not installed. Only bash-based watchdog is viable for auto-restart. VPS ticket (Ticket 5) added to tickets.md.

---
_Last system refresh: 2026-05-08 03:51 UTC_
