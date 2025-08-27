#!/usr/bin/env python3
"""
Setup script for Gate.io Arbitrage Suite
Production deployment for Hummingbot 2.x
"""

from setuptools import setup, find_packages
from pathlib import Path

# Read README for long description
readme_file = Path(__file__).parent / "README.md"
long_description = readme_file.read_text(encoding="utf-8") if readme_file.exists() else ""

# Read requirements
requirements_file = Path(__file__).parent / "requirements.txt"
requirements = []
if requirements_file.exists():
    with open(requirements_file, 'r') as f:
        requirements = [
            line.strip() for line in f.readlines() 
            if line.strip() and not line.startswith('#')
        ]

setup(
    name="gate-arbitrage-suite",
    version="1.0.0",
    description="Production-grade arbitrage suite for Gate.io with 75% fee rebate optimization",
    long_description=long_description,
    long_description_content_type="text/markdown",
    author="Gate.io Arbitrage Suite",
    author_email="support@example.com",
    url="https://github.com/yourusername/gate-arbitrage-suite",
    
    packages=find_packages(),
    include_package_data=True,
    package_data={
        "": ["*.yml", "*.yaml", "*.json", "*.txt", "*.md"],
        "conf": ["**/*.yml", "**/*.yaml"],
        "webui": ["**/*"],
        "tests": ["**/*.py"]
    },
    
    python_requires=">=3.11",
    install_requires=requirements,
    
    extras_require={
        "dev": [
            "black>=22.0.0",
            "flake8>=5.0.0", 
            "mypy>=0.991",
            "pytest>=7.0.0",
            "pytest-asyncio>=0.20.0"
        ],
        "monitoring": [
            "prometheus-client>=0.15.0",
            "grafana-api>=1.0.3"
        ]
    },
    
    entry_points={
        "console_scripts": [
            "gate-arb-install=scripts.install:main",
            "gate-arb-deploy=scripts.deploy:main"
        ]
    },
    
    classifiers=[
        "Development Status :: 5 - Production/Stable",
        "Intended Audience :: Financial and Insurance Industry",
        "Topic :: Office/Business :: Financial :: Investment",
        "License :: OSI Approved :: Apache Software License",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3.12",
        "Operating System :: OS Independent",
        "Environment :: Console",
        "Framework :: AsyncIO"
    ],
    
    keywords="arbitrage trading cryptocurrency gate.io hummingbot algorithmic-trading",
    project_urls={
        "Documentation": "https://github.com/yourusername/gate-arbitrage-suite/wiki",
        "Source": "https://github.com/yourusername/gate-arbitrage-suite",
        "Tracker": "https://github.com/yourusername/gate-arbitrage-suite/issues"
    }
)