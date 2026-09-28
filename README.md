# Data Center News Clipper

**What this does:** This tool automatically finds news articles about data centers, sorts them into categories, and creates a nice PDF report for you.

**How it works:** Setup once, then run one command whenever you want a new report.

---

## Which document do I read?

Four documents, in reading order. **This one is setup only.** The day-to-day
ones are in Portuguese, because whoever operates the clipping works in
Portuguese.

| Read | What it is | When |
|---|---|---|
| **`README.md`** (this file, English) | Installing the thing on a new machine | Once |
| **`LEIA-ME.md`** (Portuguese) | How to operate it: every command, what to check before sending, how to correct an edition | Every week |
| **`COMANDOS.txt`** (Portuguese) | The same commands with no explanation, to copy and paste | Every week |
| **`DECISOES.md`** (Portuguese) | Why each rule is what it is, and what was measured to decide it | Before changing anything |

`TODO.md` is the queue of what is still open. `propostas/` holds the written
proposals behind some of the rules, kept for the record.

---

# 🔧 ONE-TIME SETUP

**Do this section ONCE, on the computer that will run the clipping.** About 20
minutes, most of it waiting for downloads.

> **Mac only.** Every step below has been tested on macOS. There is no tested
> route for Windows: the part that draws the PDF (WeasyPrint) needs system
> libraries that are installed differently there. If the clipping has to run on
> Windows, that route has to be written and tested first.

## Setup Steps Index

