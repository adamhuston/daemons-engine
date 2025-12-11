Here are the commands for building and uploading a new PyPI package:

```powershell
# 1. Delete old build artifacts
Remove-Item -Recurse -Force dist, build, *.egg-info -ErrorAction SilentlyContinue

# 2. Build the package
python -m build

# 3. Upload to PyPI (production)
python -m twine upload dist/*

# Or upload to TestPyPI first
python -m twine upload --repository testpypi dist/*
```

Make sure you have the required tools installed:
```powershell
pip install build twine
```

You'll be prompted for your PyPI credentials (or use an API token).
