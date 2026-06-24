# Tweeq Engineering Archive

Static archive of the Tweeq Engineering Medium publication.

The rendered GitHub Pages site lives in `docs/`. Source RSS and parsed post data live in `archive-data/` when regenerated with `build_archive.py`.

## Regenerate

```powershell
python build_archive.py
Copy-Item -LiteralPath site -Destination docs -Recurse -Force
```
