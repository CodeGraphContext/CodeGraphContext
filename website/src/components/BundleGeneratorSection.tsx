import { useState } from 'react';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Alert, AlertDescription } from '@/components/ui/alert';
import { Progress } from '@/components/ui/progress';
import { Loader2, Package, Download, ExternalLink, CheckCircle2, XCircle, Clock } from 'lucide-react';
import { useToast } from '@/hooks/use-toast';

interface GenerationStatus {
    status: 'idle' | 'validating' | 'exists' | 'triggered' | 'processing' | 'ready' | 'error';
    message?: string;
    repository?: string;
    run_id?: string | null;
    run_url?: string | null;
    download_url?: string;
    bundle?: any;
    error?: string;
    estimated_time?: string;
    repo_size_mb?: string;
}

const BundleGeneratorSection = () => {
    const [repoUrl, setRepoUrl] = useState('');
    const [generationStatus, setGenerationStatus] = useState<GenerationStatus>({ status: 'idle' });
    const [progress, setProgress] = useState(0);
    const { toast } = useToast();

    const handleGenerateBundle = async () => {
        if (!repoUrl.trim()) {
            toast({
                title: 'Error',
                description: 'Please enter a GitHub repository URL',
                variant: 'destructive'
            });
            return;
        }

        setGenerationStatus({ status: 'validating' });
        setProgress(5);

        // Check if running in development mode (API endpoints won't work locally)
        const isDevelopment = import.meta.env.DEV;

        if (isDevelopment) {
            // Show development mode message
            toast({
                title: '🚧 Development Mode',
                description: 'API endpoints only work when deployed to Vercel. Showing mock response for UI testing.',
            });

            // Simulate API delay
            setTimeout(() => {
                setGenerationStatus({
                    status: 'ready',
                    message: 'Mock bundle ready (development mode)',
                    repository: repoUrl.replace('https://github.com/', ''),
                    download_url: '#',
                    bundle: {
                        repo: repoUrl.replace('https://github.com/', ''),
                        bundle_name: 'example-repo-v1.0.0-abc123.cgc',
                        size: '25MB',
                        generated_at: new Date().toISOString(),
                        commit: 'abc123'
                    }
                });
                setProgress(100);
            }, 2000);
            return;
        }

        try {
            const response = await fetch('/api/trigger-bundle', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ repoUrl })
            });

            const data = await response.json();

            if (!response.ok) {
                setGenerationStatus({
                    status: 'error',
                    error: data.error || 'Failed to generate bundle'
                });
                setProgress(0);
                return;
            }

            if (data.status === 'exists') {
                // Bundle already exists
                setGenerationStatus({
                    status: 'ready',
                    message: 'Bundle already exists!',
                    repository: data.bundle.repo,
                    download_url: data.download_url,
                    bundle: data.bundle
                });
                setProgress(100);

                toast({
                    title: 'Bundle Found!',
                    description: 'This repository has already been indexed. You can download it now.',
                });
            } else if (data.status === 'triggered') {
                // Bundle generation started
                setGenerationStatus({
                    status: 'triggered',
                    message: 'Bundle generation started',
                    repository: data.repository,
                    run_id: data.run_id,
                    run_url: data.run_url,
                    estimated_time: data.estimated_time,
                    repo_size_mb: data.repo_size_mb
                });
                setProgress(15);

                toast({
                    title: 'Generation Started!',
                    description: `Indexing ${data.repository}. This will take ${data.estimated_time}.`,
                });

                // Start polling for status
                if (data.run_id) {
                    pollBundleStatus(data.run_id, data.repository);
                }
            }

        } catch (err: any) {
            setGenerationStatus({
                status: 'error',
                error: err.message || 'Network error'
            });
            setProgress(0);
        }
    };

    const pollBundleStatus = async (runId: string, repo: string) => {
        const pollInterval = setInterval(async () => {
            try {
                const response = await fetch(`/api/bundle-status?run_id=${runId}`);
                const data = await response.json();

                if (data.status === 'completed') {
                    clearInterval(pollInterval);

                    if (data.conclusion === 'success') {
                        // Check manifest for download URL
                        const manifestResponse = await fetch(`/api/bundle-status?repo=${repo}`);
                        const manifestData = await manifestResponse.json();

                        if (manifestData.status === 'ready') {
                            setGenerationStatus({
                                status: 'ready',
                                message: 'Bundle ready for download!',
                                repository: repo,
                                download_url: manifestData.download_url,
                                bundle: manifestData.bundle
                            });
                            setProgress(100);

                            toast({
                                title: 'Bundle Ready!',
                                description: 'Your bundle has been generated successfully.',
                            });
                        }
                    } else {
                        setGenerationStatus({
                            status: 'error',
                            error: 'Bundle generation failed. Please try again.'
                        });
                        setProgress(0);
                    }
                } else if (data.status === 'in_progress') {
                    setGenerationStatus(prev => ({ ...prev, status: 'processing' }));
                    setProgress(data.progress || 50);
                }

            } catch (err) {
                console.error('Error polling status:', err);
            }
        }, 10000); // Poll every 10 seconds

        // Stop polling after 30 minutes
        setTimeout(() => clearInterval(pollInterval), 30 * 60 * 1000);
    };

    const renderStatusContent = () => {
        switch (generationStatus.status) {
            case 'idle':
                return (
                    <div className="space-y-4">
                        <div className="flex gap-2">
                            <Input
                                type="url"
                                placeholder="https://github.com/owner/repo"
                                value={repoUrl}
                                onChange={(e) => setRepoUrl(e.target.value)}
                                className="flex-1"
                                onKeyDown={(e) => e.key === 'Enter' && handleGenerateBundle()}
                            />
                            <Button onClick={handleGenerateBundle} size="lg">
                                <Package className="mr-2 h-4 w-4" />
                                Generate Bundle
                            </Button>
                        </div>
                        <p className="text-sm text-muted-foreground">
                            💡 Enter any public GitHub repository URL to generate a .cgc bundle
                        </p>
                    </div>
                );

            case 'validating':
                return (
                    <Alert>
                        <Loader2 className="h-4 w-4 animate-spin" />
                        <AlertDescription>Validating repository...</AlertDescription>
                    </Alert>
                );

            case 'triggered':
            case 'processing':
                return (
                    <Card>
                        <CardHeader>
                            <CardTitle className="flex items-center gap-2">
                                <Clock className="h-5 w-5 text-blue-500" />
                                Generating Bundle
                            </CardTitle>
                            <CardDescription>{generationStatus.repository}</CardDescription>
                        </CardHeader>
                        <CardContent className="space-y-4">
                            <Progress value={progress} className="w-full" />
                            <div className="space-y-2 text-sm">
                                <p>
                                    <strong>Status:</strong> {generationStatus.status === 'triggered' ? 'Queued' : 'Indexing repository'}
                                </p>
                                <p>
                                    <strong>Estimated Time:</strong> {generationStatus.estimated_time}
                                </p>
                                {generationStatus.repo_size_mb && (
                                    <p>
                                        <strong>Repository Size:</strong> {generationStatus.repo_size_mb} MB
                                    </p>
                                )}
                                {generationStatus.run_url && (
                                    <Button variant="link" asChild className="p-0 h-auto">
                                        <a href={generationStatus.run_url} target="_blank" rel="noopener noreferrer">
                                            View Progress on GitHub <ExternalLink className="ml-1 h-3 w-3" />
                                        </a>
                                    </Button>
                                )}
                            </div>
                        </CardContent>
                    </Card>
                );

            case 'exists':
            case 'ready':
                return (
                    <Card className="border-green-500">
                        <CardHeader>
                            <CardTitle className="flex items-center gap-2">
                                <CheckCircle2 className="h-5 w-5 text-green-500" />
                                Bundle Ready!
                            </CardTitle>
                            <CardDescription>{generationStatus.repository}</CardDescription>
                        </CardHeader>
                        <CardContent className="space-y-4">
                            {generationStatus.bundle && (
                                <div className="grid grid-cols-2 gap-2 text-sm">
                                    <div>
                                        <strong>Bundle:</strong> {generationStatus.bundle.bundle_name}
                                    </div>
                                    <div>
                                        <strong>Size:</strong> {generationStatus.bundle.size}
                                    </div>
                                    <div>
                                        <strong>Generated:</strong> {new Date(generationStatus.bundle.generated_at).toLocaleDateString()}
                                    </div>
                                    <div>
                                        <strong>Commit:</strong> {generationStatus.bundle.commit}
                                    </div>
                                </div>
                            )}
                            <div className="flex gap-2">
                                <Button asChild className="flex-1">
                                    <a href={generationStatus.download_url} download>
                                        <Download className="mr-2 h-4 w-4" />
                                        Download Bundle
                                    </a>
                                </Button>
                                <Button variant="outline" onClick={() => {
                                    setGenerationStatus({ status: 'idle' });
                                    setRepoUrl('');
                                    setProgress(0);
                                }}>
                                    Generate Another
                                </Button>
                            </div>
                            <div className="bg-muted p-3 rounded-md text-sm">
                                <p className="font-mono">cgc load {generationStatus.bundle?.bundle_name || 'bundle.cgc'}</p>
                            </div>
                        </CardContent>
                    </Card>
                );

            case 'error':
                return (
                    <Alert variant="destructive">
                        <XCircle className="h-4 w-4" />
                        <AlertDescription>
                            {generationStatus.error}
                            <Button
                                variant="link"
                                className="ml-2 p-0 h-auto text-destructive underline"
                                onClick={() => {
                                    setGenerationStatus({ status: 'idle' });
                                    setProgress(0);
                                }}
                            >
                                Try Again
                            </Button>
                        </AlertDescription>
                    </Alert>
                );

            default:
                return null;
        }
    };

    return (
        <section className="py-20 px-4 bg-muted/30">
            <div className="container mx-auto max-w-4xl">
                <div className="text-center mb-12" data-aos="fade-up">
                    <Badge variant="secondary" className="mb-4">
                        <Package className="w-4 h-4 mr-2" />
                        On-Demand Generation
                    </Badge>
                    <h2 className="text-4xl font-bold mb-4">Generate Custom Bundle</h2>
                    <p className="text-xl text-muted-foreground">
                        Index any public GitHub repository and get a downloadable .cgc bundle
                    </p>
                </div>

                <div data-aos="fade-up" data-aos-delay="200">
                    {import.meta.env.DEV && (
                        <Alert className="mb-4 border-yellow-500 bg-yellow-50 dark:bg-yellow-950/20">
                            <AlertDescription className="text-yellow-800 dark:text-yellow-200">
                                <strong>Development Mode:</strong> API endpoints require deployment to Vercel.
                                The UI will show mock responses for testing purposes.
                            </AlertDescription>
                        </Alert>
                    )}
                    {renderStatusContent()}
                </div>

                <div className="mt-8 text-center text-sm text-muted-foreground" data-aos="fade-up" data-aos-delay="400">
                    <p>⏱️ Generation typically takes 5-10 minutes depending on repository size</p>
                    <p className="mt-2">📦 Bundles are cached for 30 days for faster access</p>
                </div>
            </div>
        </section>
    );
};

export default BundleGeneratorSection;
