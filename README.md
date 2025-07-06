# C++ Unit Test Generator

This tool generates comprehensive Google Test unit tests for C++ projects using GitHub-hosted LLMs.

## Features

- **GitHub LLM Integration**: Uses GitHub Models API for intelligent test generation
- **YAML-driven Configuration**: Strict instruction files for consistent test generation
- **Google Test Framework**: Generates tests compatible with Google Test and Google Mock
- **Automatic Project Analysis**: Scans C++ projects and identifies classes to test
- **CMake Integration**: Generates build files for easy compilation

## Setup

### 1. Install Python Dependencies

```bash
pip install -r requirements.txt
```

### 2. Install Google Test

#### Using vcpkg (Recommended for Windows):
```bash
vcpkg install gtest gmock
```

#### Using package manager on Linux:
```bash
# Ubuntu/Debian
sudo apt-get install libgtest-dev libgmock-dev

# CentOS/RHEL
sudo yum install gtest-devel gmock-devel
```

### 3. Get GitHub API Token

1. Go to [GitHub Settings > Developer settings > Personal access tokens](https://github.com/settings/tokens)
2. Generate a new token with appropriate permissions
3. Set it as environment variable:
   ```bash
   export GITHUB_TOKEN="your_token_here"
   ```

## Usage

### Basic Usage

```bash
python main.py /path/to/your/cpp/project
```

### Advanced Usage

```bash
python main.py /path/to/your/cpp/project --output tests --model gpt-4o --token YOUR_TOKEN
```

### Command Line Options

- `project_path`: Path to your C++ project directory (required)
- `--output, -o`: Output directory for generated test files (default: "test")
- `--token`: GitHub API token (or set GITHUB_TOKEN env var)
- `--model`: LLM model to use (default: "gpt-4o")

## Configuration Files

The tool uses three YAML configuration files in the `Instruction Files/` directory:

### 1. `test_generation_rules.yaml`
- Google Test framework configuration
- Naming conventions
- Test structure templates
- Coverage requirements

### 2. `llm_prompt_config.yaml`
- LLM prompt templates
- Task descriptions
- Quality requirements
- Code style guidelines

### 3. `gtest_setup_config.yaml`
- Google Test installation instructions
- CMake configuration
- Compilation commands
- Environment setup

## Example Workflow

1. **Prepare your C++ project**:
   ```
   MyProject/
   ├── src/
   │   ├── Calculator.h
   │   ├── Calculator.cpp
   │   ├── StringUtils.h
   │   └── StringUtils.cpp
   └── ...
   ```

2. **Generate tests**:
   ```bash
   python main.py MyProject/src --output MyProject/tests
   ```

3. **Generated output**:
   ```
   MyProject/tests/
   ├── calculator_test.cpp
   ├── stringutils_test.cpp
   └── CMakeLists.txt
   ```

4. **Build and run tests**:
   ```bash
   cd MyProject/tests
   cmake .
   make
   ./unit_tests
   ```

## Generated Test Features

The LLM generates tests with:

- **Comprehensive Coverage**: Tests for all public methods
- **Edge Cases**: Boundary conditions and error scenarios
- **Mock Objects**: For testing dependencies
- **Parameterized Tests**: For multiple input scenarios
- **Proper Structure**: Arrange-Act-Assert pattern
- **Google Test Best Practices**: Fixtures, setup/teardown, assertions

## Example Generated Test

```cpp
#include "gtest/gtest.h"
#include "gmock/gmock.h"
#include "Calculator.h"

using namespace testing;

class CalculatorTest : public ::testing::Test {
protected:
    void SetUp() override {
        calc = std::make_unique<Calculator>();
    }
    
    void TearDown() override {
        calc.reset();
    }
    
    std::unique_ptr<Calculator> calc;
};

TEST_F(CalculatorTest, test_Add_PositiveNumbers) {
    // Arrange
    int a = 5, b = 3;
    
    // Act
    int result = calc->add(a, b);
    
    // Assert
    EXPECT_EQ(8, result);
}

TEST_F(CalculatorTest, test_Divide_ByZero_ThrowsException) {
    // Arrange
    int a = 10, b = 0;
    
    // Act & Assert
    EXPECT_THROW(calc->divide(a, b), std::invalid_argument);
}
```
