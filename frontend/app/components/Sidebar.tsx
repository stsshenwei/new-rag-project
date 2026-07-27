"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { LibraryIcon, NewChatIcon } from "./Icons";

export function Sidebar() {
  const pathname = usePathname();
  const router = useRouter();

  function handleNewChat() {
    window.dispatchEvent(new Event("bee:new-chat"));
    router.push("/chat");
  }

  return (
    <aside className="sidebar">
      <Link href="/chat" className="sidebar-brand" aria-label="Bee 首页">
        <span className="brand-mark">B</span>
        <span>
          <strong>Bee</strong>
        </span>
      </Link>

      <button type="button" className="new-thread" onClick={handleNewChat}>
        <NewChatIcon />
        新对话
      </button>

      <p className="sidebar-section-label">工作台</p>
      <nav className="sidebar-nav" aria-label="主导航">
        <button type="button" onClick={() => router.push("/chat")} className={pathname === "/chat" ? "active" : ""}>
          <NewChatIcon />
          <span>对话</span>
        </button>
        <button type="button" onClick={() => router.push("/knowledge")} className={pathname === "/knowledge" ? "active" : ""}>
          <LibraryIcon />
          <span>知识库</span>
        </button>
      </nav>
    </aside>
  );
}
