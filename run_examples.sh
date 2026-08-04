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
EXAMPLES_DIR="Examples"
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

if [[ ! -d "$EXAMPLES_DIR" ]]; then
    echo -e "${RED}Examples directory not found: ${EXAMPLES_DIR}${NC}"
    exit 1
fi

# Determine which files to run recursively
if [[ $# -ge 1 ]]; then
    FILES=()
    for num in "$@"; do
        while IFS= read -r f; do
            FILES+=("$f")
        done < <(find "$EXAMPLES_DIR" -type f -name '*.arb' | sort | while IFS= read -r f; do
            base=$(basename "$f" .arb)
            if [[ "$base" == *"$num"* ]]; then
                printf '%s\n' "$f"
            fi
        done)
    done
    FILES=($(printf '%s\n' "${FILES[@]}" | sort -u))
else
    mapfile -t FILES < <(find "$EXAMPLES_DIR" -type f -name '*.arb' | sort)
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

    num=""
    if [[ "$fname" =~ ^([0-9]+)_ ]]; then
        num="${BASH_REMATCH[1]}"
    fi

    label="$fname"
    [[ -n "$num" ]] && label="Example $num: $fname"

    set +e
    output=$("$INTERPRETER" "$f" 2>&1)
    status=$?
    set -e

    if [[ $status -ne 0 ]]; then
        echo -e "  ${RED}FAIL${NC}  $label"
        first_error=$(printf '%s\n' "$output" | grep -m1 -E '^Traceback|^ArbPlus Error|^Error:|^Parse error' || true)
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
