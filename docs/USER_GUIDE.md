# User guide

## Channel list

Select an animated object or pose controllers, then enable **Maya 1.26** in a Graph Editor. Click a channel to focus it. Shift/Ctrl-click adds or removes channels. Show All restores all listed curves; Automatic: ALL Channels affects every listed channel on the scoped controllers.

The controller list has its own scrollbar and eight visible rows. Triangles expand/collapse groups; search can match translated channel labels. When controller selection changes, the first controller is expanded and the others are collapsed. You can expand them manually afterward.

## Keys and tangents

Drag a diamond key directly: vertical movement is the default. Shift enables both time and value movement. Release confirms; Esc cancels the drag. B selects key points without selecting handles. Only selected keys show their tangent handles; click a handle directly to edit it.

## R region box

Select keys and press R. With no keys selected, R starts point-only box selection. Drag inside the box to move, edges to scale one dimension, or corners to scale both. In this box, Shift constrains movement/scaling to values vertically. Enter finishes; Esc cancels the current drag.

### Boundary percentages

Percentages are measured from the selected region's center, not from zero on the value axis.

Example: values span -10 to +10, so the center is 0. Lower Boundary 60% puts the lower bound at -6; Upper Boundary 80% puts the upper bound at +8. Apply Percentages remaps the selected values across these bounds. 100% keeps each bound unchanged. Time Width 50% halves the selected timing intervals about the time center.

Do not expect repeated Apply clicks to be an absolute setting for the original curve: each application uses the current selected bounds.

## Local loops

1. Match endpoint pose/key values yourself.
2. Select keys at the intended beginning and end. Interior selected keys are permitted: the earliest/latest selected times define the boundaries.
3. Enable **Smooth Inside Loop (Auto Clamped)** if you want interior tangent cleanup.
4. Click **Generate Loop: Selected Keys** once.

The two boundary times are resolved before editing. Every participating curve must have real keys at those times. Missing or overlapping endpoints cancel the operation.

For each curve, the next interior key is compared with the start value, and the previous interior key with the end value. Both higher means a trough; both lower means a peak. Peak/trough seams flatten all four endpoint handles, with each endpoint's outside handle matching the inside handle's length. If neighbor directions differ, the end's incoming Free tangent matches the start's outgoing slope, with a length based on its local neighbor spacing.

With cleanup enabled: match the seam, set strictly interior handles to Auto Clamped, recalculate, then match the seam again. Endpoint handles stay Free. Key values and selection are unchanged. Disable cleanup to keep manually sculpted interior tangents.

## Language and help

English is the default. The top button cycles English → 中文 → 日本語 → English and remembers your choice. Question marks provide hover explanations; click for a readable popup. The same preference is shared with updated companion tools, if installed.
