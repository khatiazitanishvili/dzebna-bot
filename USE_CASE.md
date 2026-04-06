Here's the complete user journey from zero to receiving their first job notification.

---

**The setup (done once, takes about 5 minutes)**

Sarah is a Python developer in Berlin actively looking for a new job. She finds your project on GitHub, clones it, and opens the `.env` file. She changes three lines to match what she's looking for:

```env
DEFAULT_SEARCH_TERM=Python developer
DEFAULT_LOCATION=Berlin, Germany
NOTIFY_INTERVAL_HOURS=6
```

She then goes to Telegram, searches for `@BotFather`, and sends `/newbot`. BotFather gives her a token that looks like `7123456789:AAFxyz...`. She pastes that into `.env`:

```env
TELEGRAM_BOT_TOKEN=7123456789:AAFxyz...
```

She runs one command in her terminal:

```bash
docker compose up
```

Three containers start — MySQL, her Python app, and Adminer. She sees the logs settle and the health check pass. The app is running.

---

**First contact with the bot**

Sarah opens Telegram on her phone, finds her newly created bot by its username, and sends:

```
/start
```

The bot replies instantly:

```
You're all set! I'll notify you about 'Python developer'
jobs in Berlin, Germany every 6 hours.

Send /trigger to get your first batch now.
```

Behind the scenes, two things just happened silently: a row was inserted into the `users` table with her Telegram `chat_id`, and a row was inserted into `search_configs` with her search preferences from `.env`. She never saw any of that — it just worked.

---

**Getting the first results immediately**

Sarah doesn't want to wait 6 hours. She sends:

```
/trigger
```

The bot replies:

```
Scraping now, this takes about 20 seconds...
```

The scraper hits LinkedIn, Indeed, and Glassdoor simultaneously looking for "Python developer" in Berlin. It finds 18 results, deduplicates them against the database (all 18 are new since it's the first run), and stores them. Then the notifier formats a digest and sends it back to Sarah in the same Telegram chat:

```
14 new jobs matching 'Python developer, Berlin'
─────────────────────────────────────────
1. Senior Python Engineer
   Zalando · Berlin, DE · €80k–110k · Remote OK
   → linkedin.com/jobs/view/123456

2. Backend Engineer (Python)
   N26 · Berlin, DE · Not disclosed · Hybrid
   → indeed.com/viewjob?jk=abc123

3. Python Developer – FinTech
   Trade Republic · Berlin, DE · €70k–95k · On-site
   → glassdoor.com/job-listing/...

... and 11 more
─────────────────────────────────────────
Next automatic check in 6 hours · /trigger to refresh now
```

Sarah taps a link directly in Telegram and lands on the job posting. No browser tabs, no filtering through irrelevant results, no logging into five different job boards.

---

**The automatic rhythm kicks in**

Six hours later, while Sarah is having lunch, her phone buzzes:

```
3 new jobs matching 'Python developer, Berlin'
─────────────────────────────────────────
1. Python Backend Developer
   Delivery Hero · Berlin, DE · €75k–95k · Remote OK
   → linkedin.com/jobs/view/789012
...
```

She didn't do anything. The scheduler woke up, ran the scraper, compared the results against everything already in the database, found 3 jobs that weren't there before, and sent only those. The 18 from earlier are already in the database — they'll never appear again. She only ever sees genuinely new postings.

If the scheduler runs and finds nothing new, Sarah gets no message at all. No noise, no "0 new jobs found" ping. Silence means nothing new.

---

**Checking status and adjusting**

A few days in Sarah wants to know what's going on. She sends:

```
/status
```

The bot replies:

```
Active since: 3 days ago
Search: Python developer · Berlin, Germany
Boards: LinkedIn, Indeed, Glassdoor
Interval: every 6 hours
Total jobs stored: 47
Last notification: 2 hours ago (3 new jobs)
```

She decides she also wants to see remote-only roles. She sends:

```
/search Python developer remote
```

The bot updates her search config and confirms:

```
Updated! I'll now search for 'Python developer'
with remote filter on.
Send /trigger to apply immediately.
```

---

**Pausing when she needs a break**

Sarah gets two offers and wants to stop the notifications while she decides. She sends:

```
/pause
```

```
Notifications paused. Send /resume to start again.
```

The scheduler still runs in the background but skips sending to Sarah because her `is_active` flag is `false` in the database. When she's ready:

```
/resume
```

```
You're back! Next check in 6 hours, or send /trigger now.
```

---

**What Sarah never had to do**

She never opened a browser to LinkedIn. She never set up search alerts on five different platforms that spam her inbox. She never filtered through jobs she'd already seen. She never logged into Glassdoor. She just set her search term once, ran one Docker command, and let the bot handle the rest.
