# cpp-build-stamp

![GitHub License](https://img.shields.io/github/license/RobertSundling/cpp-build-stamp)
![GitHub issues](https://img.shields.io/github/issues/RobertSundling/cpp-build-stamp)
![GitHub last commit](https://img.shields.io/github/last-commit/RobertSundling/cpp-build-stamp)
![Static Badge](https://img.shields.io/badge/AI-AI%20Generated-BA1B1B)

A Python script that modifies C++ source files to include build timestamps, dates, version numbers, and auto-incrementing build numbers. Uses [libclang](https://pypi.org/project/libclang/) for robust C++ parsing to ensure modifications preserve code structure and comments.

## Table of Contents

<!-- @import "[TOC]" {cmd="toc" depthFrom=2 depthTo=6 orderedList=false} -->
<!-- code_chunk_output -->

- [Table of Contents](#table-of-contents)
- [Motivation](#motivation)
- [Acknowledgements](#acknowledgements)
- [Features](#features)
- [Prerequisites](#prerequisites)
- [Installation](#installation)
- [Usage](#usage)
  - [Basic Command Line Usage](#basic-command-line-usage)
    - [Arguments:](#arguments)
    - [Placeholders:](#placeholders)
    - [Options:](#options)
    - [Exit Code:](#exit-code)
  - [Example Usage](#example-usage)
- [Example Source File](#example-source-file)
- [Example CMake Integration](#example-cmake-integration)
- [License](#license)

<!-- /code_chunk_output -->


## Motivation

I previously used simple scripts that searched for patterns or regular expressions to embed build information in C++ projects. However, these scripts were not robust, and would occasionally fail due to file modifications between builds or conflicts with automated code formatters like clang-format. This would lead to the need for manual corrections or to stale build information.

To address these issues, this script leverages [libclang](https://pypi.org/project/libclang/) for robust C++ parsing. By fully understanding the code structure, it can safely modify C++ source files, even if they have been extensively modified. It preserves code integrity and compatibility with formatting tools.

This script uses [libclang](https://pypi.org/project/libclang/) to properly parse and understand C++ code of arbitrary complexity. It can therefore can make modifications properly.

## Acknowledgements

Rather than spending my own time writing this tool myself, I delegated it to various AI assistants. **This script was primarily written by Claude 3.5 Sonnet, ChatGPT 4o, and GitHub Copilot Codex.** This README.md file was written by Claude 3.5 Sonnet with revisions by GitHub Copilot Codex, Gemini 2.0 Flash, and some light final editing by me. All of this initial work was done in February 2025.

## Features

- Safely modifies C++ constants using libclang parsing
- Supports multiple placeholder types:
  - `{date}`: Current date (configurable format)
  - `{time}`: Current time (configurable format)
  - `{++}`: Auto-incrementing numbers
- Preserves code structure and formatting
- Works with namespaced and global variables
- Configurable timezone support
- CMake integration support

## Prerequisites

- Python 3.7+
- Python packages (found in [requirements.txt](requirements.txt)):
    - libclang
    - tzlocal
    - pytz

## Installation

1. Clone the repository:
   ```bash
   git clone https://github.com/RobertSundling/cpp-build-stamp.git
   cd cpp-build-stamp
   ```

2. It is often a good idea to create a virtual environment:
   ```bash
   python -m venv .venv
   source .venv/bin/activate  # On Linux/macOS
   .venv\Scripts\activate     # On Windows
   ```

3. Install required packages:
   ```bash
   pip install -r requirements.txt
   ```

## Usage

### Basic Command Line Usage

```bash
python cpp_build_stamp.py [options] file [namespace] VAR=VALUE [VAR=VALUE ...] [--clang-args ...]
```

#### Arguments:
- `file`: Path to the C++ header/source file
- `namespace` (optional): Namespace containing the variables; if not specified, all namespaces (including the global namespace) will be searched
- `VAR=VALUE`: One or more variable modifications

#### Placeholders:
- `{date}`: Expands to current date
- `{time}`: Expands to current time
- `{++}`: Increments the current numeric value

#### Options:
- `-v, --verbose`: Enable verbose logging
- `--timezone`: Specify timezone (default: system timezone)
- `--date_format`: Format string for date placeholders (default: '%d %b %Y')
- `--time_format`: Format string for time placeholders (default: '%I:%M:%S %p %Z')
- `--clang-args`: Additional arguments to pass to clang. The default argument is `-std=c++26`. If you're using an C++ standard for your code, you may need to change this.

#### Exit Code:
- `0`: Success, all variables were modified
- `1`: Failure, one or more variables could not be modified

### Example Usage

Modify a build info file with variables in the global namespace:

```bash
python cpp_build_stamp.py src/build_info.cpp \
    build_date="{date}" \
    build_time="{time}" \
    build_number="{++}"
```

Modify variables in a specific namespace:

```bash
python cpp_build_stamp.py header.hpp \
    build_info \
    version="v1.2.3" \
    date_time="Built on {date} at {time}"
```

Using `--clang-args` to specify a different C++ standard:

```bash
python cpp_build_stamp.py src/build_info.cpp \
    build_date="{date}" \
    --clang-args -std=c++17
```

## Example Source File

Suppose you have a C++ source file `src/build_info.cpp` with the following content:

```cpp
namespace build_info {
    const char* date = "17 Jul 2024";       // Build date
    const char* time = "12:33:15 PM EDT";   // Build time
    const int number = 42;                  // Build number
}
```

You would run `cpp_build_stamp.py` with the following command:

```bash
python cpp_build_stamp.py src/build_info.cpp \
    build_info \
    date="{date}" \
    time="{time}" \
    number="{++}"
```

This would update the file to something such as the following:

```cpp
namespace build_info {
    const char* date = "11 Feb 2025";       // Build date
    const char* time = "3:45:23 PM EST";    // Build time
    const int number = 43;                  // Build number
}
```

All comments, formatting, and code structure are preserved. Note that, in this case, as the build number increases to three digits, the `// Build number` comment will be shifted to the right. You may wish to run a code formatting tool such as clang-format *after* running `cpp_build_stamp.py` to ensure consistent formatting. If you are using CMake, this is easily done with an additional command.

## Example CMake Integration

`cpp_build_stamp.py` can be integrated into CMake builds to automatically update build information.

Here is a basic example, assuming you have the `src/build_info.cpp` file above, and have already set `YOUR_SOURCE_FILES` to a list of all of the source files in your project (including the `src/build_info.cpp` file):

```cmake
# Define the build info file
set(BUILD_INFO_FILE "${CMAKE_SOURCE_DIR}/src/build_info.cpp")

# Remove the build info file from a copy of the source files list
set(ALL_SOURCE_FILES_EXCEPT_BUILD_INFO ${YOUR_SOURCE_FILES})
list(REMOVE_ITEM ALL_SOURCE_FILES_EXCEPT_BUILD_INFO ${BUILD_VERSION_FILE})

# Add a custom command to update the build information
add_custom_command(
    OUTPUT ${BUILD_INFO_FILE}
    COMMAND python ${CMAKE_SOURCE_DIR}/tools/cpp_build_stamp.py 
            ${BUILD_INFO_FILE}
            build_info
            build_date="{date}"
            build_time="{time}"
            build_number="{++}"
    DEPENDS ${ALL_SOURCE_FILES_EXCEPT_BUILD_INFO}
    COMMENT "Updating build information"
)

# Add a custom target to update the build information
add_custom_target(update_build_info DEPENDS ${BUILD_INFO_FILE})
add_dependencies(${YOUR_TARGET} update_build_info)
```

This assumes that the required Python packages are installed in the environment the script runs in, and that the `cpp_build_stamp.py` script is located in a `tools` subdirectory. The `YOUR_TARGET` variable should be replaced with the target you are building in CMake.

## License

Since I barely even wrote this anyway, this project is dedicated to the public domain under the CC0 License. See the [LICENSE](LICENSE) file for details.
