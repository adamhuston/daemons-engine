const fs = require('fs');
const path = require('path');

const srcFile = path.join(__dirname, 'src', 'index.html');
const distDir = path.join(__dirname, 'dist');
const distFile = path.join(distDir, 'index.html');

// Create dist directory if it doesn't exist
if (!fs.existsSync(distDir)) {
  fs.mkdirSync(distDir, { recursive: true });
}

// Copy the file
fs.copyFileSync(srcFile, distFile);
console.log(`Copied ${srcFile} to ${distFile}`);