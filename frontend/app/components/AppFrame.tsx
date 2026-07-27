import { Sidebar } from "./Sidebar";

export function AppFrame({ children }: { children: React.ReactNode }) {
  return (
    <div className="app-frame">
      <Sidebar />
      <main className="workspace">{children}</main>
    </div>
  );
}
