# UI Rework Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Replace scattered page-based navigation with a persistent Mantine AppShell sidebar containing session list, new session button, settings, and logout.

**Architecture:** Mantine `AppShell` wraps the protected layout. A custom `AppNavbar` component renders in `AppShell.Navbar`. Pages render in `AppShell.Main`. The navbar is collapsible on desktop and becomes a drawer on mobile.

**Tech Stack:** Mantine AppShell/ScrollArea/Burger, @tabler/icons-react, React Query, Next.js App Router, CSS modules.

---

### Task 1: Add `useSessions` hook to `lib/hooks.ts`

**Files:**
- Modify: `frontend/src/lib/hooks.ts` (add hook at end of file)

**Step 1: Write the hook**

Add to end of `frontend/src/lib/hooks.ts`:

```typescript
export function useSessions() {
  return useQuery<import("@/types/session").SessionSummary[]>({
    queryKey: ["sessions"],
    queryFn: async () => {
      const resp = await apiFetch("/api/sessions");
      if (!resp.ok) throw new Error("Failed to fetch sessions");
      const data = await resp.json();
      return data.sessions;
    },
  });
}
```

**Step 2: Verify it compiles**

Run: `cd frontend && bun run build --no-lint 2>&1 | head -20`
Expected: No type errors related to this hook.

**Step 3: Commit**

```bash
git add frontend/src/lib/hooks.ts
git commit -m "feat: add useSessions hook"
```

---

### Task 2: Create `AppNavbar` component + styles

**Files:**
- Create: `frontend/src/components/AppNavbar.tsx`
- Create: `frontend/src/components/AppNavbar.module.css`

**Step 1: Create CSS module**

Create `frontend/src/components/AppNavbar.module.css`:

```css
.navbar {
  display: flex;
  flex-direction: column;
  height: 100%;
  padding: var(--mantine-spacing-md);
}

.logo {
  padding-bottom: var(--mantine-spacing-md);
  margin-bottom: var(--mantine-spacing-md);
  border-bottom: 1px solid light-dark(var(--mantine-color-gray-3), var(--mantine-color-dark-4));
}

.sessions {
  flex: 1;
  margin-top: var(--mantine-spacing-sm);
}

.sessionLink {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--mantine-spacing-xs);
  text-decoration: none;
  font-size: var(--mantine-font-size-sm);
  color: light-dark(var(--mantine-color-gray-7), var(--mantine-color-dark-1));
  padding: var(--mantine-spacing-xs) var(--mantine-spacing-sm);
  border-radius: var(--mantine-radius-sm);
  font-weight: 500;
  cursor: pointer;

  &:hover {
    background-color: light-dark(var(--mantine-color-gray-0), var(--mantine-color-dark-6));
    color: light-dark(var(--mantine-color-black), var(--mantine-color-white));
  }

  &[data-active] {
    &,
    &:hover {
      background-color: var(--mantine-color-blue-light);
      color: var(--mantine-color-blue-light-color);
    }
  }
}

.sessionText {
  flex: 1;
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.activeDot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background-color: var(--mantine-color-blue-6);
  flex-shrink: 0;
  animation: pulse 2s ease-in-out infinite;
}

@keyframes pulse {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.4; }
}

.footer {
  padding-top: var(--mantine-spacing-md);
  margin-top: var(--mantine-spacing-md);
  border-top: 1px solid light-dark(var(--mantine-color-gray-3), var(--mantine-color-dark-4));
}

.footerLink {
  display: flex;
  align-items: center;
  text-decoration: none;
  font-size: var(--mantine-font-size-sm);
  color: light-dark(var(--mantine-color-gray-7), var(--mantine-color-dark-1));
  padding: var(--mantine-spacing-xs) var(--mantine-spacing-sm);
  border-radius: var(--mantine-radius-sm);
  font-weight: 500;
  cursor: pointer;

  &:hover {
    background-color: light-dark(var(--mantine-color-gray-0), var(--mantine-color-dark-6));
    color: light-dark(var(--mantine-color-black), var(--mantine-color-white));
  }
}

.footerLinkIcon {
  color: light-dark(var(--mantine-color-gray-6), var(--mantine-color-dark-2));
  margin-right: var(--mantine-spacing-sm);
  width: 20px;
  height: 20px;
}
```

**Step 2: Create AppNavbar component**

Create `frontend/src/components/AppNavbar.tsx`:

