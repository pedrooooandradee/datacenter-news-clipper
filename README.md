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

It runs on **Mac, Windows and Linux**. The only step that differs is Step 3: the
part that draws the PDF (WeasyPrint) needs system libraries that `pip` cannot
install, and each system installs them its own way. The Mac route was tested
from scratch by hand. On every change to the code, a GitHub workflow
(`.github/workflows/instalacao.yml`) installs the project from scratch following
these steps on Windows, Ubuntu 22.04 and 24.04, and an Apple-chip Mac, and runs
Step 6 there; its header says what it does not cover.

## Setup Steps Index

1. [Install the tools](#step-1-install-the-tools)
2. [Download the project](#step-2-download-the-project)
3. [Create the Python environment](#step-3-create-the-python-environment) — one route per system
4. [Install the libraries](#step-4-install-the-libraries)
5. [Configure the .env file](#step-5-configure-the-env-file)
6. [Check that everything works](#step-6-check-that-everything-works)

---

## Step 1: Install the tools

Every command below is typed in a terminal: **Terminal** on a Mac (Applications
→ Utilities), **PowerShell** on Windows (Start menu → "PowerShell"), the terminal
on Linux. Once Cursor is installed, its own terminal (Terminal → New Terminal)
works just as well.

| Tool | Mac | Windows | Linux (Ubuntu/Debian) |
|---|---|---|---|
| **Git** | `git --version`; if macOS offers the "command line developer tools", accept | [git-scm.com/download/win](https://git-scm.com/download/win), defaults | `sudo apt install git` |
| **Google Chrome** | [google.com/chrome](https://www.google.com/chrome/) | [google.com/chrome](https://www.google.com/chrome/) | the `.deb` from [google.com/chrome](https://www.google.com/chrome/) |
| **Python 3.12** | comes with conda in Step 3 | [python.org/downloads](https://www.python.org/downloads/) — 3.12, and tick **"Add python.exe to PATH"** | `python3 --version` must say 3.10 or more; `sudo apt install python3-venv` |
| **PDF libraries** | conda, Step 3 | MSYS2, Step 3 | `apt`, Step 3 |

Chrome has to be installed: the collection stage opens each article in an
invisible Chrome. The piece that lets the program drive it is downloaded
automatically the first time.

---

## Step 2: Download the project

Go to the folder where you keep projects — **not iCloud Drive, OneDrive or
Dropbox**: those sync file by file and corrupt the project's history.

Mac and Linux:

```bash
mkdir -p ~/dev && cd ~/dev
git clone https://github.com/pedrooooandradee/datacenter-news-clipper.git
cd datacenter-news-clipper
```

Windows (PowerShell):

```powershell
mkdir $HOME\dev -Force; cd $HOME\dev
git clone https://github.com/pedrooooandradee/datacenter-news-clipper.git
cd datacenter-news-clipper
```

This is where version 2 lives. The older repository under `Orimadros` holds
version 1 and is no longer maintained — do not clone that one.

---

## Step 3: Create the Python environment

A virtual environment (`venv`) inside the project folder, built from a Python
that can see the PDF libraries. Follow **only your system's** block.

### Mac

conda brings Python 3.12 and the PDF libraries together — a new Mac comes with
Python 3.9, too old for this project. If `conda --version` already prints a
number, skip the installer. Otherwise install Miniforge:

```bash
curl -L -O "https://github.com/conda-forge/miniforge/releases/latest/download/Miniforge3-$(uname)-$(uname -m).sh"
bash Miniforge3-$(uname)-$(uname -m).sh
```

Answer `yes` to the licence and to "initialize conda", then **close the Terminal
and open it again**. Which chip? Apple menu → About This Mac: "Chip: Apple M1"
(or M2, M3…) is Apple; "Processor: Intel" is Intel.

```bash
CONDA_SUBDIR=osx-arm64 conda create -y -p ~/.clipping247-python --override-channels -c conda-forge python=3.12 pango cairo gdk-pixbuf libffi
~/.clipping247-python/bin/python3 -m venv venv
source venv/bin/activate
```

On an **Intel** Mac, drop the `CONDA_SUBDIR=osx-arm64` at the start.

> **Why `CONDA_SUBDIR=osx-arm64`?** Found on 28 Sep 2026, testing this recipe
> from scratch. An Anaconda installed for Intel — common, even on Apple Macs —
> builds Intel environments by default. Python then runs translated (Rosetta),
> everything installs and every test passes, and the Chrome it drives freezes on
> every heavy news page. The prefix forces the Apple build. Step 6 checks it.

### Windows

The PDF libraries come from **MSYS2**. Install it from [msys2.org](https://www.msys2.org/)
with the default folder, `C:\msys64`. Then open **"MSYS2 UCRT64"** from the Start
menu (not PowerShell) and run:

```bash
pacman -S --noconfirm mingw-w64-ucrt-x86_64-pango
```

Close that window. Back in PowerShell, in the project folder:

```powershell
py -3.12 -m venv venv
venv\Scripts\Activate.ps1
```

If PowerShell refuses with "running scripts is disabled on this system", run
this once — it only allows scripts you created yourself, for your user — and
activate again:

```powershell
Set-ExecutionPolicy -Scope CurrentUser RemoteSigned
```

MSYS2 in another folder? Put its `ucrt64\bin` in the `.env` (Step 5):
`WEASYPRINT_DLL_DIRECTORIES=D:\msys64\ucrt64\bin`.

### Linux (Ubuntu or Debian)

```bash
sudo apt install libpango-1.0-0 libpangoft2-1.0-0 python3-venv
python3 -m venv venv
source venv/bin/activate
```

On Ubuntu 24.04 or Debian 12 and newer, also install `libharfbuzz-subset0`
(`sudo apt install libharfbuzz-subset0`). It does not exist on Ubuntu 22.04 or
Debian 11: skip it there, the PDF works without it. Other distributions: the same
libraries under their own package names (pango, pangoft2).

### All systems

The prompt now starts with `(venv)`. Check the version:

```bash
python --version
```

It has to be 3.10 or newer (3.12 recommended). Anything older: delete the `venv`
folder and repeat your block with the right Python.

---

## Step 4: Install the libraries

With `(venv)` showing:

```bash
pip install -r requirements.lock.txt
```

`requirements.lock.txt` holds the **exact versions** that produced real
editions; every one of them has a ready-made package for Windows, Linux and Mac,
so nothing is compiled. `requirements.txt` holds
only the minimum versions and would pull whatever is newest on the day you
install — combinations nobody has tested. If something breaks after a
reinstall, reinstall from the lock before touching any code.

It downloads about 80 packages. That is normal, and `venv/` is not in the
repository.

---

## Step 5: Configure the .env file

The `.env` file holds the OpenAI key — the program pays for its AI calls with it.
It is never in the repository. Create it from the template:

```bash
cp .env.example .env
```

(Windows: `copy .env.example .env`.) Open `.env` and replace the placeholder with
the key. The key comes from the **company's OpenAI account** (organisation
`elementum3`), created by whoever administers it — never a personal key, which
stops working when its owner leaves.

**CRITICAL:** Never share this file with anyone. It's connected to a credit card
and costs money every time it's used.

---

## Step 6: Check that everything works

```bash
python conferir_instalacao.py
```

It checks, on this computer and without spending anything: the Python, the
libraries, the time zone, a test PDF drawn with the right font, Chrome opening a
page, Google News answering, the OpenAI key (with the free model lookup) and the
tests. Every line has to show ✅; a ⛔ says what to fix. It ends with "Tudo certo
neste computador".

Then open the project in **Cursor** (File → Open Folder → the project folder).
The free plan is enough: the program runs in the terminal, and Cursor's AI is not
needed. VS Code or a plain terminal work just as well. The repository's settings
(`.vscode/`) open every new Cursor terminal with the venv already active, on all
three systems.

You are ready. The day-to-day guide is `LEIA-ME.md`.

---

## Setup Troubleshooting

`python conferir_instalacao.py` names most problems. The ones it cannot reach:

| Problem | Solution |
|---|---|
| `conda: command not found` (Mac) | Close and reopen the Terminal after installing Miniforge. Still missing: install again and answer `yes` to "initialize conda" |
| "py is not recognized" (Windows) | The py launcher was not installed. Run the python.org installer again, choose Modify, and tick "py launcher". Or, if `python --version` says 3.12, use `python -m venv venv` instead |
| `python` opens the Microsoft Store (Windows) | Python was installed without "Add python.exe to PATH". Run the python.org installer again, choose Modify, and tick it |
| "running scripts is disabled" (Windows) | `Set-ExecutionPolicy -Scope CurrentUser RemoteSigned`, then activate again |
| `python --version` says 3.9 inside the venv | The venv was built from an old Python. Delete `venv/` and repeat Step 3 |
| `No module named '...'` | The venv is not active (Mac/Linux `source venv/bin/activate`, Windows `venv\Scripts\Activate.ps1`), or Step 4 was skipped |
| "A parte que desenha o PDF (WeasyPrint) não carregou" | The PDF libraries of Step 3 are missing. The message says which command installs them on this system |
| `pip install` fails compiling something | Almost always a Python older than 3.10. Check with `python --version` |
| ⛔ "Python … de Intel num Mac com chip Apple" | Redo the Mac block of Step 3 with `CONDA_SUBDIR=osx-arm64` |

---

# 🎯 DAILY USAGE

**The day-to-day guide is `LEIA-ME.md`, in Portuguese.** This section is the
short version, and it is deliberately short: everything below has a longer
explanation there, and duplicating it is how the two drift apart.

Every command is run from a terminal, with the venv active. In Cursor or VS
Code, **Terminal → New Terminal** already opens with `(venv)` at the start of the
line, on Mac, Windows and Linux. If it does not, activate it:

- Mac and Linux: `source venv/bin/activate`
- Windows (PowerShell): `venv\Scripts\Activate.ps1`

There is no Run button: everything runs from the terminal. The commands are the
same on every system.

Every full run also saves everything it printed to `output/logs/`, so the
warnings can be read again after the terminal is closed.

## The three commands

| Command | What it does | Cost |
|---|---|---|
| `python main.py` | The full edition: search, classify, scrape, summarise, extract, deduplicate, PDF | **Money and 10–30 minutes.** Only with authorisation |
| `python services/pdf_builder.py` | Rebuilds only the PDF from what is already in `output/` | Free, seconds |
| `python -m unittest discover -s tests` | The tests of the rules that decide what the investor reads | Free, no network |
| `python conferir_instalacao.py` | Checks that this computer can run the clipping | Free, seconds |

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

- **PDF:** `output/AAAA.MM.DD Clipping Atualização Semanal (DD_MM - DD_MM às HhMM).pdf`
  — the name the Drive folder "Clippings Semanais" uses, ready to upload
- **Data:** `output/clippings.json` (and the previous version in
  `output/clippings.anterior.json`)
- **Archive:** `output/archive/<date>/` — kept out of the repository; it holds
  third-party article text and the hand-corrected editions

---

## Usage Troubleshooting

| Problem | Solution |
|---|---|
| `No module named '...'` | The venv is not active (see above) |
| "A parte que desenha o PDF (WeasyPrint) não carregou" | Step 3 of your system |
| Any line starting with `⛔` | `LEIA-ME.md`, "Quando quebrar", lists each one and what to do. Most stop before anything is paid |
| `(venv)` not showing | Activate it (see above), from the project folder |
| PDF has no logo in the header | `configs/247.original.jpg` was deleted. `git checkout configs/247.original.jpg` |
| PDF generation fails | `configs/clipping_template.html` is the only file the PDF truly needs; the logo is optional |
| "Já existe uma execução em andamento" | Another run is going, or one died. `output/execucao.lock` holds the pid |

---

## File Locations

- **`.env`**: main folder, next to `main.py` — KEEP PRIVATE
- **`venv/`**: main folder — created during setup, not in the repository
- **Output**: `output/clippings.json` and the PDF, `output/<Drive name>.pdf`
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
