"""Basic four-function calculator using Tkinter."""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk


class Calculator:
    """Simple four-function calculator with Tkinter GUI."""

    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.root.title("Calculator")
        self.root.geometry("300x400")
        self.root.resizable(False, False)

        self.display_value = tk.StringVar(value="0")
        self._setup_display()
        self._setup_buttons()

    def _setup_display(self) -> None:
        display = ttk.Entry(
            self.root,
            textvariable=self.display_value,
            font=("Arial", 24),
            justify="right",
            state="readonly",
        )
        display.pack(fill="x", padx=10, pady=(20, 10))

    def _setup_buttons(self) -> None:
        container = ttk.Frame(self.root, padding=10)
        container.pack(fill="both", expand=True)

        for widget in container.winfo_children():
            widget.destroy()

        # Button layout: [AC] [÷] [×] [−]
        #                [7] [8] [9] [+]
        #                [4] [5] [6]
        #                [1] [2] [3]
        #                [0] [.] [=]

        # Row 0: AC, ÷, ×, −
        ttk.Button(container, text="AC", command=self._on_clear).grid(
            row=0, column=0, sticky="nsew", padx=2, pady=2
        )
        ttk.Button(container, text="÷", command=lambda: self._on_op("/")).grid(
            row=0, column=1, sticky="nsew", padx=2, pady=2
        )
        ttk.Button(container, text="×", command=lambda: self._on_op("*")).grid(
            row=0, column=2, sticky="nsew", padx=2, pady=2
        )
        ttk.Button(container, text="−", command=lambda: self._on_op("-")).grid(
            row=0, column=3, sticky="nsew", padx=2, pady=2
        )

        # Row 1: 7, 8, 9, +
        for i, digit in enumerate(["7", "8", "9"]):
            ttk.Button(
                container, text=digit, command=lambda d=digit: self._on_digit(d)
            ).grid(row=1, column=i, sticky="nsew", padx=2, pady=2)
        ttk.Button(container, text="+", command=lambda: self._on_op("+")).grid(
            row=1, column=3, sticky="nsew", padx=2, pady=2
        )

        # Row 2: 4, 5, 6
        for i, digit in enumerate(["4", "5", "6"]):
            ttk.Button(
                container, text=digit, command=lambda d=digit: self._on_digit(d)
            ).grid(row=2, column=i, sticky="nsew", padx=2, pady=2)

        # Row 3: 1, 2, 3
        for i, digit in enumerate(["1", "2", "3"]):
            ttk.Button(
                container, text=digit, command=lambda d=digit: self._on_digit(d)
            ).grid(row=3, column=i, sticky="nsew", padx=2, pady=2)

        # Row 4: 0, ., =
        ttk.Button(container, text="0", command=lambda: self._on_digit("0")).grid(
            row=4, column=0, sticky="nsew", padx=2, pady=2
        )
        ttk.Button(container, text=".", command=self._on_decimal).grid(
            row=4, column=1, sticky="nsew", padx=2, pady=2
        )
        ttk.Button(container, text="=", command=self._on_equals).grid(
            row=4, column=2, columnspan=2, sticky="nsew", padx=2, pady=2
        )

        for i in range(5):
            container.rowconfigure(i, weight=1)
        for i in range(4):
            container.columnconfigure(i, weight=1)

    def _on_digit(self, digit: str) -> None:
        current = self.display_value.get()
        if current == "Error":
            return
        if current == "0" and digit == "0":
            return
        if current == "0" and digit != "0":
            self.display_value.set(digit)
        else:
            self.display_value.set(current + digit)

    def _on_decimal(self) -> None:
        current = self.display_value.get()
        if current == "Error":
            return
        if "." not in current:
            self.display_value.set(current + ".")

    def _on_clear(self) -> None:
        self.display_value.set("0")

    def _on_op(self, op: str) -> None:
        current = self.display_value.get()
        if current == "Error":
            return
        self.display_value.set(current + f" {op} ")

    def _on_equals(self) -> None:
        expression = self.display_value.get()
        if expression == "Error":
            return
        try:
            result = eval(expression)  # noqa: S307
            self.display_value.set(str(result))
        except ZeroDivisionError:
            self.display_value.set("Error")
            self.root.after(2000, self._on_clear)
        except Exception:
            self.display_value.set("Error")
            self.root.after(2000, self._on_clear)


def main() -> None:
    root = tk.Tk()
    Calculator(root)
    root.mainloop()


if __name__ == "__main__":
    main()
