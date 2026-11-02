# Technical Precision

Current UI design reference for the Smart Factory Annotation Tool: PPE, safety
signs and worker behavior, with separate Labeling and Inference workflows.
The interface uses a dark theme, compact controls, teal accents and layered
surfaces to keep media and annotations prominent.

## Sources of truth

Use this map to find the implementation behind each design rule. Source paths
are relative to the repository root.

| Concern | Source |
|---|---|
| Color, typography, spacing and radius tokens | `frontend/tailwind.config.js` |
| Shared control styles, decoration and motion | `frontend/src/index.css` |
| Font loading | `frontend/index.html` |
| Navigation and screens | `frontend/src/App.tsx`, `frontend/src/pages/` |
| Image class colors | `frontend/src/constants.ts` |
| Video status vocabulary | `frontend/src/features/video/videoPresentation.ts` |

The [token reference](#token-reference) mirrors named theme tokens. Component dimensions and local
utility overrides are described below. Configured tokens do not imply that every
screen uses them; this document describes the implementation rather than a
separate target design. Backend architecture is documented in
[ARCHITECTURE.md](ARCHITECTURE.md).

## Foundations

### Color and depth

Core surface, text and action colors are listed below. `on-*` tokens provide
foreground colors for their matching surfaces; the token reference contains
the complete palette.

| Role | Token / value | Use |
|---|---|---|
| App background | `background`, `surface` / `#0e1513` | Page foundation |
| Media stage / inputs | `surface-container-lowest` / `#09100e` | Recessed surfaces |
| Low panel | `surface-container-low` / `#161d1b` | Lists and cards |
| Panel / toolbar | `surface-container` / `#1a211f` | Main UI surfaces |
| Raised / hover | `surface-container-high` / `#242b2a` | Menus, dialogs, hover |
| Highest surface | `surface-container-highest` / `#2f3634` | Tracks and placeholders |
| Main / secondary text | `on-surface` / `#dde4e1`; `on-surface-variant` / `#bacac5` | Content and metadata |
| Border | `outline-variant` / `#3c4a46` | Panel and control separation |
| Primary | `primary` / `#57f1db`; `on-primary` / `#003731` | Active states, links, filled actions |
| Primary container | `primary-container` / `#2dd4bf`; `on-primary-container` / `#00574d` | Filled actions and selections |
| Error | `error` / `#ffb4ab`; `error-container` / `#93000a` | Errors and destructive feedback |

Depth combines tonal surfaces and thin borders with shadows on menus, dialogs,
selected thumbnails and hovered cards. Some screens also use faint teal radial
gradients, a 28px technical grid, panel rails and ambient stage decoration.

### Typography

Inter is used for headings and body text; JetBrains Mono for labels, frame
numbers and technical metadata. Both are loaded from Google Fonts with local
fallbacks. Named sizes are defined in the token reference: headings 18/24/32px,
body 14/16px, code 14px and labels 11/12px. Screens also use local sizes and
weight overrides, including 10px metadata and a 40px dashboard heading.

### Spacing and shape

The named spacing scale uses a 4px unit, 16px gutter, 24px margin and 48px toolbar.
Components also use finer spacing; the 4px unit is not a universal constraint.
`panel-width-sm` (280px) and `panel-width-lg` (400px) are configured tokens;
current workspace dimensions are listed separately below.

### Corner radius

This table maps Tailwind utilities to their current rendered radii, assuming
a 16px root font size. Theme overrides make this scale non-monotonic.

| Utility | Effective radius |
|---|---|
| `rounded`, `rounded-sm` | 2px |
| `rounded-md` | 6px (Tailwind default) |
| `rounded-lg` | 4px |
| `rounded-xl` | 8px |
| `rounded-full` | 12px |

These are the current theme values: `rounded-full` is a fixed radius, so it does
not guarantee a circle. Image bounding boxes have square corners.

## Screens and layout

All workspaces use a top toolbar and a flexible media stage with independently
scrolling panels. Workspace shells fill the viewport; landing pages use card grids.

### Screen map

Routes identify each screen; widths describe the current sidebar layout.
`md` refers to Tailwind's 768px breakpoint.

| Screen | Structure and behavior |
|---|---|
| Dashboard `/` | PPE, Sign and Behavior cards; image approval progress when available; one column, three from `md` |
| Task homes `/ppe`, `/sign`, `/behavior` | Labeling and Inference cards; one column, two from `md` |
| Image labeling `/task/:taskId` | 300px image list on the left, Konva canvas in the center, 300px Properties panel on the right |
| Video projects `/video` | Project selection and creation for Behavior labeling |
| Video labeling `/video/:projectId` | Video browser and queue on the left; player, playback controls and annotation/trim timeline in the center; inspector and review controls on the right |
| Detection inference `/ppe/inference`, `/sign/inference` | 288px media list, result image/video in the center, 256px class legend on the right |
| Behavior inference `/behavior/inference` | 288px video list, pose player and behavior timeline with raw prediction windows, 320px Events/Workers panel |

Image sidebars start open and can be toggled manually; the image list is vertical,
not a bottom filmstrip. Video sidebars default to 320px left and 360px right,
resize between 240px and 520px subject to a viewport cap during dragging, and
persist their widths in localStorage. They initially open at viewport widths of
900px (left) and 1200px (right), with manual toggles afterward. Video toolbar
controls and breadcrumbs also hide at responsive breakpoints. Inference panels
have fixed widths; there is no shared automatic-collapse behavior across screens.

## Components and interaction

### Controls and feedback

- **Filled actions:** use `primary`/`on-primary` or
  `primary-container`/`on-primary-container`. Image AI Batch Label uses the latter;
  image Export Dataset and Upload Images use outlined secondary styling.
- **Shared controls:** `.toolbar-icon` is 32px square; `.panel-button` and
  `.editor-input` are 32px high by default. Inputs use recessed backgrounds,
  outline borders and teal focus treatment. Individual screens have overrides.
- **Selection:** teal borders, tinted fills or rings mark active cards and tools.
  Image class controls use class-specific colors. There is no universal 4px
  active-indicator line or shared custom checkbox/radio design.
- **Status:** compact bordered `.status-pill` labels, progress bars, spinners and
  save indicators communicate activity. Video labeling distinguishes Saved,
  Saving and Unsaved changes. Errors use error colors; its dismissible feedback
  bar uses `alert` or `status` roles.
- **Dialogs and menus:** raised surfaces, outline borders and shadows;
  video labeling includes export and delete dialogs. Other flows also use native
  browser confirmations. Empty views provide import/upload guidance.

### Image annotations

Class IDs 0-7 use green `#10b981`, yellow `#eab308`, blue `#3b82f6`, red
`#ef4444`, purple `#a855f7`, orange `#f97316`, cyan `#06b6d4` and pink
`#ec4899`; higher IDs repeat the palette. Boxes use translucent class fills and
2px screen-space strokes. Selected boxes have white strokes and blue `#00a1ff`
transform controls. Class names are shown in Properties, not drawn on the canvas.

Image thumbnails distinguish active selection, label presence and approval.
The status marker means **Approved** (teal) or **Pending** (error color), not
processing success or failure.

The canvas supports selection, Shift multi-selection, drag/resize, drawing,
zoom, pan and overlay visibility. Shortcuts include `V` select, `H` pan,
`Space` held pan, `A`/`D` previous/next image, `Ctrl+Z` undo,
`Delete`/`Backspace` delete and `Escape` cancel drawing/selection rectangle.

### Video annotations and inference

The player fits media and pose overlays into the same viewport; fullscreen
retains the overlay. Labeling adds editable worker segments, annotation and trim
timelines, undo/redo, Suggestions (Threshold or Model), review and export.
Holding `Alt` displays the video-labeling shortcut guide.

### Video states and behavior colors

State labels describe processing or annotation progress. Behavior colors identify
worker activities consistently across the pose overlay and timelines.

| Meaning | Display |
|---|---|
| Processing state | Unprocessed, Processing, Ready, Failed |
| Annotation state | Unlabeled, Labeled, Approved |
| `others` behavior | Slate `#64748b` |
| `running` behavior | Blue `#3b82f6` |
| `falling` behavior | Red `#ef4444` |

Processing and approval are separate states. Behavior inference shows inspectable
predictions and events with worker selection and seeking, without annotation
editing. Its timeline fills uncovered worker ranges with `others`; raw window
predictions are shown separately. Detection inference displays rendered model
results and a class-color legend rather than an editable annotation canvas.

## Motion and accessibility

Shared controls use short color, border, shadow and press transitions. Menus,
dialogs and status messages enter in roughly 140-180ms; cards lift or shimmer on
hover, progress bars shimmer, and timeline segments animate after edits. Global
`prefers-reduced-motion` rules reduce animation and transition durations and
disable smooth scrolling.

Shared controls provide visible focus rings. Many video and inference controls
include accessible names, dialogs use dialog roles, and status/error messages
use live-region roles where implemented. These patterns are not applied uniformly
across every legacy control; this document does not assert full accessibility
or mobile-layout compliance.

## Token reference

This YAML block records the named theme values for reference; the application
reads its configuration from `frontend/tailwind.config.js`. Keep these values in
sync when changing the theme. The sections cover colors, typography, corner
radii and spacing; screen-specific overrides are documented above.

```yaml
name: Technical Precision
# Complete named color palette.
colors:
  surface: '#0e1513'
  surface-dim: '#0e1513'
  surface-bright: '#333b39'
  surface-container-lowest: '#09100e'
  surface-container-low: '#161d1b'
  surface-container: '#1a211f'
  surface-container-high: '#242b2a'
  surface-container-highest: '#2f3634'
  on-surface: '#dde4e1'
  on-surface-variant: '#bacac5'
  inverse-surface: '#dde4e1'
  inverse-on-surface: '#2b3230'
  outline: '#859490'
  outline-variant: '#3c4a46'
  surface-tint: '#3cddc7'
  primary: '#57f1db'
  on-primary: '#003731'
  primary-container: '#2dd4bf'
  on-primary-container: '#00574d'
  inverse-primary: '#006b5f'
  secondary: '#c8c6c5'
  on-secondary: '#303030'
  secondary-container: '#474746'
  on-secondary-container: '#b7b5b4'
  tertiary: '#dcd9d8'
  on-tertiary: '#313030'
  tertiary-container: '#c0bdbd'
  on-tertiary-container: '#4d4c4c'
  error: '#ffb4ab'
  on-error: '#690005'
  error-container: '#93000a'
  on-error-container: '#ffdad6'
  primary-fixed: '#62fae3'
  primary-fixed-dim: '#3cddc7'
  on-primary-fixed: '#00201c'
  on-primary-fixed-variant: '#005047'
  secondary-fixed: '#e5e2e1'
  secondary-fixed-dim: '#c8c6c5'
  on-secondary-fixed: '#1b1b1c'
  on-secondary-fixed-variant: '#474746'
  tertiary-fixed: '#e5e2e1'
  tertiary-fixed-dim: '#c8c6c5'
  on-tertiary-fixed: '#1c1b1b'
  on-tertiary-fixed-variant: '#474646'
  background: '#0e1513'
  on-background: '#dde4e1'
  surface-variant: '#2f3634'
# Named type styles; components may override individual properties.
typography:
  headline-lg:
    fontFamily: Inter
    fontSize: 32px
    fontWeight: '600'
    lineHeight: 40px
    letterSpacing: -0.02em
  headline-md:
    fontFamily: Inter
    fontSize: 24px
    fontWeight: '600'
    lineHeight: 32px
    letterSpacing: -0.01em
  headline-sm:
    fontFamily: Inter
    fontSize: 18px
    fontWeight: '500'
    lineHeight: 24px
  body-lg:
    fontFamily: Inter
    fontSize: 16px
    fontWeight: '400'
    lineHeight: 24px
  body-md:
    fontFamily: Inter
    fontSize: 14px
    fontWeight: '400'
    lineHeight: 20px
  code-md:
    fontFamily: JetBrains Mono
    fontSize: 14px
    fontWeight: '400'
    lineHeight: 20px
  label-caps:
    fontFamily: JetBrains Mono
    fontSize: 11px
    fontWeight: '600'
    lineHeight: 16px
    letterSpacing: 0.05em
  label-sm:
    fontFamily: JetBrains Mono
    fontSize: 12px
    fontWeight: '500'
    lineHeight: 16px
# Effective radius tokens, including inherited sm/md defaults.
rounded:
  sm: 0.125rem
  DEFAULT: 0.125rem
  md: 0.375rem
  lg: 0.25rem
  xl: 0.5rem
  full: 0.75rem
# Named spacing tokens; actual panel dimensions are in the screen map.
spacing:
  unit: 4px
  gutter: 16px
  margin: 24px
  panel-width-sm: 280px
  panel-width-lg: 400px
  toolbar-height: 48px
```
