# 📚 Documentation Update Guide

This guide explains how to update the CodeGraphContext documentation website.

## 🏗️ Documentation Structure

CodeGraphContext has **two separate web properties**:

### 1. **MkDocs Documentation** (Main Docs)
- **Location**: `/docs/`
- **URL**: https://CodeGraphContext.github.io/CodeGraphContext/
- **Purpose**: Technical documentation, guides, API reference
- **Technology**: MkDocs with Material theme

### 2. **React Landing Page** (Marketing Site)
- **Location**: `/website/`
- **URL**: https://codegraphcontext.vercel.app/ (or similar)
- **Purpose**: Marketing, features showcase, quick start
- **Technology**: React + Vite + TypeScript

---

## 📝 Updating MkDocs Documentation

### Quick Start

```bash
cd docs
pip install mkdocs-material
mkdocs serve  # Preview at http://127.0.0.1:8000
```

### File Structure

```
docs/
├── mkdocs.yml           # Configuration & navigation
├── docs/                # Markdown content
│   ├── index.md
│   ├── installation.md
│   ├── cookbook.md
│   └── ...
└── deployment/          # Deployment guides (NEW!)
    ├── README.md
    ├── DOCKER_README.md
    └── ...
```

### Adding New Pages

1. **Create a markdown file** in `docs/docs/`:
   ```bash
   touch docs/docs/my-new-page.md
   ```

2. **Add to navigation** in `docs/mkdocs.yml`:
   ```yaml
   nav:
     - My New Page: my-new-page.md
   ```

3. **Preview changes**:
   ```bash
   cd docs && mkdocs serve
   ```

### Building & Deploying

```bash
cd docs
mkdocs build  # Generates static site in docs/site/
mkdocs gh-deploy  # Deploys to GitHub Pages
```

---

## 🎨 Updating React Landing Page

### Quick Start

```bash
cd website
npm install
npm run dev  # Preview at http://localhost:5173
```

### Key Files to Edit

- **`src/pages/Index.tsx`** - Main landing page
- **`src/components/HeroSection.tsx`** - Hero banner
- **`src/components/FeaturesSection.tsx`** - Features list
- **`src/components/InstallationSection.tsx`** - Installation guide
- **`src/components/Footer.tsx`** - Footer links (just updated!)
- **`src/components/CookbookSection.tsx`** - Code examples

### Building for Production

```bash
cd website
npm run build  # Generates dist/ folder
```

---

## ✅ Recent Changes

### What We Just Did

1. ✅ Moved deployment docs from root to `docs/deployment/`
2. ✅ Updated `docs/mkdocs.yml` to include deployment section
3. ✅ Updated `website/src/components/Footer.tsx` to link to deployment docs
4. ✅ Created `docs/deployment/README.md` as navigation index

### Next Steps to Publish

1. **Test MkDocs locally**:
   ```bash
   cd docs
   mkdocs serve
   # Visit http://127.0.0.1:8000 and check the "Deployment" section
   ```

2. **Deploy to GitHub Pages**:
   ```bash
   cd docs
   mkdocs gh-deploy
   ```

3. **Update React site** (if needed):
   ```bash
   cd website
   npm run build
   # Deploy to Vercel/Netlify/etc.
   ```

---

## 🔗 Useful Links

- **MkDocs Documentation**: https://www.mkdocs.org/
- **Material Theme**: https://squidfunk.github.io/mkdocs-material/
- **Current Docs Site**: https://CodeGraphContext.github.io/CodeGraphContext/

---

## 💡 Tips

- **MkDocs** uses relative paths from `docs/docs/` directory
- Use `../deployment/FILE.md` to reference files outside `docs/docs/`
- The React site links to GitHub for docs (see Footer.tsx)
- TypeScript errors in `website/` are normal without `npm install`
