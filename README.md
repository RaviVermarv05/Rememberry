# Rememberry 🇩🇪

**A German vocabulary practice app for building a stronger, more usable vocabulary beyond the basics.**

Rememberry helps you review German words in a structured way, using vocabulary grouped by chapter and practice/review tools. The project uses a JavaScript frontend and a Python backend.

> **Status note:** This README is based on the project structure and features currently known to the maintainer. Confirm the exact entry-point names, environment-variable names, and optional features against the current code before treating this as a release-ready setup guide.

## Contents

- [What you can do](#what-you-can-do)
- [How the app is organised](#how-the-app-is-organised)
- [Run Rememberry locally](#run-rememberry-locally)
- [Choose the right entry point](#choose-the-right-entry-point)
- [Using the app](#using-the-app)
- [Configuration and API keys](#configuration-and-api-keys)
- [Troubleshooting](#troubleshooting)
- [Development notes](#development-notes)

## What you can do

- Practise German vocabulary from the project's word list.
- Work with vocabulary organised into chapters or ranges.
- Search and review words instead of only reading a static list.
- Use the available review and audio features where they are enabled in your current version.
- Explore AI-assisted vocabulary support if the optional Groq integration is configured.

The exact set of buttons and modes depends on the current frontend and backend files.

## How the app is organised

The main parts of the project are:

| File or folder | Responsibility |
|---|---|
| `app.py` | Application entry point, if this is the launcher used by your current checkout. |
| `api.py` | Flask API routes and requests from the frontend, where used. |
| `main.py` | Additional Python application or startup logic, depending on the current version. |
| `Data/word_list.py` | Vocabulary data used by the application. |
| `index.html` | Browser interface structure. |
| `app.js` | Frontend interactions and requests to the Python backend. |
| `requirements.txt` | Python packages required by the project. |

Keep the frontend and backend files in their expected relative locations. If you move a file or rename a folder, update any imports, file paths, and API URLs that refer to it.

## Run Rememberry locally

### 1. Install the prerequisites

You need:

- Git
- Python 3
- A browser
- A terminal (Terminal on macOS/Linux, or PowerShell on Windows)

Check that Python and Git are available:

```bash
python3 --version
git --version
```

On Windows, use `py --version` if `python` or `python3` is not recognised.

### 2. Clone the repository

```bash
git clone https://github.com/RaviVermarv05/Rememberry.git
cd Rememberry
```

If you already downloaded the project as a ZIP, extract it and open a terminal in the extracted `Rememberry` folder instead.

### 3. Create a virtual environment

**macOS / Linux**

```bash
python3 -m venv .venv
source .venv/bin/activate
```

**Windows PowerShell**

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
```

When the environment is active, the terminal usually shows `(.venv)` at the start of the prompt.

### 4. Install Python dependencies

From the project root, run:

```bash
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

If this fails because `requirements.txt` is missing or incomplete, do not install random packages one by one. Check the imports in the Python files and update the requirements file to match the actual code.

### 5. Configure optional secrets

If your checkout uses the Groq integration, obtain your own API key from Groq and configure it using the **exact environment-variable name read by the code**. Do not paste a real API key into `app.py`, `api.py`, `app.js`, or this README, and never commit `.env` files containing secrets.

If the code uses a `.env` file, install and configure the environment-loading package only if the project code supports it. A `.env.example` file with placeholder values is a good way to document required settings safely.

### 6. Start the application

From the project root, with the virtual environment active, try the intended launcher:

```bash
python app.py
```

If your current version instead starts through `api.py` or `main.py`, use the entry point documented in that file or its `if __name__ == "__main__":` block:

```bash
python api.py
```

or

```bash
python main.py
```

Do not start all three at once unless the code explicitly requires separate processes. Use the terminal output to identify the address and port the server reports.

### 7. Open it in your browser

Open the local URL printed in the terminal. For a Flask development server using its default port, that is commonly:

```text
http://127.0.0.1:5000
```

Use the actual address printed by your application if it differs. Leave the server terminal running while using the app; press `Ctrl+C` there to stop it.

## Choose the right entry point

| Goal | Command to try | Important detail |
|---|---|---|
| Start the main app | `python app.py` | Use this if `app.py` creates or runs the application. |
| Start the Flask API | `python api.py` | Use this if `api.py` contains the Flask app and its startup block. |
| Run another project launcher | `python main.py` | Use this only if `main.py` is the intended entry point in your checkout. |

If one command exits immediately, reports that a module cannot be imported, or starts a server on a different port, check that file's imports and startup block rather than guessing which command should run.

## Using the app

1. Start the Python application using the steps above.
2. Open the local URL shown in the terminal.
3. Choose the vocabulary chapter, range, or practice mode available in the interface.
4. Search for a word or begin a review session.
5. Use the available answer/review controls to continue through the words.
6. If audio or AI-assisted features are present, test them separately; they may need additional packages, internet access, or an API key.

For the most reliable first test, try a basic vocabulary or chapter view before testing optional AI or audio functionality.

## Configuration and API keys

- **Keep secrets out of Git.** Never commit API keys, passwords, personal data, or a real `.env` file.
- **Use your own key.** If an AI feature requires Groq, configure your own Groq API key locally.
- **Check the exact variable name.** The README should match the name used by the code (for example, the key passed to `os.getenv(...)`); do not assume a variable name.
- **Do not expose keys in the frontend.** Secret API keys belong on the Python/backend side, not in browser JavaScript.

## Troubleshooting

<details>
<summary><strong><code>python</code> or <code>python3</code> is not found</strong></summary>

Install Python 3, then reopen the terminal. On Windows, try `py` instead of `python3`.
</details>

<details>
<summary><strong><code>requirements.txt</code> is missing or installation fails</strong></summary>

Make sure the terminal is in the repository root. Upgrade pip and retry. If a package is still missing, check the import that failed and update `requirements.txt` to reflect the actual dependencies.
</details>

<details>
<summary><strong>The browser says the site cannot be reached</strong></summary>

- Confirm that the Python server is still running.
- Open the exact host and port printed in the terminal.
- If testing from a phone, both devices generally need to be on the same Wi-Fi network. `127.0.0.1` on the phone points to the phone itself, not your computer. The server may also need to bind to the computer's LAN interface, and the firewall must allow the connection.
</details>

<details>
<summary><strong>The page loads but vocabulary or API features fail</strong></summary>

Check the terminal for Python errors and the browser developer console for JavaScript errors. Confirm that the vocabulary data file exists at the path expected by the code and that the frontend is requesting the correct API endpoint.
</details>

<details>
<summary><strong>An AI or audio feature fails</strong></summary>

First test the core vocabulary flow. Then check whether the optional feature's dependencies are installed, whether internet access is available, and whether the required API key or audio tools are configured. Never share your API key when asking for help.
</details>

## Development notes

- Run commands from the repository root unless the code says otherwise.
- Activate `.venv` before installing packages or launching the app.
- After adding a Python dependency, update `requirements.txt` so another developer can reproduce the setup.
- Keep sample configuration in a file such as `.env.example`; keep real secrets local.
- If you change API routes in Python, update the corresponding request URLs in `app.js`.
- Test the main vocabulary flow after changing data files, backend routes, or frontend code.

---

**Maintainer:** [RaviVermarv05](https://github.com/RaviVermarv05)  
**Repository:** [RaviVermarv05/Rememberry](https://github.com/RaviVermarv05/Rememberry)
