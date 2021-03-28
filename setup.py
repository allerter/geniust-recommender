import pathlib

from setuptools import find_packages, setup

here = pathlib.Path(__file__).parent.resolve()

with open(here / "runtime.txt", "r") as f:
    runtime = f.read().replace("python-", "")


with open(here / "gtr" / "VERSION") as version_file:
    version = version_file.read().strip()

readme_file = here / "README.md"

extras_require = {
    "checks": [
        "tox>=3.23.0,<3.24.0",
        "mypy==0.812",
        "black==20.8b1",
        "flake8>=3.9.0,<4.0.0",
        "flake8-bugbear>=21.3.2,<21.4.0",
        "isort>=5.8.0,<5.9.0",
    ],
    "tests": [
        "pytest>=6.2.2,<6.3.0",
        "pytest-asyncio==0.14.0",
        "pytest-httpx==0.11.0",
        "coverage>=5.5,<5.6",
    ],
}

extras_require["dev"] = extras_require["checks"] + extras_require["tests"]

setup(
    name="genisut-recommender",
    author="allerter",
    license="MIT",
    description="Genre-based music recommender.",
    long_description=readme_file.read_text(),
    long_description_content_type="text/markdown",
    url="https://github.com/allerter/geniust-recommender",
    version=version,
    packages=find_packages(
        exclude=(
            "tests",
            "tests.*",
        )
    ),
    extras_require=extras_require,
    python_requires=">=" + runtime,
)
