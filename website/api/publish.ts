// api/publish.ts
// Handles open-access client-side bundle publishing to the Hugging Face registry

import JSZip from 'jszip';
import crypto from 'crypto';

export default async function handler(req: any, res: any) {
    if (req.method !== 'POST') {
        res.setHeader('Allow', 'POST');
        return res.status(405).json({ error: `Method ${req.method} not allowed` });
    }

    try {
        let { repo, version } = req.query;

        if (!repo || typeof repo !== 'string') {
            return res.status(400).json({ error: "Repository parameter is required." });
        }

        // Clean repository name (extract owner/repo from URL or path)
        let cleanRepo = repo.trim().replace(/\/$/, "");
        if (cleanRepo.includes("github.com/")) {
            const parts = cleanRepo.split("github.com/");
            cleanRepo = parts[parts.length - 1];
        }
        cleanRepo = cleanRepo.replace(/^(https?:\/\/)?(www\.)?github\.com\//, "");
        const segments = cleanRepo.split("/").filter(Boolean);
        if (segments.length < 2) {
            return res.status(400).json({ error: "Invalid repository format. Expected 'owner/repo' or a GitHub URL." });
        }
        repo = `${segments[0]}/${segments[1]}`;

        if (!version || typeof version !== 'string') {
            return res.status(400).json({ error: "Version parameter is required." });
        }

        // 1. Read binary octet-stream payload
        const chunks: Buffer[] = [];
        let receivedBytes = 0;
        const MAX_SIZE = 100 * 1024 * 1024; // Increased to 100MB for larger codebases

        for await (const chunk of req) {
            receivedBytes += chunk.length;
            if (receivedBytes > MAX_SIZE) {
                return res.status(413).json({ error: "Payload too large. Maximum allowed size is 20MB." });
            }
            chunks.push(chunk);
        }
        const fileBuffer = Buffer.concat(chunks);

        if (fileBuffer.length === 0) {
            return res.status(400).json({ error: "Request body is empty." });
        }

        // 2. structural archive validation
        let zip;
        try {
            zip = await JSZip.loadAsync(fileBuffer);
        } catch (zipErr) {
            return res.status(400).json({ error: "Invalid bundle file. Must be a valid zip archive." });
        }

        const nodesFile = zip.file("nodes.jsonl");
        const edgesFile = zip.file("edges.jsonl");
        const metadataFile = zip.file("metadata.json");

        if (!nodesFile || !edgesFile || !metadataFile) {
            return res.status(400).json({
                error: "Invalid CGC bundle structure. Archive must contain nodes.jsonl, edges.jsonl, and metadata.json."
            });
        }

        let bundleMetadata: any = {};
        try {
            const metadataText = await metadataFile.async("text");
            bundleMetadata = JSON.parse(metadataText);
        } catch (metaErr) {
            console.warn("[Publish API] Failed to parse metadata.json in bundle:", metaErr);
        }

        // 3. Verify public GitHub repository exists
        try {
            const token = process.env.GITHUB_TOKEN;
            const useToken = token && !token.startsWith("your-") && !token.includes("token");
            const ghRes = await fetch(`https://api.github.com/repos/${repo}`, {
                headers: {
                    'Accept': 'application/vnd.github.v3+json',
                    'User-Agent': 'CodeGraphContext-Registry-Proxy',
                    ...(useToken && {
                        'Authorization': `token ${token}`
                    })
                }
            });

            if (!ghRes.ok) {
                if (ghRes.status === 404) {
                    return res.status(404).json({ error: `Repository '${repo}' was not found on GitHub or is private.` });
                }
                throw new Error(`GitHub API returned status ${ghRes.status}`);
            }

            const ghData = await ghRes.json();
            if (ghData.private) {
                return res.status(400).json({ error: `Repository '${repo}' is private. Only public repositories can be published.` });
            }
        } catch (err: any) {
            console.error('GitHub Verification Error:', err);
            return res.status(500).json({ error: "Failed to verify repository on GitHub.", details: err.message });
        }

        // 4. Connect to Hugging Face Registry
        const hfRepo = process.env.HF_REGISTRY_REPO || 'codegraphcontext/bundles';
        const hfToken = process.env.HF_ADMIN_WRITE_TOKEN;

        if (!hfToken) {
            return res.status(500).json({ error: "Registry write credentials are not configured on the server." });
        }

        // A. Load existing manifest.json from Hugging Face CDN
        let manifest: any = { bundles: [] };
        const manifestUrl = `https://huggingface.co/datasets/${hfRepo}/raw/main/manifest.json`;
        try {
            const manifestRes = await fetch(manifestUrl);
            if (manifestRes.ok) {
                manifest = await manifestRes.json();
            }
        } catch (e) {
            console.log('No existing manifest.json found, creating a new one.');
        }

        // B. Compile metadata record
        let finalBundleName = "";
        if (repo.includes("/")) {
            const owner = repo.split('/')[0];
            const repoName = repo.split('/')[1];
            const branch = bundleMetadata.branch || "main";
            const commit = bundleMetadata.commit || bundleMetadata.version || version || "latest";
            const cleanCommit = commit.length === 40 && /^[0-9a-fA-F]+$/.test(commit) ? commit.substring(0, 7) : commit;
            finalBundleName = `${owner}__${repoName}__${branch}__${cleanCommit}.cgc.base64`;
        } else {
            finalBundleName = `${repo}.cgc.base64`;
        }

        const bundleFilename = `bundles/${finalBundleName}`;
        
        const newEntry = {
            name: repo.includes("/") ? repo.split('/')[1] : repo,
            repo: repo,
            bundle_name: finalBundleName,
            version: version,
            size: `${(fileBuffer.length / 1024 / 1024).toFixed(2)}MB`,
            download_url: `https://huggingface.co/datasets/${hfRepo}/resolve/main/${bundleFilename}`,
            generated_at: new Date().toISOString(),
            source: 'web-upload'
        };

        // De-duplicate existing matches for same repo/version
        if (manifest.bundles && Array.isArray(manifest.bundles)) {
            manifest.bundles = manifest.bundles.filter(
                (b: any) => !(b.repo.toLowerCase() === repo.toLowerCase() && b.version === version)
            );
        } else {
            manifest.bundles = [];
        }
        manifest.bundles.push(newEntry);

        // C. Base64 encode file buffer and calculate its SHA256 / size
        const base64Cgc = fileBuffer.toString('base64');
        const base64CgcBuffer = Buffer.from(base64Cgc, 'utf-8');
        const sha256 = crypto.createHash('sha256').update(base64CgcBuffer).digest('hex');
        const size = base64CgcBuffer.length;

        // D. Perform LFS Batch handshake with Hugging Face
        const lfsUrl = `https://huggingface.co/datasets/${hfRepo}.git/info/lfs/objects/batch`;
        const lfsRes = await fetch(lfsUrl, {
            method: 'POST',
            headers: {
                'Accept': 'application/vnd.git-lfs+json',
                'Content-Type': 'application/vnd.git-lfs+json',
                'Authorization': `Bearer ${hfToken}`
            },
            body: JSON.stringify({
                operation: 'upload',
                transfers: ['basic'],
                ref: { name: 'refs/heads/main' },
                objects: [{ oid: sha256, size }]
            })
        });

        if (!lfsRes.ok) {
            const lfsErr = await lfsRes.text();
            throw new Error(`Hugging Face LFS handshake failed: ${lfsErr}`);
        }

        const lfsData = await lfsRes.json();
        const obj = lfsData.objects?.[0];
        if (!obj || obj.error) {
            throw new Error(`Hugging Face LFS handshake rejected the file: ${obj?.error?.message || 'Unknown object error'}`);
        }

        // E. Upload raw base64 data to S3 via LFS action if required
        if (obj.actions?.upload) {
            const upload = obj.actions.upload;
            const putRes = await fetch(upload.href, {
                method: 'PUT',
                headers: { ...upload.header },
                body: base64CgcBuffer
            });

            if (!putRes.ok) {
                const putErr = await putRes.text();
                throw new Error(`Hugging Face LFS PUT upload failed: ${putErr}`);
            }
        }

        // F. Send atomic commit to Hugging Face referencing the LFS object and updating manifest
        const base64Manifest = Buffer.from(JSON.stringify(manifest, null, 2)).toString('base64');
        const commitUrl = `https://huggingface.co/api/datasets/${hfRepo}/commit/main`;
        const commitRes = await fetch(commitUrl, {
            method: 'POST',
            headers: {
                'Authorization': `Bearer ${hfToken}`,
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                summary: `Publish ${repo} (v${version}) via CGC Open-Access Web Proxy`,
                lfsFiles: [
                    {
                        path: bundleFilename,
                        oid: sha256,
                        algo: 'sha256',
                        size: size
                    }
                ],
                files: [
                    {
                        path: 'manifest.json',
                        content: base64Manifest,
                        encoding: 'base64'
                    }
                ]
            })
        });

        if (!commitRes.ok) {
            const commitErr = await commitRes.text();
            throw new Error(`Hugging Face API commit failed: ${commitErr}`);
        }

        return res.status(200).json({
            success: true,
            message: "Successfully published to the public registry!",
            entry: newEntry
        });

    } catch (err: any) {
        console.error('Publishing Exception:', err);
        return res.status(500).json({
            error: "Failed to publish bundle to the registry.",
            details: err.message
        });
    }
}
