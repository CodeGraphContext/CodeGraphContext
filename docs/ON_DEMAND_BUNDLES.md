# On-Demand Bundle Generation Setup

This guide explains how to set up and use the on-demand bundle generation feature.

## Overview

The on-demand bundle generation feature allows users to:
- Enter any public GitHub repository URL on your website
- Automatically trigger indexing and bundle creation via GitHub Actions
- Download the generated `.cgc` bundle file

## Architecture

```
User (Website) → API Endpoint → GitHub Actions → Bundle Created → GitHub Release
```

## Setup Instructions

### 1. GitHub Personal Access Token

You need a GitHub Personal Access Token (PAT) with the following permissions:

**Required Scopes:**
- `repo` (Full control of private repositories)
- `workflow` (Update GitHub Action workflows)

**Steps to create:**
1. Go to GitHub Settings → Developer settings → Personal access tokens → Tokens (classic)
2. Click "Generate new token (classic)"
3. Select scopes: `repo` and `workflow`
4. Generate and copy the token

### 2. Configure Environment Variables

#### For Local Development:

Create `/website/.env`:
```bash
GITHUB_TOKEN="ghp_your_token_here"
GITHUB_REPOSITORY="CodeGraphContext/CodeGraphContext"
```

#### For Vercel Deployment:

1. Go to your Vercel project settings
2. Navigate to "Environment Variables"
3. Add the following variables:
   - `GITHUB_TOKEN` = your GitHub PAT
   - `GITHUB_REPOSITORY` = `CodeGraphContext/CodeGraphContext`

### 3. Test the Workflow

#### Manual Test (GitHub UI):

1. Go to your repository on GitHub
2. Click "Actions" tab
3. Select "Generate Bundle On-Demand" workflow
4. Click "Run workflow"
5. Enter a repository URL (e.g., `https://github.com/psf/requests`)
6. Click "Run workflow"
7. Wait 5-10 minutes
8. Check the "on-demand-bundles" release for the generated bundle

#### API Test (Local):

```bash
# Start the website locally
cd website
npm run dev

# In another terminal, trigger bundle generation
curl -X POST http://localhost:5173/api/trigger-bundle \
  -H "Content-Type: application/json" \
  -d '{"repoUrl": "https://github.com/psf/requests"}'
```

### 4. Deploy to Vercel

```bash
cd website
vercel --prod
```

Make sure environment variables are set in Vercel dashboard before deploying.

## Usage

### For Users:

1. Visit your website
2. Scroll to "Generate Custom Bundle" section
3. Enter a GitHub repository URL
4. Click "Generate Bundle"
5. Wait for completion (5-10 minutes)
6. Download the `.cgc` file
7. Run: `cgc load bundle.cgc`

### API Endpoints:

#### Trigger Bundle Generation
```bash
POST /api/trigger-bundle
Content-Type: application/json

{
  "repoUrl": "https://github.com/owner/repo"
}
```

**Response (Success):**
```json
{
  "status": "triggered",
  "message": "Bundle generation started",
  "repository": "owner/repo",
  "repo_size_mb": "15.23",
  "estimated_time": "5-10 minutes",
  "run_id": "12345",
  "run_url": "https://github.com/.../actions/runs/12345",
  "status_url": "/api/bundle-status?repo=owner/repo"
}
```

**Response (Already Exists):**
```json
{
  "status": "exists",
  "message": "Bundle already exists",
  "bundle": {
    "repo": "owner/repo",
    "bundle_name": "repo-v1.0.0-abc123.cgc",
    "download_url": "https://github.com/.../releases/download/..."
  }
}
```

#### Check Bundle Status
```bash
GET /api/bundle-status?run_id=12345
# or
GET /api/bundle-status?repo=owner/repo
```

**Response:**
```json
{
  "status": "completed",
  "conclusion": "success",
  "progress": 100,
  "run_url": "https://github.com/.../actions/runs/12345"
}
```

## Troubleshooting

### Issue: "Failed to trigger workflow"

**Cause:** Invalid GitHub token or insufficient permissions

**Solution:**
1. Verify `GITHUB_TOKEN` is set correctly
2. Ensure token has `repo` and `workflow` scopes
3. Check token hasn't expired

### Issue: "Repository too large"

**Cause:** Repository exceeds 1GB size limit

**Solution:**
- This is a safety limit to prevent long-running workflows
- Consider increasing the limit in `/website/api/trigger-bundle.ts` if needed
- Or add the repository to the weekly pre-indexed list instead

### Issue: "Bundle generation failed"

**Cause:** Indexing error or unsupported language

**Solution:**
1. Check the GitHub Actions workflow logs
2. Verify the repository has supported languages (Python, JavaScript, etc.)
3. Check if the repository has unusual structure

### Issue: Workflow doesn't start

**Cause:** GitHub Actions quota exceeded or workflow disabled

**Solution:**
1. Check GitHub Actions usage in repository settings
2. Ensure workflow file is in `main` branch
3. Verify workflow is enabled in Actions settings

## Limitations

- **Repository Size:** Max 1GB (configurable)
- **Processing Time:** 5-30 minutes depending on size
- **GitHub Actions Quota:** 2000 minutes/month (free tier)
- **Public Repositories Only:** Private repos require user's own token
- **Bundle Retention:** 30 days (configurable)

## Future Enhancements

- [ ] Email notifications when bundle is ready
- [ ] Priority queue for premium users
- [ ] Support for private repositories
- [ ] Batch generation (multiple repos at once)
- [ ] Automatic cleanup of old bundles
- [ ] Bundle analytics and popularity tracking

## Security Notes

- Never commit `.env` file with real tokens
- Use Vercel environment variables for production
- GitHub token should have minimal required permissions
- Consider implementing rate limiting to prevent abuse
- Monitor GitHub Actions usage to avoid quota exhaustion

## Support

If you encounter issues:
1. Check the GitHub Actions workflow logs
2. Review the API response error messages
3. Open an issue on GitHub with details

---

**Last Updated:** 2026-01-21
