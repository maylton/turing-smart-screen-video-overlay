# Theme Editor versioned backups

Every validated atomic replacement of `theme.yaml` or `theme.yml` in the GTK
Theme Editor now creates a copy of the previous file under:

```text
<theme>/.theme-editor-backups/
```

The default retention is 20 versions per theme. Override it for a Theme Editor
process with:

```bash
TURING_THEME_BACKUP_RETENTION=50 theme-editor-gtk.py
```

Values are bounded from 1 to 200.

## Inspect backups

```bash
python3 theme-backups.py list res/themes/<theme>/theme.yaml
```

## Restore a backup

```bash
python3 theme-backups.py restore \
  res/themes/<theme>/theme.yaml \
  res/themes/<theme>/.theme-editor-backups/<backup>.yaml
```

Restoration is atomic and first backs up the current file, so restoring an older
version never destroys the latest state.

## Scope

The runtime guard is loaded only for `theme-editor-gtk.py`. It reacts only when:

- the destination is named `theme.yaml` or `theme.yml`;
- the source is the validated `<filename>.tmp` in the same directory;
- the destination is not already inside the backup directory.

Other `os.replace` calls and other application entry points are unaffected.
