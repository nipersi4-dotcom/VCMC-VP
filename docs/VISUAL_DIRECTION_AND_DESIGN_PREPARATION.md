# VCMC-VP Visual Direction & Design Preparation

Status: PREPARATION — visual specification only; not merged or deployed.

## Design objective

Target a substantial visual upgrade from the current interface: approximately “5x more refined” in perceived quality, while preserving the operational character of VCMC-VP.

The product should feel like one deliberately planned global city:
- one visual language
- distinct districts
- distinct rooms
- clear streets/navigation
- orderly buildings/components
- calm, premium, modern presentation
- strong readability and operational truth

This is not a redesign of VCMC governance, authority, API semantics, or payment boundaries.

## Visual character

Desired character:
- modern
- elegant
- mature
- calm
- trustworthy
- slightly classical in typography
- contemporary in layout and interaction
- restrained rather than flashy

Avoid:
- dashboard-template appearance
- random gradients
- excessive glassmorphism
- excessive rounded cards
- decorative animation
- crowded screens
- too many competing colors
- inconsistent button/card styles
- mixed-language copy

## Typography direction

Use a deliberate type system rather than one generic font everywhere.

Recommended pairing:
- Display / major room titles: a refined serif family with classical character.
- Interface / body / controls: a highly readable modern sans-serif.
- Data and technical identifiers: readable system/monospace treatment only where it improves scanning.

Typography hierarchy:
1. City/product identity
2. District title
3. Room title
4. Section title
5. Record title
6. Body/data
7. Metadata/status
8. Action

Serif is a visual accent for identity and hierarchy, not for dense operational data.

All fonts must support the selected language adequately. Never sacrifice legibility for style.

## Color architecture

Use a restrained semantic palette with a strong neutral foundation.

Roles:
- page background
- elevated surface
- primary text
- secondary text
- border/divider
- brand/accent
- success
- warning
- danger
- information
- focus

Rules:
- brand color should identify VCMC, not fill every component
- status colors must have text/icon support, not color alone
- success must not visually mean PROVEN unless evidence says PROVEN
- READY, PROVEN, UNKNOWN, HOLD and simulation states must remain semantically distinct
- payment/simulation boundaries remain visually explicit
- dark and light presentation should use the same semantic roles

## Layout / city planning

### Global city
The application shell is the city boundary.

### Districts
Group the 13 canonical rooms into four navigation districts:

Foundation
- Architecture
- Global Network

Development
- Partners & Candidates
- Pilots
- Programs & Projects
- Development Direction
- Capital & Development

Control & Proof
- Distribution
- Evidence & Verification
- Reconciliation

Operations
- Security
- System & Operations
- Payment / Providers

District grouping is navigation only. The canonical room set remains unchanged.

### Streets
Navigation should always make these paths obvious:
Home → District → Room → Record/workspace → Evidence/history where applicable.

The user should always know:
- where they are
- what this room does
- what action is available
- what was recorded
- what is still unknown

## Grid and spacing

Use a consistent spacing scale and grid.

Principles:
- generous whitespace
- aligned left edges
- consistent card padding
- predictable vertical rhythm
- forms and records share alignment
- desktop uses columns only when comparison benefits
- mobile collapses naturally to one column

Do not stretch content merely to fill the screen.

## Components

Create one reusable visual language for:
- navigation
- breadcrumbs
- district navigation
- room headers
- primary/secondary buttons
- inputs/selects
- cards
- metric tiles
- status pills
- alerts
- empty states
- loading states
- record lists
- evidence records
- reconciliation records
- audit/history rows
- confirmation feedback

A component should look the same everywhere unless its semantic purpose genuinely differs.

## Room composition

Every room should visually follow a recognizable composition:

1. Room identity
2. Short purpose statement
3. Status/boundary
4. Primary action
5. Main workspace
6. Existing records
7. Evidence/history when applicable
8. Empty/success/error state
9. Return/navigation

This creates the feeling of buildings designed from the same city code.

## Home composition

Home should become the city map, not a wall of unrelated cards.

Suggested hierarchy:
- VCMC identity and welcome
- system/session status
- district navigation
- room map / room groups
- important operational snapshot
- attention / proof boundaries
- quick actions

The 13 rooms should be discoverable without making the Home visually crowded.

## Interaction quality

Use subtle interaction:
- clear hover/focus
- pressed state
- lightweight transitions
- save confirmation
- loading indication
- disabled state
- error recovery

No animation should obscure data or slow operational work.

## Responsive target

HP/mobile is a first-class experience:
- compact but elegant header
- district navigation remains understandable
- cards stack
- forms use full width
- buttons remain reachable
- no ordinary horizontal scrolling
- important statuses remain visible

Desktop:
- stronger spatial composition
- useful multi-column layouts
- readable maximum content width
- stable navigation

## Internationalization visual rule

The selected locale controls ordinary UI language consistently.

Initial locales:
- id-ID
- en
- es

Translations must not be scattered manually through individual screens. Use localization keys.

Canonical VCMC terms remain protected when translation would change their governance meaning.

Longer languages must be allowed to expand naturally; never design around English-only text lengths.

## Accessibility

Target WCAG 2.2 AA-compatible implementation:
- keyboard/focus visibility
- sufficient contrast
- labels associated with controls
- status not conveyed by color alone
- readable text sizing
- touch targets suitable for mobile
- reduced-motion consideration

## Truthful visual semantics

The visual system must reinforce the locked distinctions:
- CLAIM ≠ EVIDENCE
- Candidate ≠ Pilot
- READY ≠ PROVEN
- UNKNOWN ≠ FAILED
- RECORDED ≠ DONE ≠ PROVEN
- PAYMENT SUCCESS ≠ automatic evidence
- AI/automation ≠ authority
- REAL_MONEY remains disabled unless separately authorized and proven

Visual polish must never blur these distinctions.

## Implementation sequence

1. Verify PR #16 and current main.
2. Verify deployed baseline.
3. Fix password reset after logout.
4. Settle public access architecture.
5. Establish i18n foundation.
6. Add visual design tokens.
7. Add typography system.
8. Add semantic color system.
9. Standardize global shell/navigation.
10. Standardize reusable components.
11. Redesign Home as the city map.
12. Apply district/room layout to all 13 rooms.
13. Apply responsive behavior.
14. Apply locale expansion.
15. Accessibility pass.
16. Regression tests.
17. Deploy.
18. Verify on HP and desktop.
19. Record evidence.
20. Only then mark the relevant visual gate complete.

## Tomorrow's starting point

No rebuild, import, provider hop, or repository recreation.

Start from the existing repository and the prepared design documents. The objective is to turn the prepared blueprint into an actual visual system, then apply it consistently across the house.

Completion means the user can enter VCMC-VP and experience one coherent city rather than a collection of unrelated pages.
