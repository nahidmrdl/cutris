"""Optional system-browser launcher for development and compatibility."""
from desktop import main

if __name__ == "__main__":
    raise SystemExit(main(["--browser", "--port", "3020"]))
