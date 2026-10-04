# VCMC-VP Global UX / Information Architecture Blueprint

Status: PREPARATION — not merged, not deployed.

## Goal
Make the VCMC-VP "house" feel orderly: every room has a clear place, purpose, hierarchy, entry/return path, and visual rhythm. "Rooms" means product areas; this document does not change VCMC governance.

## Global shell
Every authenticated screen follows one stable frame:
1. Brand / VCMC identity
2. Current location (room name + breadcrumb)
3. Primary navigation
4. Main content
5. Context/status area
6. Consistent mobile navigation
7. Clear return path

Do not make users hunt for the Home/Rooms navigation.

## Information architecture
Recommended grouping:

### Foundation
- Architecture
- Global Network

### Development
- Partners & Candidates
- Pilots
- Programs & Projects
- Development Direction
- Capital & Development

### Control & Proof
- Distribution
- Evidence & Verification
- Reconciliation

### Operations
- Security
- System & Operations
- Payment / Providers (simulation boundary)

The existing 13 rooms remain the canonical room set. Grouping is navigation only and does not remove or rename the rooms.

## Room template
Each room should use the same visual skeleton:
- room header: name, purpose, status/boundary
- primary action area
- current records / workspace
- evidence or history area where relevant
- empty state when no records exist
- success/error feedback
- return/navigation control

Room-specific functionality remains specific to the room.

## Visual hierarchy
Use predictable levels:
- Level 1: page/room title
- Level 2: section title
- Level 3: record/card title
- body: explanation/data
- label: field/status metadata
- action: primary/secondary controls

Avoid putting too many competing buttons at the top.

## "City / district / room" metaphor
If a future visual metaphor is used, keep it structural rather than decorative:
- VCMC = global house/platform
- domain group = district
- room = operational function
- record = entity/work item
- evidence = proof attached to a record
- reconciliation = control/result layer

The metaphor must never replace clear labels or make navigation ambiguous.

## Responsive behavior
Mobile:
- single-column content
- compact header
- grouped room navigation
- cards stack naturally
- forms use full available width
- important actions remain reachable
- no horizontal scrolling for ordinary content

Desktop:
- use available width without excessive stretching
- retain readable content measure
- use grids where they improve comparison
- keep navigation stable

## State design
Every operational component should visibly distinguish:
- empty
- loading
- saved/recorded
- error
- pending/review
- READY
- PROVEN
- UNKNOWN
- HOLD

Do not imply PROVEN from a successful save.

## Language behavior
All visible UI copy must come from localization keys once i18n is implemented.

Initial locales:
- id-ID
- en
- es

A locale switch changes UI copy consistently. Do not mix languages on the same ordinary screen.

## Visual polish pass
After functionality is frozen:
1. establish design tokens
2. establish typography
3. establish navigation hierarchy
4. standardize cards/forms/buttons
5. standardize status treatment
6. apply depth/elevation
7. refine icons and empty/loading/error states
8. apply Home
9. apply all rooms
10. verify mobile
11. verify desktop
12. verify each locale
13. accessibility review
14. regression test
15. deploy and collect evidence

## Tomorrow's work gate
Tomorrow should begin from the existing repository state, not a rebuild.

First:
- verify PR #16 state and tests
- verify current main/deployed baseline
- fix password reset-on-logout issue
- settle public access model (public registration/login versus SOVEREIGN controls)
- implement i18n foundation
- then begin visual system implementation

## Completion definition
The UI redesign is complete only when:
- all 13 rooms remain reachable
- each room has a coherent purpose and layout
- no functional regression is introduced
- selected locale produces a consistent language
- mobile and desktop layouts are usable
- status semantics remain truthful
- accessibility baseline is met
- existing tests pass
- deployed result is separately verified

PROVEN is reserved for evidence-backed verification.
