import { formatTime } from '../utils/format';

interface Props {
  online: boolean;
  loading: boolean;
  hasData: boolean;
  error: string | null;
  noRecentPoll: boolean;
  expired: boolean;
  dataUpdatedAt?: string;
}

export default function StatusBanner({ online, loading, hasData, error, noRecentPoll, expired, dataUpdatedAt }: Props) {
  if (!online)
    return (
      <div className="banner banner-err" role="alert">
        Thiết bị đang mất kết nối mạng. Bản đồ hiển thị dữ liệu đã nhận lần cuối{dataUpdatedAt ? ` (${formatTime(dataUpdatedAt)})` : ''} và không còn được cập nhật.
      </div>
    );
  if (loading && !hasData) return <div className="banner banner-info" role="status">Đang tải dữ liệu ngập…</div>;
  if (error && !hasData)
    return (
      <div className="banner banner-err" role="alert">
        Không tải được dữ liệu ngập: {error}. Đang thử lại tự động.
      </div>
    );
  if (error)
    return (
      <div className="banner banner-warn" role="alert">
        Lỗi cập nhật ({error}). Đang giữ dữ liệu cũ từ {formatTime(dataUpdatedAt)}, <strong>không còn được cập nhật</strong>.
      </div>
    );
  if (noRecentPoll || expired)
    return (
      <div className="banner banner-warn" role="status">
        Dữ liệu ngập đã quá hạn (cập nhật lúc {formatTime(dataUpdatedAt)}). Hãy kiểm tra lại tình hình thực tế.
      </div>
    );
  return (
    <div className="banner banner-ok" role="status">
      Dữ liệu cập nhật lúc {formatTime(dataUpdatedAt)}
    </div>
  );
}
