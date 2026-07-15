from setuptools import setup, find_packages

setup(
    name="minilua",
    version="1.1.0",
    description="A Lua / Luau source code minifier supporting Lua 5.1–5.4 and Luau",
    author="Ardo",
    python_requires=">=3.8",
    packages=find_packages(),
    install_requires=[
        "click>=8.0",
        "colorama>=0.4",
    ],
    entry_points={
        "console_scripts": [
            "minilua=lua_minifier.cli:main",
        ],
    },
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
        "Topic :: Software Development :: Build Tools",
        "Topic :: Text Processing :: Filters",
    ],
)