```tsx
"use client";

import { useRouter, usePathname } from "next/navigation";
import { Button, ScrollArea, Text, Title } from "@mantine/core";
import { IconSettings, IconLogout } from "@tabler/icons-react";
import { useAuth } from "@/lib/auth-context";
import { useSessions } from "@/lib/hooks";
import classes from "./AppNavbar.module.css";

const ACTIVE_STATUSES = new Set(["pending", "responding", "critiquing"]);

interface AppNavbarProps {
  onNavigate?: () => void;
}

export function AppNavbar({ onNavigate }: AppNavbarProps) {
  const router = useRouter();
  const pathname = usePathname();
  const { logout } = useAuth();
  const { data: sessions = [] } = useSessions();

  const handleNavigate = (path: string) => {
    router.push(path);
    onNavigate?.();
  };

  const handleLogout = async () => {
    await logout();
    router.push("/login");
  };

  return (
    <nav className={classes.navbar}>
      {/* Logo */}
      <div className={classes.logo}>
        <Title order={3} onClick={() => handleNavigate("/")} style={{ cursor: "pointer" }}>
          Nelson
        </Title>
      </div>

      {/* New Session button */}
      <Button fullWidth onClick={() => handleNavigate("/sessions/new")}>
        New Session
      </Button>

      {/* Session list */}
      <ScrollArea className={classes.sessions}>
        {sessions.map((session) => (
          <div
            key={session.id}
            className={classes.sessionLink}
            data-active={pathname === `/sessions/${session.id}` || undefined}
            onClick={() => handleNavigate(`/sessions/${session.id}`)}
          >
            <span className={classes.sessionText}>{session.enquiry}</span>
            {ACTIVE_STATUSES.has(session.status) && (
              <span className={classes.activeDot} />
            )}
          </div>
        ))}
        {sessions.length === 0 && (
          <Text size="sm" c="dimmed" ta="center" mt="md">
            No sessions yet
          </Text>
        )}
      </ScrollArea>

      {/* Footer */}
      <div className={classes.footer}>
        <div className={classes.footerLink} onClick={() => handleNavigate("/settings")}>
          <IconSettings className={classes.footerLinkIcon} stroke={1.5} />
          <span>Settings</span>
        </div>
        <div className={classes.footerLink} onClick={handleLogout}>
          <IconLogout className={classes.footerLinkIcon} stroke={1.5} />
          <span>Logout</span>
        </div>
      </div>
    </nav>
  );
}
```

**Step 3: Verify it compiles**

Run: `cd frontend && bun run build --no-lint 2>&1 | head -20`
Expected: No errors.

**Step 4: Commit**

```bash
git add frontend/src/components/AppNavbar.tsx frontend/src/components/AppNavbar.module.css
git commit -m "feat: add AppNavbar component with session list and footer"
```

---

### Task 3: Rewrite protected layout with AppShell

**Files:**
- Modify: `frontend/src/app/(protected)/layout.tsx` (full rewrite)

**Step 1: Rewrite the layout**

Replace entire contents of `frontend/src/app/(protected)/layout.tsx`:

```tsx
"use client";

import { useRouter } from "next/navigation";
import { useEffect } from "react";
import { AppShell, Burger, Center, Group, Loader } from "@mantine/core";
import { useDisclosure } from "@mantine/hooks";
import { useAuth } from "../../lib/auth-context";
import { AppNavbar } from "../../components/AppNavbar";

export default function ProtectedLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  const { isAuthenticated, isLoading } = useAuth();
  const router = useRouter();
  const [opened, { toggle, close }] = useDisclosure();

  useEffect(() => {
    if (!isLoading && !isAuthenticated) {
      router.push("/login");
    }
  }, [isLoading, isAuthenticated, router]);

  if (isLoading) {
    return (
      <Center style={{ minHeight: "100vh" }}>
        <Loader />
      </Center>
    );
  }

  if (!isAuthenticated) {
    return null;
  }

  return (
    <AppShell
      navbar={{
        width: 300,
        breakpoint: "sm",
        collapsed: { mobile: !opened, desktop: !opened },
      }}
      padding="md"
    >
      <AppShell.Navbar>
        <AppNavbar onNavigate={close} />
      </AppShell.Navbar>
      <AppShell.Main>
        <Group hiddenFrom="sm" mb="md">
          <Burger opened={opened} onClick={toggle} size="sm" />
        </Group>
        {opened ? null : null}
        {children}
      </AppShell.Main>
    </AppShell>
  );
}
```

Wait — the desktop collapse behavior needs refinement. On desktop, the navbar should be visible by default, and the user can toggle it. On mobile, it starts hidden. Let me adjust:

