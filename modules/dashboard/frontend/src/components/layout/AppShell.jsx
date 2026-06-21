import { useEffect, useState } from "react";
import { Link, NavLink, useLocation, useNavigate, Outlet } from "react-router-dom";
import {
  LayoutDashboard, ShieldAlert, Boxes, BarChart3, Bot, FileText,
  Bell, Settings, Menu, Sun, Moon, ChevronsLeft, ChevronsRight,
  LogOut, User, Command, CircleHelp, Search, Cloud,
} from "lucide-react";
import { cn } from "../../lib/utils";
import { useTheme } from "../../lib/theme";
import { useData } from "../../lib/data";
import { useTour } from "../../lib/tour";
import { Avatar, Badge, Dropdown, DropdownItem, Separator } from "../ui";
import CommandPalette from "./CommandPalette";

function buildNav(metrics, unread) {
  const crit = metrics?.kpis?.find((k) => k.id === "critical")?.value;
  return [
    { section: "Overview", items: [
      { to: "/app", label: "Dashboard", icon: LayoutDashboard, end: true },
      { to: "/app/findings", label: "Risk Findings", icon: ShieldAlert, badge: crit ? String(crit) : null },
      { to: "/app/resources", label: "Resource Explorer", icon: Boxes },
      { to: "/app/analytics", label: "Analytics", icon: BarChart3 },
    ]},
    { section: "Intelligence", items: [
      { to: "/app/chat", label: "AI Risk Analyst", icon: Bot, pill: "AI" },
      { to: "/app/reports", label: "Reports", icon: FileText },
    ]},
    { section: "Workspace", items: [
      { to: "/app/notifications", label: "Notifications", icon: Bell, badge: unread ? String(unread) : null },
      { to: "/app/settings", label: "Settings", icon: Settings },
    ]},
  ];
}

function Logo({ collapsed }) {
  return (
    <Link to="/app" className="flex items-center gap-2.5 px-1">
      <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-btn bg-primary text-primary-foreground shadow-sm">
        <Cloud className="h-5 w-5" />
      </div>
      {!collapsed && (
        <div className="leading-tight">
          <div className="text-[15px] font-bold tracking-tight">EphemeraLens</div>
          <div className="text-[10px] font-medium uppercase tracking-wider text-muted-foreground">Cloud &amp; K8s Risk</div>
        </div>
      )}
    </Link>
  );
}

function Sidebar({ nav, collapsed, setCollapsed, mobileOpen, setMobileOpen }) {
  return (
    <>
      {mobileOpen && <div className="fixed inset-0 z-40 bg-black/40 lg:hidden" onClick={() => setMobileOpen(false)} />}
      <aside
        className={cn(
          "fixed inset-y-0 left-0 z-50 flex flex-col border-r border-border bg-card transition-all duration-200 lg:static lg:translate-x-0",
          collapsed ? "w-[72px]" : "w-64",
          mobileOpen ? "translate-x-0" : "-translate-x-full"
        )}
      >
        <div className="flex h-16 items-center justify-between px-3">
          <Logo collapsed={collapsed} />
        </div>
        <nav className="flex-1 space-y-5 overflow-y-auto scrollbar-thin px-3 py-2">
          {nav.map((group) => (
            <div key={group.section}>
              {!collapsed && (
                <div className="mb-1 px-2 text-[10px] font-semibold uppercase tracking-wider text-muted-foreground">
                  {group.section}
                </div>
              )}
              <div className="space-y-0.5">
                {group.items.map((item) => (
                  <NavLink
                    key={item.to}
                    to={item.to}
                    end={item.end}
                    onClick={() => setMobileOpen(false)}
                    title={collapsed ? item.label : undefined}
                    className={({ isActive }) =>
                      cn(
                        "group relative flex items-center gap-3 rounded-btn px-2.5 py-2 text-sm font-medium transition-colors",
                        isActive ? "bg-primary/10 text-primary" : "text-muted-foreground hover:bg-muted hover:text-foreground"
                      )
                    }
                  >
                    {({ isActive }) => (
                      <>
                        {isActive && <span className="absolute left-0 top-1/2 h-5 w-0.5 -translate-y-1/2 rounded-r-full bg-primary" />}
                        <item.icon className="h-[18px] w-[18px] shrink-0" />
                        {!collapsed && <span className="flex-1">{item.label}</span>}
                        {!collapsed && item.badge && <Badge variant="danger" className="h-5 px-1.5">{item.badge}</Badge>}
                        {!collapsed && item.pill && <Badge variant="primary" className="h-5 px-1.5">{item.pill}</Badge>}
                      </>
                    )}
                  </NavLink>
                ))}
              </div>
            </div>
          ))}
        </nav>
        <div className="border-t border-border p-3">
          <button
            onClick={() => setCollapsed((c) => !c)}
            className="hidden w-full items-center gap-3 rounded-btn px-2.5 py-2 text-sm text-muted-foreground hover:bg-muted hover:text-foreground lg:flex"
          >
            {collapsed ? <ChevronsRight className="h-[18px] w-[18px]" /> : <><ChevronsLeft className="h-[18px] w-[18px]" /><span>Collapse</span></>}
          </button>
        </div>
      </aside>
    </>
  );
}

