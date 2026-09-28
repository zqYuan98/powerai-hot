import Link from "next/link";

import { Empty } from "@/components/ui";

export default function NotFound() {
  return (
    <Empty title="找不到这个页面">
      <Link href="/" className="text-accent hover:underline">
        回到精选
      </Link>
    </Empty>
  );
}