```tsx
"use client";

import { useRouter } from "next/navigation";
import { useEffect } from "react";
import { AppShell, Burger, Center, Group, Loader } from "@mantine/core";
import { useDisclosure } from "@mantine/hooks";
import { useAuth } from "../../lib/auth-context";
import { AppNavbar } from "../../components/AppNavbar";

export default function ProtectedLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  const { isAuthenticated, isLoading } = useAuth();
  const router = useRouter();
  const [mobileOpened, { toggle: toggleMobile, close: closeMobile }] = useDisclosure();
  const [desktopOpened, { toggle: toggleDesktop }] = useDisclosure(true);

  useEffect(() => {
    if (!isLoading && !isAuthenticated) {
      router.push("/login");
    }
  }, [isLoading, isAuthenticated, router]);

  if (isLoading) {
    return (
      <Center style={{ minHeight: "100vh" }}>
        <Loader />
      </Center>
    );
  }

  if (!isAuthenticated) {
    return null;
  }

  return (
    <AppShell
      navbar={{
        width: 300,
        breakpoint: "sm",
        collapsed: { mobile: !mobileOpened, desktop: !desktopOpened },
      }}
      padding="md"
    >
      <AppShell.Navbar>
        <AppNavbar onNavigate={closeMobile} />
      </AppShell.Navbar>
      <AppShell.Main>
        <Group mb="md">
          <Burger opened={mobileOpened} onClick={toggleMobile} hiddenFrom="sm" size="sm" />
          <Burger opened={desktopOpened} onClick={toggleDesktop} visibleFrom="sm" size="sm" />
        </Group>
        {children}
      </AppShell.Main>
    </AppShell>
  );
}
```

**Step 2: Verify it compiles**

Run: `cd frontend && bun run build --no-lint 2>&1 | head -20`
Expected: No errors.

**Step 3: Commit**

```bash
git add frontend/src/app/\(protected\)/layout.tsx
git commit -m "feat: rewrite protected layout with AppShell and navbar"
```

---

### Task 4: Create welcome page + update root redirect

**Files:**
- Create: `frontend/src/app/(protected)/page.tsx` (welcome/empty state)
- Modify: `frontend/src/app/page.tsx` (change redirect from `/dashboard` to `/sessions/new` or just `/`)

**Step 1: Create the welcome page**

Create `frontend/src/app/(protected)/page.tsx`:

```tsx
import { Center, Stack, Text, Title } from "@mantine/core";

export default function WelcomePage() {
  return (
    <Center style={{ minHeight: "50vh" }}>
      <Stack align="center" gap="sm">
        <Title order={2} c="dimmed">Welcome to Nelson</Title>
        <Text c="dimmed">Select a session from the sidebar or create a new one.</Text>
      </Stack>
    </Center>
  );
}
```

**Step 2: Update root page redirect**

Modify `frontend/src/app/page.tsx` — change line 14 from:
```tsx
router.push(isAuthenticated ? "/dashboard" : "/login");
```
to:
```tsx
router.push(isAuthenticated ? "/" : "/login");
```

Wait — this would cause an infinite redirect since `/` IS the root page. The protected layout sits at `(protected)/` which maps to `/`. The root `app/page.tsx` is the unauthenticated entry. When authenticated, we need to redirect somewhere inside the protected group. Since `(protected)/page.tsx` now exists and serves as the welcome page, we should redirect to `/` BUT that conflicts with `app/page.tsx`.

Actually, Next.js route groups with `(protected)` don't add a URL segment. So `app/(protected)/page.tsx` maps to `/` and `app/page.tsx` ALSO maps to `/`. That's a conflict.

The fix: delete `app/page.tsx` entirely and handle the unauthenticated redirect in the protected layout (which already does this). The `(protected)/page.tsx` becomes the root `/` page. Unauthenticated users hitting `/` get redirected to `/login` by the protected layout.

**Step 2 (revised): Delete root page, create protected welcome page**

Delete `frontend/src/app/page.tsx`.

Create `frontend/src/app/(protected)/page.tsx` as shown in Step 1.

**Step 3: Verify it compiles**

Run: `cd frontend && bun run build --no-lint 2>&1 | head -20`
Expected: No errors.

**Step 4: Commit**

```bash
git rm frontend/src/app/page.tsx
git add frontend/src/app/\(protected\)/page.tsx
git commit -m "feat: add welcome page as root, remove old redirect page"
```

---

### Task 5: Delete dashboard and sessions list pages

**Files:**
- Delete: `frontend/src/app/(protected)/dashboard/page.tsx`
- Delete: `frontend/src/app/(protected)/sessions/page.tsx`
- Delete: `frontend/src/app/(protected)/sessions/__tests__/page.test.tsx`

