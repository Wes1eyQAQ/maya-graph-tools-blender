# FAQ and troubleshooting

**Installed a new ZIP but still seeing the old UI?** Disable the old add-on, install the new ZIP, enable it, then fully restart Blender. A running Python module can otherwise remain older than the files on disk. Confirm Maya 1.26 in the header.

**Is this drawing fake replacement curves?** No. Animation remains in native Blender F-curves. Custom diamond/triangle graphics are display overlays connected to real key/handle positions.

**Does a loop copy my first pose to the last?** No. Match endpoint values first. The loop operation changes handles and optional interior handle types, not key values.

**Why did a loop operation cancel?** A participating curve may lack a key at one of the selected boundary times, or have overlapping endpoint keys. Select a range whose endpoints exist on every intended curve. The operation validates pairs before changing them.

**Why did interior tangents change?** Smooth Inside Loop (Auto Clamped) is enabled by default. Disable it to preserve manual interior tangents.

**What does 100% mean in the region settings?** It means unchanged distance from the selected region's center. Lower/upper bounds can be scaled independently; timing has its own percentage. See the guide for an example.

**Can I use newer Blender versions?** They are not currently validated. The guarded Blender 4.4 adapter does not operate on unknown layouts. Please report your version/platform and a minimal reproduction.

**Does it need an API key, subscription or cloud connection?** No. The add-on runs locally. Its language preference is stored in a small JSON file in Blender's user configuration directory.

**Will dragging across another key delete it?** The direct-drag implementation preserves overlapping keys rather than using FCurve.update() deduplication. Other native Blender operations can still apply their own merging rules.

**Can it edit bone rest axes?** The companion Precision Axes tool adjusts the rotation tool coordinate system, not a bone's rest axes or existing animation channels.
