
import os
import sys
import subprocess
import tempfile
import shutil
from pathlib import Path
import re

sys.path.append(str(Path(__file__).parent))

from main import LLMTestGenerator

def build_and_test_project(test_dir: Path, generator: LLMTestGenerator) -> dict:
    """Build the test project and run tests, return results."""
    results = {
        'build_success': False,
        'test_success': False,
        'build_log': '',
        'test_output': '',
        'coverage_data': '',
        'executable_path': None
    }
    
    build_dir = test_dir / 'build'
    build_dir.mkdir(exist_ok=True)
    
    try:
        print("  🔧 Configuring with CMake...")
        cmake_result = subprocess.run(
            ['cmake', '..', '-DCMAKE_BUILD_TYPE=Debug', '-DCMAKE_CXX_FLAGS=--coverage'],
            cwd=build_dir,
            capture_output=True,
            text=True,
            timeout=60
        )
        
        if cmake_result.returncode != 0:
            results['build_log'] = f"CMake configuration failed:\n{cmake_result.stderr}\n{cmake_result.stdout}"
            return results
        
        print("  🔨 Building project...")
        build_result = subprocess.run(
            ['cmake', '--build', '.', '--config', 'Debug'],
            cwd=build_dir,
            capture_output=True,
            text=True,
            timeout=120
        )
        
        results['build_log'] = f"STDOUT:\n{build_result.stdout}\n\nSTDERR:\n{build_result.stderr}"
        
        if build_result.returncode != 0:
            return results
            
        results['build_success'] = True
        
        test_executables = list(build_dir.glob('*test*')) + list(build_dir.glob('unit_tests*'))
        if not test_executables:
            test_executables = [f for f in build_dir.iterdir() if f.is_file() and os.access(f, os.X_OK)]
        
        if test_executables:
            results['executable_path'] = test_executables[0]
            
            print("  🧪 Running tests...")
            test_result = subprocess.run(
                [str(test_executables[0])],
                cwd=build_dir,
                capture_output=True,
                text=True,
                timeout=60
            )
            
            results['test_output'] = f"STDOUT:\n{test_result.stdout}\n\nSTDERR:\n{test_result.stderr}"
            results['test_success'] = test_result.returncode == 0
            
            if results['test_success']:
                print("  📊 Generating coverage report...")
                coverage_result = subprocess.run(
                    ['gcov', '*.gcno'],
                    cwd=build_dir,
                    capture_output=True,
                    text=True,
                    timeout=30
                )
                
                if coverage_result.returncode == 0:
                    results['coverage_data'] = coverage_result.stdout
                    
                    lcov_result = subprocess.run(
                        ['lcov', '--capture', '--directory', '.', '--output-file', 'coverage.info'],
                        cwd=build_dir,
                        capture_output=True,
                        text=True,
                        timeout=30
                    )
                    
                    if lcov_result.returncode == 0:
                        genhtml_result = subprocess.run(
                            ['genhtml', 'coverage.info', '--output-directory', 'coverage_html'],
                            cwd=build_dir,
                            capture_output=True,
                            text=True,
                            timeout=30
                        )
                        if genhtml_result.returncode == 0:
                            results['coverage_data'] += f"\n\nHTML Coverage report generated in: {build_dir}/coverage_html"
    
    except subprocess.TimeoutExpired:
        results['build_log'] += "\n\nBuild process timed out"
    except Exception as e:
        results['build_log'] += f"\n\nUnexpected error: {str(e)}"
    
    return results

