// api/publish.ts
// Handles open-access client-side bundle publishing to the Hugging Face registry
// Supports both a legacy single-stage binary POST flow (up to 4.5MB limit)
// and a robust two-stage direct-to-S3 LFS handshake/commit flow (up to 100MB+).

import JSZip from 'jszip';
import crypto from 'crypto';

export default async function handler(req: any, res: any) {
    if (req.method !== 'POST') {
        res.setHeader('Allow', 'POST');
        return res.status(405).json({ error: `Method ${req.method} not allowed` });
    }

    try {
        const contentType = req.headers['content-type'] || '';
        const isJson = contentType.includes('application/json');

        let repo = '';
        let version = '';
        let stage = '';
        let sha256 = '';
        let size = 0;
        let bundleMetadata: any = {};
        let displaySize = '';
        let fileBuffer = Buffer.alloc(0);

        if (isJson) {
            // Read JSON body
            const chunks: Buffer[] = [];
            for await (const chunk of req) {
                chunks.push(chunk);
            }
            const jsonText = Buffer.concat(chunks).toString('utf-8');
            let body: any = {};
            try {
                body = JSON.parse(jsonText);
            } catch (err) {
                return res.status(400).json({ error: "Invalid JSON body payload." });
            }

            repo = body.repo;
            version = body.version;
            stage = (req.headers['x-publish-stage'] || body.stage || '').toLowerCase();
            sha256 = body.sha256;
            size = body.size;
            bundleMetadata = body.bundleMetadata || {};
            displaySize = body.displaySize || 'unknown';

            if (!stage || !['handshake', 'commit'].includes(stage)) {
                return res.status(400).json({ error: "Invalid or missing 'X-Publish-Stage' header. Expected 'handshake' or 'commit'." });
            }
            if (!sha256 || !size) {
                return res.status(400).json({ error: "SHA256 hash and file size are required for the two-stage flow." });
            }
        } else {
            // Legacy direct binary payload stream
            repo = req.query.repo || '';
            version = req.query.version || '';
            
            const chunks: Buffer[] = [];
            let receivedBytes = 0;
            const MAX_SIZE = 100 * 1024 * 1024; // 100MB limit for legacy (though Vercel limits to 4.5MB)

            for await (const chunk of req) {
                receivedBytes += chunk.length;
                if (receivedBytes > MAX_SIZE) {
                    return res.status(413).json({ error: "Payload too large. Maximum allowed size is 100MB." });
                }
                chunks.push(chunk);
            }
            fileBuffer = Buffer.concat(chunks);

            if (fileBuffer.length === 0) {
                return res.status(400).json({ error: "Request body is empty." });
            }

            // structural archive validation
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

            try {
                const metadataText = await metadataFile.async("text");
                bundleMetadata = JSON.parse(metadataText);
            } catch (metaErr) {
                console.warn("[Publish API] Failed to parse metadata.json in bundle:", metaErr);
            }
        }

        // Clean repository name (extract owner/repo from URL or path)
        if (!repo || typeof repo !== 'string') {
            return res.status(400).json({ error: "Repository parameter is required." });
        }

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

        // 3. Verify public GitHub repository exists (done for handshake stage or legacy flow)
        if (stage === 'handshake' || !isJson) {
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
        }

        // 4. Connect to Hugging Face Registry
        const hfRepo = process.env.HF_REGISTRY_REPO || 'codegraphcontext/registry';
        const hfToken = process.env.HF_ADMIN_WRITE_TOKEN;

        if (!hfToken) {
            return res.status(500).json({ error: "Registry write credentials are not configured on the server." });
        }

        // Build standard paths and filenames
        let finalBundleName = "";
        const owner = repo.split('/')[0];
        const repoName = repo.split('/')[1];
        const branch = bundleMetadata.branch || "main";
        const commit = bundleMetadata.commit || bundleMetadata.version || version || "latest";
        const cleanCommit = commit.length === 40 && /^[0-9a-fA-F]+$/.test(commit) ? commit.substring(0, 7) : commit;
        finalBundleName = `${owner}__${repoName}__${branch}__${cleanCommit}.cgc.base64`;
        
        const bundleFilename = `bundles/${finalBundleName}`;

        // ----------------- STAGE: HANDSHAKE -----------------
        if (stage === 'handshake') {
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

            const uploadAction = obj.actions?.upload;
            if (uploadAction) {
                return res.status(200).json({
                    success: true,
                    uploadRequired: true,
                    uploadUrl: uploadAction.href,
                    uploadHeaders: uploadAction.header || {}
                });
            } else {
                return res.status(200).json({
                    success: true,
                    uploadRequired: false,
                    message: "Bundle already uploaded to LFS storage."
                });
            }
        }

        // ----------------- STAGE: COMMIT or LEGACY FLOW -----------------
        let manifest: any = { bundles: [] };
        const manifestUrl = `https://huggingface.co/datasets/${hfRepo}/raw/main/manifest.json`;
        
        try {
            const manifestRes = await fetch(manifestUrl, {
                headers: {
                    'Authorization': `Bearer ${hfToken}`
                }
            });
            if (manifestRes.ok) {
                manifest = await manifestRes.json();
            }
        } catch (e) {
            console.log('No existing manifest.json found, creating a new one.');
        }

        const sizeStr = isJson ? displaySize : `${(fileBuffer.length / 1024 / 1024).toFixed(2)}MB`;

        const newEntry = {
            name: repoName,
            repo: repo,
            bundle_name: finalBundleName,
            version: version,
            commit: cleanCommit,
            size: sizeStr,
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

        const base64Manifest = Buffer.from(JSON.stringify(manifest, null, 2)).toString('base64');

        if (!isJson) {
            // Legacy single-stage flow: calculates hashes and uploads LFS binary inline
            const base64Cgc = fileBuffer.toString('base64');
            const base64CgcBuffer = Buffer.from(base64Cgc, 'utf-8');
            const legacySha256 = crypto.createHash('sha256').update(base64CgcBuffer).digest('hex');
            const legacySize = base64CgcBuffer.length;

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
                    objects: [{ oid: legacySha256, size: legacySize }]
                })
            });

            if (!lfsRes.ok) {
                throw new Error(`Hugging Face LFS handshake failed`);
            }

            const lfsData = await lfsRes.json();
            const obj = lfsData.objects?.[0];
            if (obj?.actions?.upload) {
                const upload = obj.actions.upload;
                const putRes = await fetch(upload.href, {
                    method: 'PUT',
                    headers: { ...upload.header },
                    body: base64CgcBuffer
                });
                if (!putRes.ok) {
                    throw new Error(`Hugging Face LFS PUT upload failed`);
                }
            }

            sha256 = legacySha256;
            size = legacySize;
        }

        // Commit file references to manifest on HF datasets API
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
