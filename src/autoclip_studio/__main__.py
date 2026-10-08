"""Desktop entry point. --doctor works without launching the GUI."""
import sys

if __name__ == '__main__':
    if len(sys.argv) > 1 and sys.argv[1] == '--doctor':
        from .doctor import run
        raise SystemExit(run())
    from .app import main
    main()
