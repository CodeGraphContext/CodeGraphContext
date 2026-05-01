import { Parser, Language, Query } from "web-tree-sitter";
// Leverage Vite's asset pipeline to guarantee we receive the exact .wasm file that matches our NPM package version
import treeSitterWasmUrl from "web-tree-sitter/tree-sitter.wasm?url";

let parser: any = null;
let initPromise: Promise<void> | null = null;
const wasmLanguageCache = new Map<string, any>();

async function initParser() {
  if (parser) return;
  if (!initPromise) {
    initPromise = (async () => {
      await Parser.init({
        locateFile(scriptName: string) {
          if (scriptName.endsWith('tree-sitter.wasm')) {
            return treeSitterWasmUrl;
          }
          return `${location.origin}/wasm/${scriptName}`;
        }
      });
      parser = new Parser();
    })();
  }
  await initPromise;
}

async function getLanguageForFile(path: string) {
  if (!parser) await initParser();
  const extMatch = path.match(/\.([a-zA-Z0-9]+)$/);
  if (!extMatch) return null;
  const ext = extMatch[1].toLowerCase();
  
  let wasmName = '';
  switch(ext) {
    case 'py': wasmName = 'tree-sitter-python.wasm'; break;
    case 'js':
    case 'jsx': wasmName = 'tree-sitter-javascript.wasm'; break;
    case 'ts': wasmName = 'tree-sitter-typescript.wasm'; break; 
    case 'tsx': wasmName = 'tree-sitter-tsx.wasm'; break; 
    case 'java': wasmName = 'tree-sitter-java.wasm'; break;
    case 'c':
    case 'h': wasmName = 'tree-sitter-c.wasm'; break;
    case 'cpp':
    case 'hpp':
    case 'cc': wasmName = 'tree-sitter-cpp.wasm'; break;
    case 'cs': wasmName = 'tree-sitter-c_sharp.wasm'; break;
    case 'go': wasmName = 'tree-sitter-go.wasm'; break;
    case 'rs': wasmName = 'tree-sitter-rust.wasm'; break;
    case 'rb': wasmName = 'tree-sitter-ruby.wasm'; break;
    case 'php': wasmName = 'tree-sitter-php.wasm'; break;
    case 'swift': wasmName = 'tree-sitter-swift.wasm'; break;
    case 'kt':
    case 'kts': wasmName = 'tree-sitter-kotlin.wasm'; break;
    case 'dart': wasmName = 'tree-sitter-dart.wasm'; break;
    case 'pl':
    case 'pm': wasmName = 'tree-sitter-perl.wasm'; break;
    default: return null;
  }

  if (wasmLanguageCache.has(wasmName)) {
    return wasmLanguageCache.get(wasmName);
  }

  try {
    const response = await fetch(`${location.origin}/wasm/${wasmName}`);
    if (!response.ok) {
        console.warn(`Could not load tree-sitter language: ${wasmName}. Proceeding without it.`);
        return null;
    }
    const buffer = await response.arrayBuffer();
    const lang = await Language.load(new Uint8Array(buffer));
    wasmLanguageCache.set(wasmName, lang);
    return lang;
  } catch (err) {
    console.warn(`Could not load tree-sitter language: ${wasmName}. Proceeding without it.`, err);
    return null;
  }
}

// ---------------------------------------------------------------------------
// Language-specific S-expression query strings (Query API)
// Each language declares exactly what it wants — definitions, imports, calls.
// The grammar engine does the searching; we just describe the shape.
// ---------------------------------------------------------------------------

