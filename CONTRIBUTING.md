# Contributing

Please describe the animation task, expected behavior, actual behavior, Blender version and operating system. A short screen recording and a minimal shareable .blend file make curve issues much easier to reproduce. Do not include private client rigs or production assets without permission.

Keep animation edits on native F-curves. Preserve key values unless the feature explicitly transforms values. Validate endpoint pairs before loop mutations, preserve point/handle selection behavior, and keep unsupported native adapters disabled.

UI translations live in MayaGraphTools/i18n.py. Test English, Chinese and Japanese after label/help changes. New data-layout adapters require verification against the exact Blender version and architecture; never guess offsets.

Run the bundled smoke test with Blender 4.4.3 in factory startup, using the command in tests/README.md. Source syntax can also be checked with Python's compileall.
