import Parser from 'web-tree-sitter';
import { SupportedLanguages, detectLanguage } from './config';
import { LANGUAGE_QUERIES } from './tree-sitter-queries';

export interface FileData {
  path: string;
  content: string;
}

export interface NodeData {
  id: string;
  label: string;
  type: 'file' | 'folder' | 'class' | 'function' | 'interface' | 'method';
  file: string;
}

export interface EdgeData {
  id: string;
  source: string;
  target: string;
  type: 'contains' | 'calls' | 'inherits';
}

export interface GraphData {
  nodes: NodeData[];
  edges: EdgeData[];
  files: Record<string, string>;
}

let parserInitialized = false;
let languageInstances: Partial<Record<SupportedLanguages, Parser.Language>> = {};

export async function processFiles(files: FileData[], progressCallback: (msg: string) => void): Promise<GraphData> {
  const nodes: NodeData[] = [];
  const edges: EdgeData[] = [];
  const fileMap: Record<string, string> = {};

  progressCallback('Initializing parser...');
  if (!parserInitialized) {
    await Parser.init({
      locateFile() {
        return '/tree-sitter.wasm';
      },
    });
    parserInitialized = true;
  }

  // MUST initialize parser after Parser.init finishes resolving!
  const parser = new Parser();

  const getLanguage = async (lang: SupportedLanguages) => {
    if (!languageInstances[lang]) {
      progressCallback(`Loading grammar for ${lang}...`);
      const url = `https://unpkg.com/tree-sitter-wasms@0.1.13/out/tree-sitter-${lang}.wasm`;
      try {
         languageInstances[lang] = await Parser.Language.load(url);
      } catch (e) {
          console.error("Failed to load grammar", url, e);
          return null;
      }
    }
    return languageInstances[lang]!;
  };

  const fileCount = files.length;
  let processed = 0;
  const dirs = new Set<string>();
  const unresolvedCalls: Array<{ source: string, targetName: string }> = [];

  for (const file of files) {
    fileMap[file.path] = file.content;
    // Create folder hierarchy (ENSURE folders and files exist even if lang not supported)
    const parts = file.path.split('/');
    let currentDir = "";
    for (let i = 0; i < parts.length - 1; i++) {
       const nextDir = currentDir ? currentDir + '/' + parts[i] : parts[i];
       if (!dirs.has(nextDir)) {
          nodes.push({ id: nextDir, label: parts[i], type: 'folder' as any, file: nextDir });
          if (currentDir) {
             edges.push({ id: `dir_contains_${currentDir}_${nextDir}`, source: currentDir, target: nextDir, type: 'contains' });
          }
          dirs.add(nextDir);
       }
       currentDir = nextDir;
    }

    // Create File Node
    nodes.push({ id: file.path, label: parts[parts.length - 1], type: 'file', file: file.path });

    // Connect folder to file
    if (currentDir) {
       edges.push({ id: `dir_contains_${currentDir}_${file.path}`, source: currentDir, target: file.path, type: 'contains' });
    }

    const lang = detectLanguage(file.path);
    if (!lang) {
      processed++;
      continue;
    }

    const language = await getLanguage(lang);
    if (!language) continue;

    parser.setLanguage(language);

    progressCallback(`Parsing ${Math.round((processed / fileCount) * 100)}%: ${file.path}`);
    const tree = parser.parse(file.content);
    
    // Execute built-in queries exactly like GitNexus
    const queryString = LANGUAGE_QUERIES[lang];
    if (queryString && language.query) {
      try {
        const query = language.query(queryString);
        const matches = query.matches(tree.rootNode);
        
        for (const match of matches) {
          // Identify if this is a definition
          const defCapture = match.captures.find(c => c.name.startsWith('definition.'));
          const nameCapture = match.captures.find(c => c.name === 'name');

          if (defCapture && nameCapture) {
            const defType = defCapture.name.split('.')[1] as NodeData['type'];
            const name = nameCapture.node.text;
            const nodeId = `${file.path}:${name}`;
            
            nodes.push({
              id: nodeId,
              label: name, // Short name!
              type: defType,
              file: file.path
            });

            edges.push({
              id: `${file.path}->${nodeId}`,
              source: file.path,
              target: nodeId,
              type: 'contains'
            });
          }
          
          // Identify if this is a call
          const callNameCapture = match.captures.find(c => c.name === 'call.name');

          if (callNameCapture) {
             const name = callNameCapture.node.text;
             unresolvedCalls.push({
               source: file.path, 
               targetName: name
             });
          }
        }
      } catch(e) {
        console.warn(`Query failed for ${file.path}: `, e);
      }
    }
    
    tree.delete();
    processed++;
  }

  // Resolve Calls (Cross-File or Same-File)
  const defMap = new Map<string, string>();
  for (const node of nodes) {
    if (['function', 'class', 'method'].includes(node.type)) {
      defMap.set(node.label, node.id);
    }
  }

  for (const call of unresolvedCalls) {
    const targetId = defMap.get(call.targetName);
    if (targetId) {
      edges.push({
         id: `call_${call.source}_to_${targetId}_${Math.random()}`,
         source: call.source,
         target: targetId,
         type: 'calls'
      });
    }
  }

  progressCallback('Graph constructed.');

  const validNodes = new Set(nodes.map(n => n.id));
  const validEdges = edges.filter(e => validNodes.has(e.source) && validNodes.has(e.target)); 

  return { nodes, edges: validEdges, files: fileMap };
}
