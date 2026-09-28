// 从后端 OpenAPI 生成前端类型：node scripts/gen-api.mjs
// 需要 server/ 的 uv 环境；不连数据库，只导出 schema。
import { execFileSync } from "node:child_process";
import { writeFileSync } from "node:fs";
import openapiTS, { astToString } from "openapi-typescript";

const spec = execFileSync(
  "uv",
  ["run", "python", "-c", "import json; from app.main import app; print(json.dumps(app.openapi()))"],
  { cwd: new URL("../../server", import.meta.url), encoding: "utf8", env: { ...process.env, VIRTUAL_ENV: "" } },
);
const ast = await openapiTS(JSON.parse(spec));
writeFileSync(
  new URL("../lib/api-types.ts", import.meta.url),
  "// 自动生成，请勿手改：npm run gen:api\n" + astToString(ast),
);
console.log("lib/api-types.ts 已更新");
