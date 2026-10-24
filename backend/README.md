# LexiTrace

See the root README.md and docs/SRS_ALIGNMENT.md for current three-class labels, setup, API contracts, grouped data and limitations.

Administrator login and signup require a six-digit email verification code before a session is created. Configure the `LEXITRACE_SMTP_*` settings shown in `.env.example` in `backend/.env`, then restart the backend. Use your mail provider's SMTP credentials (or an app password where required). Delivery requires authenticated STARTTLS (default port 587) or SSL (port 465); a missing or failing mail configuration blocks administrator sign-in.

`POST /api/auth/login` and administrator signup return `{verification_required: true, challenge_id, expires_in: 600}`. Submit `{challenge_id, code}` to `POST /api/auth/verify-admin` to receive the session cookie and user. Codes are single use, expire after 10 minutes, and allow five incorrect attempts. Signing in again sends a replacement code after a 60-second cooldown. Regular user authentication is unchanged. An administrator account remains registered if its signup email fails; retry through login after fixing delivery.
