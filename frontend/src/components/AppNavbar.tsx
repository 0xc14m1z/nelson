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