**Step 1: Delete the files**

```bash
rm frontend/src/app/\(protected\)/dashboard/page.tsx
rmdir frontend/src/app/\(protected\)/dashboard
rm frontend/src/app/\(protected\)/sessions/__tests__/page.test.tsx
rm frontend/src/app/\(protected\)/sessions/page.tsx
```

**Step 2: Verify no broken imports**

Run: `cd frontend && bun run build --no-lint 2>&1 | head -30`
Expected: No import errors. The sessions list was standalone — nothing imports from it.

**Step 3: Commit**

```bash
git add -A
git commit -m "feat: remove dashboard and sessions list pages (replaced by navbar)"
```

---

### Task 6: Clean up existing pages

**Files:**
- Modify: `frontend/src/app/(protected)/sessions/new/page.tsx` — remove any redundant nav
- Modify: `frontend/src/app/(protected)/sessions/[id]/page.tsx` — no changes needed (already clean)
- Modify: `frontend/src/app/(protected)/settings/page.tsx` — remove `Container` wrapper if present (AppShell.Main handles padding)

**Step 1: Check sessions/new page**

The `sessions/new/page.tsx` currently has no back-nav buttons — just the form. No changes needed.

**Step 2: Check settings page**

The settings page wraps content in `<Container size="md" py="xl">`. Since AppShell.Main provides padding, the `py="xl"` is excessive but not broken. Leave it — it's not part of navigation cleanup.

**Step 3: Commit (if any changes)**

Skip commit if no changes were made.

---

### Task 7: Write tests for AppNavbar

**Files:**
- Create: `frontend/src/components/__tests__/AppNavbar.test.tsx`

**Step 1: Write the test**

Create `frontend/src/components/__tests__/AppNavbar.test.tsx`:

```tsx
import { render, screen, fireEvent } from "@testing-library/react";
import { describe, it, expect, vi } from "vitest";
import React from "react";

const mockPush = vi.fn();
const mockLogout = vi.fn();

const { mockSessions } = vi.hoisted(() => ({
  mockSessions: [
    {
      id: "s1",
      enquiry: "What is the meaning of life?",
      status: "consensus_reached",
      model_ids: ["m1"],
      current_round: 3,
      total_cost: 0,
      total_input_tokens: 0,
      total_output_tokens: 0,
      total_duration_ms: 0,
      max_rounds: null,
      created_at: "2026-03-01T00:00:00Z",
      completed_at: null,
    },
    {
      id: "s2",
      enquiry: "Explain quantum computing",
      status: "responding",
      model_ids: ["m1", "m2"],
      current_round: 1,
      total_cost: 0,
      total_input_tokens: 0,
      total_output_tokens: 0,
      total_duration_ms: 0,
      max_rounds: null,
      created_at: "2026-03-02T00:00:00Z",
      completed_at: null,
    },
  ],
}));

let currentSessions = mockSessions;

vi.mock("@mantine/core", () => {
  // eslint-disable-next-line @typescript-eslint/no-require-imports
  const R = require("react");
  const wrap = () => (props: Record<string, unknown>) => R.createElement("div", null, props.children);
  return {
    Button: (props: Record<string, unknown>) =>
      R.createElement("button", { onClick: props.onClick }, props.children),
    ScrollArea: wrap(),
    Text: wrap(),
    Title: (props: Record<string, unknown>) =>
      R.createElement(`h${props.order || 1}`, { onClick: props.onClick, style: props.style }, props.children),
  };
});

vi.mock("next/navigation", () => ({
  useRouter: () => ({ push: mockPush }),
  usePathname: () => "/",
}));

vi.mock("@/lib/auth-context", () => ({
  useAuth: () => ({ logout: mockLogout }),
}));

vi.mock("@/lib/hooks", () => ({
  useSessions: () => ({ data: currentSessions }),
}));

vi.mock("@tabler/icons-react", () => {
  // eslint-disable-next-line @typescript-eslint/no-require-imports
  const R = require("react");
  return {
    IconSettings: (props: Record<string, unknown>) => R.createElement("svg", props),
    IconLogout: (props: Record<string, unknown>) => R.createElement("svg", props),
  };
});

import { AppNavbar } from "../AppNavbar";

describe("AppNavbar", () => {
  beforeEach(() => {
    mockPush.mockClear();
    mockLogout.mockClear();
    currentSessions = mockSessions;
  });

  it("renders Nelson logo", () => {
    render(<AppNavbar />);
    expect(screen.getByText("Nelson")).toBeInTheDocument();
  });

  it("renders New Session button", () => {
    render(<AppNavbar />);
    expect(screen.getByText("New Session")).toBeInTheDocument();
  });

  it("renders session entries", () => {
    render(<AppNavbar />);
    expect(screen.getByText("What is the meaning of life?")).toBeInTheDocument();
    expect(screen.getByText("Explain quantum computing")).toBeInTheDocument();
  });

  it("renders Settings and Logout in footer", () => {
    render(<AppNavbar />);
    expect(screen.getByText("Settings")).toBeInTheDocument();
    expect(screen.getByText("Logout")).toBeInTheDocument();
  });

  it("navigates to /sessions/new on button click", () => {
    render(<AppNavbar />);
    fireEvent.click(screen.getByText("New Session"));
    expect(mockPush).toHaveBeenCalledWith("/sessions/new");
  });

  it("navigates to session on click", () => {
    render(<AppNavbar />);
    fireEvent.click(screen.getByText("What is the meaning of life?"));
    expect(mockPush).toHaveBeenCalledWith("/sessions/s1");
  });

  it("navigates to /settings on click", () => {
    render(<AppNavbar />);
    fireEvent.click(screen.getByText("Settings"));
    expect(mockPush).toHaveBeenCalledWith("/settings");
  });

  it("calls logout and redirects to /login", async () => {
    render(<AppNavbar />);
    fireEvent.click(screen.getByText("Logout"));
    expect(mockLogout).toHaveBeenCalled();
    expect(mockPush).toHaveBeenCalledWith("/login");
  });

  it("shows pulsing dot for active sessions only", () => {
    const { container } = render(<AppNavbar />);
    // "responding" session should have the dot, "consensus_reached" should not
    const dots = container.querySelectorAll("[class*='activeDot']");
    expect(dots).toHaveLength(1);
  });

  it("shows empty state when no sessions", () => {
    currentSessions = [];
    render(<AppNavbar />);
    expect(screen.getByText("No sessions yet")).toBeInTheDocument();
  });

  it("calls onNavigate callback on navigation", () => {
    const onNavigate = vi.fn();
    render(<AppNavbar onNavigate={onNavigate} />);
    fireEvent.click(screen.getByText("Settings"));
    expect(onNavigate).toHaveBeenCalled();
  });
});
```

