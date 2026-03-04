"use client";

import { useState } from "react";
import {
  Container,
  Title,
  TextInput,
  Button,
  Text,
  Paper,
  Stack,
} from "@mantine/core";

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

export default function LoginPage() {
  const [email, setEmail] = useState("");
  const [sent, setSent] = useState(false);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError("");
    setLoading(true);

    try {
      const resp = await fetch(`${API_URL}/api/auth/magic-link`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ email }),
      });

      if (resp.status === 429) {
        setError("Too many requests. Please try again later.");
        return;
      }
      if (!resp.ok) {
        setError("Something went wrong. Please try again.");
        return;
      }

      setSent(true);
    } catch {
      setError("Network error. Please try again.");
    } finally {
      setLoading(false);
    }
  }

  return (
    <Container
      size="xs"
      py="xl"
      style={{ minHeight: "100vh", display: "flex", alignItems: "center" }}
    >
      <Paper w="100%" p="xl" radius="md" withBorder>
        {sent ? (
          <Stack>
            <Title order={2}>Check your email</Title>
            <Text c="dimmed">
              We sent a login link to <strong>{email}</strong>. Click it to sign
              in.
            </Text>
          </Stack>
        ) : (
          <form onSubmit={handleSubmit}>
            <Stack>
              <Title order={2}>Sign in to Nelson</Title>
              <TextInput
                label="Email"
                placeholder="you@example.com"
                type="email"
                required
                value={email}
                onChange={(e) => setEmail(e.currentTarget.value)}
              />
              {error && (
                <Text c="red" size="sm">
                  {error}
                </Text>
              )}
              <Button type="submit" loading={loading} fullWidth>
                Send login link
              </Button>
            </Stack>
          </form>
        )}
      </Paper>
    </Container>
  );
}
