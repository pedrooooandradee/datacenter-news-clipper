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

**Do this section ONCE when you first get the project. You'll never need to repeat these steps.**

## Setup Steps Index

1. [Install System Dependencies (macOS only) - CRITICAL STEP!](#step-1-install-system-dependencies-macos-only---critical-step)
2. [Download the Project from Github](#step-2-download-the-project)
3. [Set Up Python Environment](#step-3-set-up-python-environment)
4. [Install Python Dependencies](#step-4-install-python-dependencies)
5. [Configure .env file](#step-5-configure-env-file)
6. [Add the Client's Logo](#step-6-add-the-clients-logo-optional)

---

## Step 1: Install System Dependencies (macOS only) - CRITICAL STEP!

**⚠️ WARNING: This is the most error-prone step. Follow it exactly or you'll get confusing errors later.**

**What are system dependencies?** System dependencies are essential software components or libraries that your operating system needs to run certain applications. Unlike Python dependencies, which are packages required by Python programs, system dependencies are required by the system itself or by applications that interact closely with the system, such as WeasyPrint. These dependencies often include C libraries like cairo, pango, and gdk-pixbuf, which are necessary for rendering graphics and processing images.

**What happens if I skip this step?** When you try to `pip install -r requirements.txt` later, you'll see scary error messages like:
- `error: Microsoft Visual C++ 14.0 is required`
- `Failed building wheel for weasyprint`
- `No module named '_cairo'`
- `cairo >= 1.15.4 is required`

### Install Homebrew (if you don't have it)

**What is Homebrew?** Think of it like the Mac App Store, but for developer tools and system dependencies. Homebrew is a package manager for macOS that simplifies the installation of software and system libraries. By using Homebrew, you can quickly set up the necessary C libraries for WeasyPrint, ensuring everything is installed correctly and reducing the risk of errors during setup.

**How do I know if I have it?** Open Terminal and type:
```bash
brew --version
```

If you see a version number, you're good. If you see "command not found", install it:

```bash
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
```

### Install the Required System Libraries

**Why each one is needed:**
- **cairo**: Handles 2D graphics rendering (drawing text, shapes in PDFs)
- **pango**: Handles text layout and font rendering  
- **gdk-pixbuf**: Handles image processing
- **libffi**: Allows Python to talk to C libraries

Install all four at once:
```bash
brew install cairo pango gdk-pixbuf libffi
```

**What you'll see:** Homebrew will download and compile these libraries. This might take up to 10 minutes and you'll see lots of text scrolling by. This is normal.

**How to verify it worked:** After installation completes, check that they're installed:
```bash
brew list | grep -E "(cairo|pango|gdk-pixbuf|libffi)"
```

You should see all four names listed.

### Install Google Chrome

The scraping stage opens each article in a headless Chrome, driven by Selenium.
**Chrome has to be installed on the machine** — `pip` does not install a
browser, and `webdriver-manager` downloads only the driver, not Chrome itself.
Without it, the `scrape` stage fails on every article.

Download it from [google.com/chrome](https://www.google.com/chrome/) if it is
not already there.

---

## Step 2: Download the Project

### How to Get the Project Files on Your Computer

To work with this project, you need to get a copy of its files from GitHub onto your computer. This process is called "cloning" a repository. Here's how you can do it step-by-step:

1. **Install Git (if you don't have it):**
   - **What is Git?** Git is a tool that helps you download and manage code from the internet.
   - **How to check if you have it:** Open Terminal (on macOS) or Command Prompt (on Windows) and type:
     ```bash
     git --version
     ```
     If you see a version number, you have Git installed. If not, you'll need to install it.
   - **How to install Git:**
     - **macOS:** You can install Git using Homebrew by typing:
       ```bash
       brew install git
       ```
     - **Windows:** Download the installer from [git-scm.com](https://git-scm.com/) and follow the installation instructions.

2. **Clone the Repository:**
   - **What does "clone" mean?** Cloning is like making a copy of the project files from GitHub's server to your computer.
   - **How to clone:**
     - On the GitHub page of this repository, locate and click the green "Code" button.
     - Copy the URL that appears.
     - In your Terminal (macOS) or Command Prompt (Windows), navigate to your desired directory using the `cd` command. For example:
       ```bash
       cd path/to/your/folder
       ```
     - Execute the following command, substituting `URL` with the copied URL:
       ```bash
       git clone URL
       ```
     - Hit Enter to initiate the download of the project files to your system.

3. **Navigate to the Project Folder:**
   - After cloning, you need to go into the project folder to start working with the files.
   - Use the `cd` command to navigate into the project folder. For example, if the project folder is named `datacenter-news-clipper`, type:
     ```bash
     cd datacenter-news-clipper
     ```

Now you have a local copy of the project on your computer and are ready to start working with it!

---

## Step 3: Set Up Python Environment

### What is a Virtual Environment?

**Think of it as:** A separate, clean room in your computer for this project. It keeps all the project's dependencies isolated so they don't interfere with other Python projects on your computer, which might have different versions of the same dependencies.

**Why do we need it?** Different projects need different versions of libraries. A venv prevents conflicts and keeps everything organized.

### Create the Virtual Environment

```bash
python -m venv venv
```

**What just happened?** You created a folder called `venv` that will store all the project's Python dependencies.

> **⚠️ If you skipped Step 1, or Homebrew is not an option on your machine,
> this exact command produces a broken project.** It installs WeasyPrint fine
> and then fails at import with `cannot load library 'libpango-1.0-0'`.
>
> The second route is conda, which brings `libpango` and `libcairo` itself. This
> is how the machine the program was written on is set up — it has no Homebrew.
> Create the environment once, then build the venv from *its* Python:
>
> ```bash
> conda create -p ~/.clipping247-python -c conda-forge python=3.12 pango cairo
> ~/.clipping247-python/bin/python3 -m venv venv
> ```
>
> Either route works. **Mixing them does not.**
>
> On Apple Silicon with the Homebrew route, if it still fails, Homebrew installs
> into `/opt/homebrew/lib` and WeasyPrint does not look there. Add
> `PKG_CONFIG_PATH=/opt/homebrew/lib/pkgconfig` to your `.env` (Step 5).

### Activate the Virtual Environment

From your project folder, run:
```bash
source venv/bin/activate
```

**How do I know it's working?** You should see `(venv)` at the beginning of your terminal prompt.

---

## Step 4: Install Python Dependencies

**What is requirements.txt?** A shopping list for code. It lists all the Python libraries this project needs installed in its environment to work.

**Why do we install them in the venv?** So they're only available for this project and don't mess with your other Python projects.

### Install All Required Libraries

```bash
pip install -r requirements.txt
```

**What just happened?** Python downloaded the 11 libraries listed in
`requirements.txt`, plus everything those depend on — about 160 packages and
1.5 GB in `venv/`. That is normal, and `venv/` is not in the repository.

**Which Python?** It is developed and run on **Python 3.12**. Anything from 3.10
up should work; below that, it will not.

**If you get errors here:** Make sure you completed Step 1 (system dependencies) and Step 3 (activated venv).

---

## Step 5: Configure .env file

### What is a .env File?

**Think of it as:** A file that stores secret information (like passwords or API keys) that the program needs but shouldn't be shared publicly. (That's why I didn't include it in the public project you downloaded)

**What is an API key?** It's like a password that lets this program talk to OpenAI's services. Each time the program uses AI features, it costs money.

**Why is this separate?** Because API keys are personal and should never be shared or uploaded to the internet.

### Set Up Your .env File

There is a template in the repository. Copy it and fill it in:

```bash
cp .env.example .env
```

The only variable the program requires is `OPENAI_API_KEY`. Ask whoever runs the
project at 247 for a key on the **company account** — not a personal one, which
dies with the person who created it.

```
OPENAI_API_KEY=your_actual_api_key_here
```

`.env.example` also documents `PKG_CONFIG_PATH`, which only matters if the PDF
fails to build (see Step 3).

**CRITICAL:** Never share this file with anyone. It's connected to a credit card and costs money every time it's used.

---

## Step 6: Add the Client's Logo (optional)

Everything the program needs to run is in the repository. One file is not: the
client's logo, `configs/247.original.jpg`. It is a brand asset and this
repository is public, so it is deliberately left out.

**The program runs without it.** The PDF is generated complete, without the
image in the header, and the program prints a warning saying the file is
missing. Ask whoever already has it for a copy and drop it in `configs/` when
you need the branded edition.

(Until 23 Sep 2026 that warning did not exist: WeasyPrint silently drops the
image and returns a valid PDF, so a logo-less edition could be sent to the
client unnoticed. The warning is now printed by the program itself.)

---

## Setup Troubleshooting

**Issue**: "brew: command not found"
**Solution**: Homebrew isn't installed. Go back to Step 1.

**Issue**: "Error: Cannot install cairo because conflicting formulae are installed"
**Solution**: You have old versions. Update them:
```bash
brew update
brew upgrade cairo pango gdk-pixbuf libffi
```

**Issue**: Installation seems stuck
**Solution**: Be patient. Compiling C libraries takes time. If it's been over 20 minutes, press Ctrl+C and try again, or ask ChatGPT if you're doing it right.

**Issue**: Permission errors
**Solution**: Don't use `sudo` with Homebrew. Fix permissions instead:
```bash
sudo chown -R $(whoami) $(brew --prefix)/*
```

**Issue**: `No module named '...'` when running Python
**Solution**: Make sure venv is activated (`source venv/bin/activate`) and you ran `pip install -r requirements.txt`

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

The prompt starts showing `(venv)`. There is no Run button configured in this
repository — no `.vscode/launch.json`, and `.vscode/` is gitignored — so run
things from the terminal.

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

Read what the program prints at the end. One warning matters more than the rest:

```
🚨 RESUMOS CITAM NÚMERO QUE NÃO ESTÁ NA MATÉRIA
```

It means a summary quotes a figure the program could not find anywhere in the
article. **Open the link and check the number before sending.** On the
21 Sep 2026 edition, three published figures did not exist in the source.

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
| `cannot load library 'libpango-1.0-0'` | Step 1 / Step 3. The venv was built without pango and cairo |
| OpenAI API error | `.env` missing or the key is wrong. `cp .env.example .env` |
| Chrome or driver errors in `scrape` | Google Chrome is not installed. Step 1 |
| `(venv)` not showing | Run `source venv/bin/activate` from the project folder |
| PDF has no logo in the header | `configs/247.original.jpg` is missing. Step 6 |
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

This repository is public. Three things are kept out on purpose:

- **`.env`** — the OpenAI key, tied to a credit card.
- **`configs/247.original.jpg`** — the client's logo, a brand asset.
- **`output/archive/`** — full text of third-party articles, and the editions
  already corrected by hand for the client.

Everything else is here, including the PDF template, so a clone builds a
complete edition.

---

## Security Reminder

The `.env` file contains an API key connected to a credit card. **NEVER**:
- Share it with anyone
- Upload it to GitHub
- Take screenshots of it
- Leave it visible anywhere
