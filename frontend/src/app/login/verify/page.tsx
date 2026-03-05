"use client";

import { Suspense } from "react";
import { useEffect, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { Container, Loader, Text, Stack, Button } from "@mantine/core";
import { useAuth } from "../../../lib/auth-context";

function VerifyContent() {
  const searchParams = useSearchParams();
  const router = useRouter();
  const { login } = useAuth();
  const [error, setError] = useState("");

  const token = searchParams.get("token");
  const email = searchParams.get("email");

  useEffect(() => {
    if (!token || !email) {
      return;
    }

    async function verify() {
      try {
        const resp = await fetch("/api/auth/verify", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ email, token }),
        });

        if (!resp.ok) {
          setError("This link is expired or invalid.");
          return;
        }

        const data = await resp.json();
        await login(data.access_token);
        router.push("/dashboard");
      } catch {
        setError("Something went wrong. Please try again.");
      }
    }

    verify();
  }, [token, email, login, router]);

  if (!token || !email) {
    return (
      <Container
        size="xs"
        py="xl"
        style={{
          minHeight: "100vh",
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
        }}
      >
        <Stack align="center">
          <Text c="red">Invalid link.</Text>
          <Button variant="outline" onClick={() => router.push("/login")}>
            Back to login
          </Button>
        </Stack>
      </Container>
    );
  }

  return (
    <Container
      size="xs"
      py="xl"
      style={{
        minHeight: "100vh",
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
      }}
    >
      {error ? (
        <Stack align="center">
          <Text c="red">{error}</Text>
          <Button variant="outline" onClick={() => router.push("/login")}>
            Back to login
          </Button>
        </Stack>
      ) : (
        <Stack align="center">
          <Loader />
          <Text c="dimmed">Verifying your login...</Text>
        </Stack>
      )}
    </Container>
  );
}

export default function VerifyPage() {
  return (
    <Suspense
      fallback={
        <Container
          size="xs"
          py="xl"
          style={{
            minHeight: "100vh",
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
          }}
        >
          <Loader />
        </Container>
      }
    >
      <VerifyContent />
    </Suspense>
  );
}