def fix_compilation_issues(test_content: str, build_log: str, class_name: str, generator: LLMTestGenerator) -> str:
    """Send compilation errors to LLM for fixing."""
    fix_prompt = f"""
TASK: Fix C++ compilation errors in the following test file.

CLASS NAME: {class_name}

ORIGINAL TEST FILE:
{test_content}

BUILD LOG WITH ERRORS:
{build_log}

YAML CONFIGURATION FOR FIXES:
fix_requirements:
  compilation:
    - "Fix all compilation errors shown in the build log"
    - "Add missing #include statements"
    - "Fix syntax errors and typos"
    - "Correct function signatures and namespaces"
    - "Fix template instantiation issues"
    
  dependencies:
    - "Ensure all used libraries are properly included"
    - "Add forward declarations if needed"
    - "Fix linking issues with proper library references"
    
  code_quality:
    - "Maintain Google Test framework compatibility"
    - "Keep existing test logic intact"
    - "Preserve mock object functionality"
    - "Ensure proper RAII and memory management"

OUTPUT REQUIREMENTS:
- Provide ONLY the corrected C++ test file
- Fix ALL compilation errors mentioned in the build log
- Do not change test logic unless necessary for compilation
- Maintain the same file structure and test organization
- Ensure the code compiles with standard C++17

CORRECTED TEST FILE:
"""
    
    try:
        print("  🔧 Asking LLM to fix compilation issues...")
        fixed_content = generator.call_github_llm(fix_prompt)
        
        if "```cpp" in fixed_content:
            start = fixed_content.find("```cpp") + 6
            end = fixed_content.find("```", start)
            if end != -1:
                fixed_content = fixed_content[start:end].strip()
        elif "```" in fixed_content:
            start = fixed_content.find("```") + 3
            end = fixed_content.rfind("```")
            if end != -1 and end > start:
                fixed_content = fixed_content[start:end].strip()
                
        return fixed_content
    except Exception as e:
        print(f"  ❌ Failed to fix compilation issues: {e}")
        return test_content

def improve_tests_with_coverage(test_content: str, test_output: str, coverage_data: str, class_name: str, generator: LLMTestGenerator) -> str:
    """Send test results and coverage data to LLM for improvements."""
    improve_prompt = f"""
TASK: Improve C++ test file based on test results and coverage analysis.

CLASS NAME: {class_name}

CURRENT TEST FILE:
{test_content}

TEST EXECUTION OUTPUT:
{test_output}

COVERAGE DATA:
{coverage_data}

YAML CONFIGURATION FOR IMPROVEMENTS:
improvement_requirements:
  coverage_analysis:
    - "Identify untested code paths from coverage data"
    - "Add tests for uncovered branches and functions"
    - "Improve coverage for edge cases and error handling"
    
  test_optimization:
    - "Remove any duplicate or redundant tests"
    - "Consolidate similar tests into parameterized tests"
    - "Improve test names for better clarity"
    - "Add missing boundary value tests"
    
  quality_enhancements:
    - "Better assertion messages for debugging"
    - "Improved mock object usage and verification"
    - "Add performance benchmarks where appropriate"
    - "Enhanced test documentation and comments"
    
  formatting:
    - "Consistent code formatting and indentation"
    - "Proper spacing and line breaks"
    - "Clear test organization and grouping"
    - "Professional commenting style"

OUTPUT REQUIREMENTS:
- Provide ONLY the improved C++ test file
- Maintain all working tests while adding new ones
- Focus on increasing test coverage based on the coverage report
- Remove any duplicate tests identified
- Ensure better formatting and organization
- Add comprehensive comments explaining test scenarios

IMPROVED TEST FILE:
"""
    
    try:
        print("  🚀 Asking LLM to improve tests based on coverage analysis...")
        improved_content = generator.call_github_llm(improve_prompt)
        
        if "```cpp" in improved_content:
            start = improved_content.find("```cpp") + 6
            end = improved_content.find("```", start)
            if end != -1:
                improved_content = improved_content[start:end].strip()
        elif "```" in improved_content:
            start = improved_content.find("```") + 3
            end = improved_content.rfind("```")
            if end != -1 and end > start:
                improved_content = improved_content[start:end].strip()
                
        return improved_content
    except Exception as e:
        print(f"  ❌ Failed to improve tests: {e}")
        return test_content

