# ntulearn-digest

Turn the scattered pieces of NTULearn into **one calendar, one deadline dashboard, and an AI-readable folder per course**.

[中文](README.md) · Unofficial, not affiliated with NTU

![Demo dashboard (all data is fictional)](docs/dashboard-demo.png)

## What it does

Exam dates, quizzes, assignment deadlines and announcements live in different course sites, PDFs and gradebooks. The project has two layers:

| Layer | Who | What |
|---|---|---|
| Fetch and render | the `ntulearn` CLI | Reads courses, content trees, gradebooks and announcements, downloads every file, writes an `.ics` calendar, an HTML dashboard and Markdown summaries, and diffs each sync against the previous one |
| Read and organise | an AI assistant such as Claude Code | Reads syllabi and announcements, writes each course's assessment breakdown, policies and weekly topics, and adds exam dates that only exist in PDFs to the calendar |

Gradebook items with due dates go into the calendar directly. Exam times usually sit only in the course outline, so the AI reads them into `events.json` and the calendar is rebuilt.

## Quick start

Python 3.9+, no third-party dependencies.

```bash
git clone https://github.com/ericwu666666/ntulearn-digest.git
cd ntulearn-digest
pip install -e .
ntulearn demo        # preview with fictional data in demo-output/
```

### 1. Copy your token

1. Log in to NTULearn in Chrome or Edge.
2. Open DevTools (F12, or ⌥⌘J on a Mac), paste the one-liner from [`tools/get_token.js`](tools/get_token.js) into the Console and press Enter. The token is now on your clipboard.
3. In a terminal:

```bash
ntulearn auth --clipboard
```

The token expires after about an hour; repeat when it does. The tool never sees your password. The token is stored only at `~/.config/ntulearn-digest/token`, readable by you alone.

### 2. Sync

```bash
ntulearn sync
```

By default it picks the latest term from the course ID prefix (for example `26S1`), downloads all files and renders every output. Options: `--term 26S1`, `--course HE3001` (repeatable), `--no-download`, `-o <folder>` and `--workers 4`. Please keep concurrency low.

Later runs only download new files, and `changes.md` lists new announcements, new gradebook items, moved due dates and released grades.

### 3. Weekly class times (optional)

NTULearn does not expose class times, but NTU's public class schedule does. Use your STARS index or group names:

```bash
ntulearn classes HE3001:19541 HW0218:GP12 \
  --acadsem "2026;1" --week1 2026-08-10 --skip 2026-11-09
```

`--week1` is the Monday of teaching week 1. A recess week after week 7 is assumed. Public holidays are not removed automatically; list them with `--skip`.

### 4. Let an AI fill in exams and course notes (optional)

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

NTULearn runs Blackboard Learn Ultra. The web app keeps a short-lived access token in `sessionStorage`, and that token is accepted by Blackboard's public REST API at `/learn/api/public/v1`. The tool sends GET requests only and reads only what you can already see: your course list with a membership check that reveals dropped courses, content trees and attachments, Ultra document bodies (files embedded in a page only appear there), gradebook columns with your own status, and announcements.

## Privacy, copyright and fair use

- **Never commit or share your output folder.** It contains your lecturers' materials and your grades. The default output folder is already in `.gitignore`.
- Course materials belong to their authors and the university. Keep them for your own study.
- A token is a live login for about an hour. Do not share it.
- This is an unofficial personal tool, unrelated to NTU or Blackboard. Check that your use fits your university's IT policies. It defaults to low concurrency with backoff; please do not raise it or run it in a tight loop.
- "No submission in gradebook" only means the gradebook shows no attempt. Turnitin or survey submissions may not appear there.

## Limitations

- Tested on NTULearn only. Other Blackboard Ultra sites may work with `--base-url`.
- Closed courses refuse file downloads.
- Exam times and weightings that only exist in PDFs need step 4 or manual entry.

## Development

```bash
python -m unittest discover -s tests -v
```

Tests run against an in-memory fake Blackboard API, with no network or account. Issues and pull requests are welcome.

## License

MIT
