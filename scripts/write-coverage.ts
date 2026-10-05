import{writeFile}from'node:fs/promises';import{coverage}from'../core/coverage.ts';
await writeFile('docs/coverage-matrix.md','# Coverage matrix\n\nStatuses describe this release only. INTEGRATED does not mean production-ready or complete offline SIH acceptance.\n\n| Capability | Status | Scope |\n|---|---|---|\n'+coverage.map(row=>'| '+row.join(' | ')+' |').join('\n')+'\n');
await writeFile('FEATURE_STATUS.json',JSON.stringify(coverage.map(([capability,status,limitations])=>({capability,status,limitations})),null,2)+'\n');