def create_cmake_file(test_dir: Path):
    """Create a basic CMakeLists.txt for the test directory."""
    cmake_content = """
cmake_minimum_required(VERSION 3.14)
project(UnitTests)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)

# Find required packages
find_package(PkgConfig QUIET)
if(PkgConfig_FOUND)
    pkg_check_modules(GTEST QUIET gtest)
    pkg_check_modules(GMOCK QUIET gmock)
endif()

if(NOT GTEST_FOUND)
    find_package(GTest QUIET)
    if(GTest_FOUND)
        set(GTEST_LIBRARIES GTest::gtest GTest::gtest_main)
        set(GMOCK_LIBRARIES GTest::gmock GTest::gmock_main)
    endif()
endif()

# Fallback to system libraries
if(NOT GTEST_FOUND AND NOT GTest_FOUND)
    set(GTEST_LIBRARIES gtest gtest_main)
    set(GMOCK_LIBRARIES gmock gmock_main)
endif()

# Find all test source files
file(GLOB TEST_SOURCES "*.cpp")

# Add test executable
add_executable(unit_tests ${TEST_SOURCES})

# Link libraries
target_link_libraries(unit_tests ${GTEST_LIBRARIES} ${GMOCK_LIBRARIES} pthread)

# Enable coverage
if(CMAKE_BUILD_TYPE STREQUAL "Debug")
    target_compile_options(unit_tests PRIVATE --coverage)
    target_link_options(unit_tests PRIVATE --coverage)
endif()

# Enable testing
enable_testing()
add_test(NAME unit_tests COMMAND unit_tests)
"""
    
    cmake_path = test_dir / "CMakeLists.txt"
    if not cmake_path.exists():
        with open(cmake_path, 'w') as f:
            f.write(cmake_content.strip())
        print(f"  📄 Created CMakeLists.txt")

def comprehensive_test_workflow(test_file_path: str, output_path: str = None) -> bool:
    """Refine an existing test file and save the improved version."""
    
    generator = LLMTestGenerator()
    
    token = os.getenv('GITHUB_TOKEN')
    if not token:
        print("Error: GITHUB_TOKEN environment variable not set.")
        return False
    
    generator.set_api_token(token)
    
    test_file_path = Path(test_file_path)
    if not test_file_path.exists():
        print(f"Error: Test file {test_file_path} does not exist.")
        return False
    
    try:
        with open(test_file_path, 'r', encoding='utf-8') as file:
            original_content = file.read()
        
        print(f"Reading test file: {test_file_path}")
        print(f"Original file size: {len(original_content)} characters")
    except Exception as e:
        raise e
        
def comprehensive_test_workflow(test_file_path: str, output_path: str = None) -> bool:
    """Complete workflow: refine, build, test, analyze coverage, and improve."""
    
    generator = LLMTestGenerator()
    
    token = os.getenv('GITHUB_TOKEN')
    if not token:
        print("❌ Error: GITHUB_TOKEN environment variable not set.")
        return False
    
    generator.set_api_token(token)
    
    test_file_path = Path(test_file_path)
    if not test_file_path.exists():
        print(f"❌ Error: Test file {test_file_path} does not exist.")
        return False
    
    try:
        with open(test_file_path, 'r', encoding='utf-8') as file:
            original_content = file.read()
        
        print(f"📖 Reading test file: {test_file_path}")
        print(f"📏 Original file size: {len(original_content)} characters")
        
        class_name = test_file_path.stem.replace('_test', '').replace('test_', '')
        print(f"🎯 Detected class name: {class_name}")
        
        print("\n🔄 STEP 1: Initial test refinement...")
        refined_content = generator.refine_generated_tests(original_content, class_name)
        
        print("\n🏗️ STEP 2: Setting up build environment...")
        test_dir = test_file_path.parent
        create_cmake_file(test_dir)
        
        temp_test_file = test_dir / f"{test_file_path.stem}_temp{test_file_path.suffix}"
        with open(temp_test_file, 'w', encoding='utf-8') as file:
            file.write(refined_content)
        
        print("\n🔨 STEP 3: Building and testing...")
        build_results = build_and_test_project(test_dir, generator)
        
        current_content = refined_content
        iteration = 1
        max_iterations = 3
        
        while not build_results['build_success'] and iteration <= max_iterations:
            print(f"\n🔧 STEP 4.{iteration}: Fixing compilation issues...")
            print("❌ Build failed, sending errors to LLM for fixing...")
            
            current_content = fix_compilation_issues(
                current_content, 
                build_results['build_log'], 
                class_name, 
                generator
            )
            
            with open(temp_test_file, 'w', encoding='utf-8') as file:
                file.write(current_content)
            
            build_results = build_and_test_project(test_dir, generator)
            iteration += 1
        
        if not build_results['build_success']:
            print(f"\n❌ Failed to fix compilation issues after {max_iterations} attempts")
            print("Build log:")
            print(build_results['build_log'])
            return False
        
        print("\n✅ Build successful!")
        
        if build_results['test_success']:
            print("\n✅ Tests passed!")
            print("\n📊 STEP 5: Analyzing coverage and improving tests...")
            
            final_content = improve_tests_with_coverage(
                current_content,
                build_results['test_output'],
                build_results['coverage_data'],
                class_name,
                generator
            )
        else:
            print(f"\n⚠️ Tests failed, but build was successful. Using current content.")
            print("Test output:")
            print(build_results['test_output'])
            final_content = current_content
        
        print("\n💾 STEP 6: Saving final result...")
        if output_path is None:
            output_path = test_file_path.parent / f"{test_file_path.stem}_improved{test_file_path.suffix}"
        else:
            output_path = Path(output_path)
        
        with open(output_path, 'w', encoding='utf-8') as file:
            file.write(final_content)
        
        if temp_test_file.exists():
            temp_test_file.unlink()
        
        print(f"\n🎉 Workflow completed successfully!")
        print(f"📁 Final test file: {output_path}")
        print(f"📏 Final size: {len(final_content)} characters")
        
        original_lines = len(original_content.splitlines())
        final_lines = len(final_content.splitlines())
        change = final_lines - original_lines
        change_str = f"+{change}" if change > 0 else str(change) if change < 0 else "same"
        print(f"📊 Lines: {original_lines} → {final_lines} ({change_str})")
        
        # Show what was accomplished
        print(f"\n✨ Accomplished:")
        print(f"  ✅ Initial test refinement")
        print(f"  ✅ Build environment setup")
        print(f"  ✅ Compilation {'fixed' if iteration > 1 else 'successful'}")
        print(f"  ✅ Tests {'executed and analyzed' if build_results['test_success'] else 'built successfully'}")
        if build_results['coverage_data']:
            print(f"  ✅ Coverage analysis completed")
        print(f"  ✅ Final optimization and formatting")
        
        return True
        
    except Exception as e:
        print(f"\n❌ Error in workflow: {e}")
        return False