interface LangQueries {
  /** Captures @def.name (identifier) + @def.node (container) for each definition */
  definitions: string;
  /** Captures @import.module for each import */
  imports: string;
  /** Captures @call.name for each call site */
  calls: string;
  /** Captures @inherit.base for each base/parent class name */
  inherits: string;
}
const QUERIES: Record<string, LangQueries> = {
  python: {
    definitions: `
      (class_definition     name: (identifier) @def.name) @def.node
      (function_definition  name: (identifier) @def.name) @def.node
    `,
    imports: `
      (import_statement      (dotted_name (identifier) @import.module) )
      (import_from_statement module_name: (dotted_name (identifier) @import.module))
      (import_from_statement module_name: (relative_import
                                              (dotted_name (identifier) @import.module)))
    `,
    calls: `
      (call function: (identifier)          @call.name)
      (call function: (attribute attribute: (identifier) @call.name))
    `,
    inherits: `
      (class_definition
        superclasses: (argument_list
          [ (identifier) @inherit.base
            (attribute attribute: (identifier) @inherit.base) ]))
    `,
  },

  javascript: {
    definitions: `
      (function_declaration   name: (identifier) @def.name) @def.node
      (class_declaration      name: (identifier) @def.name) @def.node
      (method_definition      name: (property_identifier) @def.name) @def.node
      (lexical_declaration
        (variable_declarator  name: (identifier) @def.name
                              value: [(function_expression)(arrow_function)] @def.node))
    `,
    imports: `
      (import_statement source: (string (string_fragment) @import.module))
      (call_expression
        function: (identifier) @_req (#eq? @_req "require")
        arguments: (arguments (string (string_fragment) @import.module)))
    `,
    calls: `
      (call_expression function: (identifier)           @call.name)
      (call_expression function: (member_expression
                         property: (property_identifier) @call.name))
      (new_expression  constructor: (identifier)        @call.name)
    `,
    inherits: ``,
  },

  typescript: {
    definitions: `
      (function_declaration   name: (identifier) @def.name) @def.node
      (class_declaration      name: (type_identifier) @def.name) @def.node
      (method_definition      name: (property_identifier) @def.name) @def.node
      (interface_declaration  name: (type_identifier) @def.name) @def.node
      (enum_declaration       name: (identifier) @def.name) @def.node
      (lexical_declaration
        (variable_declarator  name: (identifier) @def.name
                              value: [(function_expression)(arrow_function)] @def.node))
    `,
    imports: `
      (import_statement source: (string (string_fragment) @import.module))
      (call_expression
        function: (identifier) @_req (#eq? @_req "require")
        arguments: (arguments (string (string_fragment) @import.module)))
    `,
    calls: `
      (call_expression function: (identifier)                 @call.name)
      (call_expression function: (member_expression
                         property: (property_identifier)       @call.name))
      (new_expression  constructor: (identifier)              @call.name)
      (new_expression  constructor: (member_expression
                         property: (property_identifier)       @call.name))
    `,
    inherits: ``,
  },

  java: {
    definitions: `
      (class_declaration      name: (identifier) @def.name) @def.node
      (interface_declaration  name: (identifier) @def.name) @def.node
      (enum_declaration       name: (identifier) @def.name) @def.node
      (method_declaration     name: (identifier) @def.name) @def.node
    `,
    imports: `
      (import_declaration (scoped_identifier (identifier) @import.module))
    `,
    calls: `
      (method_invocation name: (identifier) @call.name)
      (object_creation_expression type: (type_identifier) @call.name)
    `,
    inherits: `
      (class_declaration
        (superclass (type_identifier) @inherit.base))
      (class_declaration
        (super_interfaces (type_list (type_identifier) @inherit.base)))
      (interface_declaration
        (extends_interfaces (type_list (type_identifier) @inherit.base)))
    `,
  },


  c: {
    definitions: `
      (function_definition declarator:
        (function_declarator declarator: (identifier) @def.name)) @def.node
      (struct_specifier name: (type_identifier) @def.name) @def.node
      (enum_specifier   name: (type_identifier) @def.name) @def.node
    `,
    imports: `
      (preproc_include path: [(string_literal) (system_lib_string)] @import.module)
    `,
    calls: `
      (call_expression function: (identifier) @call.name)
    `,
    inherits: ``,
  },

  cpp: {
    definitions: `
      (function_definition declarator:
        (function_declarator declarator:
          [(identifier)(qualified_identifier)] @def.name)) @def.node
      (class_specifier  name: (type_identifier) @def.name) @def.node
      (struct_specifier name: (type_identifier) @def.name) @def.node
      (enum_specifier   name: (type_identifier) @def.name) @def.node
    `,
    imports: `
      (preproc_include path: [(string_literal)(system_lib_string)] @import.module)
    `,
    calls: `
      (call_expression function:
        [(identifier) @call.name
         (field_expression field: (field_identifier) @call.name)
         (qualified_identifier name: (identifier) @call.name)
        ])
    `,
    inherits: `
      (class_specifier
        (base_class_clause
          (type_identifier) @inherit.base))
    `,
  },

  go: {
    definitions: `
      (function_declaration  name: (identifier) @def.name) @def.node
      (method_declaration    name: (field_identifier) @def.name) @def.node
      (type_declaration (type_spec name: (type_identifier) @def.name)) @def.node
    `,
    imports: `
      (import_spec path: (interpreted_string_literal) @import.module)
    `,
    calls: `
      (call_expression function: (identifier)        @call.name)
      (call_expression function: (selector_expression
                         field: (field_identifier)   @call.name))
    `,
    inherits: ``,
  },

  rust: {
    definitions: `
      (function_item  name: (identifier) @def.name) @def.node
      (struct_item    name: (type_identifier) @def.name) @def.node
      (enum_item      name: (type_identifier) @def.name) @def.node
      (trait_item     name: (type_identifier) @def.name) @def.node
      (impl_item      type: (type_identifier) @def.name) @def.node
    `,
    imports: `
      (use_declaration argument: (scoped_identifier name: (identifier) @import.module))
      (use_declaration argument: (identifier) @import.module)
    `,
    calls: `
      (call_expression function:
        [(identifier) @call.name
         (field_expression field: (field_identifier) @call.name)
         (scoped_identifier name: (identifier) @call.name)
        ])
    `,
    inherits: ``,
  },

  ruby: {
    definitions: `
      (class  name: (constant) @def.name) @def.node
      (module name: (constant) @def.name) @def.node
      (method name: (identifier) @def.name) @def.node
      (singleton_method name: (identifier) @def.name) @def.node
    `,
    imports: `
      (call method: (identifier) @_req
            (#match? @_req "^(require|require_relative|load)$")
            arguments: (argument_list (string (string_content) @import.module)))
    `,
    calls: `
      (call method: (identifier) @call.name)
    `,
    inherits: `
      (class (superclass (constant) @inherit.base))
    `,
  },

  php: {
    definitions: `
      (class_declaration     name: (name) @def.name) @def.node
      (interface_declaration name: (name) @def.name) @def.node
      (function_definition   name: (name) @def.name) @def.node
      (method_declaration    name: (name) @def.name) @def.node
    `,
    imports: `
      (include_expression (string) @import.module)
      (require_expression (string) @import.module)
      (include_once_expression (string) @import.module)
      (require_once_expression (string) @import.module)
    `,
    calls: `
      (function_call_expression function: (name) @call.name)
      (member_call_expression   name: (name) @call.name)
    `,
    inherits: `
      (class_declaration (base_clause (name) @inherit.base))
    `,
  },

  kotlin: {
    definitions: `
      (class_declaration    (type_identifier) @def.name) @def.node
      (object_declaration   (type_identifier) @def.name) @def.node
      (function_declaration (simple_identifier) @def.name) @def.node
    `,
    imports: `
      (import_header (identifier) @import.module)
    `,
    calls: `
      (call_expression (simple_identifier) @call.name)
      (call_expression
        (navigation_expression
          (navigation_suffix (simple_identifier) @call.name)))
    `,
    inherits: `
      (class_declaration
        (delegation_specifier
          (user_type (type_identifier) @inherit.base)))
    `,
  },

  dart: {
    definitions: `
      (class_definition  name: (identifier) @def.name) @def.node
      (mixin_declaration name: (identifier) @def.name) @def.node
    `,
    imports: ``,
    calls: ``,
    inherits: ``,
  },

  csharp: {
    definitions: `
      (class_declaration       name: (identifier) @def.name) @def.node
      (interface_declaration   name: (identifier) @def.name) @def.node
      (struct_declaration      name: (identifier) @def.name) @def.node
      (enum_declaration        name: (identifier) @def.name) @def.node
      (method_declaration      name: (identifier) @def.name) @def.node
      (constructor_declaration name: (identifier) @def.name) @def.node
    `,
    imports: `
      (using_directive (identifier) @import.module)
      (using_directive (qualified_name (identifier) @import.module))
    `,
    calls: `
      (invocation_expression function: (identifier) @call.name)
      (invocation_expression
        function: (member_access_expression name: (identifier) @call.name))
      (object_creation_expression type: (identifier) @call.name)
    `,
    inherits: `
      (class_declaration     (base_list (identifier) @inherit.base))
      (interface_declaration (base_list (identifier) @inherit.base))
    `,
  },

  swift: {
    definitions: `
      (class_declaration    name: (type_identifier) @def.name) @def.node
      (protocol_declaration name: (type_identifier) @def.name) @def.node
      (function_declaration name: (simple_identifier) @def.name) @def.node
    `,
    imports: `
      (import_declaration (identifier) @import.module)
    `,
    calls: `
      (call_expression (simple_identifier) @call.name)
    `,
    inherits: ``,
  },

  perl: {
    definitions: `
      (subroutine (identifier) @def.name) @def.node
    `,
    imports: `
      (use_statement (package) @import.module)
      (require_expression (string) @import.module)
    `,
    calls: `
      (call_expression (identifier) @call.name)
    `,
    inherits: ``,
  },
};

