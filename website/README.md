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

## API Security Configuration

The on-demand bundle trigger endpoint (`/api/trigger-bundle`) now includes abuse protections.

Optional environment variables:

- `BUNDLE_TRIGGER_API_KEY`: if set, requests must include header `x-bundle-trigger-key`.
- `BUNDLE_TRIGGER_ALLOWED_ORIGINS`: comma-separated origin allow-list (for example: `https://codegraphcontext.io,https://www.codegraphcontext.io`).
- `BUNDLE_TRIGGER_RATE_LIMIT_MAX`: max requests per IP inside rate-limit window (default: `10`).
- `BUNDLE_TRIGGER_RATE_LIMIT_WINDOW_MS`: rate-limit window in ms (default: `900000`, i.e. 15 minutes).
- `BUNDLE_TRIGGER_REPO_COOLDOWN_MS`: cooldown per repository after a trigger (default: `300000`, i.e. 5 minutes).
- `BUNDLE_TRIGGER_ACTIVE_JOB_TTL_MS`: TTL for in-memory active-job dedupe records (default: `2700000`, i.e. 45 minutes).