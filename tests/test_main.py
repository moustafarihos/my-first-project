from main import add_task, complete_task, format_tasks, remove_task


def test_add_task():
    tasks = add_task([], "Buy milk")
    assert tasks == [{"text": "Buy milk", "done": False}]


def test_complete_task():
    tasks = [{"text": "Buy milk", "done": False}]
    complete_task(tasks, 0)
    assert tasks[0]["done"] is True


def test_remove_task():
    tasks = [{"text": "Buy milk", "done": False}]
    remove_task(tasks, 0)
    assert tasks == []


def test_format_tasks_empty():
    assert format_tasks([]) == "No tasks yet."


def test_format_tasks_with_items():
    tasks = [{"text": "Buy milk", "done": False}, {"text": "Walk dog", "done": True}]
    output = format_tasks(tasks)
    assert "[ ] 0: Buy milk" in output
    assert "[x] 1: Walk dog" in output
