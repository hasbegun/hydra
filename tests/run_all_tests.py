#!/usr/bin/env python3
"""
Master Test Runner
Executes all LLM security test sections using hydra backend
"""

import sys
import subprocess
import time
from datetime import datetime
from pathlib import Path
from test_config import print_section_header, REPORTS_DIR, TEST_SECTIONS

# ANSI colors
GREEN = '\033[92m'
YELLOW = '\033[93m'
RED = '\033[91m'
BLUE = '\033[94m'
BOLD = '\033[1m'
RESET = '\033[0m'


def print_banner():
    """Print test suite banner"""
    print("\n" + "=" * 70)
    print(f"{BOLD}  AEGIS SECURITY - LLM VULNERABILITY TEST SUITE{RESET}")
    print("=" * 70)
    print(f"\nTarget:    Open WebUI (localhost:3030)")
    print(f"Backend:   Hydra API (localhost:8888)")
    print(f"Framework: Garak LLM Scanner")
    print(f"Date:      {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("\n" + "=" * 70)


def print_menu():
    """Print test selection menu"""
    print(f"\n{BOLD}Test Sections:{RESET}\n")

    sections = [
        ("1", "section_1", "Prompt Injection"),
        ("2", "section_2", "Jailbreak & DAN"),
        ("3", "section_3", "Data Leakage"),
        ("4", "section_4", "Toxicity & Harm"),
        ("5", "section_5", "Encoding Attacks"),
        ("A", "all", "Run All Sections"),
        ("Q", "quit", "Quit")
    ]

    for num, key, name in sections:
        if key in TEST_SECTIONS:
            section = TEST_SECTIONS[key]
            time_est = section.get("time_estimate", "N/A")
            severity = section.get("severity", "")

            # Color code by severity
            if severity == "CRITICAL":
                color = RED
            elif severity == "HIGH":
                color = YELLOW
            elif severity == "MEDIUM":
                color = BLUE
            else:
                color = RESET

            print(f"  [{num}] {color}{name:<25}{RESET} ({time_est})")
        else:
            print(f"  [{num}] {name}")

    print()


def run_section(section_num: int):
    """Run a specific test section"""
    script_name = f"section_{section_num}_*.py"
    test_scripts = list(Path(__file__).parent.glob(script_name))

    if not test_scripts:
        print(f"{RED}✗ Test script not found: {script_name}{RESET}")
        return False

    test_script = test_scripts[0]

    print(f"\n{BOLD}{GREEN}▶ Executing: {test_script.name}{RESET}\n")
    print("-" * 70)

    try:
        # Run the test script
        result = subprocess.run(
            [sys.executable, str(test_script)],
            cwd=test_script.parent,
            check=False
        )

        if result.returncode == 0:
            print(f"\n{GREEN}✓ Section {section_num} completed successfully{RESET}")
            return True
        else:
            print(f"\n{YELLOW}⚠ Section {section_num} completed with warnings{RESET}")
            return False

    except KeyboardInterrupt:
        print(f"\n{YELLOW}⚠ Test interrupted by user{RESET}")
        return False
    except Exception as e:
        print(f"\n{RED}✗ Error running section {section_num}: {e}{RESET}")
        return False


def run_all_sections():
    """Run all test sections sequentially"""
    print(f"\n{BOLD}{BLUE}Running All Test Sections{RESET}\n")
    print("This will take approximately 2-4 hours.")
    print("You can interrupt at any time with Ctrl+C.\n")

    response = input("Continue? [y/N]: ").strip().lower()
    if response != 'y':
        print("Cancelled.")
        return

    start_time = time.time()
    results = {}

    for section_num in range(1, 6):
        print(f"\n{'=' * 70}")
        print(f"{BOLD}Section {section_num}/5{RESET}")
        print('=' * 70)

        success = run_section(section_num)
        results[f"section_{section_num}"] = success

        # Brief pause between sections
        if section_num < 5:
            print(f"\n{BLUE}Pausing 5 seconds before next section...{RESET}")
            time.sleep(5)

    # Print summary
    elapsed_time = time.time() - start_time
    print("\n" + "=" * 70)
    print(f"{BOLD}  ALL SECTIONS COMPLETED{RESET}")
    print("=" * 70)

    print(f"\nTotal Time: {elapsed_time/60:.1f} minutes")
    print("\nResults:")
    for section, success in results.items():
        status = f"{GREEN}✓ PASS{RESET}" if success else f"{YELLOW}⚠ WARN{RESET}"
        print(f"  {section}: {status}")

    print(f"\nReports saved to: {REPORTS_DIR}")
    print("=" * 70)


def main():
    """Main entry point"""
    print_banner()

    while True:
        print_menu()
        choice = input(f"{BOLD}Select option:{RESET} ").strip().upper()

        if choice == 'Q':
            print(f"\n{BLUE}Exiting.{RESET}\n")
            break
        elif choice == 'A':
            run_all_sections()
        elif choice in ['1', '2', '3', '4', '5']:
            run_section(int(choice))
        else:
            print(f"\n{RED}Invalid choice. Please try again.{RESET}")

        if choice != 'A':
            input(f"\n{BLUE}Press Enter to continue...{RESET}")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print(f"\n\n{YELLOW}Interrupted by user.{RESET}\n")
        sys.exit(0)
    except Exception as e:
        print(f"\n{RED}Error: {e}{RESET}\n")
        sys.exit(1)
