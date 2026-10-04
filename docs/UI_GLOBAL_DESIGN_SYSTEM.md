# VCMC-VP Global UI & Language Design System

Status: DESIGN PREPARATION — not merged, not deployed.

## Purpose
Define a single visual and interaction system for VCMC-VP before UI polishing begins. This changes presentation only; it must not alter VCMC governance, authority boundaries, allocation rules, evidence rules, or real-money boundaries.

## Product direction
VCMC-VP should feel:
- modern
- global
- calm and trustworthy
- operational rather than decorative
- dimensional through restrained layers, elevation, spacing and hierarchy
- mobile-first and comfortable on desktop

Avoid:
- excessive gradients
- visual clutter
- decorative animation that competes with evidence/status
- inconsistent button/card/icon styles
- color-only status communication
- mixed languages on one localized interface

## Visual system
### Color roles
Define semantic tokens rather than hard-coded colors:
- background
- surface
- surface-elevated
- text-primary
- text-secondary
- border
- brand-primary
- brand-secondary
- success
- warning
- danger
- info
- focus

Status must use both color and text/icon labels.

### Typography
Use a clear hierarchy:
- display/title
- section heading
- card heading
- body
- supporting text
- label
- status/value

Choose font stacks that support Latin and major non-Latin scripts. Do not force one font where it damages readability for a user's language.

### Shape and depth
Use consistent:
- border radius scale
- spacing scale
- border treatment
- shadow/elevation levels
- button/input heights
- card padding

Depth should communicate hierarchy, not decoration.

### Components
Standardize:
- top navigation
- mobile navigation
- buttons
- inputs/selects
- cards
- tiles
- status pills
- alerts
- empty states
- loading states
- tables/lists
- evidence records
- reconciliation records
- room navigation
- confirmation/error feedback

## Global language architecture
Use localization (i18n) rather than mixing translated strings into page code.

Rules:
1. Each UI string has a translation key.
2. User language is selected at the account/browser/application layer.
3. Indonesian, English, Spanish and future languages use the same component structure.
4. A single screen should render in one selected UI language.
5. Official VCMC names and locked terminology remain canonical where translation would alter meaning.
6. Date, number and currency presentation must follow locale where appropriate.
7. Text expansion must be tested; translated labels must not break mobile layouts.
8. Do not use machine translation as authority for locked governance language; canonical wording must be controlled.

Initial language plan:
- id-ID
- en
- es
Then expand by demand.

## Accessibility baseline
Target WCAG 2.2 AA-compatible implementation.
Minimum design requirements:
- sufficient text/background contrast
- keyboard/focus visibility
- semantic labels for controls
- color is never the sole status signal
- readable text and spacing
- responsive reflow
- reduced-motion support
- accessible error and success feedback

## VCMC-specific visual language
The interface should visually reinforce:
- CLAIM != EVIDENCE
- READY != PROVEN
- UNKNOWN != FAILED
- RECORDED != DONE != PROVEN
- REAL_MONEY remains disabled unless separately authorized and proven

Evidence, reconciliation and authority boundaries should be visually clear without implying authority that the UI does not possess.

## Implementation order
1. Freeze current functional behavior.
2. Introduce semantic design tokens.
3. Normalize typography and spacing.
4. Normalize components.
5. Add localization framework and language selector.
6. Refactor rooms to shared components without changing APIs.
7. Apply visual polish across Home and Rooms.
8. Test mobile and desktop layouts.
9. Test localization expansion.
10. Run existing repository tests and UI verification.
11. Deploy only after evidence supports the change.

## Acceptance gate for visual redesign
The redesign is not complete merely because it looks better.

PASS requires:
- no governance rule changes
- no API/authorization regression
- no room functionality regression
- no mixed-language UI in a selected locale
- responsive behavior verified
- accessibility checks completed
- existing tests pass
- deployed build verified separately

PROVEN remains reserved for evidence-backed verification.
