import { useState, useEffect } from 'react';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { Search, Download, Package, Calendar, HardDrive, Star, Loader2, ExternalLink, Copy, Check, HelpCircle } from 'lucide-react';
import { Alert, AlertDescription } from '@/components/ui/alert';
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle, DialogTrigger } from '@/components/ui/dialog';
import { toast } from 'sonner';

interface Bundle {
    name: string;
    repo: string;
    bundle_name?: string;  // Full bundle filename (e.g., "python-bitcoin-utils-main-61d1969.cgc")
    version?: string;
    commit: string;
    size: string;
    download_url: string;
    generated_at: string;
    category?: string;
    description?: string;
    stars?: number;
}

const BundleRegistrySection = () => {
    const [bundles, setBundles] = useState<Bundle[]>([]);
    const [loading, setLoading] = useState(true);
    const [searchQuery, setSearchQuery] = useState('');
    const [selectedCategory, setSelectedCategory] = useState('all');
    const [copiedBundleIndex, setCopiedBundleIndex] = useState<number | null>(null);

    useEffect(() => {
        fetchBundles();
    }, []);

    const fetchBundles = async () => {
        setLoading(true);

        try {
            // In development, show mock data
            if (import.meta.env.DEV) {
                setTimeout(() => {
                    setBundles(getMockBundles());
                    setLoading(false);
                }, 1000);
                return;
            }

            // Fetch from our API endpoint (production)
            const response = await fetch('/api/bundles');

            if (response.ok) {
                const data = await response.json();
                setBundles(data.bundles || []);
            } else {
                console.error('Failed to fetch bundles');
                setBundles(getMockBundles());
            }
        } catch (error) {
            console.error('Error fetching bundles:', error);
            // Fallback to mock data on error
            setBundles(getMockBundles());
        } finally {
            setLoading(false);
        }
    };

    const getMockBundles = (): Bundle[] => [
        {
            name: 'numpy',
            repo: 'numpy/numpy',
            version: '1.26.4',
            commit: 'a1b2c3d',
            size: '50MB',
            download_url: '#',
            generated_at: '2026-01-13T00:00:00Z',
            category: 'Data Science',
            description: 'Fundamental package for scientific computing',
            stars: 25000
        },
        {
            name: 'pandas',
            repo: 'pandas-dev/pandas',
            version: '2.1.0',
            commit: 'def456',
            size: '80MB',
            download_url: '#',
            generated_at: '2026-01-13T00:00:00Z',
            category: 'Data Science',
            description: 'Data analysis and manipulation library',
            stars: 40000
        },
        {
            name: 'fastapi',
            repo: 'tiangolo/fastapi',
            version: '0.109.0',
            commit: 'ghi789',
            size: '15MB',
            download_url: '#',
            generated_at: '2026-01-13T00:00:00Z',
            category: 'Web Framework',
            description: 'Modern web framework for building APIs',
            stars: 70000
        },
        {
            name: 'requests',
            repo: 'psf/requests',
            version: '2.31.0',
            commit: 'jkl012',
            size: '10MB',
            download_url: '#',
            generated_at: '2026-01-13T00:00:00Z',
            category: 'HTTP',
            description: 'HTTP library for Python',
            stars: 50000
        },
        {
            name: 'flask',
            repo: 'pallets/flask',
            version: '3.0.0',
            commit: 'mno345',
            size: '12MB',
            download_url: '#',
            generated_at: '2026-01-13T00:00:00Z',
            category: 'Web Framework',
            description: 'Lightweight WSGI web application framework',
            stars: 65000
        }
    ];

    const parseWeeklyBundles = (release: any): Bundle[] => {
        // Parse bundle files from release assets
        return release.assets
            .filter((asset: any) => asset.name.endsWith('.cgc'))
            .map((asset: any) => {
                const nameParts = asset.name.replace('.cgc', '').split('-');
                return {
                    name: nameParts[0],
                    repo: `${nameParts[0]}/${nameParts[0]}`,
                    version: nameParts[1] || 'latest',
                    commit: nameParts[2] || 'unknown',
                    size: `${(asset.size / 1024 / 1024).toFixed(1)}MB`,
                    download_url: asset.browser_download_url,
                    generated_at: asset.updated_at,
                    category: 'Pre-indexed'
                };
            });
    };

    const filteredBundles = bundles.filter(bundle => {
        const matchesSearch =
            (bundle.name?.toLowerCase() || '').includes(searchQuery.toLowerCase()) ||
            (bundle.repo?.toLowerCase() || '').includes(searchQuery.toLowerCase()) ||
            (bundle.description?.toLowerCase() || '').includes(searchQuery.toLowerCase());

        const matchesCategory =
            selectedCategory === 'all' || bundle.category === selectedCategory;

        return matchesSearch && matchesCategory;
    });

    const categories = ['all', ...new Set(bundles.map(b => b.category).filter(Boolean))];

    const handleCopyCommand = async (bundleName: string, index: number) => {
        const command = `cgc load ${bundleName}`;
        try {
            await navigator.clipboard.writeText(command);
            setCopiedBundleIndex(index);
            toast.success('Command copied to clipboard!');
            setTimeout(() => setCopiedBundleIndex(null), 2000);
        } catch (err) {
            toast.error('Failed to copy command');
            console.error('Copy failed:', err);
        }
    };

    return (
        <section id="bundle-registry" className="py-20 px-4">
            <div className="container mx-auto max-w-7xl">
                {/* Header */}
                <div className="text-center mb-12" data-aos="fade-up">
                    <Badge variant="secondary" className="mb-4">
                        <Package className="w-4 h-4 mr-2" />
                        Bundle Registry
                    </Badge>
                    <div className="flex items-center justify-center gap-3 mb-4">
                        <h2 className="text-4xl font-bold">Pre-indexed Repositories</h2>
                        <Dialog>
                            <DialogTrigger asChild>
                                <button 
                                    className="inline-flex items-center justify-center rounded-full p-2 hover:bg-muted transition-colors"
                                    aria-label="Help - How to use pre-indexed bundles"
                                >
                                    <HelpCircle className="w-6 h-6 text-muted-foreground hover:text-primary" />
                                </button>
                            </DialogTrigger>
                            <DialogContent className="max-w-2xl max-h-[90vh] overflow-y-auto">
                                <DialogHeader>
                                    <DialogTitle>How to Use Pre-indexed Bundles</DialogTitle>
                                    <DialogDescription>
                                        Learn how to quickly download and load pre-indexed repositories
                                    </DialogDescription>
                                </DialogHeader>
                                <div className="space-y-4 mt-4">
                                    <div className="prose dark:prose-invert max-w-none">
                                        <h3 className="text-lg font-semibold mb-2">What are Pre-indexed Bundles?</h3>
                                        <p className="text-sm text-muted-foreground mb-4">
                                            Pre-indexed bundles are ready-to-use knowledge graph snapshots of popular repositories. 
                                            Instead of indexing code yourself (which can take time), you can download and load these bundles instantly.
                                        </p>

                                        <h3 className="text-lg font-semibold mb-2">Quick Start Guide</h3>
                                        <ol className="text-sm text-muted-foreground space-y-2 list-decimal list-inside">
                                            <li>Browse the available bundles below and find one you need</li>
                                            <li>Click the <strong>Download Bundle</strong> button to download the .cgc file</li>
                                            <li>Copy the CLI command shown (click the copy icon next to it)</li>
                                            <li>Run the command in your terminal to load the bundle</li>
                                            <li>Start using the knowledge graph with your AI assistant immediately!</li>
                                        </ol>

                                        <h3 className="text-lg font-semibold mb-2 mt-4">Example Usage</h3>
                                        <div className="bg-muted p-3 rounded-md font-mono text-xs space-y-2">
                                            <div># Download a bundle (e.g., numpy)</div>
                                            <div># Then load it:</div>
                                            <div className="text-primary font-semibold">cgc load numpy-1.26.4.cgc</div>
                                        </div>

                                        <div className="mt-6 bg-blue-50 dark:bg-blue-950/20 border border-blue-200 dark:border-blue-800 rounded-lg p-4">
                                            <h4 className="text-sm font-semibold mb-2 text-blue-900 dark:text-blue-100">💡 Pro Tip</h4>
                                            <p className="text-xs text-blue-800 dark:text-blue-200">
                                                Use the copy button next to each command to avoid typos. The bundle filename is automatically included in the command.
                                            </p>
                                        </div>

                                        {/* Placeholder for video/GIF */}
                                        <div className="mt-6 bg-muted rounded-lg p-8 text-center border-2 border-dashed">
                                            <Package className="w-12 h-12 mx-auto mb-3 text-muted-foreground" />
                                            <p className="text-sm text-muted-foreground">
                                                Video tutorial coming soon!
                                            </p>
                                            <p className="text-xs text-muted-foreground mt-1">
                                                For now, follow the steps above to get started
                                            </p>
                                        </div>
                                    </div>
                                </div>
                            </DialogContent>
                        </Dialog>
                    </div>
                    <p className="text-xl text-muted-foreground">
                        Download and load instantly - no indexing required
                    </p>
                </div>

                {/* Development Mode Alert */}
                {import.meta.env.DEV && (
                    <Alert className="mb-6 border-blue-500 bg-blue-50 dark:bg-blue-950/20">
                        <AlertDescription className="text-blue-800 dark:text-blue-200">
                            <strong>Development Mode:</strong> Showing mock bundle data.
                            Deploy to production to see real bundles from GitHub Releases.
                        </AlertDescription>
                    </Alert>
                )}

                {/* Search and Filters */}
                <div className="mb-8 space-y-4" data-aos="fade-up">
                    <div className="relative">
                        <Search className="absolute left-3 top-3 h-5 w-5 text-muted-foreground" />
                        <Input
                            placeholder="Search bundles by name, repository, or description..."
                            value={searchQuery}
                            onChange={(e) => setSearchQuery(e.target.value)}
                            className="pl-10"
                        />
                    </div>

                    {/* Category Tabs */}
                    <Tabs value={selectedCategory} onValueChange={setSelectedCategory}>
                        <TabsList>
                            {categories.map(category => (
                                <TabsTrigger key={category} value={category}>
                                    {category === 'all' ? 'All' : category}
                                </TabsTrigger>
                            ))}
                        </TabsList>
                    </Tabs>
                </div>

                {/* Loading State */}
                {loading && (
                    <div className="flex justify-center items-center py-20">
                        <Loader2 className="h-8 w-8 animate-spin text-primary" />
                        <span className="ml-3 text-muted-foreground">Loading bundles...</span>
                    </div>
                )}

                {/* Bundle Grid */}
                {!loading && filteredBundles.length === 0 && (
                    <div className="text-center py-20">
                        <Package className="h-16 w-16 mx-auto text-muted-foreground mb-4" />
                        <p className="text-xl text-muted-foreground">No bundles found</p>
                        <p className="text-sm text-muted-foreground mt-2">
                            Try adjusting your search or filters
                        </p>
                    </div>
                )}

                {!loading && filteredBundles.length > 0 && (
                    <div className="grid md:grid-cols-2 lg:grid-cols-3 gap-6" data-aos="fade-up">
                        {filteredBundles.map((bundle, index) => (
                            <Card
                                key={`${bundle.repo}-${index}`}
                                className="hover:shadow-lg transition-all duration-300 hover:scale-105"
                            >
                                <CardHeader>
                                    <div className="flex items-start justify-between">
                                        <div className="flex-1">
                                            <CardTitle className="text-lg">{bundle.name}</CardTitle>
                                            <CardDescription className="text-sm mt-1">
                                                <a
                                                    href={`https://github.com/${bundle.repo}`}
                                                    target="_blank"
                                                    rel="noopener noreferrer"
                                                    className="inline-flex items-center gap-1 text-muted-foreground hover:text-primary transition-colors underline underline-offset-2"
                                                >
                                                    {bundle.repo}
                                                    <ExternalLink className="h-3.5 w-3.5 shrink-0" />
                                                </a>
                                            </CardDescription>
                                        </div>
                                        {bundle.category && (
                                            <Badge variant="outline" className="ml-2">
                                                {bundle.category}
                                            </Badge>
                                        )}
                                    </div>
                                </CardHeader>
                                <CardContent className="space-y-4">
                                    {/* Description */}
                                    {bundle.description && (
                                        <p className="text-sm text-muted-foreground line-clamp-2">
                                            {bundle.description}
                                        </p>
                                    )}

                                    {/* Stats */}
                                    <div className="grid grid-cols-2 gap-2 text-sm">
                                        {bundle.stars && (
                                            <div className="flex items-center gap-1 text-muted-foreground">
                                                <Star className="w-4 h-4" />
                                                <span>{(bundle.stars / 1000).toFixed(1)}k</span>
                                            </div>
                                        )}
                                        <div className="flex items-center gap-1 text-muted-foreground">
                                            <HardDrive className="w-4 h-4" />
                                            <span>{bundle.size}</span>
                                        </div>
                                        <div className="flex items-center gap-1 text-muted-foreground col-span-2">
                                            <Calendar className="w-4 h-4" />
                                            <span>{new Date(bundle.generated_at).toLocaleDateString()}</span>
                                        </div>
                                    </div>

                                    {/* Version Info */}
                                    <div className="flex gap-2 text-xs">
                                        {bundle.version && (
                                            <Badge variant="secondary">v{bundle.version}</Badge>
                                        )}
                                        <a href={`https://github.com/${bundle.repo}/commit/${bundle.commit}`}
                                        target="_blank"
                                        rel="noopener noreferrer"
                                        className="inline-flex items-center gap-1"
                                        >
                                       <Badge
                                       variant="secondary"
                                       className="font-mono cursor-pointer hover:bg-muted"
                                        >
                                       {bundle.commit}
                                       <ExternalLink className="h-3 w-3 ml-1" />
                                       </Badge>
                                       </a>

                                    </div>

                                    {/* Download Button */}
                                    <Button className="w-full" asChild>
                                        <a href={bundle.download_url} download>
                                            <Download className="w-4 h-4 mr-2" />
                                            Download Bundle
                                        </a>
                                    </Button>

                                    {/* Usage Hint with Copy Button */}
                                    <div className="bg-muted p-2 rounded text-xs font-mono flex items-center justify-between gap-2 group">
                                        <span className="flex-1 truncate">
                                            cgc load {bundle.bundle_name || `${bundle.name}-${bundle.version || 'latest'}.cgc`}
                                        </span>
                                        <button
                                            onClick={() => handleCopyCommand(
                                                bundle.bundle_name || `${bundle.name}-${bundle.version || 'latest'}.cgc`,
                                                index
                                            )}
                                            className="shrink-0 p-1 rounded hover:bg-background transition-colors"
                                            aria-label={`Copy command for ${bundle.name}`}
                                            title="Copy to clipboard"
                                        >
                                            {copiedBundleIndex === index ? (
                                                <Check className="w-4 h-4 text-green-600 dark:text-green-400" />
                                            ) : (
                                                <Copy className="w-4 h-4 text-muted-foreground group-hover:text-foreground" />
                                            )}
                                        </button>
                                    </div>
                                </CardContent>
                            </Card>
                        ))}
                    </div>
                )}

                {/* Stats Summary */}
                {!loading && bundles.length > 0 && (
                    <div className="mt-12 text-center text-sm text-muted-foreground" data-aos="fade-up">
                        <p>
                            Showing {filteredBundles.length} of {bundles.length} available bundles
                        </p>
                        <p className="mt-2">
                            💡 All bundles are pre-indexed and ready to load instantly
                        </p>
                    </div>
                )}
            </div>
        </section>
    );
};

export default BundleRegistrySection;
