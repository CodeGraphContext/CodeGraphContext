# Website

This directory contains the source code for the CodeGraphContext website.

## Development

To run the website locally, follow these steps:

1.  Navigate to this directory:
    ```bash
    cd website
    ```

2.  Install the dependencies:
    ```bash
    npm install
    ```

3.  Start the development server:
    ```bash
    npm run dev
    ```

## Build

To create a production build of the website, run:

```bash
npm run build
```

## AI providers

In the graph explorer, open **AI Knowledge Explorer → BYOK Settings** to select
Google Gemini, Mistral AI, or Anthropic (Claude) and enter your own API key.
Anthropic defaults to `claude-sonnet-4-6`; the optional model field accepts another
Claude model ID available to your account.

The key is saved in this browser's local storage, and graph context is sent directly
to the selected provider. Changing providers clears the key and custom model fields
so credentials are not reused with a different provider.

Run the provider regression tests (mocked requests; no API key required):

```bash
npm run test:summary
```

## API Security Configuration

The on-demand bundle trigger endpoint (`/api/trigger-bundle`) now includes abuse protections.

Optional environment variables:

- `BUNDLE_TRIGGER_API_KEY`: if set, requests must include header `x-bundle-trigger-key`.
- `BUNDLE_TRIGGER_ALLOWED_ORIGINS`: comma-separated origin allow-list (for example: `https://codegraphcontext.io,https://www.codegraphcontext.io`).
- `BUNDLE_TRIGGER_RATE_LIMIT_MAX`: max requests per IP inside rate-limit window (default: `10`).
- `BUNDLE_TRIGGER_RATE_LIMIT_WINDOW_MS`: rate-limit window in ms (default: `900000`, i.e. 15 minutes).
- `BUNDLE_TRIGGER_REPO_COOLDOWN_MS`: cooldown per repository after a trigger (default: `300000`, i.e. 5 minutes).
- `BUNDLE_TRIGGER_ACTIVE_JOB_TTL_MS`: TTL for in-memory active-job dedupe records (default: `2700000`, i.e. 45 minutes).
