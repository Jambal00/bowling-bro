# Bowling Bro'

A phone-first web app for tracking bowling scores, shot stats and season progress. It runs in the browser, installs to the home screen, and needs no app store.

Live app: https://jambal00.github.io/bowling-bro/

## What it does

- **Score a night frame by frame.** Tap the pins left standing on each ball. The app keeps the scoresheet, the line you played (feet and arrow), the ball used and notes per frame.
- **League and practice.** Each series is saved as a league night or a practice session and reported separately.
- **Your Stats.** Four tabs:
  - **Summary:** season average, high game, high series, and a trend chart (running average with weekly series totals, per-game scores with each game's season average, and high-low consistency). Seasons longer than 10 weeks default to the last 10, with a full-season view.
  - **Shots:** strike %, spare %, single-pin %, split % and open frames, overall and per night, from nights scored frame by frame.
  - **Goals:** progress against scoring goals and shot-by-shot goals (league only).
  - **History:** the week-by-week table with rank and notes, editing, and CSV export.
- **Goals.** Fill-in-the-blank goals for season average, high game, high series, strike %, spare %, single-pin spare % and open frames per game, plus custom score-based goals such as "50% of games at 200 or better".
- **First-time setup.** A three-step, skippable wizard for name, home center, the balls in your bag and an average goal.
- **Accounts.** Sign in with a code sent by email; no password. Scores, goals, profile and bag follow the account across devices. It can also be used without signing in, saved on one device only.
- **Series summary and PDF.** End-of-night summary with per-game stats and a printable report.

## How the stats are calculated

- **Strike %** = strikes divided by first balls thrown (every ball at a full rack: 10 to 12 per game, counting 10th-frame fill balls).
- **Spare %** = spares divided by spare chances (every second ball at pins left standing, including a leave after a 10th-frame strike).
- **Single-pin %** = single-pin spares made divided by single-pin leaves.
- **Split %** = first balls that left a split divided by first balls thrown.
- **Open frames** = frames with neither a strike nor a spare.

## How it is built

- One static page: `index.html` holds the markup, styles and script. `manifest.webmanifest` and `icons/` make it installable.
- Hosted on GitHub Pages from the `main` branch; a push to `main` is a release.
- Supabase provides email sign-in and per-bowler storage. Each bowler's rows are private to them through row-level security.
- No build step and no dependencies beyond the Supabase client loaded from a CDN.

## Running it locally

Serve the folder with any static web server, for example `python3 -m http.server`, and open the page. Without a network connection to Supabase the app still works in "this device only" mode.
