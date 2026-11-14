from setuptools import setup, find_packages

setup(
    name="enigma-sac-summarizer",
    version="1.0.0",
    description="Evidence-based dataset summarization for NASA PSI Combustion Science datasets",
    packages=find_packages(where="src"),
    package_dir={"": "src"},
    python_requires=">=3.9",
    install_requires=[
        "asyncpg>=0.29.0",
        "sqlalchemy[asyncio]>=2.0.25",
        "pgvector>=0.2.5",
        "pydantic>=2.5.3",
        "pydantic-settings>=2.1.0",
        "httpx>=0.26.0",
        "pandas>=2.1.4",
        "numpy>=1.26.2",
        "scipy>=1.11.4",
        "tenacity>=8.2.3",
        "structlog>=24.1.0",
        "python-json-logger>=2.0.7",
        "prometheus-client>=0.19.0",
        "pyyaml>=6.0.1",
        "click>=8.1.7",
    ],
    extras_require={
        "dev": [
            "pytest>=7.4.3",
            "pytest-asyncio>=0.21.1",
            "pytest-cov>=4.1.0",
            "ruff>=0.1.6",
            "mypy>=1.7.1",
        ],
    },
    entry_points={
        "console_scripts": [
            "summarizer=cli:cli",
        ],
    },
)