import fs from 'node:fs';
import { addDebugNavigation } from '../src/lib/debug-navigation.mjs';

const file = process.argv[2] || 'dist/line-latest/index.html';
const html = fs.readFileSync(file, 'utf8');
fs.writeFileSync(file, addDebugNavigation(html));
console.log('Installed Debug tab immediately before Benchmark in LINE Latest.');
