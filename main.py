import argparse
import json
import sys
from pathlib import Path

TASKS_FILE = Path(__file__).parent / "tasks.json"


def load_tasks(path: Path = TASKS_FILE) -> list[dict]:
    if not path.exists():
        return []
    return json.loads(path.read_text())


def save_tasks(tasks: list[dict], path: Path = TASKS_FILE) -> None:
    path.write_text(json.dumps(tasks, indent=2))


def add_task(tasks: list[dict], text: str) -> list[dict]:
    tasks.append({"text": text, "done": False})
    return tasks


def complete_task(tasks: list[dict], index: int) -> list[dict]:
    tasks[index]["done"] = True
    return tasks


def remove_task(tasks: list[dict], index: int) -> list[dict]:
    del tasks[index]
    return tasks


def format_tasks(tasks: list[dict]) -> str:
    if not tasks:
        return "No tasks yet."
    lines = []
    for i, task in enumerate(tasks):
        mark = "x" if task["done"] else " "
        lines.append(f"[{mark}] {i}: {task['text']}")
    return "\n".join(lines)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="A simple to-do list.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    add_parser = subparsers.add_parser("add", help="Add a task")
    add_parser.add_argument("text", help="Task description")

    subparsers.add_parser("list", help="List tasks")

    done_parser = subparsers.add_parser("done", help="Mark a task as done")
    done_parser.add_argument("index", type=int, help="Task index")

    remove_parser = subparsers.add_parser("remove", help="Remove a task")
    remove_parser.add_argument("index", type=int, help="Task index")

    return parser


def main(argv: list[str] | None = None) -> None:
    parser = build_parser()
    args = parser.parse_args(argv)
    tasks = load_tasks()

    if args.command == "add":
        add_task(tasks, args.text)
        save_tasks(tasks)
        print(f"Added: {args.text}")
    elif args.command == "list":
        print(format_tasks(tasks))
    elif args.command == "done":
        complete_task(tasks, args.index)
        save_tasks(tasks)
        print(f"Marked task {args.index} as done")
    elif args.command == "remove":
        remove_task(tasks, args.index)
        save_tasks(tasks)
        print(f"Removed task {args.index}")


if __name__ == "__main__":
    main(sys.argv[1:])
