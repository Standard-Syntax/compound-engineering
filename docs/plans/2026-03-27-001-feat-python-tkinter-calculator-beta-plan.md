---
title: feat: Add Python Tkinter calculator app
type: feat
status: active
date: 2026-03-27
origin: docs/brainstorms/2026-03-27-python-tkinter-calculator-requirements.md
---

# feat: Add Python Tkinter calculator app

## Overview

A standalone Python desktop calculator application using only the standard library (Tkinter) to provide a dependency-free basic four-function calculator.

## Problem Frame

Users need a simple desktop calculator with basic arithmetic operations (+, -, ×, ÷) that requires no external dependencies beyond Python itself. The calculator should feel like a traditional handheld calculator with button-only input.

## Requirements Trace

- R1. Application launches GUI window titled "Calculator" using Tkinter
- R2. Display area shows current number, starting at "0"
- R3. Digit buttons 0-9 update the display when clicked
- R4. Operation buttons (+, -, ×, ÷) support chaining
- R5. Decimal point button for fractional numbers
- R6. Equals button evaluates and displays result
- R7. Clear (AC) button resets to initial state
- R8. Division by zero displays "Error" without crashing
- R9. Standard operator precedence for sequential operations

## Scope Boundaries

- Buttons only — no keyboard input
- No scientific, programmer, or memory functions
- No history or theming

## Context & Research

### Relevant Code and Patterns

- Tkinter is part of Python standard library — no external patterns needed
- Standard calculator layout: display at top, buttons in grid below
- Classic button layout follows handheld calculator conventions (digits right, operations left or below)

## Key Decisions

- **Single-file script**: `calculator.py` in project root — no package structure needed for this scope
- **Grid-based layout**: 4 columns for digits 0-9 plus decimal and equals, operations in separate column
- **String-based expression storage**: Store display as string, evaluate using Python's `eval()` safely (limited to arithmetic ops)

## Implementation Units

- [ ] **Unit 1: Create calculator scaffold**

**Goal:** Basic Tkinter window with display area

**Requirements:** R1, R2

**Dependencies:** None

**Files:**
- Create: `calculator.py`

**Approach:**
- Import `tkinter` and `ttk` from standard library
- Create main window with title "Calculator"
- Configure window size (roughly 300x400 pixels)
- Add a read-only display `Entry` widget at top, right-aligned, large font
- Start display with "0"

**Patterns to follow:**
- Standard Tkinter application structure with `if __name__ == "__main__":` guard

**Test scenarios:**
- Application launches without error
- Window has correct title
- Display shows "0" initially

**Verification:**
- Running `python calculator.py` opens a visible window titled "Calculator"

---

- [ ] **Unit 2: Add digit and decimal buttons**

**Goal:** Digit buttons 0-9 and decimal point that update the display

**Requirements:** R3, R5

**Dependencies:** Unit 1

**Files:**
- Modify: `calculator.py`

**Approach:**
- Create a `create_digit_button(digit)` helper that returns a button widget
- Each digit button calls a handler that appends the digit to the display string
- Handle leading zero case: if display is "0" and user clicks "0", don't add another zero
- Handle decimal: if display already has a decimal point, don't add another
- Layout digits in standard phone/calculator layout:
  ```
  [7] [8] [9]
  [4] [5] [6]
  [1] [2] [3]
  [0] [.] [=]
  ```
- Use `ttk.Button` for consistent styling

**Patterns to follow:**
- Tkinter button creation with `command=` callback

**Test scenarios:**
- Clicking "5" when display shows "0" changes display to "5"
- Clicking "5" when display shows "12" changes display to "125"
- Clicking "." when display shows "3" changes display to "3."
- Clicking "." when display already has "." does nothing

**Verification:**
- Each digit button updates display correctly

---

- [ ] **Unit 3: Add operation and control buttons**

**Goal:** Add +, -, ×, ÷, AC buttons with proper calculation logic

**Requirements:** R4, R7, R8, R9

**Dependencies:** Unit 2

**Files:**
- Modify: `calculator.py`

**Approach:**
- Add operation buttons to the left of or above digit grid
- Store `first_operand` (float) and `operation` (string) when an operation is pressed
- When equals is pressed, evaluate `first_operand op second_operand`
- For division, check if second_operand is 0 before dividing
- Implement basic two-operand logic: `first_operand OP second_operand = result`
- For R9 (operator precedence in sequential entry), store each operation and apply when equals is pressed — Python's `eval()` handles precedence naturally when we build the expression string
- AC button resets display to "0", clears first_operand and operation

**Layout suggestion:**
```
[+] [−] [×] [÷]
[7] [8] [9]
[4] [5] [6]
[1] [2] [3]
[0] [.] [=]
[AC]
```

Or classic calculator with operations in a column:
```
[AC] [+/-] [%]
[7] [8] [9] [×]
[4] [5] [6] [−]
[1] [2] [3] [+]
[0] [.] [=] [÷]
```

For simplicity, use a 4-column grid without [+/-] and [%]:
```
[AC] [+] [−] [×]
[7] [8] [9] [÷]
[4] [5] [6]
[1] [2] [3]
[0] [.] [=]
```

Actually, standard 4-function calculator layout:
```
[AC] [÷] [×] [−]
[7] [8] [9] [+]
[4] [5] [6]
[1] [2] [3]
[0] [.] [=]
```

**Patterns to follow:**
- State machine pattern: track `current_value`, `pending_operation`, `new_input`

**Test scenarios:**
- Enter "5", press "+", enter "3", press "=" → display shows "8"
- Enter "10", press "−", enter "4", press "=" → display shows "6"
- Enter "6", press "×", enter "7", press "=" → display shows "42"
- Enter "20", press "÷", enter "4", press "=" → display shows "5"
- Press AC at any time → display resets to "0"

**Verification:**
- Basic chained operations work correctly
- AC clears all state

---

- [ ] **Unit 4: Add error handling and polish**

**Goal:** Division by zero protection and clean UI

**Requirements:** R8

**Dependencies:** Unit 3

**Files:**
- Modify: `calculator.py`

**Approach:**
- In the equals handler, before performing division, check if second operand is 0
- If division by zero would occur, display "Error" for 2 seconds then reset
- Use `after(2000, reset_display)` to clear error after delay
- Ensure all buttons are disabled or ignored during error state
- Add button padding and consistent styling using ttk style
- Configure button fonts and sizes for readability

**Patterns to follow:**
- Error state handling with timeout auto-recovery

**Test scenarios:**
- Enter "5", press "÷", enter "0", press "=" → display shows "Error"
- After 2 seconds, display returns to "0"
- During error state, clicking any button (except AC) does nothing

**Verification:**
- Division by zero never crashes and displays clean error message

## System-Wide Impact

- Standalone single-file application — no impact on existing codebase

## Risks & Dependencies

- No meaningful risks for a self-contained calculator script
- No external dependencies — Python standard library only

## Documentation / Operational Notes

- Run with: `python calculator.py`
- No installation or dependencies required

## Sources & References

- Origin document: [docs/brainstorms/2026-03-27-python-tkinter-calculator-requirements.md](../brainstorms/2026-03-27-python-tkinter-calculator-requirements.md)
- Tkinter documentation: https://docs.python.org/3/library/tkinter.html
