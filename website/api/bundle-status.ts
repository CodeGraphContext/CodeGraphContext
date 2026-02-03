// api/bundle-status.ts
// Checks the status of a bundle generation request

export default async function handler(req: any, res: any) {
    const { repo, run_id } = req.query;

    if (!repo && !run_id) {
        return res.status(400).json({
            error: 'Either repo or run_id parameter is required'
        });
    }

    try {
        // If run_id is provided, check specific workflow run
        if (run_id) {
            const runResponse = await fetch(
                `https://api.github.com/repos/${process.env.GITHUB_REPOSITORY || 'CodeGraphContext/CodeGraphContext'}/actions/runs/${run_id}`,
                {
                    headers: {
                        'Authorization': `token ${process.env.GITHUB_TOKEN}`,
                        'Accept': 'application/vnd.github.v3+json'
                    }
                }
            );

            if (!runResponse.ok) {
                return res.status(404).json({ error: 'Workflow run not found' });
            }

            const runData = await runResponse.json();

            return res.status(200).json({
                status: runData.status, // queued, in_progress, completed
                conclusion: runData.conclusion, // success, failure, cancelled, null
                created_at: runData.created_at,
                updated_at: runData.updated_at,
                run_url: runData.html_url,
                progress: getProgress(runData.status, runData.conclusion)
            });
        }

        // If repo is provided, check manifest for bundle
        if (repo) {
            const manifestResponse = await fetch(
                `https://github.com/${process.env.GITHUB_REPOSITORY || 'CodeGraphContext/CodeGraphContext'}/releases/download/on-demand-bundles/manifest.json`
            );

            if (!manifestResponse.ok) {
                return res.status(200).json({
                    status: 'not_found',
                    message: 'Bundle not found in manifest'
                });
            }

            const manifest = await manifestResponse.json();
            const bundle = manifest.bundles?.find((b: any) => b.repo === repo);

            if (bundle) {
                return res.status(200).json({
                    status: 'ready',
                    bundle: bundle,
                    download_url: bundle.download_url
                });
            } else {
                return res.status(200).json({
                    status: 'not_found',
                    message: 'Bundle not found in manifest'
                });
            }
        }

    } catch (err: any) {
        console.error('Error checking bundle status:', err);
        return res.status(500).json({
            error: 'Failed to check bundle status',
            details: err.message
        });
    }
}

function getProgress(status: string, conclusion: string | null): number {
    if (status === 'queued') return 10;
    if (status === 'in_progress') return 50;
    if (status === 'completed') {
        if (conclusion === 'success') return 100;
        if (conclusion === 'failure') return 0;
    }
    return 0;
}