1. [Install the tools (Git, Chrome, conda)](#step-1-install-the-tools)
2. [Download the project](#step-2-download-the-project)
3. [Create the Python environment](#step-3-create-the-python-environment)
4. [Install the libraries](#step-4-install-the-libraries)
5. [Configure the .env file](#step-5-configure-the-env-file)
6. [Check that everything works](#step-6-check-that-everything-works)

---

## Step 1: Install the tools

Open the **Terminal** app (Applications → Utilities → Terminal). Every command
below is typed there.

### Git

```bash
git --version
```

If a version number appears, you have it. If macOS offers to install the
"command line developer tools", accept — that is how Git arrives on a Mac.

### Google Chrome

The collection stage opens each article in an invisible Chrome. **Chrome has to
be installed** — download it from [google.com/chrome](https://www.google.com/chrome/)
if it is not already there. The piece that lets the program drive Chrome is
downloaded automatically the first time it runs.

### conda (through Miniforge)

**Why?** The program draws the PDF with WeasyPrint, which needs two system
libraries, `pango` and `cairo`, that Python's `pip` cannot install. conda can.
It also brings its own Python 3.12 — a new Mac comes with Python 3.9, and the
libraries this project uses need 3.10 or newer.

If `conda --version` already prints a number (Anaconda or Miniconda installed),
skip this — Step 3 takes care of the one trap an existing Anaconda can set.
Otherwise, install Miniforge:

```bash
curl -L -O "https://github.com/conda-forge/miniforge/releases/latest/download/Miniforge3-$(uname)-$(uname -m).sh"
bash Miniforge3-$(uname)-$(uname -m).sh
```

Answer `yes` to the licence and to "initialize conda". Then **close the Terminal
and open it again**, and check:

```bash
conda --version
```

> **Why not Homebrew?** Earlier versions of this README used Homebrew. That route
> was never tested on a machine other than the one the program was written on,
> and on a new Mac it fails: `python3` there is 3.9. One route, tested, is better
> than two where one is broken. (The environment that runs the clipping today was
> built with exactly the conda command in Step 3.)

---

## Step 2: Download the project

Go to the folder where you keep projects — **not iCloud Drive, not Dropbox**:
those sync file by file and corrupt the project's history. A folder like
`~/dev` is ideal:

```bash
mkdir -p ~/dev && cd ~/dev
git clone https://github.com/pedrooooandradee/datacenter-news-clipper.git
cd datacenter-news-clipper
```

This is where version 2 lives. The older repository under `Orimadros` holds
version 1 and is no longer maintained — do not clone that one.

---

## Step 3: Create the Python environment

Two layers. First a conda environment that holds Python 3.12 and the PDF
libraries — once per computer.

**Which chip does the Mac have?**  menu → About This Mac. "Chip: Apple M1" (or
M2, M3…) is Apple; "Processor: Intel" is Intel. Almost every Mac from 2021 on is
Apple.

```bash
CONDA_SUBDIR=osx-arm64 conda create -y -p ~/.clipping247-python --override-channels -c conda-forge python=3.12 pango cairo gdk-pixbuf libffi
```

On an **Intel** Mac, drop the `CONDA_SUBDIR=osx-arm64` at the start.

> **Why `CONDA_SUBDIR=osx-arm64`?** Found on 28 Sep 2026, testing this very
> recipe from scratch. An Anaconda installed for Intel — common, even on Apple
> Macs — builds Intel environments by default. Python then runs translated
> (Rosetta), everything installs and every test passes, and the Chrome it drives
> freezes on every heavy news page: 30-second timeouts on Valor and G1, which the
> Apple build opens in under a second. The prefix forces the Apple build.

Then, inside the project folder, a virtual environment (`venv`) built **from
that Python** — this is the step that makes the PDF libraries visible:

```bash
~/.clipping247-python/bin/python3 -m venv venv
source venv/bin/activate
python --version
python -c "import platform; print(platform.machine())"
```

The prompt now starts with `(venv)`, and the two last lines have to print:

- **Python 3.12.something.** If it prints 3.9, the venv was built from the Mac's
  own Python: delete the `venv` folder and repeat the block above.
- **arm64**, on an Apple Mac (`x86_64` on an Intel one). `x86_64` on an Apple Mac
  means the conda environment was built for Intel: delete both
  `~/.clipping247-python` and `venv`, and repeat from the conda command.

---

## Step 4: Install the libraries

```bash
pip install -r requirements.lock.txt
```

`requirements.lock.txt` holds the **exact versions** that produced real
editions. `requirements.txt` holds only the minimum versions and would pull
whatever is newest on the day you install — combinations nobody has tested. If
something breaks after a reinstall, reinstall from the lock before touching any
code.

It downloads about 80 packages. That is normal, and `venv/` is not in the
repository.

---

## Step 5: Configure the .env file

The `.env` file holds the OpenAI key — the program pays for its AI calls with it
(about US$ 0.20 per edition). It is never in the repository. Create it from the
template:

```bash
cp .env.example .env
```

Open `.env` and replace the placeholder with the key. The key comes from the
**company's OpenAI account** (organisation `elementum3`), created by whoever
administers it — never a personal key, which stops working when its owner leaves.

**CRITICAL:** Never share this file with anyone. It's connected to a credit card
and costs money every time it's used.

---

## Step 6: Check that everything works

```bash
python -m unittest discover -s tests
```

It has to end in `OK`. It is free and needs no internet. If it fails, the
installation is wrong somewhere — do not run the clipping.

Then open the project in **Cursor** (File → Open Folder → the project folder).
The free plan is enough: the program runs in the terminal, and Cursor's AI is not
needed. VS Code or the plain Terminal work just as well.

You are ready. The day-to-day guide is `LEIA-ME.md`.

---

## Setup Troubleshooting

| Problem | Solution |
|---|---|
| `conda: command not found` | Close and reopen the Terminal after installing Miniforge. Still missing: install again and answer `yes` to "initialize conda" |
| `python --version` says 3.9 inside the venv | The venv was built from the Mac's Python. Delete `venv/` and repeat Step 3 exactly |
| `No module named '...'` | The venv is not active (`source venv/bin/activate`), or Step 4 was skipped |
| `cannot load library 'libpango-1.0-0'` | The venv was not built from `~/.clipping247-python/bin/python3`. Delete `venv/` and repeat Step 3 |
| `pip install` fails compiling something | Almost always the wrong Python (3.9). Check with `python --version` |
| Almost every page is listed as "descartadas por falha de coleta", with `timeout no carregamento` or `TimeoutException` | The environment is Intel on an Apple Mac. `python -c "import platform; print(platform.machine())"` says `x86_64`. Redo Step 3 with `CONDA_SUBDIR=osx-arm64` |

---

# 🎯 DAILY USAGE

**The day-to-day guide is `LEIA-ME.md`, in Portuguese.** This section is the
short version, and it is deliberately short: everything below has a longer
explanation there, and duplicating it is how the two drift apart.

Every command is run from a terminal, with the venv active. In Cursor or VS
Code: **Terminal → New Terminal**, then:

```bash
source venv/bin/activate
```

The prompt starts showing `(venv)`. In Cursor and VS Code the repository's own
settings (`.vscode/`) already open every new terminal with the venv active — if
`(venv)` is there, skip the command above. There is no Run button: everything
runs from the terminal.

Every full run also saves everything it printed to `output/logs/`, so the
warnings can be read again after the terminal is closed.

## The three commands

| Command | What it does | Cost |
|---|---|---|
| `python main.py` | The full edition: search, classify, scrape, summarise, extract, deduplicate, PDF | **Money and 10–30 minutes.** Only with authorisation |
| `python services/pdf_builder.py` | Rebuilds only the PDF from what is already in `output/` | Free, seconds |
| `python -m unittest discover -s tests` | The tests of the rules that decide what the investor reads | Free, no network |

A full run cost US$ 0.20 and took 13 minutes on the 22 Sep 2026 edition
(56 articles).

## Everything else

Redoing a single stage without paying for the ones before it, correcting an
edition so the correction survives the next run, what each warning means: all of
that is in **`LEIA-ME.md`**, and only there.

It used to be repeated here too. That is exactly how the number of tests came to
be wrong in three documents at once — the same fact written four times drifts in
three of them. One subject, one owner.

## Before you send

Do the item-by-item review in `LEIA-ME.md` ("Revisão da edição, item a item").
Reading the terminal is not enough: on the 28 Sep 2026 edition, 11 of 36 stories
needed a correction and none of those errors showed up in the terminal.

## Your results

- **PDF:** `output/clippings_output.pdf`
- **Data:** `output/clippings.json` (and the previous version in
  `output/clippings.anterior.json`)
- **Archive:** `output/archive/<date>/` — kept out of the repository; it holds
  third-party article text and the hand-corrected editions

---

## Usage Troubleshooting

| Problem | Solution |
|---|---|
| `No module named '...'` | The venv is not active. `source venv/bin/activate` |
| `cannot load library 'libpango-1.0-0'` | Step 3. The venv was not built from `~/.clipping247-python/bin/python3` |
| Any line starting with `⛔` | `LEIA-ME.md`, "Quando quebrar", lists each one and what to do. Most stop before anything is paid |
| `(venv)` not showing | Run `source venv/bin/activate` from the project folder |
| PDF has no logo in the header | `configs/247.original.jpg` was deleted. `git checkout configs/247.original.jpg` |
| PDF generation fails | `configs/clipping_template.html` is the only file the PDF truly needs; the logo is optional |
| "Já existe uma execução em andamento" | Another run is going, or one died. `output/execucao.lock` holds the pid |

---

## File Locations

- **`.env`**: main folder, next to `main.py` — KEEP PRIVATE
- **`venv/`**: main folder — created during setup, not in the repository
- **Output**: `output/clippings.json` and `output/clippings_output.pdf`
- **Configuration and prompts**: `configs/`
- **Corrections that survive a rerun**: `configs/overrides.json`

---

## What is deliberately NOT in this repository

This repository is public. Two things are kept out on purpose:

- **`.env`** — the OpenAI key, tied to a credit card.
- **`output/archive/`** — full text of third-party articles, and the editions
  already corrected by hand for the client.

Everything else is here, including the PDF template and the client's logo, so a
clone builds a complete, branded edition.

---

## Security Reminder

The `.env` file contains an API key connected to a credit card. **NEVER**:
- Share it with anyone
- Upload it to GitHub
- Take screenshots of it
- Leave it visible anywhere
