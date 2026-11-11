# RYUUNDY cron drama lanes

Chinese drama (`chinese_drama_story`) joins the existing performance/demand/cooldown rotation for Shorts and paired or independent review Longs. Korean drama (`korean_drama_story`) is prepared behind `AUTO_VIRAL_SCHEDULE_KOREAN_DRAMA_ENABLED=false` by default because the owner's phrase "ora drama2 Korea" may explicitly exclude Korea. A clarification is pending; no Korean lane was enabled in production.

Both briefs use RYUUNDY's "satu momen, satu makna" concept: decisions, relationship/family conflicts, consequences and a complete payoff. Long creation retains source identity and Short anchor ranges. Drama metadata explicitly identifies fiction/dramatization, avoids unsupported real-life/religious labels, separates character from actor and prohibits invented dialogue/translations. Source selection requires origin, story and commentary/narration signals, with existing Indonesian language, rights, source process limit, HD, preflight, editorial and QC checks intact. Raw scene compilations and off-theme celebrity/news/game content do not qualify.

The query model retains drama-specific queries on serialized reload even if general trend expansion is off. Channel/live trend queries are scoped to the chosen drama origin before consuming search quota. The new source module is covered automatically by the standard Compose build integrity manifest. No extra activation script is required.

See focused.xml and regression.xml for offline tests, including actual Short/Long request construction, ordinary theme exploration, disabled Korean performance/demand winners, restart stability, off-theme query budget, language rejection and rights checks. Tests never render, upload or publish media. The local syntax/image-input check passed; no Docker image was built in this session.

Live backend was healthy with cron enabled and director policy 4, but did not yet report `cron_drama_lanes`. Deployment remains pending because sudo requires the user's terminal password. Activate using the owner's standard command:

```sh
sudo docker-compose --env-file .env up -d --build --force-recreate backend frontend telegram-bot
```

No production cron flag, upload queue, public/private choice, session or remote post was modified during this task.
