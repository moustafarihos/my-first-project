# my-first-project

My first repository on GitHub, created while learning the basics of git and GitHub.

## Setup

```
python -m venv .venv
.venv\Scripts\python.exe -m pip install -r requirements.txt
```

## Run

A simple command-line to-do list.

```
.venv\Scripts\python.exe main.py add "Buy milk"
.venv\Scripts\python.exe main.py list
.venv\Scripts\python.exe main.py done 0
.venv\Scripts\python.exe main.py remove 0
```

## Test

```
.venv\Scripts\python.exe -m pytest
```

## Options bot

`options_bot/` is a starter bot that sells Bitcoin put spreads on the Deribit testnet, where all money is fake. See [options_bot/README.md](options_bot/README.md).
