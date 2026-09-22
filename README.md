# Data Center News Clipper

**What this does:** This tool automatically finds news articles about data centers, sorts them into categories, and creates a nice PDF report for you.

**How it works:** Setup once, then run one command whenever you want a new report.

---

# 🔧 ONE-TIME SETUP

**Do this section ONCE when you first get the project. You'll never need to repeat these steps.**

## Setup Steps Index

1. [Install System Dependencies (macOS only) - CRITICAL STEP!](#step-1-install-system-dependencies-macos-only---critical-step)
2. [Download the Project from Github](#step-2-download-the-project)
3. [Set Up Python Virtual Environment](#step-3-set-up-python-virtual-environment)
4. [Install Python Dependencies](#step-4-install-python-dependencies)
5. [Configure Environment .env File](#step-5-configure-environment-variables-optional)

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

> **⚠️ On Pedro's Mac, this exact command produces a broken project.**
> There is no Homebrew on that machine, so Step 1 never happened there. The
> libraries WeasyPrint needs (`libpango`, `libcairo`) come from a dedicated conda
> environment instead, and the venv has to be created from *its* Python:
>
> ```bash
> /Users/pedroandrade/.clipping247-python/bin/python3 -m venv venv
> ```
>
> A venv built with the `python3` on the PATH there installs WeasyPrint fine and
> then fails at import with `cannot load library 'libpango-1.0-0'`. Either route
> works; mixing them does not.

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

**What just happened?** Python downloaded and installed about 9 different libraries that this project needs to function.

**If you get errors here:** Make sure you completed Step 1 (system dependencies) and Step 3 (activated venv).

---

## Step 5: Configure .env file

### What is a .env File?

**Think of it as:** A file that stores secret information (like passwords or API keys) that the program needs but shouldn't be shared publicly. (That's why I didn't include it in the public project you downloaded)

**What is an API key?** It's like a password that lets this program talk to OpenAI's services. Each time the program uses AI features, it costs money.

**Why is this separate?** Because API keys are personal and should never be shared or uploaded to the internet.

### Set Up Your .env File

You should create a file named simply `.env` in the main project folder (yes, starting with a dot). Ask Leo for the API key uesd for the AI models employed in this project. You will write it to the `.env` file

The `.env` file should look like this:
```
OPENAI_API_KEY=your_actual_api_key_here
```

**CRITICAL:** Never share this file with anyone. It's connected to a credit card and costs money every time it's used.

---

## Step 6: Add Required Files

You should receive other miscallenous configuration files, which you should place in the `configs/` folder.

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

**Do this section EVERY TIME you want to generate a news report.**

**Assumption:** You're using an IDE like VS Code, Cursor, or PyCharm (which most people do). If you prefer Terminal, you'll need to activate the venv manually first.

## Generate a News Report

1. **Open the project folder** in your IDE
2. **Run the script** by clicking the "Run" button or pressing F5 on `main.py`

**That's it!** The script is running, now just wait for the magic. You will know it's done when you see these messages:

```
Wrote clippings JSON to output/clippings.json
Generated PDF clipping at output/clippings_output.pdf
```

## What Happens When You Run

**The program will:**
1. Search for news articles about data centers
2. Use AI to classify and filter them
3. Generate summaries
4. Create a PDF report

**Wait time:** This typically takes up to 10 minutes depending on how many articles it finds.

**Your results:**
- **Raw data:** `output/clippings.json` 
- **PDF report:** `output/clippings_output.pdf`

**Remember:** Every time you run this, it uses the OpenAI API which costs money. Use responsibly!

---

## Edit Your Report (Optional)

> **Edits made directly in `output/clippings.json` are lost on the next run.**
> The durable place for them is `configs/overrides.json`, which is applied over
> the pipeline's output every time the PDF is built. See `LEIA-ME.md` for the
> blocks and their format. The instructions below still work for a one-off
> rebuild you are about to send and never repeat.

### Remove Articles

Open `output/clippings.json` and delete the JSON objects for articles you don't want.

### Add Articles

Use ChatGPT with this prompt:

```
"Create a valid JSON object for a news clipping. Use exactly this format:

{
"title": "Article title here",
"source": "Source name", 
"url": "https://article-url.com",
"pubDate": "DD MMM",
"class": "relevant",
"category": "clientes",
"summary": "Detailed summary of the news piece in Portuguese. ~100 words, focusing on actual facts, happenings, decisions, numbers, not opinions."
}

Category options (EXACTLY these five, lowercase — anything else and the
article is silently missing from the PDF):
- clientes (cloud providers / clients)
- competidores (competing operators)
- governo (regulation and policy)
- inovação (technology and infrastructure advances)
- outros (everything else that still matters)

Create JSON for this article: [PASTE ARTICLE URL/TEXT HERE]"
```

Copy the JSON and paste it into your `clippings.json` file.

### Regenerate Just the PDF

After editing the JSON, regenerate only the PDF:

Open the `services/pdf_builder.py` file in your code editor and run it directly from there.

---

## Usage Troubleshooting

| Problem | Solution |
|---------|----------|
| `No module named '...'` | Make sure venv is activated (`source venv/bin/activate`) |
| OpenAI API error | Check that `.env` file is in the main folder with correct API key |
| `(venv)` not showing | Run `source venv/bin/activate` from the project folder |
| PDF generation fails | Check that you have both files in `configs/` folder |

---

## File Locations

- **`.env`**: Main folder (same level as `main.py`) - KEEP PRIVATE!
- **`venv/`**: Main folder (same level as `main.py`) - created during setup
- **Output files**: `output/clippings.json` and `output/clippings_output.pdf`
- **Config files**: `configs/` folder

---

## Security Reminder

The `.env` file contains an API key connected to a credit card. **NEVER**:
- Share it with anyone
- Upload it to GitHub
- Take screenshots of it
- Leave it visible anywhere

Treat it like your banking password! 