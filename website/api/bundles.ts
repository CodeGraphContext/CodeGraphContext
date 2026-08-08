// api/bundles.ts
// Fetches all available bundles from GitHub Releases

export default async function handler(req: any, res: any) {
    try {
        // Query the official CodeGraphContext parent repository for pre-indexed releases,
        // unless a custom registry is explicitly set in environment variables.
        const org = process.env.OFFICIAL_REGISTRY_ORG || 'CodeGraphContext';
        const repo = process.env.OFFICIAL_REGISTRY_REPO || 'CodeGraphContext';

        const allBundles: any[] = [];

        // 1. Fetch community and server bundles from Hugging Face manifest
        try {
            const hfRepo = process.env.HF_REGISTRY_REPO || 'codegraphcontext/registry';
            const manifestUrl = `https://huggingface.co/datasets/${hfRepo}/raw/main/manifest.json`;
            const manifestResponse = await fetch(manifestUrl);

            if (manifestResponse.ok) {
                const manifest = await manifestResponse.json();
                if (manifest.bundles && Array.isArray(manifest.bundles)) {
                    allBundles.push(...manifest.bundles.map((b: any) => ({
                        ...b,
                        name: b.repo ? b.repo.split('/')[1] : b.name || 'unknown',
                        category: b.source === 'server-indexed' ? 'Server' : 'Community',
                        source: b.source || 'community'
                    })));
                }
            }
        } catch (err) {
            console.log('No manifest found on Hugging Face:', err);
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
