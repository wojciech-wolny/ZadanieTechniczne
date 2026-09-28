---
name: python-code-style
description: Enforces the project Python code style (PEP 8, docstring only documentation, readable naming, simple control flow). Use whenever writing, editing, refactoring or reviewing any Python code in this repository.
---

# Python Code Style

Simple, laconic, human readable code. PEP 8 is the base for formatting.

## Python version

Target **Python 3.13.7**. Set `requires-python = ">=3.13"` in `pyproject.toml` and `target-version = "py313"` for ruff.

Use modern syntax available in 3.13:

1. `X | None` and builtin generics `list[float]`, `dict[str, Task]`. Never `Optional`, `List`, `Dict`.
2. Annotations are evaluated at definition time. Do not add `from __future__ import annotations`. Quote a forward reference only when the name is not yet defined.
3. `type` statement for aliases: `type Samples = list[float]`.
4. PEP 695 generics: `class Registry[ItemType]:` and `def find_first[ItemType](items: list[ItemType]) -> ItemType:`, no `TypeVar`.
5. `match` statement when choosing between several named variants.
6. `except (ValueError, TypeError):` with parentheses, and only when `except` is unavoidable.
7. `typing.Self`, `typing.override` for methods returning the instance or overriding a base.

## Design principles

Apply in this order when they conflict: KISS, then YAGNI, then DRY.

1. **KISS (keep it simple):** choose the most direct solution a reader understands at first glance. Plain functions before classes, a dictionary before a plugin system, a `for` loop before a clever trick.
2. **YAGNI (you aren't gonna need it):** build only what a current requirement or test needs. No unused parameters, hooks, config options, base classes with one child, or "future proof" layers. The task will grow, but extension points are added when the second variant arrives, except the algorithm and sink registries required by the task.
3. **DRY (don't repeat yourself):** every piece of knowledge has one home (wire format, ASCII mapping, limits, defaults). Extract duplicated logic on the third repetition (rule of three); two similar lines are cheaper than a wrong abstraction.
4. **Single responsibility:** a function does one thing, a module has one reason to change. Parsing, processing and I/O live apart.
5. **Composition over inheritance:** combine small objects (a task owns an algorithm and a sink). Inherit only for a real "is a" relation with shared state, such as `WindowAlgorithm`.
6. **Fail fast:** validate at the boundary (Pydantic, CLI arguments) and raise clear errors; inner code trusts validated input and does not check it again.
7. **Explicit over implicit:** no hidden global state, no magic values; name constants (`SAMPLE_FORMAT = "<d"`) and pass dependencies as parameters.

## Rules

1. **No comments in code.** The only allowed documentation is a docstring.
2. **Docstring format:** one sentence of explanation, then only `:param:`, `:return:`, `:raises:` or `:attr:` fields when they add value.
3. **No "-" characters in docstrings or comments.** Rephrase instead of using dashes or hyphens (write "non overlapping", "read only", "end to end").
4. **Typing is essential** for public functions, methods, class attributes and return values. Skip it for obvious local variables.
5. **Prefer `if` over `try/except`.** Check the condition first. Use `try/except` only when there is no way to check beforehand (network, OS, parsing external input), and catch the narrowest exception.
6. **Functions and methods are named as actions:** `read_samples`, `create_task`, `send_batch`, `calculate_slope`. Never `data`, `processor`, `handle`.
7. **Variables are human readable:** `sample_count`, `window_size`, `active_tasks`. No single letters except `x`, `y` in math, no abbreviations like `cnt`, `tmp`, `buf`.
8. **Prefer a regular `for` loop over a comprehension** when the comprehension has a condition, nesting or a non trivial expression. Readable beats short one liners.
9. **Keep it laconic:** small functions, early returns, no dead code, no speculative abstractions.
10. Line length 99, imports ordered stdlib, third party, local.

## Example

```python
def calculate_slope(window: list[float]) -> float:
    """Calculate the least squares slope of samples placed at positions 0..N.

    :param window: sample values used as y coordinates
    :return: slope of the fitted line
    :raises ValueError: when the window has fewer than two samples
    """
    sample_count = len(window)
    if sample_count < 2:
        raise ValueError("window needs at least two samples")

    mean_x = (sample_count - 1) / 2
    mean_y = sum(window) / sample_count

    numerator = 0.0
    denominator = 0.0
    for position, value in enumerate(window):
        numerator += (position - mean_x) * (value - mean_y)
        denominator += (position - mean_x) ** 2

    return numerator / denominator
```

## Avoid

```python
# compute slope - OLS
def calc(w):
    try:
        n = len(w); mx = (n-1)/2; my = sum(w)/n
        return sum((i-mx)*(v-my) for i, v in enumerate(w)) / sum((i-mx)**2 for i in range(n))
    except ZeroDivisionError:
        return 0
```

## Class example

```python
class AverageAlgorithm:
    """Produce the arithmetic mean of every complete window of samples.

    :attr window_size: number of samples in one window
    :attr windows_processed: number of complete windows so far
    """

    def __init__(self, window_size: int) -> None:
        self.window_size = window_size
        self.windows_processed = 0
        self.last_result: float | None = None
        self._window: list[float] = []

    def process_sample(self, sample: float) -> float | None:
        """Add a sample and return the window mean when the window is complete.

        :param sample: incoming sample value
        :return: mean of the window or None when the window is not complete
        """
        self._window.append(sample)
        if len(self._window) < self.window_size:
            return None

        self.last_result = sum(self._window) / self.window_size
        self.windows_processed += 1
        self._window.clear()
        return self.last_result
```

## Checklist before finishing

- [ ] KISS: the simplest working solution, nothing clever
- [ ] YAGNI: no code without a current requirement or test using it
- [ ] DRY: constants and rules defined once, no logic repeated three times
- [ ] No `#` comments anywhere
- [ ] Every public function and class has a one sentence docstring
- [ ] No "-" inside docstrings
- [ ] Public signatures are typed
- [ ] No `try/except` where an `if` check is possible
- [ ] Names read as actions (functions) and plain words (variables)
- [ ] No hard to read comprehensions or one liners
