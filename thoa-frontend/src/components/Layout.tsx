import React from 'react';
import { Link, useLocation } from 'react-router-dom';
import { Activity, LayoutDashboard, Settings, User, BarChart3 } from 'lucide-react';

export default function Layout({ children }: { children: React.ReactNode }) {
  const location = useLocation();

  const navigation = [
    { name: 'Dashboard', href: '/', icon: LayoutDashboard },
    { name: 'Analytics', href: '/analytics', icon: BarChart3 },
    { name: 'Settings', href: '/settings', icon: Settings },
  ];

  const getPageTitle = () => {
    if (location.pathname === '/') return 'Dashboard';
    if (location.pathname === '/analytics') return 'Analytics';
    if (location.pathname === '/settings') return 'System Configuration';
    if (location.pathname === '/cases/new') return 'New Case';
    return 'Case Review';
  };

  return (
    <div className="flex h-screen bg-slate-50">
      {/* Sidebar */}
      <div className="w-64 bg-white border-r border-slate-200 flex flex-col">
        <div className="h-16 flex items-center px-6 border-b border-slate-200">
          <Activity className="h-8 w-8 text-blue-600 mr-2" />
          <span className="text-xl font-bold text-slate-800 tracking-tight">THOA Screen</span>
        </div>
        <nav className="flex-1 px-4 py-6 space-y-2">
          {navigation.map((item) => {
            const isActive = location.pathname === item.href;
            return (
              <Link
                key={item.name}
                to={item.href}
                className={`flex items-center px-4 py-3 text-sm font-medium rounded-lg transition-colors ${
                  isActive
                    ? 'bg-blue-50 text-blue-700'
                    : 'text-slate-600 hover:bg-slate-100 hover:text-slate-900'
                }`}
              >
                <item.icon className={`h-5 w-5 mr-3 ${isActive ? 'text-blue-700' : 'text-slate-400'}`} />
                {item.name}
              </Link>
            );
          })}
        </nav>
        <div className="p-4 border-t border-slate-200">
          <Link to="/settings" className="flex items-center hover:bg-slate-50 rounded-lg p-2 -m-2 transition-colors">
            <div className="h-8 w-8 rounded-full bg-blue-100 flex items-center justify-center text-blue-700">
              <User className="h-5 w-5" />
            </div>
            <div className="ml-3">
              <p className="text-sm font-medium text-slate-700">Dr. Reviewer</p>
              <p className="text-xs text-slate-500">Authorization Comm.</p>
            </div>
          </Link>
        </div>
      </div>

      {/* Main Content */}
      <div className="flex-1 flex flex-col overflow-hidden">
        <header className="h-16 bg-white border-b border-slate-200 flex items-center justify-between px-8 shadow-sm z-10">
          <h1 className="text-lg font-medium text-slate-800">
            {getPageTitle()}
          </h1>
          <div className="flex items-center space-x-4">
            {/* Header controls can go here */}
          </div>
        </header>
        <main className="flex-1 overflow-auto bg-slate-50 p-8">
          {children}
        </main>
      </div>
    </div>
  );
}
