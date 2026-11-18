import { createContext, useCallback, useContext, useState, type ReactNode } from 'react';
import type { Lang } from './types';

const STORAGE_KEY = 'flood_app_lang';

const MESSAGES = {
  vi: {
    appTitle: 'Hệ thống Cảnh báo Ngập lụt & Định tuyến Thông minh',
    navDemo: 'Kịch bản ngập lụt',
    navStations: 'Quản lý trạm quan trắc IoT',
    navAdmin: 'Hệ thống',
    navBack: '← Về Bản đồ & Tìm đường',
    dataSource: 'Nguồn dữ liệu',
    sourceReal: 'Trạm quan trắc thực địa (IoT Live)',
    sourceDemo: 'Kịch bản mô phỏng thủy văn',
    includeReal: 'Bao gồm trạm quan trắc thực địa',
    simulatedBanner: 'Chế độ mô phỏng kịch bản ngập lụt đô thị',
    simulatedWithReal: 'Chế độ mô phỏng kết hợp trạm quan trắc thực địa',
    routeTitle: 'Tìm đường tránh ngập',
    car: '🚗 Ô tô',
    motorcycle: '🛵 Xe máy',
    pedestrian: '🚶 Đi bộ',
    pickOrigin: 'Chọn điểm đi',
    pickDest: 'Chọn điểm đến',
    pickingHint: 'Bấm lên bản đồ…',
    notChosen: 'Chưa chọn',
    findRoute: 'Tìm đường',
    recompute: 'Tính lại tuyến',
    findingRoute: 'Đang tìm tuyến an toàn…',
    swap: 'Đổi chiều',
    clear: 'Xóa',
    offlineMsg: 'Mất kết nối mạng, chưa thể tìm đường.',
    sendingMsg: 'Đang tính toán lộ trình tránh vùng ngập…',
    distance: 'Khoảng cách',
    duration: 'Thời gian',
    calculatedAt: 'Tính lúc',
    shareLink: '📋 Chia sẻ link',
    copiedLink: '✅ Đã chép link!',
    exportGeoJson: '⬇️ Tải GeoJSON',
    stepsTitle: '🧭 Hướng dẫn từng bước',
    historyTitle: '🕒 Lịch sử tìm đường',
    clearHistory: 'Xóa lịch sử',
    searchPlaceholder: '🔍 Tìm địa chỉ (VD: Ngã tư Vạn Phúc)…',
    searchingAddr: 'Đang tìm…',
    noAddrResults: 'Không tìm thấy địa chỉ phù hợp.',
    stationsTitle: 'Điểm đo ngập',
    emptyStations: 'Chưa có điểm ngập nào trên bản đồ.',
    addDemoNow: '+ Thêm điểm ngập ngay',
    legendTitle: 'Chú giải',
    adminTitle: 'Giám sát & Quản trị hệ thống',
    themeAuto: 'Giao diện: Tự động',
    themeDark: 'Giao diện: Tối',
    themeLight: 'Giao diện: Sáng',
    alertToastTitle: '🚨 Cảnh báo ngập mới!',
    dismiss: 'Đóng',
  },
  en: {
    appTitle: 'Smart Flood Warning & Safe Routing System',
    navDemo: 'Flood Scenarios',
    navStations: 'IoT Monitoring Stations',
    navAdmin: 'System Status',
    navBack: '← Back to Map & Routing',
    dataSource: 'Data source',
    sourceReal: 'Field IoT Stations (Live)',
    sourceDemo: 'Hydrological Simulation Scenario',
    includeReal: 'Include field IoT stations',
    simulatedBanner: 'Urban Flood Simulation Scenario Active',
    simulatedWithReal: 'Simulation Scenario + Field IoT Stations',
    routeTitle: 'Safe Flood-Avoid Routing',
    car: '🚗 Car',
    motorcycle: '🛵 Motorcycle',
    pedestrian: '🚶 Walk',
    pickOrigin: 'Pick Origin',
    pickDest: 'Pick Destination',
    pickingHint: 'Click on map…',
    notChosen: 'Not selected',
    findRoute: 'Find Route',
    recompute: 'Recalculate',
    findingRoute: 'Routing around floods…',
    swap: 'Swap',
    clear: 'Clear',
    offlineMsg: 'Offline — cannot compute route.',
    sendingMsg: 'Computing safest route avoiding flood zones…',
    distance: 'Distance',
    duration: 'Duration',
    calculatedAt: 'Calculated at',
    shareLink: '📋 Share Link',
    copiedLink: '✅ Link copied!',
    exportGeoJson: '⬇️ Export GeoJSON',
    stepsTitle: '🧭 Turn-by-Turn Directions',
    historyTitle: '🕒 Route History',
    clearHistory: 'Clear history',
    searchPlaceholder: '🔍 Search address (e.g. Van Phuc)…',
    searchingAddr: 'Searching…',
    noAddrResults: 'No matching address found.',
    stationsTitle: 'Flood Sensors',
    emptyStations: 'No flood stations on map yet.',
    addDemoNow: '+ Add demo point now',
    legendTitle: 'Legend',
    adminTitle: 'System Monitoring & Admin',
    themeAuto: 'Theme: Auto',
    themeDark: 'Theme: Dark',
    themeLight: 'Theme: Light',
    alertToastTitle: '🚨 New Flood Danger Alert!',
    dismiss: 'Dismiss',
  },
} as const;

export type MessageKey = keyof typeof MESSAGES.vi;

interface I18nCtx {
  lang: Lang;
  setLang: (lang: Lang) => void;
  toggleLang: () => void;
  t: (key: MessageKey) => string;
}

const Ctx = createContext<I18nCtx | null>(null);

export function I18nProvider({ children }: { children: ReactNode }) {
  const [lang, setLangState] = useState<Lang>(() => {
    const saved = localStorage.getItem(STORAGE_KEY);
    return saved === 'en' ? 'en' : 'vi';
  });

  const setLang = useCallback((next: Lang) => {
    setLangState(next);
    localStorage.setItem(STORAGE_KEY, next);
  }, []);

  const toggleLang = useCallback(() => {
    setLang(lang === 'vi' ? 'en' : 'vi');
  }, [lang, setLang]);

  const t = useCallback((key: MessageKey) => MESSAGES[lang][key] ?? MESSAGES.vi[key], [lang]);

  return <Ctx.Provider value={{ lang, setLang, toggleLang, t }}>{children}</Ctx.Provider>;
}

export function useI18n() {
  const ctx = useContext(Ctx);
  if (!ctx) throw new Error('useI18n must be used inside I18nProvider');
  return ctx;
}
