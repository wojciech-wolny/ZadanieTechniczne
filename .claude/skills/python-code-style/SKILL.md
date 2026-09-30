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

1. **KISS (keep it simple):** choose the most direct solution a reader understands at first glance. Plain functions before a class hierarchy, a dictionary before a plugin system, a `for` loop before a clever trick. A dataclass is the simple form when several fields belong together. A protocol is the simple form when the caller needs the methods and not one concrete class.
2. **YAGNI (you aren't gonna need it):** build only what a current requirement or test needs. No unused parameters, hooks, config options, base classes with one child, or "future proof" layers. The task will grow, but extension points are added when the second variant arrives, except the algorithm and sink registries required by the task.
3. **DRY (don't repeat yourself):** every piece of knowledge has one home (wire format, ASCII mapping, limits, defaults). Extract duplicated logic on the third repetition (rule of three); two similar lines are cheaper than a wrong abstraction.
4. **Single responsibility:** a function does one thing, a module has one reason to change. Parsing, processing and I/O live apart.
5. **Composition over inheritance:** combine small objects (a task owns an algorithm and a sink). Inherit only for a real "is a" relation with shared state, such as `WindowAlgorithm`.
6. **Fail fast:** validate at the boundary (Pydantic, CLI arguments) and raise clear errors; inner code trusts validated input and does not check it again.
7. **Explicit over implicit:** no hidden global state, no magic values; name constants (`SAMPLE_FORMAT = "<d"`) and pass dependencies as parameters.
8. **Named steps:** the function name is the comment for that action. The caller stays a short flat sequence. Extract a step when the body would nest another level or grow into a long block, even if that function is used once. Leave an obvious one or two line check inline. This split is for readability, so it does not wait for the third copy.
9. **One object for a batch of values:** three or more related fields that are passed or returned together belong on a `@dataclass`. Pass that object instead of a long argument list or a tuple whose positions have no names. Use a `typing.Protocol` when several classes share the same methods and the caller must not depend on one concrete class, as `Algorithm` and `Sink` already do. Two loose values can stay as parameters. A single number does not need a class. REST bodies stay Pydantic models.

## Rules

1. **No comments in code.** The only allowed documentation is a docstring.
2. **Docstring format:** one sentence of explanation, then only `:param:`, `:return:`, `:raises:` or `:attr:` fields when they add value.
3. **No "-" characters in docstrings or comments.** Rephrase instead of using dashes or hyphens (write "non overlapping", "read only", "end to end").
4. **Typing is essential** for public functions, methods, class attributes and return values. Skip it for obvious local variables.
5. **Prefer `if` over `try/except`.** Check the condition first. Use `try/except` only when there is no way to check beforehand (network, OS, parsing external input), and catch the narrowest exception.
6. **Functions and methods are named as actions:** `read_samples`, `create_task`, `send_batch`, `calculate_slope`. Never `data`, `processor`, `handle`.
7. **Functions replace comments and deep blocks.** Each action is its own function. The caller calls those functions in order at one indentation level. Split a `while` or `with` body that stacks several `if` blocks, carries several flags, or no longer reads as a few steps. Do not wrap a single obvious expression.
8. **Dataclasses and protocols replace batches of loose values.** When a function would take or return three or more related values, put those fields on a `@dataclass` and pass that one argument. Prefer a `Protocol` over a shared base class when the point is the method set. Do not pack the same batch into a `tuple` just to keep the signature short.
9. **Variables are human readable:** `sample_count`, `window_size`, `active_tasks`. No single letters except `x`, `y` in math, no abbreviations like `cnt`, `tmp`, `buf`.
10. **Prefer a regular `for` loop over a comprehension** when the comprehension has a condition, nesting or a non trivial expression. Readable beats short one liners.
11. **Keep it laconic:** small functions, early returns, no dead code, no speculative abstractions.
12. Line length 99, imports ordered stdlib, third party, local.

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

## Named steps

The caller lists the actions. Each helper name is the comment for that action. Related fields travel on one dataclass instead of a long parameter list.

```python
@dataclass
class TextCarry:
    """Unfinished token and skip state carried between text chunks.

    :attr pending: unfinished token
    :attr skipping_long_token: whether an overlong token continues
    :attr skipped_count: tokens skipped so far in this pass
    """

    pending: str = ""
    skipping_long_token: bool = False
    skipped_count: int = 0


def next_text_tokens(carry: TextCarry, chunk: str) -> tuple[list[str], TextCarry]:
    """Take finished tokens from one read and carry the unfinished tail forward.

    :param carry: unfinished token and long token state from the previous chunk
    :param chunk: characters just read
    :return: finished tokens and the state to keep for the next chunk
    """
    text = carry.pending + chunk
    tokens = text.split()
    tokens, skipping_long_token = discard_continued_long_token(
        text,
        tokens,
        carry.skipping_long_token,
    )
    tokens, pending = hold_back_unfinished_token(text, tokens)
    pending, skipping_long_token, skipped_long = skip_pending_over_limit(
        pending,
        skipping_long_token,
    )
    return tokens, TextCarry(
        pending,
        skipping_long_token,
        carry.skipped_count + skipped_long,
    )
```

A protocol names the methods a caller needs. `Algorithm` and `Sink` are the pattern: the registry stores the protocol, and each concrete class supplies the methods.

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
- [ ] Nested or long blocks are split into functions, and the caller is a short flat sequence
- [ ] Three or more related values travel on a dataclass, and shared method sets use a protocol
- [ ] No hard to read comprehensions or one liners
