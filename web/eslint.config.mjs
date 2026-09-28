import next from "eslint-config-next";

const config = [
  ...next,
  { ignores: [".next/**", "node_modules/**", "lib/api-types.ts", "playwright-report/**", "test-results/**"] },
];

export default config;
