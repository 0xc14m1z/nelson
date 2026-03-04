"use client";

import { Suspense } from "react";
import { useEffect, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { Container, Loader, Text, Stack, Button } from "@mantine/core";
import { useAuth } from "../../../lib/auth-context";

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

function VerifyContent() {
  const searchParams = useSearchParams();
  const router = useRouter();
  const { login } = useAuth();
  const [error, setError] = useState("");

  useEffect(() => {
    const token = searchParams.get("token");
    const email = searchParams.get("email");

    if (!token || !email) {
      setError("Invalid link.");
      return;
    }

    async function verify() {
      try {
        const resp = await fetch(`${API_URL}/api/auth/verify`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          credentials: "include",
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
  }, [searchParams, login, router]);

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
