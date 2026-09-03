/** @type {import('next').NextConfig} */
const nextConfig = {
  // Empacota o servidor com apenas as dependências que o build realmente usa,
  // num diretório .next/standalone que roda com `node server.js`. Sem isto, a
  // imagem precisaria carregar node_modules inteiro (286 MB) para servir um
  // site que usa três pacotes.
  output: "standalone",
};

module.exports = nextConfig;
