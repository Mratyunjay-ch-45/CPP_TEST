"""
C++ Unit Test Generator using GitHub-hosted LLM
This application generates Google Test unit tests for C++ projects.
"""

import os
import sys
import yaml
import json
import requests
import argparse
from pathlib import Path
from typing import Dict, List, Optional, Tuple
import re


class LLMTestGenerator:
    """Main class for generating C++ unit tests using GitHub-hosted LLM."""
    
    def __init__(self, config_dir: str = "Instruction Files"):
        """Initialize the test generator with configuration files."""
        self.config_dir = Path(config_dir)
        self.test_rules = self._load_yaml_config("test_generation_rules.yaml")
        self.prompt_config = self._load_yaml_config("llm_prompt_config.yaml")
        self.gtest_config = self._load_yaml_config("gtest_setup_config.yaml")
        
        self.github_api_url = "https://models.inference.ai.azure.com"  
        self.model_name = "gpt-4o"  
        self.api_token = None  
        
        self.max_file_size = 50000  # Skip files larger than 50KB
        self.excluded_dirs = {'.git', '.svn', 'build', 'cmake-build-debug', 'cmake-build-release', 'node_modules'}  
        
    def _load_yaml_config(self, filename: str) -> Dict:
        """Load YAML configuration file."""
        config_path = self.config_dir / filename
        try:
            with open(config_path, 'r', encoding='utf-8') as file:
                return yaml.safe_load(file)
        except FileNotFoundError:
            print(f"Error: Configuration file {config_path} not found.")
            sys.exit(1)
        except yaml.YAMLError as e:
            print(f"Error parsing YAML file {config_path}: {e}")
            sys.exit(1)
    
    def set_api_token(self, token: str):
        """Set the GitHub API token for LLM access."""
        self.api_token = token
    
    def is_git_repository(self, path: str) -> bool:
        """Check if the given path is a git repository."""
        git_dir = Path(path) / '.git'
        return git_dir.exists()
    
    def get_project_info(self, project_path: str) -> Dict:
        """Get basic information about the project."""
        project_path = Path(project_path)
        info = {
            'path': str(project_path),
            'name': project_path.name,
            'is_git_repo': self.is_git_repository(project_path),
            'has_cmake': (project_path / 'CMakeLists.txt').exists(),
            'has_makefile': (project_path / 'Makefile').exists(),
            'cpp_file_count': 0,
            'header_file_count': 0
        }
        
        for pattern in ["**/*.cpp"]:
            info['cpp_file_count'] += len(list(project_path.glob(pattern)))
        for pattern in ["**/*.h", "**/*.hpp"]:
            info['header_file_count'] += len(list(project_path.glob(pattern)))
            
        return info
    
    def analyze_cpp_files(self, project_path: str) -> List[Dict]:
        """Analyze C++ project and identify files that need tests."""
        project_path = Path(project_path)
        
        if not project_path.exists():
            raise FileNotFoundError(f"Project path does not exist: {project_path}")
        
        print(f"Scanning project directory: {project_path}")
        cpp_files = []
        
        for pattern in ["**/*.h", "**/*.hpp", "**/*.cpp"]:
            for file_path in project_path.glob(pattern):
                if any(excluded_dir in file_path.parts for excluded_dir in self.excluded_dirs):
                    continue
                    
                if self._is_test_file(file_path):
                    continue
                
                if file_path.stat().st_size > self.max_file_size:
                    print(f"Skipping large file: {file_path} ({file_path.stat().st_size} bytes)")
                    continue
                
                file_content = self._read_file_safe(file_path)
                if file_content.strip():  
                    cpp_files.append({
                        'path': file_path,
                        'type': self._get_file_type(file_path),
                        'content': file_content,
                        'size': file_path.stat().st_size
                    })
        
        print(f"Found {len(cpp_files)} C++ files to analyze")
        grouped_files = self._group_files_by_class(cpp_files)
        print(f"Grouped into {len(grouped_files)} class units")
        
        return grouped_files
    
    def _is_test_file(self, file_path: Path) -> bool:
        """Check if the file is already a test file."""
        test_patterns = ["test", "Test", "_test", "_Test"]
        return any(pattern in file_path.name for pattern in test_patterns)
    
    def _get_file_type(self, file_path: Path) -> str:
        """Determine if file is header or implementation."""
        if file_path.suffix in ['.h', '.hpp']:
            return 'header'
        elif file_path.suffix == '.cpp':
            return 'implementation'
        return 'unknown'
    
    def _read_file_safe(self, file_path: Path) -> str:
        """Safely read file content."""
        try:
            with open(file_path, 'r', encoding='utf-8') as file:
                return file.read()
        except Exception as e:
            print(f"Warning: Could not read {file_path}: {e}")
            return ""
    
    def _group_files_by_class(self, cpp_files: List[Dict]) -> List[Dict]:
        """Group header and implementation files by class name."""
        grouped = {}
        
        for file_info in cpp_files:
            base_name = file_info['path'].stem
            if base_name not in grouped:
                grouped[base_name] = {'header': None, 'implementation': None}
            
            grouped[base_name][file_info['type']] = file_info
        
        return [group for group in grouped.values() if group['header'] is not None]
    
    def generate_prompt(self, class_files: Dict) -> str:
        """Generate the LLM prompt based on C++ files and YAML configuration."""
        prompt_template = self.prompt_config['llm_prompt_instructions']['example_prompt_template']
        
        header_content = class_files['header']['content'] if class_files['header'] else ""
        implementation_content = class_files['implementation']['content'] if class_files['implementation'] else ""
        
        yaml_instructions = self._format_yaml_instructions()
        
        full_prompt = f"""
{self.prompt_config['llm_prompt_instructions']['system_role']}

{self.prompt_config['llm_prompt_instructions']['task_description']}

STRICT YAML CONFIGURATION TO FOLLOW:
{yaml_instructions}

{prompt_template.format(
    header_content=header_content,
    implementation_content=implementation_content
)}

ADDITIONAL REQUIREMENTS:
- Follow exactly the test structure template provided in YAML
- Use the naming conventions specified
- Generate comprehensive test coverage as outlined
- Include all required includes and namespaces
- Create proper test fixtures with SetUp/TearDown methods
"""
        return full_prompt
    
    def _format_yaml_instructions(self) -> str:
        """Format YAML configuration as instructions for the LLM."""
        instructions = []
        
        rules = self.test_rules['test_generation_guidelines']
        instructions.append(f"Framework: {rules['framework']}")
        instructions.append(f"Naming Conventions: {yaml.dump(rules['naming_conventions'])}")
        instructions.append(f"Required Includes: {rules['test_structure']['required_includes']}")
        instructions.append(f"Test Case Requirements: {yaml.dump(rules['test_case_requirements'])}")
        instructions.append(f"Coverage Requirements: {yaml.dump(rules['coverage_requirements'])}")
        
        return "\n".join(instructions)
    
    def call_github_llm(self, prompt: str) -> str:
        """Call GitHub-hosted LLM with the generated prompt."""
        if not self.api_token:
            raise ValueError("GitHub API token not set. Use set_api_token() method.")
        
        headers = {
            "Authorization": f"Bearer {self.api_token}",
            "Content-Type": "application/json"
        }
        
        payload = {
            "model": self.model_name,
            "messages": [
                {
                    "role": "system",
                    "content": "You are an expert C++ test engineer specializing in Google Test framework."
                },
                {
                    "role": "user",
                    "content": prompt
                }
            ],
            "max_tokens": 4000,
            "temperature": 0.3
        }
        
        try:
            response = requests.post(
                f"{self.github_api_url}/chat/completions",
                headers=headers,
                json=payload,
                timeout=60
            )
            response.raise_for_status()
            
            result = response.json()
            return result['choices'][0]['message']['content']
            
        except requests.exceptions.RequestException as e:
            print(f"Error calling GitHub LLM API: {e}")
            raise
        except KeyError as e:
            print(f"Unexpected API response format: {e}")
            raise
    
    def save_test_file(self, test_content: str, class_name: str, output_dir: str = "test") -> str:
        """Save generated test content to a file."""
        output_path = Path(output_dir)
        output_path.mkdir(exist_ok=True)
        
        naming = self.test_rules['test_generation_guidelines']['naming_conventions']
        test_filename = f"{class_name.lower()}{naming['test_file_suffix']}"
        test_file_path = output_path / test_filename
        
        try:
            with open(test_file_path, 'w', encoding='utf-8') as file:
                file.write(test_content)
            print(f"Test file saved: {test_file_path}")
            return str(test_file_path)
        except Exception as e:
            print(f"Error saving test file: {e}")
            raise
    
    def generate_cmake_file(self, test_files: List[str], output_dir: str = "test"):
        """Generate CMakeLists.txt for the test files."""
        cmake_content = self.gtest_config['google_test_setup']['cmake_configuration']
        
        test_sources = "\n        ".join([f'"{Path(f).name}"' for f in test_files])
        cmake_content = cmake_content.replace('${TEST_SOURCES}', test_sources)
        
        cmake_path = Path(output_dir) / "CMakeLists.txt"
        try:
            with open(cmake_path, 'w', encoding='utf-8') as file:
                file.write(cmake_content)
            print(f"CMakeLists.txt generated: {cmake_path}")
        except Exception as e:
            print(f"Error generating CMakeLists.txt: {e}")
    
    def generate_tests_for_project(self, project_path: str, output_dir: str = "test", enable_refinement: bool = True, enable_build: bool = True) -> List[str]:
        """Main method to generate tests for an entire C++ project."""
        print(f"Analyzing C++ project at: {project_path}")
        
        project_info = self.get_project_info(project_path)
        print(f"Project: {project_info['name']}")
        print(f"Git repository: {'Yes' if project_info['is_git_repo'] else 'No'}")
        print(f"CMake project: {'Yes' if project_info['has_cmake'] else 'No'}")
        print(f"C++ files: {project_info['cpp_file_count']}, Headers: {project_info['header_file_count']}")
        print("-" * 50)
        
        class_groups = self.analyze_cpp_files(project_path)
        print(f"Found {len(class_groups)} classes to test")
        
        if not class_groups:
            print("No C++ classes found to generate tests for.")
            return []
        
        generated_files = []
        
        for i, class_files in enumerate(class_groups, 1):
            class_name = class_files['header']['path'].stem if class_files['header'] else f"Class{i}"
            print(f"[{i}/{len(class_groups)}] Generating tests for: {class_name}")
            
            try:
                prompt = self.generate_prompt(class_files)
                
                print(f"  Calling GitHub LLM for initial test generation...")
                initial_test_content = self.call_github_llm(prompt)
                
                if enable_refinement:
                    print(f"  Refining tests with follow-up prompt...")
                    final_test_content = self.refine_generated_tests(initial_test_content, class_name)
                else:
                    final_test_content = initial_test_content
                
                print(f"  Saving test file...")
                test_file = self.save_test_file(final_test_content, class_name, output_dir)
                generated_files.append(test_file)
                print(f"  ✓ Generated: {test_file}")
                
            except Exception as e:
                print(f"  ✗ Error generating tests for {class_name}: {e}")
                continue
        
        if generated_files:
            print("Generating CMakeLists.txt...")
            self.generate_cmake_file(generated_files, output_dir)
        
        if enable_build and generated_files:
            print("\n" + "=" * 50)
            print("🔨 BUILDING AND TESTING GENERATED TESTS")
            print("=" * 50)
            
            build_results = self.build_and_test_generated_tests(output_dir)
            
            if not build_results['build_success']:
                print("❌ Build failed, attempting to fix compilation issues...")
                
                for test_file_path in generated_files:
                    test_file = Path(test_file_path)
                    class_name = test_file.stem.replace('_test', '').replace('test_', '')
                    
                    try:
                        with open(test_file, 'r', encoding='utf-8') as f:
                            test_content = f.read()
                        
                        print(f"🔧 Fixing {test_file.name}...")
                        fixed_content = self.fix_compilation_issues(
                            test_content, 
                            build_results['build_log'], 
                            class_name,
                            str(test_file)
                        )
                        
                        with open(test_file, 'w', encoding='utf-8') as f:
                            f.write(fixed_content)
                        
                    except Exception as e:
                        print(f"  ❌ Failed to fix {test_file.name}: {e}")
                
                print("🔨 Rebuilding with fixes...")
                build_results = self.build_and_test_generated_tests(output_dir)
            
            if build_results['build_success']:
                print("✅ Build successful!")
                
                if build_results['test_success']:
                    print("✅ All tests passed!")
                    
                    if build_results['coverage_data']:
                        print("📊 Improving tests based on coverage analysis...")
                        
                        for test_file_path in generated_files:
                            test_file = Path(test_file_path)
                            class_name = test_file.stem.replace('_test', '').replace('test_', '')
                            
                            try:
                                with open(test_file, 'r', encoding='utf-8') as f:
                                    test_content = f.read()
                                
                                improved_content = self.improve_tests_with_coverage(
                                    test_content,
                                    build_results['test_output'],
                                    build_results['coverage_data'],
                                    class_name
                                )
                                
                                improved_file = test_file.parent / f"{test_file.stem}_improved{test_file.suffix}"
                                with open(improved_file, 'w', encoding='utf-8') as f:
                                    f.write(improved_content)
                                
                                print(f"  ✅ Improved version saved: {improved_file}")
                                
                            except Exception as e:
                                print(f"  ❌ Failed to improve {test_file.name}: {e}")
                else:
                    print("⚠️ Tests compiled but some failed execution")
                    print("Test output:")
                    print(build_results['test_output'])
            else:
                print("❌ Build failed even after attempting fixes")
                print("Build log:")
                print(build_results['build_log'])
        
        return generated_files
    
    def refine_generated_tests(self, test_content: str, class_name: str) -> str:
        """Send a follow-up prompt to refine and improve the generated tests."""
        refinement_prompt = f"""
TASK: Review and refine the following C++ unit test file for the class '{class_name}'.

ORIGINAL GENERATED TEST:
{test_content}

REFINEMENT REQUIREMENTS:
1. **Remove Duplicate Tests**: Identify and eliminate any duplicate or redundant test cases
2. **Add Missing Libraries**: Include all necessary #include statements and dependencies
3. **Improve Test Quality**: Enhance test coverage, assertions, and edge cases
4. **Fix Compilation Issues**: Ensure all code compiles without errors
5. **Optimize Test Structure**: Improve test organization and readability
6. **Add Parameterized Tests**: Where applicable, convert similar tests to parameterized tests
7. **Enhance Mock Objects**: Improve mock implementations and expectations
8. **Add Performance Tests**: Include performance-critical path testing where relevant
9. **Improve Comments**: Add clear, descriptive comments explaining test scenarios
10. **Validate Test Independence**: Ensure tests don't depend on each other

SPECIFIC IMPROVEMENTS TO MAKE:
- Remove any redundant test methods that test the same functionality
- Add comprehensive #include statements for all used libraries
- Improve assertion messages for better debugging
- Add ASSERT_* for critical checks and EXPECT_* for non-critical checks
- Include boundary value testing
- Add exception testing with proper EXPECT_THROW/EXPECT_NO_THROW
- Ensure proper setup and teardown in test fixtures
- Add death tests if applicable (EXPECT_DEATH)
- Include thread safety tests if relevant
- Add comprehensive documentation comments

OUTPUT REQUIREMENTS:
- Provide ONLY the refined C++ test file content
- Ensure the code is ready for compilation
- Follow Google Test best practices
- Include proper file header comments
- Maintain the same class name and overall structure
- Do not include explanatory text outside the code

REFINED TEST FILE:
"""
        
        try:
            print(f"  Refining tests with follow-up prompt...")
            refined_content = self.call_github_llm(refinement_prompt)
            
            if "```cpp" in refined_content:
                start = refined_content.find("```cpp") + 6
                end = refined_content.find("```", start)
                if end != -1:
                    refined_content = refined_content[start:end].strip()
            elif "```" in refined_content:
                start = refined_content.find("```") + 3
                end = refined_content.rfind("```")
                if end != -1 and end > start:
                    refined_content = refined_content[start:end].strip()
            
            return refined_content
            
        except Exception as e:
            print(f"  Warning: Test refinement failed ({e}), using original tests")
            return test_content
    

    def build_and_test_generated_tests(self, output_dir: str) -> dict:
        """Build and test the generated test files."""
        import subprocess
        
        output_path = Path(output_dir)
        build_dir = output_path / 'build'
        build_dir.mkdir(exist_ok=True)
        
        results = {
            'build_success': False,
            'test_success': False,
            'build_log': '',
            'test_output': '',
            'coverage_data': '',
            'executable_path': None
        }
        
        try:
            print("🔧 Configuring with CMake...")
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
            
            print("🔨 Building project...")
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
                
                print("🧪 Running tests...")
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
                    print("📊 Generating coverage report...")
                    coverage_result = subprocess.run(
                        ['gcov', '*.gcno'],
                        cwd=build_dir,
                        capture_output=True,
                        text=True,
                        timeout=30
                    )
                    
                    if coverage_result.returncode == 0:
                        results['coverage_data'] = coverage_result.stdout
        
        except subprocess.TimeoutExpired:
            results['build_log'] += "\n\nBuild process timed out"
        except Exception as e:
            results['build_log'] += f"\n\nUnexpected error: {str(e)}"
        
        return results
    
    def fix_compilation_issues(self, test_content: str, build_log: str, class_name: str, test_file_path: str) -> str:
        """Send compilation errors to LLM for fixing."""
        fix_prompt = f"""
TASK: Fix C++ compilation errors in the following test file.

CLASS NAME: {class_name}
TEST FILE: {test_file_path}

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
            print(f"  🔧 Asking LLM to fix compilation issues...")
            fixed_content = self.call_github_llm(fix_prompt)
            
            # Clean up markdown if present
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

    def improve_tests_with_coverage(self, test_content: str, test_output: str, coverage_data: str, class_name: str) -> str:
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
            print(f"  🚀 Asking LLM to improve tests based on coverage analysis...")
            improved_content = self.call_github_llm(improve_prompt)
            
            # Clean up markdown if present
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

def main():
    """Main function with command-line interface and build integration."""
    parser = argparse.ArgumentParser(description="Generate C++ unit tests using GitHub-hosted LLM")
    parser.add_argument("project_path", help="Path to the C++ project directory")
    parser.add_argument("--output", "-o", default="test", help="Output directory for test files")
    parser.add_argument("--token", help="GitHub API token (or set GITHUB_TOKEN env var)")
    parser.add_argument("--model", default="gpt-4o", help="LLM model to use")
    parser.add_argument("--no-refinement", action="store_true", help="Skip test refinement step (faster but lower quality)")
    parser.add_argument("--no-build", action="store_true", help="Skip building and testing step")
    parser.add_argument("--verbose", "-v", action="store_true", help="Enable verbose output")
    
    args = parser.parse_args()
    
    # Set up logging
    if args.verbose:
        print("🔍 Verbose mode enabled")
    
    try:
        # Initialize the generator
        print("🚀 Initializing C++ Unit Test Generator...")
        generator = LLMTestGenerator()
        generator.model_name = args.model
        
        # Set API token
        token = args.token or os.getenv('GITHUB_TOKEN')
        if not token:
            print("❌ Error: GitHub API token required.")
            print("   Set GITHUB_TOKEN environment variable or use --token flag.")
            print("   Get token from: https://github.com/settings/tokens")
            sys.exit(1)
        
        generator.set_api_token(token)
        print("✅ API token configured")
        
        if not os.path.exists(args.project_path):
            print(f"❌ Error: Project path does not exist: {args.project_path}")
            sys.exit(1)
        
        print(f"📁 Project path: {args.project_path}")
        print(f"📁 Output directory: {args.output}")
        print(f"🤖 Model: {args.model}")
        print(f"🔄 Refinement: {'Disabled' if args.no_refinement else 'Enabled'}")
        print(f"🔨 Building: {'Disabled' if args.no_build else 'Enabled'}")
        print("=" * 60)
        
        enable_refinement = not args.no_refinement
        enable_build = not args.no_build
        
        generated_files = generator.generate_tests_for_project(
            args.project_path, 
            args.output, 
            enable_refinement, 
            enable_build
        )
        
        print("\n" + "=" * 60)
        print("🎉 GENERATION COMPLETE!")
        print("=" * 60)
        print(f"📊 Generated {len(generated_files)} test files:")
        for file_path in generated_files:
            print(f"  ✅ {file_path}")
        
        if enable_refinement:
            print(f"\n✨ Tests were refined with follow-up prompts for improved quality")
        
        if enable_build:
            print(f"\n🔨 Tests were built and validated")
            print(f"📊 Coverage analysis was performed")
        
        print(f"\n📖 Next steps:")
        print(f"  📁 Check output directory: {args.output}")
        if not enable_build:
            print(f"  🔨 Build tests: cd {args.output} && cmake . && cmake --build . --config Debug")
            print(f"  🧪 Run tests: cd {args.output} && ctest -C Debug --verbose")
        print(f"  📝 Review and modify generated tests as needed")
        
    except KeyboardInterrupt:
        print("\n⚠️ Generation interrupted by user")
        sys.exit(130)
    except FileNotFoundError as e:
        print(f"❌ File not found error: {e}")
        print("💡 Check that all required files and directories exist")
        sys.exit(1)
    except requests.exceptions.RequestException as e:
        print(f"❌ Network/API error: {e}")
        print("💡 Check your internet connection and GitHub token")
        sys.exit(1)
    except yaml.YAMLError as e:
        print(f"❌ YAML configuration error: {e}")
        print("💡 Check the YAML files in the 'Instruction Files' directory")
        sys.exit(1)
    except Exception as e:
        print(f"❌ Unexpected error: {e}")
        if args.verbose:
            import traceback
            traceback.print_exc()
        print("💡 Try running with --verbose for more details")
        print("💡 Check the error message and ensure all dependencies are installed")
        sys.exit(1)


if __name__ == "__main__":
    main()