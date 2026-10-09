# Maya Graph Tools for Blender

**Spend less time managing animation channels, and more time shaping motion.**

Maya-inspired Graph Editor tools for Blender, built around real animation work: click a channel, drag its keys directly, and match a local loop without fighting neighboring clips.

[中文介绍](README.zh-CN.md) · [User guide](docs/USER_GUIDE.md) · [Download v1.26](downloads/MayaGraphTools-1.26.zip)

![Workflow overview — an illustration, not a Blender screenshot](assets/workflow-overview.svg)

## Why use it?

- **Single-click channel focus.** A controller/channel list keeps Translate, Rotate and Scale channels within reach. Display isolation keeps the underlying channels available for bulk edits.
- **A bounded channel list.** Eight visible rows with independent scrolling; many selected controllers no longer push every setting down the sidebar. The first controller expands by default, and the others remain collapsible.
- **Direct key dragging.** Grab a key and drag. Default movement changes its value vertically; hold **Shift** for free time/value movement.
- **Point-only box selection.** Box selection targets keys rather than accidentally selecting tangent handles. Yellow diamond keys and small triangular handles make the two easier to distinguish.
- **An R editing box.** Move or scale selected key regions using the box interior, edges and corners. Independent lower/upper boundary percentages give precise value scaling.
- **Local loop generation.** The earliest and latest selected key times define a loop, independently of playback range. Neighboring key values determine whether the seam should flatten or match Free tangents.
- **Optional interior cleanup.** Match endpoints → set interior handles to **Auto Clamped** → recalculate → match endpoints again. Disable this when you want to retain hand-edited interior tangents.
- **English by default.** One button cycles **English → 中文 → 日本語**. Question-mark help explains settings on hover or click.

## Install

1. Download **[MayaGraphTools-1.26.zip](downloads/MayaGraphTools-1.26.zip)**. Do not use GitHub's repository source ZIP as the installer.
2. In Blender, open **Edit → Preferences → Add-ons → Install from Disk** and choose the installer ZIP.
3. Enable **Maya Graph Tools**. When upgrading, disable the older version first and restart Blender afterward.
4. Open a Graph Editor and click **Maya 1.26** in its header. The **Maya Channels** sidebar contains the tools.

## Quick start

| Task | Action |
| --- | --- |
| Focus a channel | Click its row in the controller list |
| Show multiple curves | Shift/Ctrl-click channel rows |
| Move keys vertically | Drag a selected key |
| Move time and value together | Hold Shift while dragging |
| Select keys without handles | Press B |
| Edit a selected key region | Press R |
| Generate a local loop | Select boundary keys, then click **Generate Loop: Selected Keys** |
| Change interface language | Click **Language** at the top of the panel |
| Understand a setting | Hover over, or click, its question mark |

## Compatibility and practical limits

**Validated on Windows with Blender 4.4.3, 64-bit.** The published package declares Blender 4.4 as its minimum version. Other Blender versions and platforms have not been validated.

The normalized diamond overlay and optional thin-curve feature depend on a guarded Blender 4.4 native-layout adapter. On unsupported versions, normalized custom markers fall back to native points, and the thin-curve adapter is disabled. Thin Curves is off by default.

Loop generation adjusts handles, **not endpoint poses**. Match your endpoint values first. A participating curve must have real keys at both selected boundary times; missing or overlapping endpoint keys cancel the operation before edits. Auto Clamped cleanup replaces interior hand-edited tangents when enabled. The tool preserves key values and works on actual Blender F-curves rather than substitute animation curves.

This is a community add-on for testing and feedback, not a promise of identical behavior across every rig or Blender configuration. Please report reproducible issues with a small, shareable test file.

## Documentation and feedback

- [User guide](docs/USER_GUIDE.md)
- [中文使用指南](docs/USER_GUIDE.zh-CN.md)
- [Troubleshooting and FAQ](docs/FAQ.md)
- [Release notes](docs/RELEASE_NOTES.md)
- [Contributing](CONTRIBUTING.md)

## License and credits

GPL-3.0-or-later. See [LICENSE](LICENSE).

Workflow design and hands-on iteration came from the project creator's animation work; implementation was developed with Codex. This independent project is not affiliated with Autodesk or Blender Foundation.
