const fs = require('fs');
const path = require('path');

const distDir = path.join(__dirname, 'dist');
const rendererDist = path.join(__dirname, 'dist', 'renderer');
const fallbackSrc = path.join(__dirname, 'src', 'index.html');

// Create dist directory if it doesn't exist
if (!fs.existsSync(distDir)) {
  fs.mkdirSync(distDir, { recursive: true });
}

function copyRecursive(src, dest) {
  const stat = fs.statSync(src);
  if (stat.isDirectory()) {
    if (!fs.existsSync(dest)) fs.mkdirSync(dest);
    for (const item of fs.readdirSync(src)) {
      copyRecursive(path.join(src, item), path.join(dest, item));
    }
  } else {
    fs.copyFileSync(src, dest);
  }
}

// If a renderer build exists at dist/renderer, copy it into dist/
if (fs.existsSync(rendererDist)) {
  console.log(`Found renderer build at ${rendererDist}, copying to ${distDir}...`);
  copyRecursive(rendererDist, distDir);
  console.log('Renderer build copied to dist/');
} else if (fs.existsSync(fallbackSrc)) {
  // Fallback for simple projects: copy the static src/index.html
  const distFile = path.join(distDir, 'index.html');
  fs.copyFileSync(fallbackSrc, distFile);
  console.log(`Copied ${fallbackSrc} to ${distFile}`);
} else {
  console.warn('No renderer build found and no src/index.html fallback available.');
}