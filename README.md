# ntulearn-digest

把 NTULearn 上零散的课程信息，自动整理成**一份日历、一个截止日期看板，和每门课一份 AI 能读懂的资料**。

[English](README.en.md) · 非 NTU 官方工具

![示例看板（数据全部虚构）](docs/dashboard-demo.png)

## 它能做什么

每学期七八门课的考试时间、quiz、作业截止、老师公告，分散在不同课站、PDF 和成绩簿里。这个项目分两层：

| 层 | 谁来做 | 做什么 |
|---|---|---|
| 抓取与生成 | `ntulearn` 命令 | 读课程、内容、成绩簿和公告，下载全部文件，生成 `.ics` 日历、HTML 看板和文字汇总，并列出和上次相比的变化 |
| 阅读与整理 | Claude Code、Codex 等 AI agent | 读课程大纲和公告，整理考核占比、政策和逐周内容，把只写在 PDF 里的考试时间补进日历 |

## 三种上手方式

都需要 **Python 3.9 或更新版本**，以及 **Chrome 或 Edge** 浏览器。

### 方式一：双击运行，不用命令行

1. 在本页点绿色的 **Code**，选 **Download ZIP**，解压。
2. Mac 双击 `Start-macOS.command`，Windows 双击 `Start-Windows.bat`。
3. 第一次会自动安装，然后弹出一个浏览器窗口。在里面像平时一样登录 NTULearn。
4. 登录成功后窗口自动关闭，同步完成后看板自动打开。以后再双击，一般不用再输密码。

Mac 第一次双击时如果提示无法验证开发者，右键点文件，选「打开」即可。

### 方式二：一行命令

```bash
uv tool install git+https://github.com/ericwu666666/ntulearn-digest
ntulearn go
```

