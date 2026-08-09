from setuptools import find_packages, setup


setup(
    name="mvd-insights-edge-agent",
    version="0.1.0",
    description="Portable edge runtime for MVD Insights device integrations.",
    package_dir={"": "src"},
    packages=find_packages(where="src"),
    install_requires=[
        "pyserial>=3.5,<4",
        "python-dotenv>=1.0,<2",
        "requests>=2.31,<3",
    ],
    entry_points={
        "console_scripts": [
            "mvd-edge-agent=mvd_edge.app:main",
        ],
    },
    python_requires=">=3.9",
)