// Map file extension → query key
function getLanguageQueryKey(path: string): string | null {
  const ext = path.match(/\.([a-zA-Z0-9]+)$/)?.[1]?.toLowerCase();
  switch (ext) {
    case 'py':                          return 'python';
    case 'js': case 'jsx':              return 'javascript';
    case 'ts': case 'tsx':              return 'typescript';
    case 'java':                        return 'java';
    case 'c':  case 'h':               return 'c';
    case 'cpp': case 'hpp': case 'cc': return 'cpp';
    case 'go':                          return 'go';
    case 'rs':                          return 'rust';
    case 'rb':                          return 'ruby';
    case 'php':                         return 'php';
    case 'kt': case 'kts':             return 'kotlin';
    case 'dart':                        return 'dart';
    case 'cs':                          return 'csharp';
    case 'swift':                       return 'swift';
    case 'pl': case 'pm':              return 'perl';
    default: return null;
  }
}

// Label a definition node type as Class / Function / Interface / etc.
function getNodeDisplayLabel(nodeType: string): string {
  if (nodeType.includes('class')) return 'Class';
  if (nodeType.includes('interface')) return 'Interface';
  if (nodeType.includes('trait')) return 'Trait';
  if (nodeType.includes('enum')) return 'Enum';
  if (nodeType.includes('module')) return 'Module';
  if (nodeType.includes('struct')) return 'Class'; // treat struct as class-like
  if (nodeType.includes('impl')) return 'Class';
  return 'Function';
}

