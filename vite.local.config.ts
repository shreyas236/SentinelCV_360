import {defineConfig} from 'vite';
import react from '@vitejs/plugin-react';
import tailwind from '@tailwindcss/postcss';
import {fileURLToPath} from 'node:url';
export default defineConfig({root:'local/frontend',plugins:[react()],publicDir:'../../public',resolve:{alias:{'@':fileURLToPath(new URL('.',import.meta.url))}},css:{postcss:{plugins:[tailwind()]}},server:{host:'127.0.0.1',port:5173,proxy:{'/api':'http://127.0.0.1:8000'}},build:{outDir:'../../offline-dist',emptyOutDir:true}});
