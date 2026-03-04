# Milestone 2 — Auth (Magic Link Login)

## Database Models

Four new tables, one migration.

### users
`id` UUID PK, `email` VARCHAR UNIQUE, `display_name` VARCHAR NULL, `billing_mode` VARCHAR DEFAULT `'own_keys'`, `created_at`, `updated_at`

### user_settings
`user_id` FK users (PK, 1:1), `max_rounds` INT NULL (NULL = "until consensus"), `created_at`, `updated_at`. Auto-created when user is created.

### magic_links
`id` UUID PK, `email` VARCHAR, `token_hash` VARCHAR, `expires_at` TIMESTAMP, `used_at` TIMESTAMP NULL, `created_at`. Not FK'd to users — user may not exist on first login. Tokens stored as SHA-256 hashes.

### refresh_tokens
`id` UUID PK, `user_id` FK users, `token_hash` VARCHAR (SHA-256), `expires_at` TIMESTAMP, `revoked_at` TIMESTAMP NULL, `created_at`. Cascade on user delete.

## Auth Backend

### Endpoints

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| POST | `/api/auth/magic-link` | No | Send magic link email |
| POST | `/api/auth/verify` | No | Verify token -> access JWT + refresh cookie |
| POST | `/api/auth/refresh` | Cookie | Refresh token cookie -> new access JWT + new refresh cookie |

### Service (auth/service.py)

**request_magic_link(email)**: Rate limit 3 per email per 15min (DB query). Generate random token -> SHA-256 hash -> store in magic_links (15min expiry). Send email with link `{magic_link_base_url}?token={raw_token}&email={email}`. Simple if/else: smtplib for local (Mailpit), Resend SDK for production.

**verify_magic_link(email, token)**: Hash token, look up in magic_links (matching email, not expired, not used). Mark as used. Auto-create user if email not in users table (with user_settings row). Generate access JWT (15min, contains user_id + email). Generate refresh token -> hash -> store in refresh_tokens (7d expiry). Return access JWT in response body, set refresh token as httpOnly cookie.

**refresh_access_token(refresh_token_cookie)**: Hash cookie value, look up in refresh_tokens (not expired, not revoked). Revoke old refresh token. Issue new access JWT + new refresh token (rotation). JWT in body, new cookie.

### Dependencies (auth/dependencies.py)

**get_current_user()**: Extract `Authorization: Bearer <token>` header -> decode JWT -> load user from DB -> return user. 401 on missing/invalid/expired token.

### Schemas (auth/schemas.py)

- `MagicLinkRequest(email: EmailStr)`
- `MagicLinkResponse(message: str)`
- `VerifyRequest(email: EmailStr, token: str)`
- `AuthResponse(access_token: str, token_type: str = "bearer")`
- `UserResponse(id: UUID, email: str, display_name: str | None, billing_mode: str)`

## Auth Frontend

### Token Management

- Access token in memory (React context). Lost on page refresh.
- Refresh token as httpOnly cookie (set by backend).
- On page load: AuthProvider attempts silent refresh (POST /auth/refresh with cookie). If success -> store access token, user sees nothing. If failure -> redirect to /login. Loading spinner shown during silent refresh.
- API client wrapper (lib/api.ts): attaches Bearer header. On 401 -> call /auth/refresh -> retry original request. If refresh fails -> redirect to /login.

### Pages

**`/login`**: Email input (Mantine TextInput + Button). Submit -> POST /api/auth/magic-link. Success -> "Check your email" message. Rate limit (429) -> error message.

**`/login/verify`**: Reads token + email from URL query params. Calls POST /api/auth/verify. Success -> store access token in auth context, redirect to /dashboard. Error -> "Link expired or invalid" + link to /login.

**`/dashboard`**: Empty shell proving auth works. Shows user email + logout button.

### Auth Context (AuthProvider)

Wraps the app. Holds access token in state. On mount: silent refresh attempt. Provides login(accessToken), logout(), isAuthenticated, user. Logout clears state and revokes refresh token.

### Protected Layout

Wraps /dashboard and future protected routes. If not authenticated and silent refresh fails -> redirect to /login.

### No TanStack Query

Auth flow is imperative (login/verify/refresh), not data-fetching. TanStack Query deferred to Milestone 3+.

## Testing Strategy

### Backend (real Postgres + Mailpit)

**Model tests**: CRUD, cascade deletes, hash storage.

**Service tests**:
- request_magic_link -> email in Mailpit (GET http://mailpit:8025/api/v1/messages), DB row created
- Rate limiting: 4th request in 15min rejected
- verify_magic_link -> JWT returned, link marked used, user auto-created on first login
- Expired/used links rejected
- refresh_access_token -> new JWT, old token revoked, new token created
- Invalid/expired/revoked refresh tokens rejected

**Router tests** (httpx ASGI client):
- POST /api/auth/magic-link -> 200 + email sent
- POST /api/auth/verify -> 200 + access token + refresh cookie
- POST /api/auth/refresh -> 200 + new tokens
- get_current_user -> 401 on bad tokens
- Rate limit -> 429

**Integration test**: Full flow — request magic link -> extract token from Mailpit -> verify -> get JWT -> hit protected endpoint -> success.

### Frontend (Vitest + React Testing Library)

- Login form renders, submits, shows "check your email" state
- Verify page calls API on mount, redirects on success, shows error on failure
- Protected layout redirects when not authenticated
- Auth context state after login/logout

## Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Email sender | Simple if/else | Only two providers, no abstraction needed |
| 401 handling | Full interceptor from start | Avoids rework later, is the final behavior |
| Token storage | Memory + httpOnly cookie | Most secure — no XSS access to refresh token |
