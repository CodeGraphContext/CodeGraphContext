#!/bin/bash
# Quick test runner for CodeGraphContext Final Test Suite

set -e  # Exit on error

echo "🧪 CodeGraphContext Final Test Suite"
echo "==================================="
echo ""

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

# Check if pytest is installed
if ! command -v pytest &> /dev/null; then
    echo -e "${RED}❌ pytest not found. Please install it:${NC}"
    echo "   pip install pytest pytest-asyncio pytest-mock typer"
    exit 1
fi

# Export PYTHONPATH to include src
export PYTHONPATH=$PYTHONPATH:$(pwd)/src

# Parse arguments
TEST_TYPE="${1:-all}"

case "$TEST_TYPE" in
    "unit"|"1")
        echo -e "${YELLOW}Running Unit Tests (Core, Parsers)...${NC}"
        pytest tests/unit/ -v
        ;;
    
    "integration"|"int"|"2")
        echo -e "${YELLOW}Running Integration Tests (CLI, MCP)...${NC}"
        pytest tests/integration/ -v
        ;;
    
    "e2e"|"3")
        echo -e "${YELLOW}Running E2E User Journeys (Slow)...${NC}"
        pytest tests/e2e/ -v
        ;;
    
    "fast")
        echo -e "${YELLOW}Running Fast Tests (Unit + Integration)...${NC}"
        pytest tests/unit/ tests/integration/ -v
        ;;
    
    "all")
        echo -e "${YELLOW}Running All Tests...${NC}"
        pytest tests/ -v
        ;;
    
    "help"|"-h"|"--help")
        echo "Usage: ./tests/run_tests.sh [option]"
        echo ""
        echo "Options:"
        echo "  unit         - Run unit tests (fast)"
        echo "  integration  - Run integration tests (mid)"
        echo "  e2e          - Run E2E tests (slow, requires environment)"
        echo "  fast         - Run unit + integration"
        echo "  all          - Run everything [default]"
        exit 0
        ;;
    
    *)
        echo -e "${RED}❌ Unknown option: $TEST_TYPE${NC}"
        echo "Run './tests/run_tests.sh help' for usage information"
        exit 1
        ;;
esac

echo ""
echo -e "${GREEN}✅ Tests completed!${NC}"