没有 [uv](https://docs.astral.sh/uv/) 的话，用 `pipx install git+https://github.com/ericwu666666/ntulearn-digest` 也一样。

### 方式三：开发者

```bash
git clone https://github.com/ericwu666666/ntulearn-digest.git
cd ntulearn-digest
python3 -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -e .
ntulearn demo --open   # 先用虚构数据看效果
ntulearn go
```

## 登录是怎么完成的

- 没有有效登录时，`ntulearn go` 会用你电脑上的 Chrome 或 Edge 打开一个**独立窗口**。它用单独的配置文件夹，不会碰你平时的浏览器数据。
- 密码是你自己在微软的官方登录页里输入的，程序拿不到。
- 登录后，NTULearn 会在页面里放一个一小时有效的访问 token。程序在本机读到它就关掉窗口，token 保存在 `~/.config/ntulearn-digest/token`，只有你自己能读。
- 独立窗口会记住登录状态。token 过期后再运行，窗口通常几秒钟就自动关闭，不用再输密码。
- `ntulearn logout` 会删除保存的 token 和这个独立窗口的登录状态。

不想用自动登录也可以手动：在已登录的 NTULearn 页面打开控制台，运行 [`tools/get_token.js`](tools/get_token.js) 里的一行，再运行 `ntulearn auth --clipboard`。

## 常用命令

| 命令 | 作用 |
|---|---|
| `ntulearn go` | 一键：需要时登录，同步，打开看板 |
| `ntulearn go --no-download` | 不下载课件，只更新日期、成绩和公告 |
| `ntulearn go --course HE3001` | 只同步这门课，可以写多次 |
| `ntulearn go --term 26S1` | 指定学期，默认自动选最新学期 |
| `ntulearn build` | 改了 `events.json` 之后重新生成日历和看板 |
| `ntulearn demo --open` | 用虚构数据预览 |
| `ntulearn logout` | 清除本机保存的登录 |

输出默认在当前文件夹下的 `ntulearn-output/`，用 `-o` 可以改。再次同步只下载新文件，`changes.md` 会列出新公告、新成绩项、改过的截止时间和新出的成绩。

## 加上每周课表（可选）

NTULearn 不提供上课时间，但 NTU 的公开课表有。填你在 STARS 里的 index，或者组别：

```bash
ntulearn classes HE3001:19541 HW0218:GP12 \
  --acadsem "2026;1" --week1 2026-08-10 --skip 2026-11-09
```

`--week1` 是教学第一周的周一。程序默认第 7 周后有一周 recess。公共假期不会自动排除，用 `--skip` 列出来。

## 让 AI 补齐考试时间和课程要点（可选）

仓库给 AI agent 准备了操作说明。Claude Code 会自动加载 [技能](.claude/skills/ntulearn-digest/SKILL.md)，Codex、Cursor、Gemini CLI 等会读根目录的 [`AGENTS.md`](AGENTS.md)，两份内容一致。在仓库文件夹里打开任意一个 agent，说一句「更新 NTULearn」，它会：

1. 运行同步，先看 `changes.md`；
2. 读有变化的课程大纲、考试通知和公告，为每门课写 `notes.md`，包括考核占比、形式、政策、逐周内容和每个数字的出处；
3. 把成绩簿里没有的考试和展示写进 `events.json`，重新生成日历；
4. 告诉你三天内要做什么。

Codex 这类在沙盒里运行的 agent 可能不能联网或弹出浏览器。遇到这种情况，它会请你先在终端运行 `ntulearn go`，然后接着整理。

不用 AI 也可以：照 [`examples/events.example.json`](examples/events.example.json) 手写 `events.json`，放进输出文件夹，运行 `ntulearn build`。

## 输出

```
ntulearn-output/
├── dashboard.html               看板：未来两周、考试、变化、各门课、全部截止
├── calendar.ics                 课表 + 考试 + 截止，导入 Apple / Google / Outlook 日历
├── calendar-deadlines-exams.ics 不含每周课表的版本
├── deadlines.md                 同样内容的文字版
├── changes.md                   和上一次同步相比的变化
├── items.json                   所有日期项，方便 AI 或脚本使用
├── snapshot.json                原始整理数据
├── events.json                  你或 AI 补充的考试等事件
├── classes.json                 每周上课时间
└── courses/<课程>/
    ├── overview.md              成绩簿、公告全文、内容结构
    ├── notes.md                 AI 整理的考核与政策
    ├── pages/                   Ultra 页面正文
    └── files/                   按课站文件夹结构下载的文件
```

截止事项在日历里显示为截止前 30 分钟的一个时间块，提前一天和三小时提醒。已经提交或评分的项目不再提醒。

## 原理

NTULearn 是 Blackboard Learn Ultra。网页里的访问 token 可以调用 Blackboard 的公开 REST 接口 `/learn/api/public/v1`。这个工具只发 GET 请求，只读你自己能看到的内容：课程列表和选课状态、内容树和附件、Ultra 页面正文和嵌在正文里的文件、成绩簿截止时间和你的提交状态、公告。

## 隐私、版权与使用边界

- **不要把输出文件夹提交到 GitHub 或分享给别人。** 里面是老师的课件和你的成绩。`.gitignore` 已经排除了默认输出目录。
- 课件版权属于老师和学校，只供你自己学习使用。
- token 和独立登录窗口的配置文件夹都等同于你的登录状态，只保存在本机，不要发给任何人。
- 这是个人学习用的非官方工具，与 NTU 和 Blackboard 无关。使用前请自行确认符合学校的 IT 使用规定。程序默认低并发、自动退避重试，请不要调高并发或频繁运行。
- 「成绩簿未见提交」只代表成绩簿里没有记录。Turnitin、问卷类提交可能不会显示，请以课站为准。

## 局限

- 只在 NTULearn 上用过。其他学校的 Blackboard Ultra 可以用 `--base-url` 试试。
- 自动登录需要 Chrome、Edge、Chromium 或 Brave。其他浏览器请用手动方式。
- 课程关闭后，文件下载会被拒绝。
- 考试时间、考核占比这类只写在 PDF 里的信息，需要 AI 或手工补充。

## 开发

```bash
python -m unittest discover -s tests -v
```

测试包括：用虚构数据模拟 Blackboard 接口的单元测试，以及一个端到端测试。端到端测试会启动无界面的 Chrome，登录一个本地模拟的 NTULearn，再通过真实 HTTP 完成同步和下载。CI 在 Linux、macOS 和 Windows 上跑全部测试和双击启动脚本。

## License

MIT
