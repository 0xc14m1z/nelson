import { Container, Title, Text } from "@mantine/core";

export default function Home() {
  return (
    <Container size="sm" py="xl" style={{ minHeight: "100vh", display: "flex", alignItems: "center" }}>
      <div>
        <Title order={1} mb="md">Nelson</Title>
        <Text size="lg" c="dimmed">
          Multi-LLM consensus agent. Coming soon.
        </Text>
      </div>
    </Container>
  );
}
