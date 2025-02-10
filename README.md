# cpp-build-stamp

![GitHub License](https://img.shields.io/github/license/RobertSundling/cpp-build-stamp)
![GitHub issues](https://img.shields.io/github/issues/RobertSundling/cpp-build-stamp)
![GitHub last commit](https://img.shields.io/github/last-commit/RobertSundling/cpp-build-stamp)

A Python script that safely modifies C++ source files to include build timestamps, dates, and auto-incrementing build numbers. Uses libclang for robust C++ parsing to ensure modifications preserve code structure and comments.

## Motivation

I've always used quick-and-dirty script to include build numbers and time and date stamps in C++ projects. However, I was sick of the scripts that I was using occasionally not working, as they'd rely on the user not modifying files in between builds. As such, they would often blow away changes or not update things at all. In particular, they would conflict with automated code formatting tools such as clang-format, which would reformat files, making the scripts unable to find the variables to update.

This script uses [libclang](https://pypi.org/project/libclang/) to properly parse and understand C++ code of arbitrary complexity. It can therefore can make modifications properly.

## Acknowledgements

Rather than spending time myself writing this tool myself, I delegated it to some AI assistants. The script was primarily written by Claude 3.5 Sonnet, ChatGPT 4o, and GitHub Copilot Codex. This README.md file was written by Claude 3.5 Sonnet and Gemini 2.0 Flash, with light editing by GitHub Copilot Codex and me.

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
   ```

2. It is recommended to create a virtual environment:
   ```bash
   python -m venv .venv
   source .venv/bin/activate # On Linux/macOS
   .venv\Scripts\activate # On Windows
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
- `--clang-args`: Additional arguments to pass to clang. The default is `-std=c++26`. If you're using an older version of C++, you may need to change this.

### Example Usage

Modify a build info file:
```bash
python cpp_build_stamp.py src/build_info.cpp \
    build_date="{date}" \
    build_time="{time}" \
    build_number="{++}"
```

Modify variables in a specific namespace:
```bash
python cpp_build_stamp.py header.hpp my_namespace \
    version_string="v1.2.3" \
    build_date_time="Built on {date} at {time}"
```

Using --clang-args to specify a different C++ standard:

```bash
python cpp_build_stamp.py src/build_info.cpp \
    build_date="{date}" \
    --clang-args -std=c++17
```


## Example Source File

```cpp
namespace build_info {
    const char* build_date = "01 Jan 2024";
    const char* build_time = "12:00:00 PM EDT";
    const int build_number = 42;
}
```

After running cpp_build_stamp.py:
```cpp
namespace build_info {
    const char* build_date = "10 Feb 2024";
    const char* build_time = "3:45:23 PM EST";
    const int build_number = 43;
}
```

## Example CMake Integration

cpp_build_stamp.py can be integrated into CMake builds to automatically update build information. Here's a basic example, assuming you have already set `YOUR_SOURCE_FILES` to a list of all of the source files in your project, other than `BUILD_INFO_FILE`:

```cmake
set(BUILD_INFO_FILE "${CMAKE_SOURCE_DIR}/src/build_info.cpp")

add_custom_command(
    OUTPUT ${BUILD_INFO_FILE}
    COMMAND python ${CMAKE_SOURCE_DIR}/tools/cpp_build_stamp.py 
            ${BUILD_INFO_FILE}
            build_info
            build_date="{date}"
            build_time="{time}"
            build_number="{++}"
    DEPENDS ${YOUR_SOURCE_FILES} # YOUR_SOURCE_FILES should NOT include BUILD_INFO_FILE
    COMMENT "Updating build information"
)

add_custom_target(update_build_info DEPENDS ${BUILD_INFO_FILE})
add_dependencies(${YOUR_TARGET} update_build_info)
```

Of course, be sure to include `BUILD_INFO_FILE` in your source files list when you compile your project.

## License

Since I barely even wrote this anyway, this project is dedicated to the public domain under the CC0 License. See the [LICENSE](LICENSE) file for details.
