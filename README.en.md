# ntulearn-digest

Turn the scattered pieces of NTULearn into **one calendar, one deadline dashboard, and an AI-readable folder per course**.

[中文](README.md) · Unofficial, not affiliated with NTU

![Demo dashboard (all data is fictional)](docs/dashboard-demo.png)

## What it does

| Layer | Who | What |
|---|---|---|
| Fetch and render | the `ntulearn` command | Reads courses, content, gradebooks and announcements, downloads every file, writes an `.ics` calendar, an HTML dashboard and text summaries, and lists what changed since last time |
| Read and organise | an AI assistant such as Claude Code | Reads syllabi and announcements, writes each course's assessment breakdown, policies and weekly topics, and adds exam dates that only exist in PDFs to the calendar |

## Three ways to start

All of them need **Python 3.9+** and **Chrome or Edge**.

### 1. Double-click, no terminal

1. On this page click the green **Code** button, then **Download ZIP**, and unzip it.
2. Double-click `Start-macOS.command` on a Mac or `Start-Windows.bat` on Windows.
3. The first run installs itself, then opens a browser window. Log in to NTULearn there as usual.
4. The window closes by itself, the sync runs and the dashboard opens. Later runs usually need no password.

If macOS says the developer cannot be verified, right-click the file and choose **Open**.

### 2. One command

```bash
uv tool install git+https://github.com/ericwu666666/ntulearn-digest
ntulearn go
```

Without [uv](https://docs.astral.sh/uv/), `pipx install git+https://github.com/ericwu666666/ntulearn-digest` works the same way.

### 3. Developers

```bash
git clone https://github.com/ericwu666666/ntulearn-digest.git
cd ntulearn-digest
python3 -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -e .
ntulearn demo --open   # preview with fictional data
ntulearn go
```

## How login works

- When there is no valid login, `ntulearn go` opens a **separate window** of your installed Chrome or Edge. It uses its own profile folder and never touches your normal browser data.
- You type your password into Microsoft's own sign-in page. The tool never sees it.
- After sign-in, NTULearn keeps a one-hour access token in the page. The tool reads it locally over the DevTools protocol on 127.0.0.1, closes the window, and stores the token at `~/.config/ntulearn-digest/token`, readable by you only.
- The separate window remembers your session, so when the token expires the window usually closes again within seconds without asking for a password.
- `ntulearn logout` deletes the saved token and that window's session.

Manual fallback: in a logged-in NTULearn tab, run the one-liner from [`tools/get_token.js`](tools/get_token.js) in the DevTools console, then `ntulearn auth --clipboard`.

## Everyday commands

| Command | What it does |
|---|---|
| `ntulearn go` | Log in if needed, sync, open the dashboard |
| `ntulearn go --no-download` | Skip course files, refresh dates, grades and announcements only |
| `ntulearn go --course HE3001` | Only this course; repeatable |
| `ntulearn go --term 26S1` | Pick a term; the latest is chosen by default |
| `ntulearn build` | Rebuild the calendar and dashboard after editing `events.json` |
| `ntulearn demo --open` | Preview with fictional data |
| `ntulearn logout` | Remove the saved login from this computer |

Output goes to `ntulearn-output/` in the current folder; change it with `-o`. Later syncs only download new files, and `changes.md` lists new announcements, new gradebook items, moved due dates and released grades.

## Weekly class times (optional)

NTULearn does not expose class times, but NTU's public class schedule does. Use your STARS index or group names:

```bash
ntulearn classes HE3001:19541 HW0218:GP12 \
  --acadsem "2026;1" --week1 2026-08-10 --skip 2026-11-09
```

`--week1` is the Monday of teaching week 1. A recess week after week 7 is assumed. Public holidays are not removed automatically; list them with `--skip`.

## Let an AI fill in exams and course notes (optional)

The repo ships a Claude Code skill in [`.claude/skills/ntulearn-digest`](.claude/skills/ntulearn-digest/SKILL.md). Open Claude Code in the repo and say "update NTULearn". It syncs, reads `changes.md`, reads the changed syllabi and announcements, writes `notes.md` per course with a source for every number, adds missing exams to `events.json`, rebuilds, and tells you what is due in the next three days.

Without Claude Code, write `events.json` by hand following [`examples/events.example.json`](examples/events.example.json) and run `ntulearn build`.

## Outputs

| File | Contents |
|---|---|
| `dashboard.html` | Next two weeks, exams, changes, per-course cards, every deadline |
| `calendar.ics` | Classes, exams and deadlines for Apple, Google or Outlook Calendar |
| `calendar-deadlines-exams.ics` | The same without weekly classes |
| `deadlines.md`, `changes.md`, `items.json` | Text and JSON versions for reading or scripting |
| `courses/<course>/overview.md` | Gradebook, full announcements, content outline |
| `courses/<course>/files/`, `pages/` | Downloads in the course's folder structure, and Ultra page text |

## How it works

NTULearn runs Blackboard Learn Ultra. The page's access token is accepted by Blackboard's public REST API at `/learn/api/public/v1`. The tool sends GET requests only and reads only what you can already see: your course list with a membership check that reveals dropped courses, content trees and attachments, Ultra page bodies with their embedded files, gradebook due dates with your own status, and announcements.

## Privacy, copyright and fair use

- **Never commit or share your output folder.** It contains your lecturers' materials and your grades. The default output folder is already in `.gitignore`.
- Course materials belong to their authors and the university. Keep them for your own study.
- The token and the login window's profile folder are equivalent to being logged in. They stay on your computer; do not share them.
- This is an unofficial personal tool, unrelated to NTU or Blackboard. Check that your use fits your university's IT policies. It defaults to low concurrency with backoff; please do not raise it or run it in a tight loop.
- "No submission in gradebook" only means the gradebook shows no attempt. Turnitin or survey submissions may not appear there.

## Limitations

- Only used on NTULearn so far. Other Blackboard Ultra sites may work with `--base-url`.
- One-click login needs Chrome, Edge, Chromium or Brave. Use the manual fallback otherwise.
- Closed courses refuse file downloads.
- Exam times and weightings that only exist in PDFs need an AI or manual entry.

## Development

```bash
python -m unittest discover -s tests -v
```

The suite has unit tests against an in-memory fake Blackboard API, plus an end-to-end test that starts headless Chrome, logs in to a local mock NTULearn and syncs over real HTTP. CI runs everything, including the double-click launchers, on Linux, macOS and Windows.

## License

MIT
