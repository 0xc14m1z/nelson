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
