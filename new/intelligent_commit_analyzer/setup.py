from setuptools import setup, find_packages

setup(
    name="intelligent-commit-analyzer",
    version="1.0.0",
    packages=find_packages(),
    install_requires=[
        "click>=8.0",
        "gitpython>=3.1",
        "google-genai>=0.1.0",
        "networkx>=3.0",
        "pyyaml>=6.0",
        "pydantic>=2.0",
        "ratelimit>=2.2",
        "tenacity>=8.0",
        "unidiff>=0.7",
        "aiofiles>=23.0",
        "httpx>=0.24",
    ],
    entry_points={
        "console_scripts": [
            "commit-analyzer=intelligent_commit_analyzer:main",
        ],
        "commit_analysis.plugins": [
            "security=intelligent_commit_analyzer:SecurityAnalysisPlugin",
        ],
    },
    python_requires=">=3.8",
)