function valForLabel(label: string): number {
  switch (label) {
    case 'Class': case 'Interface': case 'Trait': return 8;
    case 'Enum': return 7;
    case 'Module': return 9;
    default: return 6;
  }
}

// Per-language query cache (compiled Query objects are reusable)
const compiledQueryCache = new Map<string, Record<string, Query | null>>();

function getCompiledQueries(lang: any, queryKey: string): Record<string, Query | null> {
  if (compiledQueryCache.has(queryKey)) return compiledQueryCache.get(queryKey)!;
  const spec = QUERIES[queryKey];
  const compiled: Record<string, Query | null> = {};
  for (const [k, src] of Object.entries(spec)) {
    if (!src.trim()) { compiled[k] = null; continue; }
    try {
      compiled[k] = new Query(lang, src);
    } catch (e) {
      console.warn(`[parser.worker] Query compile error [${queryKey}:${k}]:`, e);
      compiled[k] = null;
    }
  }
  compiledQueryCache.set(queryKey, compiled);
  return compiled;
}

// ---------------------------------------------------------------------------
// State
// ---------------------------------------------------------------------------

const pendingFileQueue: { path: string, content: string }[] = [];
let totalFiles = 0;
let processedCount = 0;

const nodes: any[] = [];
const links: any[] = [];
const nodeSymbolIndex = new Map<string, number[]>(); 
const filePathToNodeId = new Map<string, number>();
const folderNodes = new Map<string, number>(); // relative folder path → node id
const fileCalls = new Map<number, Set<string>>();
const inheritances = new Map<number, string[]>();
let nodeIdSequence = 1;
let repoId = -1;
let repoRootPrefix = ''; // common path prefix stripped before building folder hierarchy

