from setuptools import setup

# Read pyproject.toml
with open('pyproject.toml', 'r', encoding='utf-8') as f:
    import tomli
    pyproject = tomli.load(f)

setup(**pyproject['project'])