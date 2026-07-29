#!/usr/bin/env bash
# ArbPlus Test Runner — executes all example .arb files sequentially
# Usage:  ./run_examples.sh           # run all
#         ./run_examples.sh 5         # run only example 5
#         ./run_examples.sh 10 14     # run examples 10 through 14
#
# Child scripts (child.arb, child_noreturn.arb, child_types.arb) are skipped
# because they require parent-provided arguments (tested via 24_run_arb.arb).

set -euo pipefail
cd "$(dirname "$0")"

INTERPRETER="python3 interpreter.py"
EXAMPLES_DIR="examples"
PASSED=0
FAILED=0
SKIPPED=0
FAILED_LIST=()

# Scripts that need parent-provided args — skip standalone execution
SKIP_FILES=(
    "child.arb"
    "child_noreturn.arb"
    "child_types.arb"
)

# Text colors
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[0;33m'
CYAN='\033[0;36m'
BOLD='\033[1m'
NC='\033[0m' # No Color

should_skip() {
    local fname
    for fname in "${SKIP_FILES[@]}"; do
        [[ "$1" == "$fname" ]] && return 0
    done
    return 1
}

# Determine which files to run
if [[ $# -ge 1 ]]; then
    # Specific examples requested (by number)
    FILES=()
    for num in "$@"; do
        # Try to find file matching the number (01, 1, etc.)
        found=$(ls "$EXAMPLES_DIR"/[0-9]*"$num"*.arb 2>/dev/null || true)
        if [[ -n "$found" ]]; then
            FILES+=($found)
        fi
    done
    if [[ ${#FILES[@]} -eq 0 ]]; then
        # Fallback: try direct pattern
        for f in "$EXAMPLES_DIR"/*.arb; do
            base=$(basename "$f" .arb)
            for num in "$@"; do
                [[ "$base" == *"$num"* ]] && FILES+=("$f")
            done
        done
    fi
    FILES=($(printf '%s\n' "${FILES[@]}" | sort -u))
else
    # Run all .arb files in sorted order
    FILES=($(ls "$EXAMPLES_DIR"/*.arb | sort))
fi

TOTAL=${#FILES[@]}
if [[ $TOTAL -eq 0 ]]; then
    echo -e "${RED}No example files found in ${EXAMPLES_DIR}/${NC}"
    exit 1
fi

echo -e "${BOLD}ArbPlus Test Runner${NC}"
echo -e "${CYAN}──────────────────────────────────────────────${NC}"
echo -e "  Running ${TOTAL} example file(s)"
echo -e "${CYAN}──────────────────────────────────────────────${NC}"
echo ""

for f in "${FILES[@]}"; do
    fname=$(basename "$f")
    
    if should_skip "$fname"; then
        echo -e "  ${YELLOW}SKIP${NC}  $fname  (requires parent args, tested via 24_run_arb.arb)"
        ((SKIPPED=$((SKIPPED + 1))))
        continue
    fi
    
    # Extract example number for display
    num=""
    if [[ "$fname" =~ ^([0-9]+)_ ]]; then
        num="${BASH_REMATCH[1]}"
    fi
    
    label="$fname"
    [[ -n "$num" ]] && label="Example $num: $fname"
    
    # Run the interpreter, capture output
    output=$($INTERPRETER "$f" 2>&1) || true
    
    # Check for failure indicators
    if echo "$output" | grep -qiE '^Traceback|^ArbPlus Error|^Error:|^Parse error' && \
       ! echo "$output" | grep -q "All Part.*tests passed"; then
        echo -e "  ${RED}FAIL${NC}  $label"
        # Show first error line
        first_error=$(echo "$output" | grep -m1 -E '^Traceback|^ArbPlus Error|^Error:|^Parse error')
        [[ -n "$first_error" ]] && echo -e "        → $first_error"
        ((FAILED=$((FAILED + 1))))
        FAILED_LIST+=("$fname")
    else
        echo -e "  ${GREEN}PASS${NC}  $label"
        ((PASSED=$((PASSED + 1))))
    fi
done

echo ""
echo -e "${CYAN}──────────────────────────────────────────────${NC}"
echo -e "  ${GREEN}Passed:${NC}  $PASSED"
echo -e "  ${RED}Failed:${NC}  $FAILED"
echo -e "  ${YELLOW}Skipped:${NC} $SKIPPED"
echo -e "  Total:   $((PASSED + FAILED + SKIPPED))"
echo -e "${CYAN}──────────────────────────────────────────────${NC}"

if [[ ${#FAILED_LIST[@]} -gt 0 ]]; then
    echo -e "\n  ${RED}Failed files:${NC}"
    for f in "${FAILED_LIST[@]}"; do
        echo -e "    • $f"
    done
fi

echo ""
if [[ $FAILED -eq 0 ]]; then
    echo -e "${GREEN}${BOLD}✓ All tests passed!${NC}"
    exit 0
else
    echo -e "${RED}${BOLD}✗ $FAILED test(s) failed.${NC}"
    exit 1
fi
