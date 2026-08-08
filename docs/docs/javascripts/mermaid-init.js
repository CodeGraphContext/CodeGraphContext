// docs/docs/javascripts/mermaid-init.js

document.addEventListener("DOMContentLoaded", function() {
  if (typeof mermaid !== "undefined") {
    // 1. Find and transform all code-wrapped mermaid blocks into plain div.mermaid tags
    const blocks = document.querySelectorAll('pre.mermaid, pre code.language-mermaid');
    const processed = new Set();

    blocks.forEach(el => {
      let targetEl = el;
      // If we are looking at the code block inside a pre, target the pre
      if (el.tagName.toLowerCase() === 'code' && el.parentNode.tagName.toLowerCase() === 'pre') {
        targetEl = el.parentNode;
      }
      
      if (processed.has(targetEl)) return;
      processed.add(targetEl);

      const codeEl = targetEl.querySelector('code') || targetEl;
      const diagramText = codeEl.textContent.trim();

      const container = document.createElement('div');
      container.className = 'mermaid';
      container.textContent = diagramText;

      targetEl.parentNode.replaceChild(container, targetEl);
    });

    // 2. Initialize and run Mermaid
    const isDarkMode = document.documentElement.getAttribute('data-theme') === 'dark' ||
                       document.body.getAttribute('data-md-color-scheme') === 'dark';
    
    mermaid.initialize({
      startOnLoad: false,
      theme: isDarkMode ? 'dark' : 'default',
      securityLevel: 'loose',
      themeVariables: {
        fontSize: '13px',
        fontFamily: 'Inter, Outfit, sans-serif'
      }
    });

    // Run the parser on our normalized div elements
    mermaid.run();
  }
});
