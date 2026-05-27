import { useState, useEffect } from 'react';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Tabs, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { Search, Download, Package, Calendar, HardDrive, Star, Loader2, ExternalLink, Copy, Check, HelpCircle, ChevronLeft, ChevronRight, Share2 } from 'lucide-react';
import { Alert, AlertDescription } from '@/components/ui/alert';
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle, DialogTrigger } from '@/components/ui/dialog';
import { toast } from 'sonner';

interface Bundle {
    name: string;
    repo: string;
    bundle_name?: string;  // Full bundle filename (e.g., "numpy-v1.0.0.cgc")
    version?: string;
    commit: string;
    size: string;
    download_url: string;
    generated_at: string;
    category?: string;
    description?: string;
    stars?: number;
    source?: string;
}

const BundleRegistrySection = () => {
    const [bundles, setBundles] = useState<Bundle[]>([]);
    const [loading, setLoading] = useState(true);
    const [searchQuery, setSearchQuery] = useState('');
    const [selectedCategory, setSelectedCategory] = useState('all');
    const [copiedBundleIndex, setCopiedBundleIndex] = useState<number | null>(null);
    const [downloadingUrls, setDownloadingUrls] = useState<Record<string, boolean>>({});

    useEffect(() => {
        fetchBundles();
    }, []);

    const fetchBundles = async () => {
        setLoading(true);

        try {
            // First, try to fetch from Vercel API `/api/bundles`
            try {
                const response = await fetch('/api/bundles');
                if (response.ok) {
                    const data = await response.json();
                    if (data.bundles && data.bundles.length > 0) {
                        setBundles(data.bundles);
                        setLoading(false);
                        return;
                    }
                }
            } catch (apiErr) {
                console.warn('Local Vercel api/bundles endpoint unavailable, attempting direct fetch:', apiErr);
            }

            // Fallback to local mock bundles if offline or rate-limited
            setBundles(getMockBundles());
        } catch (error) {
            console.error('Error fetching bundles:', error);
            setBundles(getMockBundles());
        } finally {
            setLoading(false);
        }
    };

    const handleDownloadBundle = async (downloadUrl: string, bundleName: string) => {
        setDownloadingUrls(prev => ({ ...prev, [downloadUrl]: true }));
        const toastId = toast.loading(`Downloading ${bundleName}...`);

        try {
            const response = await fetch(downloadUrl);
            if (!response.ok) throw new Error(`HTTP error! status: ${response.status}`);
            
            const base64Text = await response.text();
            
            // Decode base64 to binary
            const binaryString = atob(base64Text.trim());
            const len = binaryString.length;
            const bytes = new Uint8Array(len);
            for (let i = 0; i < len; i++) {
                bytes[i] = binaryString.charCodeAt(i);
            }
            
            const blob = new Blob([bytes], { type: "application/octet-stream" });
            const cleanFilename = bundleName.replace('.base64', '');
            
            const url = URL.createObjectURL(blob);
            const a = document.createElement("a");
            a.href = url;
            a.download = cleanFilename;
            document.body.appendChild(a);
            a.click();
            document.body.removeChild(a);
            URL.revokeObjectURL(url);
            
            toast.success(`Successfully downloaded ${cleanFilename}!`, { id: toastId });
        } catch (err: any) {
            console.error("Failed to decode and download bundle:", err);
            toast.error("Failed to download bundle: " + err.message, { id: toastId });
        } finally {
            setDownloadingUrls(prev => ({ ...prev, [downloadUrl]: false }));
        }
    };

    const getMockBundles = (): Bundle[] => [
        {
            name: 'numpy',
            repo: 'numpy/numpy',
            version: '1.26.4',
            commit: 'a1b2c3d',
            size: '50MB',
            download_url: '/sample_project.cgc',
            generated_at: '2026-01-13T00:00:00Z',
            category: 'Data Science',
            description: 'Fundamental package for scientific computing',
            stars: 25000,
            source: 'trending'
        },
        {
            name: 'pandas',
            repo: 'pandas-dev/pandas',
            version: '2.1.0',
            commit: 'def456',
            size: '80MB',
            download_url: '/sample_project.cgc',
            generated_at: '2026-01-13T00:00:00Z',
            category: 'Data Science',
            description: 'Data analysis and manipulation library',
            stars: 40000,
            source: 'trending'
        },
        {
            name: 'fastapi',
            repo: 'tiangolo/fastapi',
            version: '0.109.0',
            commit: 'ghi789',
            size: '15MB',
            download_url: '/sample_project.cgc',
            generated_at: '2026-01-13T00:00:00Z',
            category: 'Web Framework',
            description: 'Modern web framework for building APIs',
            stars: 70000,
            source: 'server-indexed'
        },
        {
            name: 'requests',
            repo: 'psf/requests',
            version: '2.31.0',
            commit: 'jkl012',
            size: '10MB',
            download_url: '/sample_project.cgc',
            generated_at: '2026-01-13T00:00:00Z',
            category: 'HTTP',
            description: 'HTTP library for Python',
            stars: 50000,
            source: 'server-indexed'
        },
        {
            name: 'flask',
            repo: 'pallets/flask',
            version: '3.0.0',
            commit: 'mno345',
            size: '12MB',
            download_url: '/sample_project.cgc',
            generated_at: '2026-01-13T00:00:00Z',
            category: 'Web Framework',
            description: 'Lightweight WSGI web application framework',
            stars: 65000,
            source: 'community'
        }
    ];



    const categories = [
        { id: 'all', label: 'All' },
        { id: 'trending', label: 'Trending Repos' },
        { id: 'server-indexed', label: 'Server Indexed' },
        { id: 'community', label: 'Community' }
    ];

    const filteredBundles = bundles
        .filter(bundle => {
            const matchesSearch =
                (bundle.name?.toLowerCase() || '').includes(searchQuery.toLowerCase()) ||
                (bundle.repo?.toLowerCase() || '').includes(searchQuery.toLowerCase()) ||
                (bundle.description?.toLowerCase() || '').includes(searchQuery.toLowerCase());

            const matchesCategory =
                selectedCategory === 'all' || bundle.source === selectedCategory;

            return matchesSearch && matchesCategory;
        })
        .sort((a, b) => {
            const timeA = a.generated_at ? new Date(a.generated_at).getTime() : 0;
            const timeB = b.generated_at ? new Date(b.generated_at).getTime() : 0;
            return timeB - timeA;
        });

    const handleCopyCommand = (bundleName: string, index: number) => {
        const cmd = `cgc load ${bundleName}`;
        navigator.clipboard.writeText(cmd)
            .then(() => {
                setCopiedBundleIndex(index);
                toast.success('Command copied to clipboard!');
                setTimeout(() => setCopiedBundleIndex(null), 2500);
            })
            .catch(() => toast.error('Failed to copy command'));
    };

    const handleShareRegistry = () => {
        const shareUrl = `${window.location.origin}/pre-indexed`;
        navigator.clipboard.writeText(shareUrl)
            .then(() => {
                toast.success('Registry share link copied to clipboard!');
            })
            .catch(() => {
                toast.error('Failed to copy share link');
            });
    };

    const scrollSlider = (direction: 'left' | 'right') => {
        const slider = document.getElementById('registry-slider');
        if (slider) {
            const scrollAmount = direction === 'left' ? -380 : 380;
            slider.scrollBy({ left: scrollAmount, behavior: 'smooth' });
        }
    };

    return (
        <section id="registry" className="w-full py-20 bg-background/50 border-t border-white/5 relative overflow-hidden">
            <div className="max-w-7xl mx-auto px-6 relative z-10">
                
                {/* Section Header */}
                <div className="flex flex-col md:flex-row md:items-end justify-between mb-12 gap-6" data-aos="fade-up">
                    <div>
                        <Badge variant="secondary" className="mb-4">
                            <Package className="w-4 h-4 mr-2" />
                            Bundle Registry
                        </Badge>
                        <h2 className="text-3xl md:text-4xl font-bold bg-gradient-to-r from-white to-gray-400 bg-clip-text text-transparent">
                            Pre-indexed CGC Bundles
                        </h2>
                        <p className="text-muted-foreground mt-2 max-w-xl">
                            Browse and download pre-compiled context bundles for popular repositories. Or search servers and community contributions.
                        </p>
                    </div>

                    <div className="flex flex-col sm:flex-row gap-3 w-full md:w-auto shrink-0">
                        <Button 
                            variant="outline" 
                            size="sm" 
                            className="w-full sm:w-auto border-white/10 text-white hover:bg-white/5 hover:border-white/20 transition-all duration-300"
                            onClick={handleShareRegistry}
                        >
                            <Share2 className="w-4 h-4 mr-2 text-indigo-400" />
                            Share Registry
                        </Button>

                        <Dialog>
                            <DialogTrigger asChild>
                                <Button variant="outline" size="sm" className="w-full sm:w-auto">
                                    <HelpCircle className="w-4 h-4 mr-2" />
                                    How to Use Bundles
                                </Button>
                            </DialogTrigger>
                        <DialogContent className="sm:max-w-[480px]">
                            <DialogHeader>
                                <DialogTitle>How to Use Pre-indexed Bundles</DialogTitle>
                                <DialogDescription>
                                    Get up and running with a pre-built repository context in seconds.
                                </DialogDescription>
                            </DialogHeader>
                            <div className="space-y-4 py-4">
                                <div className="space-y-2">
                                    <h4 className="font-semibold text-sm">1. Install the CLI</h4>
                                    <pre className="bg-muted p-2 rounded text-xs overflow-x-auto">pip install codegraphcontext</pre>
                                </div>
                                <div className="space-y-2">
                                    <h4 className="font-semibold text-sm">2. Download and Load a Bundle</h4>
                                    <p className="text-xs text-muted-foreground">
                                        Click "Copy Command" on any bundle card below to copy the load command. It automatically downloads and installs the bundle context locally:
                                    </p>
                                    <pre className="bg-muted p-2 rounded text-xs overflow-x-auto">cgc load numpy</pre>
                                </div>
                                <div className="space-y-2">
                                    <h4 className="font-semibold text-sm">3. Query Context with AI Tools</h4>
                                    <p className="text-xs text-muted-foreground">
                                        Ask questions or use our MCP server to feed the code index directly to Cursor, Windsurf, or Claude:
                                    </p>
                                    <pre className="bg-muted p-2 rounded text-xs overflow-x-auto">cgc query "How is indexing structured?"</pre>
                                </div>
                            </div>
                        </DialogContent>
                    </Dialog>
                    </div>
                </div>

                {import.meta.env.DEV && (
                    <Alert className="mb-6 border-blue-500 bg-blue-50 dark:bg-blue-950/20">
                        <AlertDescription className="text-blue-800 dark:text-blue-200">
                            <strong>Development Mode:</strong> Showing mock bundle data.
                            Deploy to production to see real bundles from the Hugging Face registry.
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
                        <TabsList className="bg-white/5 p-1 rounded-xl shadow-inner border border-white/5 gap-1">
                            {categories.map(category => (
                                <TabsTrigger 
                                    key={category.id} 
                                    value={category.id}
                                    className="py-2 px-4 text-xs font-semibold rounded-lg transition-all duration-300 data-[state=active]:bg-gradient-to-br data-[state=active]:from-purple-500 data-[state=active]:to-indigo-600 data-[state=active]:text-white data-[state=active]:shadow-md text-gray-400 hover:text-white"
                                >
                                    {category.label}
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
                    <div className="w-full py-4" data-aos="fade-up">
                        {/* Vertical Scroll Grid */}
                        <div
                            id="registry-grid"
                            className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-6 overflow-y-auto max-h-[780px] pr-2 pb-4"
                            style={{
                                scrollbarWidth: 'thin',
                                scrollbarColor: 'rgba(255,255,255,0.15) transparent'
                            }}
                        >
                            {filteredBundles.map((bundle, index) => (
                                <div
                                    key={`${bundle.repo}-${index}`}
                                    className="h-full"
                                >
                                    <Card
                                        className="h-full hover:shadow-lg transition-all duration-300 hover:scale-[1.01] border border-white/10 dark:border-white/20 bg-black/40 backdrop-blur-xl shadow-xl flex flex-col justify-between"
                                    >
                                        <CardHeader className="pb-4">
                                            <div className="flex items-start justify-between">
                                                <div className="flex-1 min-w-0">
                                                    <CardTitle className="text-lg text-white font-bold truncate">{bundle.name}</CardTitle>
                                                    <CardDescription className="text-xs mt-1 truncate">
                                                        <a
                                                            href={`https://github.com/${bundle.repo}`}
                                                            target="_blank"
                                                            rel="noopener noreferrer"
                                                            className="inline-flex items-center gap-1 text-gray-400 hover:text-purple-400 transition-colors underline underline-offset-2"
                                                        >
                                                            {bundle.repo}
                                                            <ExternalLink className="h-3 w-3 shrink-0" />
                                                        </a>
                                                    </CardDescription>
                                                </div>
                                                {bundle.category && (
                                                    <Badge variant="outline" className="ml-2 shrink-0 border-white/10 text-gray-300 bg-white/5">
                                                        {bundle.category}
                                                    </Badge>
                                                )}
                                            </div>
                                        </CardHeader>
                                        <CardContent className="space-y-4 pt-0">
                                            {/* Description */}
                                            {bundle.description ? (
                                                <p className="text-xs text-gray-400 line-clamp-2 h-8">
                                                    {bundle.description}
                                                </p>
                                            ) : (
                                                <div className="h-8" />
                                            )}

                                            {/* Stats */}
                                            <div className="grid grid-cols-2 gap-2 text-[11px] text-gray-400 font-mono">
                                                {bundle.stars ? (
                                                    <div className="flex items-center gap-1">
                                                        <Star className="w-3.5 h-3.5 text-yellow-400 fill-yellow-400/20" />
                                                        <span>{(bundle.stars / 1000).toFixed(1)}k stars</span>
                                                    </div>
                                                ) : (
                                                    <div />
                                                )}
                                                <div className="flex items-center gap-1">
                                                    <HardDrive className="w-3.5 h-3.5 text-blue-400" />
                                                    <span>{bundle.size}</span>
                                                </div>
                                                <div className="flex items-center gap-1 col-span-2">
                                                    <Calendar className="w-3.5 h-3.5 text-indigo-400" />
                                                    <span>{new Date(bundle.generated_at).toLocaleDateString()}</span>
                                                </div>
                                            </div>

                                            {/* Version Info */}
                                            <div className="flex gap-2 text-[10px]">
                                                {bundle.version && (
                                                    <Badge variant="secondary" className="bg-white/10 text-gray-300 hover:bg-white/20 border-0">v{bundle.version}</Badge>
                                                )}
                                                <a href={`https://github.com/${bundle.repo}/commit/${bundle.commit}`}
                                                    target="_blank"
                                                    rel="noopener noreferrer"
                                                    className="inline-flex items-center gap-1"
                                                >
                                                    <Badge
                                                        variant="secondary"
                                                        className="font-mono cursor-pointer bg-white/10 text-gray-300 hover:bg-white/20 border-0"
                                                    >
                                                        {bundle.commit?.slice(0, 7) || 'unknown'}
                                                        <ExternalLink className="h-2.5 w-2.5 ml-1" />
                                                    </Badge>
                                                </a>
                                            </div>

                                            {/* Action Buttons */}
                                            <div className="flex gap-2.5 w-full pt-2">
                                                <Button className="flex-1 bg-gradient-to-r from-blue-500 to-indigo-600 hover:from-blue-600 hover:to-indigo-700 text-white shadow-md border-0 text-xs py-2 rounded-lg" asChild>
                                                    <a href={`/explore?bundle_url=${encodeURIComponent(bundle.download_url)}`}>
                                                        <img src="/cgcIcon.png" alt="CGC" className="w-4 h-4 mr-1.5 shrink-0" />
                                                        Visualize
                                                    </a>
                                                </Button>
                                                <Button 
                                                    variant="outline" 
                                                    className="flex-1 text-xs py-2 rounded-lg bg-black/20 border-white/10 text-white hover:bg-white/5"
                                                    onClick={() => handleDownloadBundle(bundle.download_url, bundle.bundle_name || `${bundle.name}.cgc`)}
                                                    disabled={downloadingUrls[bundle.download_url]}
                                                >
                                                    {downloadingUrls[bundle.download_url] ? (
                                                        <Loader2 className="w-3.5 h-3.5 mr-1.5 animate-spin shrink-0 text-primary" />
                                                    ) : (
                                                        <Download className="w-3.5 h-3.5 mr-1.5 shrink-0" />
                                                    )}
                                                    {downloadingUrls[bundle.download_url] ? "Downloading..." : "Download"}
                                                </Button>
                                            </div>

                                            {/* Usage Hint */}
                                            <div className="bg-black/40 border border-white/5 p-2 rounded-lg text-[10px] font-mono flex items-center justify-between gap-2 group/code">
                                                <span className="flex-1 truncate text-gray-400">
                                                    cgc load {bundle.bundle_name || `${bundle.name}-${bundle.version || 'latest'}.cgc`}
                                                </span>
                                                <button
                                                    onClick={() => handleCopyCommand(
                                                        bundle.bundle_name || `${bundle.name}-${bundle.version || 'latest'}.cgc`,
                                                        index
                                                    )}
                                                    className="shrink-0 p-1 rounded hover:bg-white/10 transition-colors"
                                                    aria-label={`Copy command for ${bundle.name}`}
                                                    title="Copy to clipboard"
                                                >
                                                    {copiedBundleIndex === index ? (
                                                        <Check className="w-3.5 h-3.5 text-green-400" />
                                                    ) : (
                                                        <Copy className="w-3.5 h-3.5 text-gray-500 group-hover/code:text-white" />
                                                    )}
                                                </button>
                                            </div>
                                        </CardContent>
                                    </Card>
                                </div>
                            ))}
                        </div>
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
