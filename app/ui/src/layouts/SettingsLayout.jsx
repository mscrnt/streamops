import React from 'react';
import { NavLink, Outlet, useNavigate, useLocation } from 'react-router-dom';
import { 
  Settings, HardDrive, Cpu, Video, Shield, 
  Bell, Lock, Palette, Server, ChevronRight 
} from 'lucide-react';
import { cn } from '@/lib/utils';

const SettingsLayout = () => {
  const navigate = useNavigate();
  const location = useLocation();
  
  // Redirect to system if at /settings root
  React.useEffect(() => {
    if (location.pathname === '/settings' || location.pathname === '/settings/') {
      navigate('/settings/system', { replace: true });
    }
  }, [location.pathname, navigate]);

  const navItems = [
    { 
      path: '/settings/system', 
      label: 'System', 
      icon: Server,
      description: 'Version, platform, and runtime information'
    },
    { 
      path: '/settings/processing', 
      label: 'Processing', 
      icon: Cpu,
      description: 'FFmpeg, hardware acceleration, and encoding'
    },
    { 
      path: '/settings/storage', 
      label: 'Storage', 
      icon: HardDrive,
      description: 'Cache, cleanup policies, and deduplication'
    },
    { 
      path: '/settings/obs', 
      label: 'OBS', 
      icon: Video,
      description: 'WebSocket connection and recording detection'
    },
    { 
      path: '/settings/guardrails', 
      label: 'Guardrails', 
      icon: Shield,
      description: 'Processing limits and safety thresholds'
    },
    { 
      path: '/settings/notifications', 
      label: 'Notifications', 
      icon: Bell,
      description: 'Email and webhook alerts'
    },
    { 
      path: '/settings/security', 
      label: 'Security', 
      icon: Lock,
      description: 'Authentication, HTTPS, and backups'
    },
    { 
      path: '/settings/interface', 
      label: 'Interface', 
      icon: Palette,
      description: 'Theme, layout, and display preferences'
    }
  ];

  return (
    <div className="flex h-full">
      {/* Left sub-navigation */}
      <nav className="w-64 bg-card border-r border-border overflow-y-auto">
        <div className="p-4">
          <h2 className="text-lg font-semibold mb-4">
            Settings
          </h2>
          
          <ul className="space-y-1" role="navigation" aria-label="Settings sections">
            {navItems.map((item) => (
              <li key={item.path}>
                <NavLink
                  to={item.path}
                  className={({ isActive }) =>
                    cn(
                      'group flex items-center justify-between px-3 py-2 rounded-lg transition-colors',
                      isActive
                        ? 'bg-primary/10 text-primary'
                        : 'text-muted-foreground hover:bg-accent hover:text-accent-foreground'
                    )
                  }
                  aria-current={location.pathname === item.path ? 'page' : undefined}
                >
                  <div className="flex items-center space-x-3">
                    <item.icon className="w-5 h-5" />
                    <div>
                      <div className="font-medium">{item.label}</div>
                      <div className="text-xs opacity-70 hidden group-hover:block text-muted-foreground">
                        {item.description}
                      </div>
                    </div>
                  </div>
                  <ChevronRight className="w-4 h-4 opacity-50" />
                </NavLink>
              </li>
            ))}
          </ul>
        </div>
      </nav>

      {/* Content area */}
      <div className="flex-1 overflow-y-auto">
        <Outlet />
      </div>
    </div>
  );
};

export default SettingsLayout;