# ab000009 gold provenance

## Direct visual observation
Clear chess layout and full starting position, but piece glyphs are stylistically inconsistent/odd (some look like mixed symbols), coordinates are tiny, and yellow New Game bar feels unrelated to the green/charcoal system.

## Independent axis reviews
- **layout:** Slightly enlarge board and tighten the oversized empty move-history panel.
- **spacing:** Align right-panel cards and controls to the board edges with consistent padding.
- **color_type:** Replace yellow bar with the board accent family; improve coordinate contrast.
- **style_orig:** Use one coherent classic chess-piece SVG/glyph style for all 32 pieces.

## MAD cross-critique / resolved trade-off
Enlarging pieces aids recognition but can crowd squares. Use consistent silhouettes at about 62% square height and preserve clear square breathing room.

## Exact revisions sent to Qwen

### GOLD-FUSED
Polish rather than restructure: replace every piece with one consistent, recognizable classic chess set, enlarge coordinate labels, and bring the right panel into the same green/ivory/charcoal system by removing the unrelated yellow New Game strip. Slightly enlarge the board, tighten the empty history card, and align all controls and card edges.

### GOLD-AXES
Use a single coherent SVG or Unicode chess set with consistent stroke, fill and scale for all 32 starting pieces. Increase board/coordinate legibility and preserve square breathing room. Normalize right-panel spacing and reduce dead space in move history. Replace the yellow CTA with a restrained green or ivory accent and align controls to the panel grid.

### GOLD-MAD
Keep the restrained club-like interface and complete starting layout. Correct the most visible craft defect by redrawing all pieces in one classic silhouette system at consistent size. Enlarge coordinates modestly, tighten the right-panel vertical rhythm, and recolor New Game to the existing green/ivory palette. Do not add decorative chess imagery or overcrowd squares.
