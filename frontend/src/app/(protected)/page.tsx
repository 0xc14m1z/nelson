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
