// api/bundles.ts
// Fetches all available bundles from GitHub Releases

export default async function handler(req: any, res: any) {
    try {
        const org = process.env.GITHUB_REPOSITORY?.split('/')[0] || 'CodeGraphContext';
        const repo = process.env.GITHUB_REPOSITORY?.split('/')[1] || 'CodeGraphContext';

        const allBundles: any[] = [];

        // 1. Fetch on-demand bundles from manifest
        try {
            const manifestResponse = await fetch(
                `https://github.com/${org}/${repo}/releases/download/on-demand-bundles/manifest.json`,
                { headers: { 'Accept': 'application/json' } }
            );

            if (manifestResponse.ok) {
                const manifest = await manifestResponse.json();
                if (manifest.bundles && Array.isArray(manifest.bundles)) {
                    allBundles.push(...manifest.bundles.map((b: any) => ({
                        ...b,
                        category: 'On-Demand',
                        source: 'on-demand'
                    })));
                }
            }
        } catch (err) {
            console.log('No on-demand manifest found:', err);
        }

        // 2. Fetch weekly pre-indexed bundles
        try {
            const releasesResponse = await fetch(
                `https://api.github.com/repos/${org}/${repo}/releases`,
                {
                    headers: {
                        'Accept': 'application/vnd.github.v3+json',
                        ...(process.env.GITHUB_TOKEN && {
                            'Authorization': `token ${process.env.GITHUB_TOKEN}`
                        })
                    }
                }
            );

            if (releasesResponse.ok) {
                const releases = await releasesResponse.json();

                // Find releases with tag pattern "bundles-YYYYMMDD"
                const weeklyReleases = releases.filter((r: any) =>
                    r.tag_name.startsWith('bundles-') && r.tag_name !== 'bundles-latest'
                );

                // Get the most recent weekly release
                if (weeklyReleases.length > 0) {
                    const latestWeekly = weeklyReleases[0];

                    // Parse bundle files from assets
                    const weeklyBundles = latestWeekly.assets
                        .filter((asset: any) => asset.name.endsWith('.cgc'))
                        .map((asset: any) => {
                            const nameParts = asset.name.replace('.cgc', '').split('-');
                            const name = nameParts[0];
                            const version = nameParts[1] || 'latest';
                            const commit = nameParts[2] || 'unknown';

                            return {
                                name,
                                repo: getRepoName(name),
                                bundle_name: asset.name,
                                version,
                                commit,
                                size: `${(asset.size / 1024 / 1024).toFixed(1)}MB`,
                                download_url: asset.browser_download_url,
                                generated_at: asset.updated_at,
                                category: getCategoryForRepo(name),
                                description: getDescriptionForRepo(name),
                                stars: getStarsForRepo(name),
                                source: 'weekly'
                            };
                        });

                    allBundles.push(...weeklyBundles);
                }
            }
        } catch (err) {
            console.log('Error fetching weekly releases:', err);
        }

        // NO DEDUPLICATION - Keep all versions
        // Users can see all available versions and choose which one to download

        return res.status(200).json({
            bundles: allBundles,
            total: allBundles.length,
            updated_at: new Date().toISOString()
        });

    } catch (err: any) {
        console.error('Error fetching bundles:', err);
        return res.status(500).json({
            error: 'Failed to fetch bundles',
            details: err.message
        });
    }
}

// Helper functions to map repo names to metadata
function getRepoName(name: string): string {
    const repoMap: Record<string, string> = {
        'numpy': 'numpy/numpy',
        'pandas': 'pandas-dev/pandas',
        'fastapi': 'tiangolo/fastapi',
        'requests': 'psf/requests',
        'flask': 'pallets/flask',
        'httpx': 'encode/httpx'
    };
    return repoMap[name] || `${name}/${name}`;
}

function getCategoryForRepo(name: string): string {
    const categoryMap: Record<string, string> = {
        'numpy': 'Data Science',
        'pandas': 'Data Science',
        'fastapi': 'Web Framework',
        'requests': 'HTTP Client',
        'flask': 'Web Framework',
        'httpx': 'HTTP Client'
    };
    return categoryMap[name] || 'Library';
}

function getDescriptionForRepo(name: string): string {
    const descMap: Record<string, string> = {
        'numpy': 'Fundamental package for scientific computing with Python',
        'pandas': 'Data analysis and manipulation library',
        'fastapi': 'Modern web framework for building APIs with Python',
        'requests': 'HTTP library for Python',
        'flask': 'Lightweight WSGI web application framework',
        'httpx': 'Next generation HTTP client for Python'
    };
    return descMap[name] || `${name} library`;
}

function getStarsForRepo(name: string): number {
    const starsMap: Record<string, number> = {
        'numpy': 25000,
        'pandas': 40000,
        'fastapi': 70000,
        'requests': 50000,
        'flask': 65000,
        'httpx': 12000
    };
    return starsMap[name] || 0;
}
