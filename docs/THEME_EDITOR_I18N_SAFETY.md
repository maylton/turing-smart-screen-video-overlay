# Theme Editor i18n value safety audit

This audit documents the safety boundary for the GTK Theme Editor Portuguese
translation work.

The goal is to translate user-facing labels without changing the canonical theme
YAML values that are saved when the user applies properties.

## Safety rules

1. UI strings may be translated.
2. Theme YAML keys must remain canonical, for example `FONT_SIZE`, `BAR_COLOR`,
   `PREVIEW_BACKGROUND`, `ENABLED`, and `OVERLAY`.
3. Theme YAML values must remain canonical, for example `left`, `center`, `lt`,
   `native`, `horizontal`, `auto`, paths, filenames, fonts, numbers, colors, and
   booleans.
4. Translation hooks must not patch generic text entry values. Values typed into
   `Gtk.Entry` or `Adw.EntryRow` are data, not labels.
5. Dropdown display labels may be translated only when the code keeps a separate
   source-of-truth value list or uses the selected index against an unchanged
   backing list.

## Audited safe paths

### Component presets

`create_component_preset_row()` builds translated display labels, but the saved
updates come from `_theme_component_preset_updates`, a tuple copied from the
original preset dictionaries. Applying a preset writes those dictionaries to the
selected node, not the translated label text.

Safe invariant:

```python
updates = dropdown._theme_component_preset_updates
current[key] = copy.deepcopy(value)
```

### Property presets

`create_property_preset_dropdown()` builds display labels separately from values:

```python
labels = tuple(label for label, _value in options)
values = tuple(value for _label, value in options)
dropdown._theme_preset_values = values
```

When a preset is selected, the code writes the canonical value into the target
entry using `value_to_text()`. It does not save the translated label.

### Text style presets

`create_text_style_preset_row()` uses the selected index to look up the original
preset name from the unchanged `preset_names` list, then applies the updates
returned by `text_style_updates()`.

### Choice rows

Choice rows keep canonical value arrays on the widget with
`_theme_choice_values`; selection changes are resolved through those values, not
through the translated display strings.

### Gradient direction

The gradient editor keeps translated labels separate from canonical direction
values:

```python
direction_options = (
    ("Auto", "auto"),
    ("Horizontal", "horizontal"),
    ...
)
direction_values = [value for _label, value in direction_options]
```

Saving uses `direction_values`, so YAML receives `auto`, `horizontal`,
`vertical`, `right-to-left`, or `bottom-to-top`.

## Translation hook boundaries

`library/theme_editor_widget_i18n.py` deliberately patches only:

- constructor keyword labels such as `label`, `title`, `subtitle`, `tooltip_text`,
  `placeholder_text`, `heading`, and `body`;
- label/title/subtitle setter methods;
- dialog response labels;
- dropdown/string-list display labels.

It does **not** patch `set_text()`. This is intentional because `set_text()` is
used by entries that carry data to be parsed and saved into YAML.

## Manual audit checklist

Use a copied theme, then:

1. Open `Temas/Galeria → Editar` with `TURING_SMART_SCREEN_LANG=pt_BR`.
2. Select a text element and choose `Preset de texto`.
3. Click `Aplicar alterações de propriedade`.
4. Check `theme.yaml`: `ALIGN` should remain `left`, `center`, or `right`, not
   `Esquerda`, `Centro`, or `Direita`.
5. Select a video element and change/apply properties.
6. Check `theme.yaml`: `MODE` should remain `native`, paths should remain paths,
   and filenames should remain unchanged.
7. Select a gradient direction and apply it.
8. Check `theme.yaml`: `DIRECTION` should remain `auto`, `horizontal`,
   `vertical`, `right-to-left`, or `bottom-to-top`.

If any translated Portuguese term is written into `theme.yaml`, the i18n patch
must be treated as a regression and reverted for that control path.
