"use client";

import Link from "next/link";
import {
  Container,
  Title,
  Text,
  Button,
  Group,
  Paper,
  Stack,
} from "@mantine/core";
import { useAuth } from "../../../lib/auth-context";

export default function DashboardPage() {
  const { user, logout } = useAuth();

  return (
    <Container size="sm" py="xl">
      <Paper p="xl" radius="md" withBorder>
        <Stack>
          <Group justify="space-between">
            <Title order={2}>Dashboard</Title>
            <Group gap="xs">
              <Button
                component={Link}
                href="/settings"
                variant="light"
              >
                Settings
              </Button>
              <Button variant="subtle" onClick={logout}>
                Sign out
              </Button>
            </Group>
          </Group>
          <Text c="dimmed">
            Signed in as <strong>{user?.email}</strong>
          </Text>
          <Text size="sm" c="dimmed">
            More features coming soon.
          </Text>
        </Stack>
      </Paper>
    </Container>
  );
}
