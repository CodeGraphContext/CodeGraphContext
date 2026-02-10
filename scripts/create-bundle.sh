#!/bin/bash
# scripts/create-bundle.sh
# Helper script to create .cgc bundles from GitHub repositories

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Function to print colored output
print_info() {
    echo -e "${BLUE}ℹ${NC} $1"
}

print_success() {
    echo -e "${GREEN}✓${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}⚠${NC} $1"
}

print_error() {
    echo -e "${RED}✗${NC} $1"
}

# Check if required tools are installed
check_requirements() {
    print_info "Checking requirements..."
    
    if ! command -v git &> /dev/null; then
        print_error "git is not installed"
        exit 1
    fi
    
    if ! command -v cgc &> /dev/null; then
        print_error "cgc is not installed. Install with: pip install codegraphcontext"
        exit 1
    fi
    
    print_success "All requirements met"
}

# Parse command line arguments
if [ $# -lt 1 ]; then
    echo "Usage: $0 <github-repo> [output-name]"
    echo ""
    echo "Examples:"
    echo "  $0 numpy/numpy"
    echo "  $0 pandas-dev/pandas pandas"
    echo "  $0 tiangolo/fastapi fastapi-bundle"
    echo ""
    exit 1
fi

REPO=$1
OUTPUT_NAME=${2:-$(basename $REPO)}

# Extract owner and repo name
OWNER=$(dirname $REPO)
REPO_NAME=$(basename $REPO)

print_info "Creating bundle for ${OWNER}/${REPO_NAME}"

# Create temporary directory
TEMP_DIR=$(mktemp -d)
trap "rm -rf $TEMP_DIR" EXIT

print_info "Using temporary directory: $TEMP_DIR"

# Clone repository
print_info "Cloning repository..."
cd $TEMP_DIR
if ! git clone --depth 1 "https://github.com/${OWNER}/${REPO_NAME}.git" repo; then
    print_error "Failed to clone repository"
    exit 1
fi
print_success "Repository cloned"

cd repo

# Get repository metadata
print_info "Gathering metadata..."
COMMIT_SHA=$(git rev-parse HEAD)
COMMIT_SHORT=$(git rev-parse --short HEAD)
TAG=$(git describe --tags --abbrev=0 2>/dev/null || echo "main")
DATE=$(date +%Y%m%d)

print_info "  Commit: $COMMIT_SHORT"
print_info "  Tag: $TAG"

# Index repository
print_info "Indexing repository (this may take a while)..."
if ! cgc index .; then
    print_error "Failed to index repository"
    exit 1
fi
print_success "Repository indexed"

# Export to bundle
BUNDLE_NAME="${OUTPUT_NAME}-${TAG}-${COMMIT_SHORT}.cgc"
print_info "Exporting to bundle: $BUNDLE_NAME"

if ! cgc export "$BUNDLE_NAME" --repo .; then
    print_error "Failed to export bundle"
    exit 1
fi

# Move bundle to original directory
mv "$BUNDLE_NAME" "$OLDPWD/"
print_success "Bundle created: $OLDPWD/$BUNDLE_NAME"

# Show bundle info
BUNDLE_PATH="$OLDPWD/$BUNDLE_NAME"
BUNDLE_SIZE=$(du -h "$BUNDLE_PATH" | cut -f1)

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
print_success "Bundle created successfully!"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo "  Repository: ${OWNER}/${REPO_NAME}"
echo "  Bundle:     $BUNDLE_NAME"
echo "  Size:       $BUNDLE_SIZE"
echo "  Location:   $BUNDLE_PATH"
echo ""
echo "To use this bundle:"
echo "  cgc load $BUNDLE_NAME"
echo ""
echo "To inspect the bundle:"
echo "  unzip -l $BUNDLE_NAME"
echo "  unzip -p $BUNDLE_NAME metadata.json | jq"
echo ""
