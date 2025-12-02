# Update deployment cheatsheet

1. Update version in [pyproject.toml](http://_vscodecontentref_/0)
2. `alembic upgrade head`
3. `pre-commit run --all-files`
4. `Remove-Item -Recurse -Force dist, build, *.egg-info -ErrorAction SilentlyContinue`
5. `python.exe -m build`
6. `python.exe -m twine upload dist/*`
