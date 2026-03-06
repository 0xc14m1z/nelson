# UI Rework: AppShell with Navbar Layout

## Overview

Replace the current scattered navigation (buttons on each page) with a persistent left sidebar using Mantine's `AppShell` component. The navbar contains the session list, replacing the standalone sessions page and dashboard.

## Layout Structure

```
+------------------+--------------------------------+
| Nelson           |                                |
|------------------|                                |
| [+ New Session]  |     Main Content Area          |
|------------------|     (welcome / session / new   |
| session text   * |      session / settings)       |
| session text     |                                |
| session text   * |                                |
| ...  (scroll)    |                                |
|                  |                                |
|------------------|                                |
| Settings         |                                |
| Logout           |                                |
+------------------+--------------------------------+
```

`*` = pulsing dot indicating active debate (right-aligned)

## Navbar Anatomy (top to bottom)

1. **Logo** — "Nelson" text, bold, separator below.
2. **New Session button** — `Button` variant `filled`, full width, primary color. Navigates to `/sessions/new`.
3. **Session list** — `ScrollArea` filling remaining vertical space. Each item is a flex row: truncated enquiry text on the left, optional pulsing dot on the right for active sessions (status: `pending`, `responding`, `critiquing`). Active/selected session is highlighted. Sorted by creation date, newest first.
4. **Footer** — `border-top` separator. Two link-style rows with icons: Settings (`IconSettings`) navigates to `/settings`, Logout (`IconLogout`) calls `logout()`.

## Responsive Behavior

- **Desktop (>= sm):** Navbar visible by default, collapsible via toggle button.
- **Mobile (< sm):** Navbar hidden, opens as overlay drawer via `Burger` button. Clicking a session or nav item closes the drawer.

## Routing Changes

| Before | After |
|--------|-------|
| `/dashboard` | **Removed** |
| `/sessions` (list page) | **Removed** — navbar is the list |
| `/sessions/new` | Kept, renders in main content |
| `/sessions/[id]` | Kept, renders in main content |
| `/settings` | Kept, renders in main content |
| `/` (protected root) | Welcome/empty state: "Select a session or create a new one" |

## Component Breakdown

### New Components

- **`components/AppNavbar.tsx`** — Logo, new session button, scrollable session list, footer (settings + logout). Uses `useRouter`, `useAuth`, React Query for sessions.
- **`components/AppNavbar.module.css`** — Styles following Mantine NavbarSimple pattern: link styles with hover/active states, footer border, pulsing dot animation.
- **`(protected)/page.tsx`** — Welcome/empty state page (replaces dashboard as root).

### Modified Components

- **`(protected)/layout.tsx`** — Major rewrite: wraps children in `AppShell` with `AppShell.Navbar`. Manages `opened` state via `useDisclosure`. Renders `Burger` for mobile toggle.
- **`(protected)/sessions/[id]/page.tsx`** — Remove back-navigation buttons.
- **`(protected)/sessions/new/page.tsx`** — Remove back-navigation buttons.

### Deleted Components

- **`(protected)/dashboard/page.tsx`** — Replaced by navbar + welcome state.
- **`(protected)/sessions/page.tsx`** — Replaced by navbar session list.

## Session List Data

Reuse existing `/api/sessions` endpoint via React Query. The navbar fetches on mount. Active session detection uses `status` field: `pending | responding | critiquing` = active (show pulsing dot), all others = terminal (no dot).

## Session Item Visual Design

Flex row with `justify-content: space-between`:
- Left: enquiry text, truncated with ellipsis, `font-size: sm`
- Right: small colored pulsing dot for active sessions only

```
| What is the best...  * |
| What causes rain...    |
| Compare React vs...  * |
```

## Technology

- `AppShell`, `AppShell.Navbar`, `ScrollArea`, `Button`, `Burger`, `UnstyledButton` from `@mantine/core`
- `useDisclosure` from `@mantine/hooks`
- `@tabler/icons-react` for Settings and Logout icons
- CSS modules for custom styles
- Existing `useAuth` context for logout
- React Query for session list fetching
