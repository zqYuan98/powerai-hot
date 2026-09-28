import { TabLinks } from "@/components/ui";
import { CHANNELS } from "@/lib/format";
import type { Meta } from "@/lib/types";

/** 频道标签，带今日精选条数。base 为当前页路径，extra 为需要保留的其他参数。 */
export function ChannelTabs({
  base,
  active,
  meta,
  extra = {},
}: {
  base: string;
  active: string;
  meta?: Meta;
  extra?: Record<string, string>;
}) {
  const today = Object.fromEntries((meta?.channels ?? []).map((c) => [c.channel, c.today]));
  const href = (channel?: string) => {
    const sp = new URLSearchParams({ ...extra, ...(channel ? { channel } : {}) });
    const s = sp.toString();
    return s ? `${base}?${s}` : base;
  };
  return (
    <TabLinks
      active={active}
      tabs={[
        { key: "", href: href(), label: "全部" },
        ...CHANNELS.map((c) => ({
          key: c.value,
          href: href(c.value),
          label: (
            <>
              {c.label}
              {today[c.value] ? <span className="ml-1 text-[11px] opacity-60">{today[c.value]}</span> : null}
            </>
          ),
        })),
      ]}
    />
  );
}
