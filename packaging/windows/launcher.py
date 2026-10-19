"""Entry point for the packaged Windows app (PyInstaller runs this instead of python -m commu_aid)."""

from commu_aid.main import main

raise SystemExit(main())
