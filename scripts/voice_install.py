"""Compatibility entrypoint for offline, pinned clean-checkout voice installation.

First follow voice/SETUP.md; downloads are a separate explicit command. This file
no longer depends on development ledgers, benchmark wheels or inherited packages.
"""

if __package__:
    from .voice_setup import main
else:
    from voice_setup import main

if __name__ == "__main__":
    raise SystemExit(main(["install"]))
