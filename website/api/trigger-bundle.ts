// api/trigger-bundle.ts
// Triggers the on-demand bundle generation GitHub Actions workflow

export default async function handler(req: any, res: any) {
    // Only allow POST requests
    if (req.method !== 'POST') {
        return res.status(405).json({ error: 'Method not allowed' });
    }

    const { repoUrl } = req.body;

    // Validate input
    if (!repoUrl) {
        return res.status(400).json({ error: 'Repository URL is required' });
    }

    // Validate GitHub URL format
    const githubUrlPattern = /^https?:\/\/(www\.)?github\.com\/([^\/]+)\/([^\/]+)(\.git)?$/;
    const match = repoUrl.match(githubUrlPattern);

    if (!match) {
        return res.status(400).json({
            error: 'Invalid GitHub URL format. Expected: https://github.com/owner/repo'
        });
    }

    const owner = match[2];
    const repo = match[3].replace('.git', '');

    try {
        // Check if repository exists
        const repoCheckResponse = await fetch(`https://api.github.com/repos/${owner}/${repo}`);

        if (!repoCheckResponse.ok) {
            if (repoCheckResponse.status === 404) {
                return res.status(404).json({ error: 'Repository not found or is private' });
            }
            throw new Error('Failed to verify repository');
        }

        const repoData = await repoCheckResponse.json();

        // Check repository size (warn if > 1GB)
        const sizeInMB = repoData.size / 1024;
        if (sizeInMB > 1000) {
            return res.status(400).json({
                error: `Repository is too large (${sizeInMB.toFixed(0)}MB). Maximum supported size is 1GB.`,
                size_mb: sizeInMB
            });
        }

        // Check if bundle already exists in manifest
        try {
            const manifestResponse = await fetch(
                `https://github.com/${process.env.GITHUB_REPOSITORY || 'CodeGraphContext/CodeGraphContext'}/releases/download/on-demand-bundles/manifest.json`
            );

            if (manifestResponse.ok) {
                const manifest = await manifestResponse.json();
                const existingBundle = manifest.bundles?.find(
                    (b: any) => b.repo === `${owner}/${repo}`
                );

                if (existingBundle) {
                    // Bundle already exists, return it
                    return res.status(200).json({
                        status: 'exists',
                        message: 'Bundle already exists',
                        bundle: existingBundle,
                        download_url: existingBundle.download_url
                    });
                }
            }
        } catch (err) {
            // Manifest doesn't exist yet, continue
            console.log('Manifest not found, will create new bundle');
        }

        // Trigger GitHub Actions workflow
        const workflowResponse = await fetch(
            `https://api.github.com/repos/${process.env.GITHUB_REPOSITORY || 'CodeGraphContext/CodeGraphContext'}/actions/workflows/generate-bundle-on-demand.yml/dispatches`,
            {
                method: 'POST',
                headers: {
                    'Authorization': `token ${process.env.GITHUB_TOKEN}`,
                    'Content-Type': 'application/json',
                    'Accept': 'application/vnd.github.v3+json'
                },
                body: JSON.stringify({
                    ref: 'main',
                    inputs: {
                        repo_url: repoUrl,
                        repo_owner: owner,
                        repo_name: repo
                    }
                })
            }
        );

        if (!workflowResponse.ok) {
            const errorData = await workflowResponse.text();
            console.error('GitHub API Error:', errorData);
            throw new Error(`Failed to trigger workflow: ${workflowResponse.statusText}`);
        }

        // Get the latest workflow run ID (we just triggered it)
        // Wait a bit for GitHub to register the run
        await new Promise(resolve => setTimeout(resolve, 2000));

        const runsResponse = await fetch(
            `https://api.github.com/repos/${process.env.GITHUB_REPOSITORY || 'CodeGraphContext/CodeGraphContext'}/actions/workflows/generate-bundle-on-demand.yml/runs?per_page=1`,
            {
                headers: {
                    'Authorization': `token ${process.env.GITHUB_TOKEN}`,
                    'Accept': 'application/vnd.github.v3+json'
                }
            }
        );

        let runId = null;
        let runUrl = null;

        if (runsResponse.ok) {
            const runsData = await runsResponse.json();
            if (runsData.workflow_runs && runsData.workflow_runs.length > 0) {
                runId = runsData.workflow_runs[0].id;
                runUrl = runsData.workflow_runs[0].html_url;
            }
        }

        return res.status(202).json({
            status: 'triggered',
            message: 'Bundle generation started',
            repository: `${owner}/${repo}`,
            repo_size_mb: sizeInMB.toFixed(2),
            estimated_time: '5-10 minutes',
            run_id: runId,
            run_url: runUrl,
            status_url: `/api/bundle-status?repo=${owner}/${repo}`
        });

    } catch (err: any) {
        console.error('Error triggering bundle generation:', err);
        return res.status(500).json({
            error: 'Failed to trigger bundle generation',
            details: err.message
        });
    }
}
