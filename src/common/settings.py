"""Load operator settings from the env file."""

import os

from dotenv import dotenv_values

ENV_FILE = ".env"


def load_env_file() -> None:
    """Fill unset environment variables from the env file.

    A variable already set in the shell stays.
    """
    for key, value in read_env_file(ENV_FILE).items():
        os.environ.setdefault(key, value)


def read_env_file(name: str) -> dict[str, str]:
    """Read one env file with python dotenv.

    :param name: env file path
    :return: names and values
    """
    loaded: dict[str, str] = {}
    for key, value in dotenv_values(name).items():
        if value is not None:
            loaded[key] = value
    return loaded
