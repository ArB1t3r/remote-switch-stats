#!/usr/bin/env python3
"""
Switch Remote Control — sys-botbase GUI Client

Launch: python main.py
"""

from src.app import App


def main() -> None:
    app = App()
    app.mainloop()


if __name__ == "__main__":
    main()
