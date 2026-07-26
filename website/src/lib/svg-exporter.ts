// SVG Exporter — reconstructs an SVG from live d3-force positions

export async function exportSvg(
  graphData: { nodes: any[], links: any[] },
  nodeColors: Record<string, string> = {},
  edgeColors: Record<string, string> = {},
  isDark: boolean = true
) {
  if (!graphData) return;

  const { nodes, links } = graphData;
  
  if (!nodes || nodes.length === 0) return;

  // Build a position map and compute bounding box
  let minX = Infinity, minY = Infinity, maxX = -Infinity, maxY = -Infinity;
  const posMap: Record<string, { x: number, y: number }> = {};
  
  nodes.forEach((node: any) => {
    if (typeof node.x === 'number' && typeof node.y === 'number') {
      const x = node.x;
      const y = node.y;
      posMap[node.id] = { x, y };
      if (x < minX) minX = x;
      if (y < minY) minY = y;
      if (x > maxX) maxX = x;
      if (y > maxY) maxY = y;
    }
  });

  const padding = 50;
  const width = (maxX - minX) + padding * 2;
  const height = (maxY - minY) + padding * 2;
  const bgColor = isDark ? '#020202' : '#f5f5f7';
  const textColor = isDark ? '#ffffff' : '#1a1a1a';

  // Collect unique edge colors
  const uniqueEdgeColors = new Set<string>();
  links.forEach((link: any) => {
    const color = edgeColors[link.type] || (isDark ? '#ffffff' : '#000000');
    uniqueEdgeColors.add(color);
  });

  // Build marker defs
  const markerDefs = Array.from(uniqueEdgeColors).map(color => {
    const id = 'arrow-' + color.replace('#', '');
    return `<marker id="${id}" viewBox="0 0 10 10" refX="9" refY="5"
      markerWidth="6" markerHeight="6" orient="auto-start-reverse">
      <path d="M 0 0 L 10 5 L 0 10 z" fill="${color}" opacity="0.6"/>
    </marker>`;
  }).join('\n');

  // Build SVG string
  const svgElements: string[] = [];
  
  // Draw edges first
  links.forEach((link: any) => {
    const sourceId = typeof link.source === 'object' ? link.source.id : link.source;
    const targetId = typeof link.target === 'object' ? link.target.id : link.target;
    
    const sourcePos = posMap[sourceId];
    const targetPos = posMap[targetId];
    
    if (sourcePos && targetPos) {
      const x1 = sourcePos.x - minX + padding;
      const y1 = sourcePos.y - minY + padding;
      const x2 = targetPos.x - minX + padding;
      const y2 = targetPos.y - minY + padding;
      
      const linkColor = edgeColors[link.type] || (isDark ? '#ffffff' : '#000000');
      const arrowId = 'arrow-' + linkColor.replace('#', '');
      
      svgElements.push(
        `<line x1="${x1}" y1="${y1}" x2="${x2}" y2="${y2}" stroke="${linkColor}" stroke-opacity="0.3" stroke-width="0.8" marker-end="url(#${arrowId})" />`
      );
    }
  });

  // Draw nodes on top
  nodes.forEach((node: any) => {
    const pos = posMap[node.id];
    if (pos) {
      const cx = pos.x - minX + padding;
      const cy = pos.y - minY + padding;
      const color = nodeColors[node.type] || nodeColors.Other || '#42a5f5';
      const N = nodes.length;
      const nScale = N > 3000 ? 0.3 : N > 1000 ? 0.5 : N > 400 ? 0.7 : 1.0;
      const r = Math.max(1.5, (node.val || 1) * 0.8 * 3.0 * nScale);
      
      svgElements.push(
        `<circle cx="${cx}" cy="${cy}" r="${r}" fill="${color}" stroke="${isDark ? '#000000' : '#ffffff'}" stroke-width="0.5" />`
      );
      
      if (node.name) {
        // Escape label text for XML safety
        const safeLabel = node.name
          .replace(/&/g, '&amp;')
          .replace(/</g, '&lt;')
          .replace(/>/g, '&gt;')
          .replace(/"/g, '&quot;')
          .replace(/'/g, '&apos;');
          
        const fontSize = Math.max(8, r * 1.5);
        svgElements.push(
          `<text x="${cx}" y="${cy + r + fontSize + 2}" font-family="Inter, ui-monospace, sans-serif" font-size="${fontSize}" fill="${textColor}" text-anchor="middle">${safeLabel}</text>`
        );
      }
    }
  });

  const svgString = `<?xml version="1.0" encoding="UTF-8" standalone="no"?>
<svg width="${width}" height="${height}" viewBox="0 0 ${width} ${height}" xmlns="http://www.w3.org/2000/svg" style="background-color: ${bgColor};">
  <defs>
    ${markerDefs}
  </defs>
  ${svgElements.join('\n  ')}
</svg>`;

  // Output as Blob and trigger download
  const blob = new Blob([svgString], { type: 'image/svg+xml' });
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = 'graph-export.svg';
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  URL.revokeObjectURL(url);
}
