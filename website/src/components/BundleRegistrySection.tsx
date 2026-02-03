import { useState, useEffect } from 'react';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { Search, Download, Package, Calendar, HardDrive, Star, Loader2, ExternalLink } from 'lucide-react';
import { Alert, AlertDescription } from '@/components/ui/alert';

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

    return (
        <section className="py-20 px-4">
            <div className="container mx-auto max-w-7xl">
                {/* Header */}
                <div className="text-center mb-12" data-aos="fade-up">
                    <Badge variant="secondary" className="mb-4">
                        <Package className="w-4 h-4 mr-2" />
                        Bundle Registry
                    </Badge>
                    <h2 className="text-4xl font-bold mb-4">Pre-indexed Repositories</h2>
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
                                        <Badge variant="secondary" className="font-mono">
                                            {bundle.commit}
                                        </Badge>
                                    </div>

                                    {/* Download Button */}
                                    <Button className="w-full" asChild>
                                        <a href={bundle.download_url} download>
                                            <Download className="w-4 h-4 mr-2" />
                                            Download Bundle
                                        </a>
                                    </Button>

                                    {/* Usage Hint */}
                                    <div className="bg-muted p-2 rounded text-xs font-mono">
                                        cgc load {bundle.bundle_name || `${bundle.name}-${bundle.version || 'latest'}.cgc`}
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
