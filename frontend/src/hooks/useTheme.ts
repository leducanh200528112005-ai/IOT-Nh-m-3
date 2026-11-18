import { useCallback, useEffect, useState } from 'react';

export type ThemeMode = 'auto' | 'light' | 'dark';
const THEME_KEY = 'flood_app_theme';

export function useTheme() {
  const [theme, setThemeState] = useState<ThemeMode>(() => {
    const saved = localStorage.getItem(THEME_KEY);
    return saved === 'dark' || saved === 'light' ? saved : 'auto';
  });

  useEffect(() => {
    const root = document.documentElement;
    if (theme === 'auto') {
      root.removeAttribute('data-theme');
    } else {
      root.setAttribute('data-theme', theme);
    }
    localStorage.setItem(THEME_KEY, theme);
  }, [theme]);

  const cycleTheme = useCallback(() => {
    setThemeState((prev) => (prev === 'auto' ? 'dark' : prev === 'dark' ? 'light' : 'auto'));
  }, []);

  return { theme, setTheme: setThemeState, cycleTheme };
}
