# Smoke test

Run in an isolated Blender process:

```text
blender --background --factory-startup --python tests/smoke_test.py
```

The test uses synthetic animation and a temporary configuration directory. It checks local loop generation, extreme interior tangent cleanup, endpoint handle types, unchanged key values and selection, unchanged keys outside the loop, and the optional cleanup-off behavior.

Validated with Blender 4.4.3 on Windows. Interactive dragging and marker alignment still require visual checks in Blender.
