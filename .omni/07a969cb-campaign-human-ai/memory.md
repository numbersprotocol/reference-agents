# Workspace Context

<!-- This file is auto-maintained. The Repositories section is refreshed -->
<!-- by the system. The AI should maintain Environment & Key Discoveries. -->

**Workspace root (absolute path):** `/home/workspaces/conversations/07a969cb-5252-49e4-b9a6-0af72ace82d2`

## Repositories

- **`reference-agents/`** — Branch: `main`, Remote: `numbersprotocol/reference-agents`
  - **"Agents Prove It" Campaign — Lever 1**

## Environment & Tools

- Python 3 with `numbersprotocol-capture-sdk` v0.2.1, httpx, dotenv
- Firebase project: `campaign-gamification` (Firestore, Cloud Functions gen2, FCM, Remote Config)
- GitHub: `numbersprotocol/reference-agents` (public, MIT, 28 files)
- Credentials: `$Capture_Auth_Token`, `$Github_PAT`, `$REDDIT_CLIENT_ID`, `$REDDIT_CLIENT_SECRET`
- Node.js 20 (Cloud Functions runtime)

## Key Discoveries

- **Workflow constraint**: For this marketing campaign, do not rely on GitHub repository/PR/merge workflow. Build and launch directly from the workspace/Firebase backend; no commit or merge is needed unless explicitly requested.
- **Agent PIDs**: provart=1357320, newsprove=1357321, dataprove=1357322, socialprove=1357323, codeprove=1357325, researchprove=1357326, agentlog=1357327 (03:24 UTC May 7)
- **Lever 2 backend**: 7 Cloud Functions: `apConfig`, `apSubmitRegistration` (deprecated), `apAutoSync` (primary), `apLeaderboard`, `apDailyDraw`, `apCampaignSite`, `apSendPushNotification`. Firestore: `ap_config`, `ap_daily_entries`, `ap_leaderboard_daily`, `ap_leaderboard_alltime`, `ap_draw_history`, `ap_sync_state`, `ap_streaks`
- **Lever 2 campaign site**: `apCampaignSite` launched at `https://us-central1-campaign-gamification.cloudfunctions.net/apCampaignSite`; includes banner SVG, live daily theme/leaderboard integration, `llms.txt`, `agent.json`, sitemap, MCP server card, agent skills index, API catalog, and `/robotstxt` fallback.
- **Automatic participation**: `apAutoSync` polls the public Numbers Protocol API (`/api/v3/assets/`) every 30 min. Excludes agents by BOTH wallet address (2 wallets) AND owner_name (`officialnumbers`). Cap is page-based (60 pages max) so agent volume cannot block real-user records. Passive trigger fires on campaign site visits. synctrigger.py (PID=1483251) provides reliable 30-min heartbeat as Cloud Scheduler workaround. 116 unique wallets enrolled as of 07:37 UTC May 7.
- **Cloud Scheduler blocker**: API not enabled on project (requires project Owner). Workaround: synctrigger.py daemon + passive site-visit triggers.
- **Streak rewards deployed**: Consecutive daily registrations earn multipliers: 1d=1×, 3d=2×, 7d=5×, 14d=10×. Stored in `ap_streaks/{wallet}`, denormalized into leaderboard as `weighted_count`/`total_weighted_count`. Indexes CREATING (will be READY in ~5 min).
- **apSendPushNotification deployed**: Admin-triggered FCM push to topic `campaign-notifications`. Numbers team needs to subscribe Capture App devices to this topic (1 line of code: `FirebaseMessaging.instance.subscribeToTopic('campaign-notifications')`).
- **Remote Config**: 11 `ap_campaign_*` parameters for Capture App banner
- **Cost**: $0.15 spent after 16h. 14-day projection: ~$3.15 of $500 budget
- **Mainnet**: 3,044 txns on Day 2 (above 3,000 target). Wallets: 36,245

---
_Last system refresh: 2026-05-07 08:21 UTC_
