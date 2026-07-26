import { useState, useEffect } from 'react';
import { motion } from 'framer-motion';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Tabs, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { Search, Download, Package, Calendar, HardDrive, Star, Loader2, ExternalLink, Copy, Check, HelpCircle, ChevronLeft, ChevronRight, Share2 } from 'lucide-react';
import { Alert, AlertDescription } from '@/components/ui/alert';
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle, DialogTrigger } from '@/components/ui/dialog';
import { toast } from 'sonner';
import GlassCard from './GlassCard';
import SectionDivider from './SectionDivider';

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
        <section id="registry" className="w-full py-24 bg-black relative overflow-hidden">
            <SectionDivider variant="dots" className="absolute top-0 left-0 right-0 z-0 opacity-50" />
            <div className="max-w-7xl mx-auto px-6 relative z-10 pt-10">
                
                {/* Section Header */}
                <div className="flex flex-col md:flex-row md:items-end justify-between mb-12 gap-6">
                    <div>
                        <Badge variant="secondary" className="mb-4 bg-white/10 text-white rounded-full uppercase tracking-widest text-[10px] font-bold">
                            <Package className="w-4 h-4 mr-2" />
                            Bundle Registry
                        </Badge>
                        <motion.h2 
                            initial={{ opacity: 0, y: -20 }}
                            whileInView={{ opacity: 1, y: 0 }}
                            viewport={{ once: true }}
                            transition={{ duration: 0.5 }}
                            className="text-3xl sm:text-4xl md:text-5xl font-black mb-6 uppercase tracking-tight py-2 text-white"
                        >
                            Pre-indexed CGC Bundles
                        </motion.h2>
                        <motion.p 
                            initial={{ opacity: 0, y: 20 }}
                            whileInView={{ opacity: 1, y: 0 }}
                            viewport={{ once: true }}
                            transition={{ duration: 0.5, delay: 0.1 }}
                            className="text-sm font-mono text-gray-400 uppercase tracking-widest max-w-2xl"
                        >
                            Browse and download pre-compiled context bundles for popular repositories. Or search servers and community contributions.
                        </motion.p>
                    </div>

                    <div className="flex flex-col sm:flex-row gap-3 w-full md:w-auto shrink-0">
                        <Button 
                            variant="outline" 
                            size="sm" 
                            className="w-full sm:w-auto border-white/10 bg-transparent text-white hover:bg-purple-600 hover:text-white shadow-[0_0_15px_rgba(168,85,247,0.4)] transition-all duration-300 rounded-full uppercase tracking-widest text-[10px] font-bold px-6 py-6"
                            onClick={handleShareRegistry}
                        >
                            <Share2 className="w-4 h-4 mr-2" />
                            Share Registry
                        </Button>

                        <Dialog>
                            <DialogTrigger asChild>
                                <Button variant="outline" size="sm" className="w-full sm:w-auto border-white/10 bg-transparent text-white hover:bg-purple-600 hover:text-white shadow-[0_0_15px_rgba(168,85,247,0.4)] transition-all duration-300 rounded-full uppercase tracking-widest text-[10px] font-bold px-6 py-6">
                                    <HelpCircle className="w-4 h-4 mr-2" />
                                    How to Use Bundles
                                </Button>
                            </DialogTrigger>
                        <DialogContent className="sm:max-w-[480px] bg-black border border-white/20 rounded-3xl text-white">
                            <DialogHeader>
                                <DialogTitle className="font-black uppercase tracking-widest text-lg">How to Use Pre-indexed Bundles</DialogTitle>
                                <DialogDescription className="text-xs font-mono text-gray-500 uppercase tracking-widest">
                                    Get up and running with a pre-built repository context in seconds.
                                </DialogDescription>
                            </DialogHeader>
                            <div className="space-y-4 py-4">
                                <div className="space-y-2">
                                    <h4 className="font-bold text-xs uppercase tracking-widest">1. Install the CLI</h4>
                                    <pre className="bg-white/5 border border-white/10 p-3 rounded-2xl text-[10px] font-mono overflow-x-auto text-white">pip install codegraphcontext</pre>
                                </div>
                                <div className="space-y-2">
                                    <h4 className="font-bold text-xs uppercase tracking-widest">2. Download and Load a Bundle</h4>
                                    <p className="text-[10px] font-mono text-gray-500 uppercase tracking-widest">
                                        Click "Copy Command" on any bundle card below to copy the load command. It automatically downloads and installs the bundle context locally:
                                    </p>
                                    <pre className="bg-white/5 border border-white/10 p-3 rounded-2xl text-[10px] font-mono overflow-x-auto text-white">cgc load numpy</pre>
                                </div>
                                <div className="space-y-2">
                                    <h4 className="font-bold text-xs uppercase tracking-widest">3. Query Context with AI Tools</h4>
                                    <p className="text-[10px] font-mono text-gray-500 uppercase tracking-widest">
                                        Ask questions or use our MCP server to feed the code index directly to Cursor, Windsurf, or Claude:
                                    </p>
                                    <pre className="bg-white/5 border border-white/10 p-3 rounded-2xl text-[10px] font-mono overflow-x-auto text-white">cgc query "How is indexing structured?"</pre>
                                </div>
                            </div>
                        </DialogContent>
                    </Dialog>
                    </div>
                </div>

                {import.meta.env.DEV && (
                    <Alert className="mb-6 border-purple-500 bg-purple-50 dark:bg-purple-950/20">
                        <AlertDescription className="text-purple-800 dark:text-purple-200">
                            <strong>Development Mode:</strong> Showing mock bundle data.
                            Deploy to production to see real bundles from the Hugging Face registry.
                        </AlertDescription>
                    </Alert>
                )}

                {/* Search and Filters */}
                <div className="mb-8 space-y-4">
                    <div className="relative">
                        <Search className="absolute left-4 top-3.5 h-5 w-5 text-gray-500" />
                        <Input
                            placeholder="SEARCH BUNDLES..."
                            value={searchQuery}
                            onChange={(e) => setSearchQuery(e.target.value)}
                            className="pl-12 bg-black border-white/20 text-white rounded-full h-12 uppercase tracking-widest text-xs font-mono placeholder:text-gray-600 focus-visible:ring-1 focus-visible:ring-white"
                        />
                    </div>

                    {/* Category Tabs */}
                    <Tabs value={selectedCategory} onValueChange={setSelectedCategory}>
                        <TabsList className="bg-white/5 p-1.5 rounded-full border border-white/10 gap-1 h-auto">
                            {categories.map(category => (
                                <TabsTrigger 
                                    key={category.id} 
                                    value={category.id}
                                    className="py-2.5 px-6 text-[10px] font-black uppercase tracking-widest rounded-full transition-all duration-300 data-[state=active]:bg-purple-600 data-[state=active]:text-white data-[state=active]:shadow-[0_0_15px_rgba(168,85,247,0.4)] text-gray-500 hover:text-white"
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
                    <div className="w-full py-4">
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
                                <motion.div 
                                    key={`${bundle.name}-${bundle.version || index}`} 
                                    className="h-full"
                                    initial={{ opacity: 0, y: 30 }}
                                    whileInView={{ opacity: 1, y: 0 }}
                                    viewport={{ once: true, margin: "-50px" }}
                                    transition={{ duration: 0.5, delay: index * 0.05 }}
                                >
                                    <GlassCard
                                        glowColor="none"
                                        className="h-full flex flex-col justify-between"
                                    >
                                        <div className="p-6 pb-4">
                                            <div className="flex items-start justify-between">
                                                <div className="flex-1 min-w-0">
                                                    <CardTitle className="text-lg text-white font-black uppercase tracking-widest truncate">{bundle.name}</CardTitle>
                                                    <CardDescription className="text-[10px] font-mono mt-1 truncate">
                                                        <a
                                                            href={`https://github.com/${bundle.repo}`}
                                                            target="_blank"
                                                            rel="noopener noreferrer"
                                                            className="inline-flex items-center gap-1 text-gray-600 dark:text-gray-400 hover:text-purple-600 dark:hover:text-purple-400 transition-colors underline underline-offset-2"
                                                        >
                                                            {bundle.repo}
                                                            <ExternalLink className="h-3 w-3 shrink-0" />
                                                        </a>
                                                    </CardDescription>
                                                </div>
                                                {bundle.category && (
                                                    <Badge variant="outline" className="ml-2 shrink-0 border-purple-500/30 text-purple-400 bg-purple-500/10 rounded-full text-[8px] uppercase tracking-widest font-black">
                                                        {bundle.category}
                                                    </Badge>
                                                )}
                                            </div>
                                        </div>
                                        <div className="p-6 pt-0 space-y-5">
                                            {/* Description */}
                                            {bundle.description ? (
                                                <p className="text-[10px] font-mono text-gray-500 uppercase tracking-widest line-clamp-2 h-8">
                                                    {bundle.description}
                                                </p>
                                            ) : (
                                                <div className="h-8" />
                                            )}

                                            {/* Stats */}
                                            <div className="grid grid-cols-2 gap-2 text-[11px] text-gray-600 dark:text-gray-400 font-mono">
                                                {bundle.stars ? (
                                                    <div className="flex items-center gap-1">
                                                        <Star className="w-3.5 h-3.5 text-yellow-400 fill-yellow-400/20" />
                                                        <span>{(bundle.stars / 1000).toFixed(1)}k stars</span>
                                                    </div>
                                                ) : (
                                                    <div />
                                                )}
                                                <div className="flex items-center gap-1">
                                                    <HardDrive className="w-3.5 h-3.5 text-purple-400" />
                                                    <span>{bundle.size}</span>
                                                </div>
                                                <div className="flex items-center gap-1 col-span-2">
                                                    <Calendar className="w-3.5 h-3.5 text-purple-400" />
                                                    <span>{new Date(bundle.generated_at).toLocaleDateString()}</span>
                                                </div>
                                            </div>

                                            {/* Version Info */}
                                            <div className="flex gap-2 text-[10px]">
                                                {bundle.version && (
                                                    <Badge variant="secondary" className="bg-white/10 text-gray-300 hover:bg-purple-500/30 border-0">v{bundle.version}</Badge>
                                                )}
                                                <a href={`https://github.com/${bundle.repo}/commit/${bundle.commit}`}
                                                    target="_blank"
                                                    rel="noopener noreferrer"
                                                    className="inline-flex items-center gap-1"
                                                >
                                                    <Badge
                                                        variant="secondary"
                                                        className="font-mono cursor-pointer bg-white/10 text-gray-300 hover:bg-purple-500/30 border-0"
                                                    >
                                                        {bundle.commit?.slice(0, 7) || 'unknown'}
                                                        <ExternalLink className="h-2.5 w-2.5 ml-1" />
                                                    </Badge>
                                                </a>
                                            </div>

                                            {/* Action Buttons */}
                                            <div className="flex gap-2 w-full pt-2">
                                                <Button className="flex-1 bg-gradient-to-r from-purple-600 to-cyan-500 shadow-[0_0_15px_rgba(168,85,247,0.3)] ring-1 ring-purple-500/30 hover:opacity-90 text-white border-0 text-[10px] uppercase font-bold tracking-wider py-3 px-2 rounded-full" asChild>
                                                    <a href={`/explore?bundle_url=${encodeURIComponent(bundle.download_url)}`}>
                                                        <img src="/cgcIcon.png" alt="CGC" className="w-3 h-3 mr-1 shrink-0" />
                                                        Visualize
                                                    </a>
                                                </Button>
                                                <Button 
                                                    variant="outline" 
                                                    className="flex-1 text-[10px] uppercase font-bold tracking-wider py-3 px-2 rounded-full bg-transparent border-white/20 text-white hover:bg-purple-600 hover:text-white shadow-[0_0_15px_rgba(168,85,247,0.4)] transition-colors overflow-hidden"
                                                    onClick={() => handleDownloadBundle(bundle.download_url, bundle.bundle_name || `${bundle.name}.cgc`)}
                                                    disabled={downloadingUrls[bundle.download_url]}
                                                >
                                                    {downloadingUrls[bundle.download_url] ? (
                                                        <Loader2 className="w-3 h-3 mr-1 animate-spin shrink-0" />
                                                    ) : (
                                                        <Download className="w-3 h-3 mr-1 shrink-0" />
                                                    )}
                                                    <span className="truncate">
                                                        {downloadingUrls[bundle.download_url] ? "DL'ING..." : "DOWNLOAD"}
                                                    </span>
                                                </Button>
                                            </div>

                                            {/* Usage Hint */}
                                            <div className="bg-white/5 border border-white/10 p-2.5 rounded-full px-4 text-[10px] font-mono flex items-center justify-between gap-2 group/code">
                                                <span className="flex-1 truncate text-gray-400">
                                                    cgc load {bundle.bundle_name || `${bundle.name}-${bundle.version || 'latest'}.cgc`}
                                                </span>
                                                <button
                                                    onClick={() => handleCopyCommand(
                                                        bundle.bundle_name || `${bundle.name}-${bundle.version || 'latest'}.cgc`,
                                                        index
                                                    )}
                                                    className="shrink-0 p-1.5 rounded-full hover:bg-purple-600 hover:text-white shadow-[0_0_15px_rgba(168,85,247,0.4)] transition-colors"
                                                    aria-label={`Copy command for ${bundle.name}`}
                                                    title="Copy to clipboard"
                                                >
                                                    {copiedBundleIndex === index ? (
                                                        <Check className="w-3.5 h-3.5 text-green-400" />
                                                    ) : (
                                                        <Copy className="w-3.5 h-3.5 text-gray-600 dark:text-gray-500 group-hover/code:text-white" />
                                                    )}
                                                </button>
                                            </div>
                                        </div>
                                    </GlassCard>
                                </motion.div>
                            ))}
                        </div>
                    </div>
                )}

                {/* Stats Summary */}
                {!loading && bundles.length > 0 && (
                    <div className="mt-12 text-center text-[10px] font-mono uppercase tracking-widest text-gray-500">
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
