#!/bin/bash

################################################################################
# RoomLife Launcher Script
# Coordinates launching of different RoomLife components
################################################################################

set -e  # Exit on error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Script directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

################################################################################
# Helper Functions
################################################################################

print_banner() {
    echo -e "${BLUE}"
    echo "╔═══════════════════════════════════════════════════════╗"
    echo "║           RoomLife Simulation Launcher               ║"
    echo "╚═══════════════════════════════════════════════════════╝"
    echo -e "${NC}"
}

print_success() {
    echo -e "${GREEN}✓ $1${NC}"
}

print_error() {
    echo -e "${RED}✗ $1${NC}"
}

print_info() {
    echo -e "${YELLOW}ℹ $1${NC}"
}

check_python() {
    if ! command -v python3 &> /dev/null; then
        print_error "Python 3 is not installed or not in PATH"
        exit 1
    fi

    python_version=$(python3 --version | cut -d' ' -f2)
    print_success "Python $python_version found"
}

check_dependencies() {
    print_info "Checking dependencies..."

    # Check if roomlife package is installed
    if ! python3 -c "import roomlife" &> /dev/null; then
        print_error "RoomLife package not found"
        print_info "Installing RoomLife package..."

        if [ -f "pyproject.toml" ]; then
            pip install -e . || {
                print_error "Failed to install RoomLife package"
                exit 1
            }
            print_success "RoomLife package installed"
        else
            print_error "pyproject.toml not found. Are you in the correct directory?"
            exit 1
        fi
    else
        print_success "RoomLife package is installed"
    fi

    # Check tkinter for GUI
    if ! python3 -c "import tkinter" &> /dev/null; then
        print_error "Tkinter is not installed"
        print_info "Install tkinter with: sudo apt-get install python3-tk (Ubuntu/Debian)"
        exit 1
    fi
}

launch_gui() {
    print_info "Launching RoomLife GUI..."

    if [ ! -f "roomlife_gui.py" ]; then
        print_error "roomlife_gui.py not found in current directory"
        exit 1
    fi

    print_success "Starting GUI application..."
    python3 roomlife_gui.py
}

launch_rest_server() {
    print_info "Launching REST API Server..."

    if [ ! -f "examples/api_rest_server.py" ]; then
        print_error "examples/api_rest_server.py not found"
        exit 1
    fi

    # Check if Flask is installed
    if ! python3 -c "import flask" &> /dev/null; then
        print_error "Flask is not installed"
        print_info "Install Flask with: pip install flask flask-cors"
        exit 1
    fi

    print_success "Starting REST API server on http://localhost:5000"
    print_info "Press Ctrl+C to stop the server"
    python3 examples/api_rest_server.py
}

launch_cli() {
    print_info "Launching CLI Demo..."

    if [ ! -f "examples/api_cli_demo.py" ]; then
        print_error "examples/api_cli_demo.py not found"
        exit 1
    fi

    print_success "Starting CLI application..."
    python3 examples/api_cli_demo.py
}

launch_basic_example() {
    print_info "Running basic API usage example..."

    if [ ! -f "examples/api_basic_usage.py" ]; then
        print_error "examples/api_basic_usage.py not found"
        exit 1
    fi

    python3 examples/api_basic_usage.py
}

launch_all() {
    print_info "Launching all components in separate terminals..."

    # Check if we're in a graphical environment
    if [ -z "$DISPLAY" ]; then
        print_error "No display found. Cannot launch multiple terminals."
        print_info "Please launch components individually."
        exit 1
    fi

    # Launch GUI in background
    if command -v gnome-terminal &> /dev/null; then
        gnome-terminal -- bash -c "cd '$SCRIPT_DIR' && python3 roomlife_gui.py; exec bash"
        print_success "Launched GUI in new terminal"
    elif command -v xterm &> /dev/null; then
        xterm -e "cd '$SCRIPT_DIR' && python3 roomlife_gui.py; exec bash" &
        print_success "Launched GUI in new terminal"
    else
        print_error "No supported terminal emulator found"
        print_info "Launching GUI in current terminal..."
        python3 roomlife_gui.py
    fi
}

show_menu() {
    echo ""
    echo "Select a component to launch:"
    echo ""
    echo "  1) GUI Application (Tkinter)"
    echo "  2) REST API Server"
    echo "  3) CLI Demo"
    echo "  4) Basic API Example"
    echo "  5) All Components (GUI only for now)"
    echo "  6) Run Tests"
    echo "  q) Quit"
    echo ""
}

run_tests() {
    print_info "Running tests..."

    if [ -d "tests" ]; then
        if command -v pytest &> /dev/null; then
            pytest tests/
        else
            print_error "pytest not found"
            print_info "Install pytest with: pip install pytest"
            exit 1
        fi
    else
        print_error "No tests directory found"
        exit 1
    fi
}

show_usage() {
    echo "Usage: $0 [OPTION]"
    echo ""
    echo "Options:"
    echo "  gui          Launch the GUI application"
    echo "  rest         Launch the REST API server"
    echo "  cli          Launch the CLI demo"
    echo "  example      Run basic API example"
    echo "  all          Launch all components"
    echo "  test         Run tests"
    echo "  menu         Show interactive menu (default)"
    echo "  -h, --help   Show this help message"
    echo ""
}

################################################################################
# Main Script
################################################################################

main() {
    print_banner
    check_python
    check_dependencies

    # Parse command line arguments
    if [ $# -eq 0 ]; then
        # No arguments, show interactive menu
        while true; do
            show_menu
            read -r -p "Enter your choice: " choice

            case $choice in
                1)
                    launch_gui
                    ;;
                2)
                    launch_rest_server
                    ;;
                3)
                    launch_cli
                    ;;
                4)
                    launch_basic_example
                    ;;
                5)
                    launch_all
                    ;;
                6)
                    run_tests
                    ;;
                q|Q)
                    print_info "Exiting..."
                    exit 0
                    ;;
                *)
                    print_error "Invalid choice. Please try again."
                    ;;
            esac

            echo ""
            read -r -p "Press Enter to continue..."
        done
    else
        # Handle command line arguments
        case $1 in
            gui)
                launch_gui
                ;;
            rest)
                launch_rest_server
                ;;
            cli)
                launch_cli
                ;;
            example)
                launch_basic_example
                ;;
            all)
                launch_all
                ;;
            test)
                run_tests
                ;;
            menu)
                exec "$0"  # Re-run with no arguments
                ;;
            -h|--help)
                show_usage
                ;;
            *)
                print_error "Unknown option: $1"
                show_usage
                exit 1
                ;;
        esac
    fi
}

# Run main function
main "$@"