function Topbar({ setMobileOpen, onOpenPalette }) {
  const { theme, toggle } = useTheme();
  const navigate = useNavigate();
  const { data } = useData();
  const { start: startTour } = useTour();
  const notifications = data?.notifications || [];
  const unread = notifications.filter((n) => !n.read).length;
  return (
    <header className="sticky top-0 z-30 flex h-16 items-center gap-3 border-b border-border bg-card/80 px-4 backdrop-blur-md">
      <button className="lg:hidden" onClick={() => setMobileOpen(true)}><Menu className="h-5 w-5" /></button>

      <button
        onClick={onOpenPalette}
        className="group flex h-9 w-full max-w-md items-center gap-2 rounded-btn border border-border bg-surface px-3 text-sm text-muted-foreground transition-colors hover:border-ring"
      >
        <Search className="h-4 w-4" />
        <span className="flex-1 text-left">Search findings, resources, namespaces…</span>
        <kbd className="hidden items-center gap-0.5 rounded border border-border bg-card px-1.5 py-0.5 text-[10px] font-medium sm:flex">
          <Command className="h-3 w-3" />K
        </kbd>
      </button>

      <div className="ml-auto flex items-center gap-1.5">
        <Badge variant="success" className="hidden md:inline-flex">
          <span className="h-1.5 w-1.5 animate-pulse-dot rounded-full bg-success" /> Live
        </Badge>
        <button onClick={toggle} className="flex h-9 w-9 items-center justify-center rounded-btn text-muted-foreground hover:bg-muted" title="Toggle theme">
          {theme === "dark" ? <Sun className="h-[18px] w-[18px]" /> : <Moon className="h-[18px] w-[18px]" />}
        </button>

        <Dropdown
          trigger={
            <button className="relative flex h-9 w-9 items-center justify-center rounded-btn text-muted-foreground hover:bg-muted">
              <Bell className="h-[18px] w-[18px]" />
              {unread > 0 && <span className="absolute right-1.5 top-1.5 h-2 w-2 rounded-full bg-primary ring-2 ring-card" />}
            </button>
          }
          className="w-80"
        >
          <div className="px-2.5 py-2 text-sm font-semibold">Notifications</div>
          <Separator />
          {notifications.slice(0, 4).map((n) => (
            <DropdownItem key={n.id} className="flex-col items-start gap-0.5 py-2.5" onClick={() => navigate("/app/notifications")}>
              <div className="flex w-full items-center gap-2">
                <ShieldAlert className={cn("h-3.5 w-3.5", n.severity === "Critical" ? "text-danger" : n.severity === "High" ? "text-warning" : "text-info")} />
                <span className="font-medium">{n.title}</span>
              </div>
              <span className="pl-5.5 text-xs text-muted-foreground line-clamp-1">{n.body}</span>
            </DropdownItem>
          ))}
          {notifications.length === 0 && <div className="px-2.5 py-3 text-xs text-muted-foreground">No notifications</div>}
          <Separator />
          <DropdownItem className="justify-center text-primary" onClick={() => navigate("/app/notifications")}>View all</DropdownItem>
        </Dropdown>

        <button
          onClick={() => startTour()}
          className="flex h-9 w-9 items-center justify-center rounded-btn text-muted-foreground hover:bg-muted"
          title="Guided tour"
        >
          <CircleHelp className="h-[18px] w-[18px]" />
        </button>

        <Dropdown
          trigger={
            <button className="flex items-center gap-2 rounded-btn p-0.5 pl-1 hover:bg-muted">
              <Avatar name="Sumanth Hegde" className="h-8 w-8" />
            </button>
          }
        >
          <div className="px-2.5 py-2">
            <div className="text-sm font-semibold">Sumanth Hegde</div>
            <div className="text-xs text-muted-foreground">analyst@ephemeralens.io</div>
            <Badge variant="primary" className="mt-1.5">Cloud Security Analyst</Badge>
          </div>
          <Separator />
          <DropdownItem onClick={() => navigate("/app/settings")}><User className="h-4 w-4" /> Profile</DropdownItem>
          <DropdownItem onClick={() => navigate("/app/settings")}><Settings className="h-4 w-4" /> Settings</DropdownItem>
          <Separator />
          <DropdownItem className="text-danger" onClick={() => navigate("/app")}><LogOut className="h-4 w-4" /> Sign out</DropdownItem>
        </Dropdown>
      </div>
    </header>
  );
}

export default function AppShell() {
  const [collapsed, setCollapsed] = useState(false);
  const [mobileOpen, setMobileOpen] = useState(false);
  const [paletteOpen, setPaletteOpen] = useState(false);
  const location = useLocation();
  const { data } = useData();

  const notifications = data?.notifications || [];
  const unread = notifications.filter((n) => !n.read).length;
  const nav = buildNav(data?.metrics, unread);

  useEffect(() => {
    function onKey(e) {
      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === "k") {
        e.preventDefault();
        setPaletteOpen((o) => !o);
      }
    }
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, []);

  useEffect(() => {
    const main = document.getElementById("main-scroll");
    if (main) main.scrollTo(0, 0);
  }, [location.pathname]);

  return (
    <div className="flex h-screen overflow-hidden bg-surface">
      <Sidebar nav={nav} collapsed={collapsed} setCollapsed={setCollapsed} mobileOpen={mobileOpen} setMobileOpen={setMobileOpen} />
      <div className="flex min-w-0 flex-1 flex-col">
        <Topbar setMobileOpen={setMobileOpen} onOpenPalette={() => setPaletteOpen(true)} />
        <main id="main-scroll" className="flex-1 overflow-y-auto scrollbar-thin">
          <div className="mx-auto max-w-[1400px] p-4 sm:p-6 animate-fade-in">
            <Outlet />
          </div>
        </main>
      </div>
      <CommandPalette open={paletteOpen} onClose={() => setPaletteOpen(false)} />
    </div>
  );
}
