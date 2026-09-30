import Link from "next/link";

const LINKS = [
  { href: "/about", label: "关于" },
  { href: "/changelog", label: "更新日志" },
  { href: "/feedback", label: "反馈" },
  { href: "/agent", label: "Agent 接入" },
];

/** 页脚：次要入口 + ICP 备案号（运行时读取 SITE_ICP，国内服务器绑定域名时需要展示）。 */
export function SiteFooter() {
  const icp = process.env.SITE_ICP;
  return (
    <footer className="mt-12 border-t border-line pt-5 text-xs text-muted">
      <nav aria-label="页脚" className="flex flex-wrap gap-x-4 gap-y-1">
        {LINKS.map((l) => (
          <Link key={l.href} href={l.href} className="hover:text-ink">
            {l.label}
          </Link>
        ))}
        <a href="/feed.xml" className="hover:text-ink">
          RSS
        </a>
      </nav>
      <p className="mt-2">
        内容由 AI 根据公开信息整理，金额、截止时间等关键信息请以原文为准。
        {icp ? (
          <>
            {" "}
            <a href="https://beian.miit.gov.cn/" target="_blank" rel="noopener noreferrer" className="hover:text-ink">
              {icp}
            </a>
          </>
        ) : null}
      </p>
    </footer>
  );
}
