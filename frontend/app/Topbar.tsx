"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

export default function Topbar() {
  const path = usePathname();
  const items = [{ href: "/intake", label: "입력" }];
  return (
    <header className="topbar">
      <div className="wrap">
        <Link className="brand" href="/">
          영양제 추천 엔진 <span>KDRI 2025</span>
        </Link>
        <nav>
          {items.map((it) => (
            <Link
              key={it.href}
              href={it.href}
              aria-current={path === it.href ? "page" : undefined}
            >
              {it.label}
            </Link>
          ))}
        </nav>
      </div>
    </header>
  );
}
