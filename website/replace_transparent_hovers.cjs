const fs = require('fs');
const path = require('path');

const dir = 'd:/frontend/CodeGraphContext/website/src/components';

function processDirectory(directory) {
  const files = fs.readdirSync(directory);
  
  for (const file of files) {
    const fullPath = path.join(directory, file);
    const stat = fs.statSync(fullPath);
    
    if (stat.isDirectory()) {
      processDirectory(fullPath);
    } else if (file.endsWith('.tsx') || file.endsWith('.ts')) {
      let content = fs.readFileSync(fullPath, 'utf8');
      const original = content;
      
      // Transparent background hovers
      content = content.replace(/hover:bg-white\/5/g, 'hover:bg-purple-500/10');
      content = content.replace(/hover:bg-white\/10/g, 'hover:bg-purple-500/20');
      content = content.replace(/hover:bg-white\/20/g, 'hover:bg-purple-500/30');
      
      // Transparent border hovers
      content = content.replace(/hover:border-white\/10/g, 'hover:border-purple-500/20');
      content = content.replace(/hover:border-white\/20/g, 'hover:border-purple-500/30');
      content = content.replace(/hover:border-white\/30/g, 'hover:border-purple-500/40');
      content = content.replace(/hover:border-white\/40/g, 'hover:border-purple-500/50');
      
      // text-white -> cyan (for hover states on gray text)
      // Wait, let's not touch text-white on hover unless specifically requested because white text is good contrast.
      
      if (content !== original) {
        fs.writeFileSync(fullPath, content, 'utf8');
        console.log(`Updated transparent hovers in ${file}`);
      }
    }
  }
}

processDirectory(dir);
console.log('Done replacing transparent white hovers.');