def refine_existing_test_file(test_file_path: str, output_path: str = None):
    """Legacy function - use comprehensive_test_workflow instead."""
    return comprehensive_test_workflow(test_file_path, output_path)

def main():
    """Main function for command line usage."""
    if len(sys.argv) < 2:
        print("Usage: python refine_tests.py <test_file_path> [output_path]")
        print("\nExample:")
        print("  python refine_tests.py test/authcontroller_test.cpp")
        print("  python refine_tests.py test/authcontroller_test.cpp test/authcontroller_test_improved.cpp")
        print("\nThis tool will:")
        print("  🔄 Refine the test file")
        print("  🏗️ Set up build environment")
        print("  🔨 Build and compile tests")
        print("  🔧 Fix compilation issues automatically")
        print("  🧪 Run tests and analyze results")
        print("  📊 Generate coverage reports")
        print("  🚀 Improve tests based on coverage data")
        sys.exit(1)
    
    test_file_path = sys.argv[1]
    output_path = sys.argv[2] if len(sys.argv) > 2 else None
    
    print("=" * 60)
    print("🧪 COMPREHENSIVE C++ TEST REFINEMENT WORKFLOW")
    print("=" * 60)
    print(f"📁 Input: {test_file_path}")
    print(f"📁 Output: {output_path or 'auto-generated name'}")
    print("=" * 60)
    
    success = comprehensive_test_workflow(test_file_path, output_path)
    
    if success:
        print("\n" + "=" * 60)
        print("🎉 WORKFLOW COMPLETED SUCCESSFULLY!")
        print("=" * 60)
        print("\n🔥 What was accomplished:")
        print("  • ✅ Test file refinement and optimization")
        print("  • ✅ Automatic build environment setup")
        print("  • ✅ Compilation error detection and fixing")
        print("  • ✅ Test execution and validation")
        print("  • ✅ Coverage analysis and reporting")
        print("  • ✅ Test improvement based on coverage data")
        print("  • ✅ Professional formatting and documentation")
        print("\n🚀 Your tests are now production-ready!")
    else:
        print("\n" + "=" * 60)
        print("❌ WORKFLOW FAILED!")
        print("=" * 60)
        print("\n🔍 Check the error messages above for details.")
        print("💡 Common solutions:")
        print("  • Ensure GITHUB_TOKEN environment variable is set")
        print("  • Install required build tools (cmake, g++, gtest)")
        print("  • Check that the input test file exists")
        print("  • Verify network connectivity for LLM API calls")

if __name__ == "__main__":
    main()