**Step 2: Run the tests**

Run: `cd frontend && bun run test -- --run src/components/__tests__/AppNavbar.test.tsx`
Expected: All tests pass.

**Step 3: Commit**

```bash
git add frontend/src/components/__tests__/AppNavbar.test.tsx
git commit -m "test: add AppNavbar component tests"
```

---

### Task 8: Update existing tests that reference removed pages

**Files:**
- Modify: `frontend/src/app/(protected)/sessions/new/__tests__/page.test.tsx` — no changes needed (tests the new session form, still exists)
- Modify: `frontend/src/app/(protected)/settings/__tests__/page.test.tsx` — no changes needed (tests settings page, still exists)

The sessions list page test was already deleted in Task 5. Verify all remaining tests pass.

**Step 1: Run full frontend test suite**

Run: `cd frontend && bun run test -- --run`
Expected: All tests pass (the deleted sessions page test is gone, all others still work).

**Step 2: Commit (if any fixes needed)**

Only commit if test fixes were required.

---

### Task 9: Ensure `@tabler/icons-react` is installed

**Files:**
- Modify: `frontend/package.json` (if needed)

**Step 1: Check if already installed**

Run: `cd frontend && cat package.json | grep tabler`

If not present:

Run: `cd frontend && bun add @tabler/icons-react`

**Step 2: Commit (if installed)**

```bash
git add frontend/package.json frontend/bun.lock
git commit -m "chore: add @tabler/icons-react dependency"
```

---

### Task 10: Manual smoke test

**Step 1: Start the app**

Run: `cd /Users/morgandam/Documents/repos/nelson && docker compose up --build`

**Step 2: Verify in browser**

- [ ] Login works, redirects to welcome page with sidebar
- [ ] "Nelson" logo visible at top of sidebar
- [ ] "New Session" button creates new session
- [ ] Sessions appear in sidebar after creation
- [ ] Active sessions show pulsing dot on right side
- [ ] Clicking session loads it in main content
- [ ] Settings link works
- [ ] Logout works
- [ ] Hamburger toggle collapses/shows sidebar on desktop
- [ ] On mobile viewport, sidebar is drawer that opens/closes
- [ ] `/dashboard` no longer exists (404 or redirect)
- [ ] `/sessions` no longer exists (404 or redirect)