/**
 * Compute the longest common directory prefix of all queued file paths.
 * e.g. ["/home/user/proj/src/a.ts", "/home/user/proj/lib/b.ts"]
 *   → "/home/user/proj"
 */
function computeCommonPrefix(paths: string[]): string {
  if (paths.length === 0) return '';
  const dirs = paths.map(p => {
    const norm = p.replace(/\\/g, '/');
    return norm.substring(0, norm.lastIndexOf('/'));
  });
  const first = dirs[0].split('/');
  let common = first;
  for (let i = 1; i < dirs.length; i++) {
    const parts = dirs[i].split('/');
    const newCommon: string[] = [];
    for (let j = 0; j < Math.min(common.length, parts.length); j++) {
      if (common[j] === parts[j]) newCommon.push(common[j]);
      else break;
    }
    common = newCommon;
  }
  return common.join('/');
}

/**
 * Lazily create (or return cached) Folder nodes for the repo-relative segments only.
 * Returns the id of the immediate-parent folder for the given file path.
 * With repoRootPrefix = "/home/user/proj":
 *   "/home/user/proj/src/lib/foo.ts" → creates "src" node, then "src/lib" node
 *   and returns the id of "src/lib".
 */
function getOrCreateFolderChain(filePath: string): number {
  const norm = filePath.replace(/\\/g, '/');
  // Strip the common prefix to get the repo-relative path
  const relative = repoRootPrefix && norm.startsWith(repoRootPrefix)
    ? norm.slice(repoRootPrefix.length).replace(/^\//, '')
    : norm.replace(/^\//, '');

  // Drop the filename, keep only the directory segments
  const dirPart = relative.substring(0, relative.lastIndexOf('/'));
  if (!dirPart) return repoId; // file sits at the repo root — attach directly

  const parts = dirPart.split('/').filter(Boolean);
  let parentId = repoId;
  let accumulated = '';

  for (const part of parts) {
    accumulated = accumulated ? `${accumulated}/${part}` : part;
    if (folderNodes.has(accumulated)) {
      parentId = folderNodes.get(accumulated)!;
    } else {
      const folderId = addNode(part, 'Folder', accumulated, 12);
      links.push({ source: parentId, target: folderId, type: 'CONTAINS' });
      folderNodes.set(accumulated, folderId);
      parentId = folderId;
    }
  }

  return parentId;
}

self.onmessage = async (e) => {
  const { type, files } = e.data;
  
  if (type === 'ADD_FILES') {
    pendingFileQueue.push(...files);
    totalFiles += files.length;
  } else if (type === 'START') {
    try {
      await initParser();
      // Compute common path prefix BEFORE building any nodes, so folder
      // nodes only represent repo-relative segments (e.g. "src", "lib").
      repoRootPrefix = computeCommonPrefix(pendingFileQueue.map(f => f.path));
      repoId = addNode("Repository", "Repository", "root", 15);
      processNextBatch();
    } catch (err: any) {
      self.postMessage({ type: 'ERROR', payload: err.message });
    }
  }
};

const addNode = (name: string, type: string, file: string, val: number, extraProps: any = {}) => {
  const id = nodeIdSequence++;
  nodes.push({ id, name, type, file, val, ...extraProps });
  const symbolKey = `${type}:${name}`;
  if (!nodeSymbolIndex.has(symbolKey)) nodeSymbolIndex.set(symbolKey, []);
  nodeSymbolIndex.get(symbolKey)!.push(id);
  if (!nodeSymbolIndex.has(name)) nodeSymbolIndex.set(name, []);
  nodeSymbolIndex.get(name)!.push(id);
  return id;
};

/**
 * Resolve a symbol name to a single node ID, preferring candidates
 * from the same file as the caller to avoid cross-file collisions.
 */
function resolveSymbol(key: string, callerFile?: string): number | undefined {
  const candidates = nodeSymbolIndex.get(key);
  if (!candidates?.length) return undefined;
  if (candidates.length === 1) return candidates[0];
  if (callerFile) {
    const sameFile = candidates.find(id => nodes[id - 1]?.file === callerFile);
    if (sameFile !== undefined) return sameFile;
  }
  return candidates[0];
}

async function processNextBatch() {
  if (pendingFileQueue.length === 0) {
    // Cross-linking phase
    self.postMessage({ type: 'PROGRESS', payload: { msg: "Building high-fidelity relationships...", percent: 95 } });
    await new Promise(r => setTimeout(r, 0));
    
    const MAX_CALL_EDGES = 50000;
    let callsAdded = 0;
    for (const [callerId, calls] of fileCalls.entries()) {
       if (callsAdded >= MAX_CALL_EDGES) break;
       const callerFile = nodes[callerId - 1]?.file;
       for (const calledName of calls) {
          const targetId = resolveSymbol(`Function:${calledName}`, callerFile) || 
                           resolveSymbol(`Class:${calledName}`, callerFile) || 
                           resolveSymbol(calledName, callerFile);
          if (targetId && targetId !== callerId) {
             links.push({ source: callerId, target: targetId, type: 'CALLS' });
             callsAdded++;
             if (callsAdded >= MAX_CALL_EDGES) break;
          }
       }
    }
    for (const [classId, bases] of inheritances.entries()) {
       const classFile = nodes[classId - 1]?.file;
       for (const baseName of bases) {
          const targetId = resolveSymbol(`Class:${baseName}`, classFile) || resolveSymbol(baseName, classFile);
          if (targetId) links.push({ source: classId, target: targetId, type: 'INHERITS' });
       }
    }
    
    const pm = (performance as any).memory;
    if (pm) {
      console.log(`[Worker RAM Pre-PostMessage] ${(pm.usedJSHeapSize / 1048576).toFixed(1)} MB used.`);
    }

    self.postMessage({ type: 'PROGRESS', payload: { msg: "Indexing complete! Transferring structures to UI...", percent: 100 } });
    const filePaths = Array.from(filePathToNodeId.keys());
    self.postMessage({ type: 'DONE', payload: { nodes, links, files: filePaths } });
    return;
  }
  
  // Smaller batch = less peak memory per tick; GC gets more breathing room
  const batch = pendingFileQueue.splice(0, 10);
  
  for (let i = 0; i < batch.length; i++) {
    const f = batch[i];
    processedCount++;
    
    if (processedCount % 5 === 0) {
      const pm = (performance as any).memory;
      const memStr = pm ? ` [RAM: ${(pm.usedJSHeapSize / 1048576).toFixed(1)}MB]` : "";
      self.postMessage({ 
        type: 'PROGRESS', 
        payload: { 
          msg: `Indexing: ${f.path.split('/').pop()}${memStr}...`, 
          percent: 50 + Math.floor((processedCount / totalFiles) * 40) 
        } 
      });
    }

    const IGNORED_DIRS = new Set([
      'node_modules', '.git', '.github', 'dist', 'build', 'out', 'coverage', 
      '.next', '.nuxt', '__pycache__', 'venv', '.venv', 'env', '.env', '.tox',
      'eggs', 'target', '.gradle', '.idea', 'cmake-build-debug', 'bin', 'obj',
      'packages', 'vendor', 'Pods', '.build', 'DerivedData', '.dart_tool',
      '.vscode'
    ]);
    const isPathIgnored = f.path.split(/[\/\\]/).some(part => IGNORED_DIRS.has(part));

    // Skip large files and cache directories; tighter limit now we parse more languages
    if (f.content.length > 200000 || isPathIgnored) continue;

    // Memory pressure guard: if heap > 900 MB yield an extra tick to let GC run
    const pm2 = (performance as any).memory;
    if (pm2 && pm2.usedJSHeapSize > 900 * 1048576) {
      await new Promise(r => setTimeout(r, 0));
    }
    
    const lang = await getLanguageForFile(f.path);
    if (!lang) continue;

    const queryKey = getLanguageQueryKey(f.path);
    if (!queryKey) continue;
    
    parser!.setLanguage(lang);
    let tree: any;
    try {
      const src = f.content;
      f.content = ''; // Free raw file string from closure/batch immediately before AST creates thousands of slices
      tree = parser!.parse(src);

      const root = tree.rootNode;
      const fileName = f.path.split('/').pop() || f.path;
      const fileId = addNode(fileName, 'File', f.path, 10);
      filePathToNodeId.set(f.path, fileId);
      const parentFolderId = getOrCreateFolderChain(f.path);
      links.push({ source: parentFolderId, target: fileId, type: 'CONTAINS' });

      // Compile (or retrieve cached) query objects for this language
      const queries = getCompiledQueries(lang, queryKey);

      // 1. DEFINITIONS
      if (queries.definitions) {
        const defCaptures = queries.definitions.captures(root);
        const nodeToName = new Map<number, string>();
        const nodeToMeta = new Map<number, any>();

        for (const cap of defCaptures) {
          const nodeId = cap.node.id;
          if (cap.name === 'def.node') {
            if (!nodeToMeta.has(nodeId)) {
              nodeToMeta.set(nodeId, { node: cap.node, nodeType: cap.node.type });
            }
          } else if (cap.name === 'def.name') {
            let cur: any = cap.node.parent;
            while (cur) {
              if (nodeToMeta.has(cur.id)) {
                nodeToName.set(cur.id, cap.node.text);
                break;
              }
              cur = cur.parent;
            }
          }
        }

        for (const [nodeId, meta] of nodeToMeta) {
          const name = nodeToName.get(nodeId);
          if (!name || name.length <= 1) continue;
          const label = getNodeDisplayLabel(meta.nodeType);
          const val   = valForLabel(label);
          const defId = addNode(name, label, f.path, val, { line_number: meta.node.startPosition.row + 1 });
          links.push({ source: fileId, target: defId, type: 'CONTAINS' });
        }
      }

      // 2. IMPORTS
      if (queries.imports) {
        const seen = new Set<string>();
        for (const cap of queries.imports.captures(root)) {
          if (cap.name !== 'import.module') continue;
          let modName = cap.node.text.replace(/['"]/g, '').trim();
          if (!modName || seen.has(modName)) continue;
          seen.add(modName);
          const shortName = modName.split(/[/\\.]/).filter(Boolean).pop() ?? modName;
          const modId = addNode(shortName, 'Module', f.path, 5);
          links.push({ source: fileId, target: modId, type: 'IMPORTS' });
        }
      }

      // 3. CALLS
      if (queries.calls) {
        const SKIP_CALLS = new Set(['if', 'for', 'while', 'print', 'console', 'log', 'with', 'super']);
        for (const cap of queries.calls.captures(root)) {
          if (cap.name !== 'call.name') continue;
          const calledName = cap.node.text;
          if (!calledName || calledName.length <= 1 || SKIP_CALLS.has(calledName)) continue;
          fileCalls.set(fileId, (fileCalls.get(fileId) || new Set()).add(calledName));
        }
      }

      // 4. INHERITANCE
      if (queries.inherits) {
        const inheritCaptures = queries.inherits.captures(root);
        for (const cap of inheritCaptures) {
          if (cap.name !== 'inherit.base') continue;
          const baseName = cap.node.text;
          if (!baseName) continue;
          let cur: any = cap.node.parent;
          let classNodeId: number | undefined;
          while (cur) {
            if (cur.type.includes('class') || cur.type.includes('interface')) {
              const nameNode = cur.children?.find((c: any) =>
                ['identifier', 'type_identifier', 'name', 'constant'].includes(c.type));
              if (nameNode) {
                classNodeId = resolveSymbol(`Class:${nameNode.text}`, f.path) ??
                              resolveSymbol(`Interface:${nameNode.text}`, f.path);
              }
              break;
            }
            cur = cur.parent;
          }
          if (classNodeId !== undefined) {
            const prev = inheritances.get(classNodeId) ?? [];
            if (!prev.includes(baseName)) prev.push(baseName);
            inheritances.set(classNodeId, prev);
          }
        }
      }
    } catch (e) {
      console.warn(`[parser.worker] Failed parsing or executing queries on ${f.path}:`, e);
    } finally {
      if (tree) {
        try { tree.delete(); } catch(e) {}
      }
    }
  }
  
  // Yield to worker event loop
  setTimeout(processNextBatch, 0);
}
