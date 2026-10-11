"""Compatibility entrypoint for offline, pinned clean-checkout voice installation.

First follow voice/SETUP.md; downloads are a separate explicit command. This file
no longer depends on development ledgers, benchmark wheels or inherited packages.
"""

from importlib import import_module

main = (
    import_module(".voice_setup", package=__package__).main
    if __package__
    else import_module("voice_setup").main
)

if __name__ == "__main__":
    raise SystemExit(main(["install"]))
