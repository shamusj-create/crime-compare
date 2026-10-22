# CrimeLedger visual direction

Sister to politicians.compare / CivicLedger. Reuse the family's white paper, dark navy ink, blue accent, fine rules, large Iowan/Palatino/Georgia serif headings and restrained system sans controls. No remote font or image requests. Tables and source evidence are the primary surface.

The identifying feature is a geographically accurate England and Wales silhouette on every row, with the relevant area shaded blue. A larger context map follows selected areas. Geometry is official ONS open data, never generated artwork.

Tokens: ink #101624, secondary #273249, muted #667085, line #cbd2de, paper #fff, soft paper #f7f9fc, blue #0a3fb7, blue hover #062f91, blue soft #eef4ff, decreasing count #087f78, increasing count #b74723. Direction colour accompanies text and arrows, not colour alone.

Desktop: 68px masthead, 34px evidence bar, generous serif introduction, then an 800–1000px comparison table with a 300–340px context column. At 900px context goes below. At 600px controls wrap, row ancillary counts collapse, table retains area, rate and year change; each map remains legible. Never overflow the body.

Interaction: geography and crime selectors, area search, region filter, rate/count sorting, shareable URLs, CSV export, clickable map and area detail, up to three areas in comparison dialog. Native dialog handles focus confinement and Escape. Visible keyboard focus, 44px targets and reduced motion supported.

Good CSS references reviewed: defensive min-width for grid/table children, fluid type with clamp, visible focus and press feedback. Adapted to existing family tokens rather than adding a CSS framework.
