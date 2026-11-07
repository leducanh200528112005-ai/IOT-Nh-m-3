# Nguồn dữ liệu huấn luyện dự báo ngập: ưu tiên Hà Nội và các bộ đối chứng tải được

**Ngày xác minh:** 02/11/2026, theo ngày của môi trường làm việc.
**Ứng dụng đích:** ESP32 + cảm biến siêu âm; dự báo **độ sâu nước trên mặt đường tại điểm đo**, trước 10/20/30 phút, pilot 1–3 trạm.
**Phạm vi:** tìm dữ liệu, kiểm tra đường tải/mẫu nhỏ và điều kiện sử dụng; chưa tải hàng loạt, chưa huấn luyện hay đo hiệu quả mô hình.
**Tài liệu đi kèm:** `NGHIEN_CUU_AI_ML_CANH_BAO_NGAP.md`; báo cáo này không sửa hay thay thế tài liệu đó.

> **Kết luận:** có dữ liệu quốc tế đủ sát để bắt đầu xây dựng và huấn luyện thử pipeline: **FloodNet NYC dạng chuỗi cảm biến, không phải bộ ảnh UAV cùng tên**. Với Hà Nội, tải được nhiều đặc trưng thời tiết và một số quan trắc mưa, nhưng **chưa xác minh được kho công khai độ sâu ngập mặt đường lịch sử tần suất phút**. Nút thắt vẫn là nhãn ngập tại trạm Hà Nội, không phải thiếu thuật toán. [FN1] [OM1] [N1] [HN1]

## 1. Nên chọn phương án nào?

| Phương án | Có thể làm ngay | Điều chưa được kết luận |
| --- | --- | --- |
| **A — Huấn luyện thử trên proxy quốc tế** | Tải FloodNet NYC theo tháng; dùng lịch sử độ sâu để tạo nhãn 10/20/30 phút. Thêm mưa **tại NYC, cùng thời kỳ** sau nếu cần. | Không gọi kết quả là mô hình dự báo Hà Nội; phải tuân giấy phép phi thương mại và thỏa thuận bổ sung. |
| **B — Đúng địa bàn Hà Nội, đúng bài toán** | Tải thời tiết Hà Nội, đồng thời tự ghi cảm biến/đối soát hoặc xin dữ liệu ngập có hiệu chuẩn từ HSDC. | Chỉ có mưa/thời tiết thì **chưa huấn luyện có giám sát được độ sâu mặt đường**. |
| **C — Bài toán thủy văn dài hạn, riêng biệt** | Dùng mực nước/lưu lượng Văn Úc–Hòn Dấu hoặc GloFAS cho nghiên cứu sông/cửa sông ở bước giờ/ngày. | Không đổi lưu lượng sông `m³/s`, mực nước theo mốc trạm hay nước trong cống thành độ sâu ngập đường `cm`. |

**Ưu tiên thực dụng:** A để kiểm chứng quy trình học và kiểm định; B để hoàn thành sản phẩm địa phương; C chỉ khi chủ động đổi hoặc mở rộng nhiệm vụ nghiên cứu.

## 2. Cách đọc mức xác minh và quyền sử dụng

- **M — Đã lấy mẫu dữ liệu:** HTTP thành công và đã đọc schema/hàng dữ liệu hoặc phần dữ liệu trong tệp nén; không đồng nghĩa đã kiểm tra toàn bộ kho.
- **D — Có đường tải được xác nhận:** đã đọc catalog/index/metadata hoặc HEAD; chưa đọc giá trị đo trong toàn bộ tệp đích.
- **A — Có dữ liệu theo tài liệu, chưa tải qua xác thực:** cần tài khoản, token hoặc chấp nhận điều khoản; không ghi là đã tải được dữ liệu số.
- **X — Chỉ xem/xin quyền:** có bản đồ/API trạng thái hoặc đầu mối liên hệ, chưa có kho nhãn huấn luyện dùng được.
- **Target:** đại lượng cần dự báo; **feature:** đầu vào bổ sung; **proxy/tiền huấn luyện:** dữ liệu khác miền hoặc khác đại lượng, không phải nhãn Hà Nội.
- `HTTP 200` có thể chỉ là metadata; `HTTP 206` chỉ xác nhận phần byte được đọc. Các số hàng mẫu bên dưới **không phải** số hàng toàn bộ dataset.
- Giấy phép dữ liệu, điều khoản dịch vụ API và quyền phân phối sản phẩm phái sinh là các vấn đề khác nhau. **Tải công khai ≠ được tái đăng hoặc dùng thương mại vô điều kiện.**

## 3. Bảng xếp hạng 14 nguồn/nhóm nguồn

Thứ tự ưu tiên cho đồ án này, không phải xếp hạng độ chính xác khí tượng. Thông tin giấy phép, độ trễ và cách tải được tách sang mục 4–8 để bảng vẫn đọc được.

| Ưu tiên / nguồn gốc | Địa bàn | Biến và đơn vị | Thời kỳ | Độ phân giải thời gian / không gian | Vai trò và mức phù hợp |
| --- | --- | --- | --- | --- | --- |
| **1. FloodNet NYC**, archive 2023 và archive cũ FloodSense [FN1] [FN2] | New York, Mỹ; từng vị trí lắp cảm biến | `depth_raw_mm`, `depth_filt_mm`, `depth_proc_mm`, khoảng cách `mm`, pin `V`, vị trí/trạm | Archive mới: 05/10/2020–31/10/2023; archive cũ bắt đầu 10/2020, chưa quét ngày cuối | Khoảng 1 phút; một số cảm biến cũ 5 phút; **điểm đo**, không phủ toàn đoạn đường | **Target độ sâu quan trắc tại miền nguồn**, sát nhất với dự báo 10/20/30 phút; proxy cho Hà Nội |
| **2. Open-Meteo Historical Weather** [OM1] | Toàn cầu, truy vấn được tọa độ Hà Nội | `precipitation`, `rain`: tổng lượng `mm` trong giờ; nhiệt độ `°C`, ẩm `%` | ERA5 từ 1940; ERA5-Land từ 1950; IFS từ 2017, tùy lựa chọn | Hourly; ERA5 0,25°, ERA5-Land 0,1°, IFS khoảng 9 km | **Feature hồi cứu** dễ tải; không phải trạm mưa hoặc target ngập |
| **3. Open-Meteo Historical Forecast / Single Runs** [OM2] [OM3] | Toàn cầu, gồm Hà Nội | Mưa dự báo theo khoảng `mm`; biến thời tiết khác; định danh model/run do người tải lưu | Historical Forecast tùy model: GFS từ 23/03/2021; Single Runs: đa số từ 02/04/2026, IFS có lịch sử riêng từ 14/03/2024 | Đầu ra hourly; native tùy model. Mẫu GFS khoảng 13 km, IFS 9 km | **Feature dự báo**; Single Runs hữu ích hơn để tái lập vintage, nhưng phải kiểm tra hindcast và giờ thực sự phát hành |
| **4. Bellinge / DTU–VCS** [BE1] [BE2] | Lưu vực thoát nước đô thị 1,7 km², Odense, Đan Mạch | Độ sâu trong công trình `m`, cao độ nước `m` theo mốc; mưa `µm/s`; lưu lượng `m³/s` | Nhiều trạm từ 2010; bản cập nhật tới 18/08/2021; độ phủ từng trạm khác nhau | Mực nước cố định 1 phút, trạm di động 2 phút; mưa gauge 1 phút; radar 1/5 phút | **Mưa–mực nước quan trắc thật, tần suất cao** để học chuỗi/QC; target là **trong cống/bể**, không phải mặt đường |
| **5. NOAA NCEI: GHCNh và ISD cũ** [N1] [N2] | Hà Đông, Nội Bài và các trạm VN/quốc tế | Mưa `mm` theo kỳ tích lũy; nhiệt độ `°C`, điểm sương, QC; ISD phải giải mã scale | ISD Hà Đông: inventory 1980–08/2025; đã thử 09/2024. GHCNh trạm–năm 2024 đã xác minh | Theo bản tin trạm; mẫu Hà Đông chủ yếu nhiều giờ, không phải mưa 1 phút; điểm đo | **Feature quan trắc** có nguồn gốc rõ; phải kiểm tra trạm/biến thực có, không suy từ tên “hourly” |
| **6. HSDC Maps / Công ty Thoát nước Hà Nội** [HN1] [HN2] | Hà Nội | API đã kiểm tra chỉ có mã/tên, tọa độ, biểu tượng trạng thái; **không có số đo độ sâu/mưa hoặc thời gian đo** | Trạng thái hiện tại khi truy cập; chưa xác minh archive | JS gọi lại mỗi 10 giây; **đó là nhịp polling**, không chứng minh nhịp quan trắc | **Đầu mối xin nhãn ưu tiên địa phương**; bản đồ/API hiện tại không phải dataset target tải được |
| **7. NASA GPM IMERG V07** [IM1] [IM2] | Toàn cầu, có Hà Nội | `precipitation` dạng tốc độ `mm/h` ở sản phẩm half-hourly; lượng 30 phút cần đổi đúng đơn vị | V07 từ 01/1998; metadata collection đã đọc kết thúc 30/09/2025, chưa xác nhận điểm cuối kho hiện hành | 30 phút; 0,1° × 0,1° | **Feature mưa ước tính**, không phải nhãn ngập; trễ phát hành làm hạn chế ứng dụng nowcast |
| **8. Mưa 172 trạm Việt Nam — World Bank phát hành** [VN1] | Việt Nam; metadata có Láng, Hà Đông, Sơn Tây đánh dấu có dữ liệu | Mưa ngày; **đơn vị phải kiểm tra trong tệp mưa gốc**, chưa suy từ tên catalog | Phần lớn trạm hoạt động 1975–2006 | Daily; điểm trạm | **Feature/đối chứng khí hậu lịch sử**; không đủ nhịp để chứng minh dự báo 10 phút |
| **9. Trung Trang–Hòn Dấu, tác giả Pénicaud / Zenodo** [VN2] | Đồng bằng sông Hồng: cửa sông Văn Úc và ven biển Hải Phòng, **không phải đường Hà Nội** | Mực nước `cm` theo header; có `Q` nhưng đơn vị Q chưa xác nhận từ phần header đã đọc | Tệp `Data_2021-2022.xlsx`; phải kiểm tra độ phủ từng sheet | Hourly; hai điểm trạm; không có mưa trong dataset này | **Target thủy văn bước giờ**, hoặc nghiên cứu chuyển miền có giới hạn; không target street-depth |
| **10. CHIRPS v3 / UC Santa Barbara CHC** [CH1] [CH2] | Đất liền 60°B–60°N, gồm VN | Mưa tích lũy `mm`, daily/pentad/monthly | `rnl`: 1981–gần hiện tại; daily `sat`: 1998–gần hiện tại | Daily trở lên; 0,05°; daily được phân rã từ pentad | **Feature nền/khí hậu**, không nowcast 10 phút; không coi là quan trắc mưa phút độc lập |
| **11. ERA5-Land gốc / Copernicus CDS** [ER1] [ER2] | Toàn cầu trên đất liền, gồm Hà Nội | `total_precipitation` đơn vị gốc `m`; ẩm đất `m³/m³`; nhiệt độ `K` | 1950–gần hiện tại | Hourly; lưới phân phối 0,1°, native khoảng 9 km | **Feature hồi cứu có kiểm soát provenance**; không có độ sâu ngập đường |
| **12. NASA POWER** [PW1] [PW2] | Toàn cầu; tọa độ Hà Nội trả được dữ liệu | `PRECTOTCORR`: `mm/hour`; `T2M`: `°C`; `RH2M`: `%` | API hourly từ 01/01/2001 tới gần hiện tại | Hourly; mẫu 2024 lấy nguồn MERRA-2, khí tượng khoảng 0,5° × 0,625° | **Feature dự phòng/thử pipeline** dễ lấy, nhưng rất thô đối với một con phố |
| **13. GloFAS gốc / CEMS EWDS; API tiện dụng Open-Meteo** [GF1] [GF2] | Toàn cầu theo ô sông, có vùng Hà Nội | Lưu lượng sông mô hình `m³/s`, không phải độ sâu | EWDS v4/v5: 1979–gần hiện tại; API Open-Meteo mô tả kho từ 1984, không đồng nhất toàn bộ kho gốc | Daily; v4/v5 0,05° khoảng 5 km | **Proxy mô hình sông/tiền huấn luyện bài toán khác**, không nhãn quan trắc hoặc target đường |
| **14. NYC street-segment flood events / Qin** [EV1] | Mạng đường NYC | Sự kiện, thời gian, cạnh đường, hình học, chiều dài `m`; **không có độ sâu cm** | Tên dataset nêu 2020–2024 | Theo sự kiện/báo cáo; đoạn đường | **Nhãn sự kiện/GIS**; chỉ positives đã ghi nhận, không có negative được xác minh; không hồi quy độ sâu liên tục |

## 4. Đường tải, giấy phép, độ trễ và mức đã kiểm chứng

Các phép tải công khai thành công bên dưới không yêu cầu thanh toán trong lần thử. Với kho cần xác thực, chưa hoàn tất tải hay kiểm tra chi phí phát sinh của cloud/subsetting; không nhầm dữ liệu mở với hạ tầng tính toán miễn phí. Phí cấp dữ liệu theo yêu cầu từ HSDC **chưa rõ**; dịch vụ Open-Meteo thương mại có gói trả phí.

| Nguồn | Đường tải/định dạng và tài khoản/phí | Quyền dùng để huấn luyện | Độ trễ, thiếu dữ liệu và mức xác minh |
| --- | --- | --- | --- |
| FloodNet | [CSV tháng 09/2021][FNCSV], 16.025.889 byte; không cần login khi lấy mẫu; không tải toàn bộ 4,5 GB | **CC BY-NC-SA 4.0 + Data Access License Agreement**: dùng phi thương mại, trích NYU/CUNY; có hạn chế phân phối thêm ở mục 5 | **M**: prefix 8 KiB, HTTP 206, 21 cột và 33 hàng đầy đủ; archive không có SLA realtime; null/che khuất/đổi mốc cần QC |
| Open-Meteo Historical Weather | `/v1/archive`, JSON/CSV/XLSX; Q1 ở mục 7; free API không cần key cho phạm vi phi thương mại | Dữ liệu **CC BY 4.0**; dịch vụ free chỉ phi thương mại, có quota; sử dụng thương mại cần gói phù hợp [OML] [OMT] | **M**: Q1 48 mốc giờ, không null trong 4 biến mẫu; ERA5/ERA5-Land trễ khoảng 5 ngày, không khả dụng tại thời điểm trận mưa |
| Open-Meteo forecast archives | Hai host `/v1/forecast`, JSON/CSV/XLSX; Q2/Q3 ở mục 7; xác thực/điều kiện dịch vụ như trên | CC BY 4.0 và điều khoản API; không dùng license phần mềm AGPL thay cho license dữ liệu [OML] | **M**: Q2/Q3 đều 48 mốc; Q2 `rain` toàn null; Q3 null ở bước đầu; run khởi tạo khác giờ phát hành [OM3] |
| Bellinge | [Cleaned sensor ZIP][BECLEAN] ~390,4 MB; [rain gauge ZIP][BERAIN] ~2,67 MB; [radar/khí tượng][BE4]; không login khi lấy mẫu | Sensor **CC BY 4.0**; **rain gauge CC BY-NC 4.0**, có điều kiện riêng trong metadata; radar/khí tượng item 3b CC BY 4.0 [BE2] [BE3] [BE4] | **M**: HTTP Range 206, đã giải nén phần đầu CSV/TXT từ ZIP; thiếu/NaN và sửa hệ thống đã được tác giả mô tả; archive không bảo đảm độ trễ vận hành |
| NOAA | [PSV Hà Đông 2024][NPSV] ~2,45 MB; GHCNh còn có Parquet. ISD có [CSV năm–trạm][NISDCSV] và API nhỏ ở mục 6; không key trong các phép thử | **GHCNh CC0** được xác nhận từ metadata XML [NLIC]. ISD là bản cũ với yêu cầu trích dẫn/miễn trừ riêng; không gán ngược giấy phép của bản mới [NOLD] | **M**: PSV prefix 32 KiB/26 hàng; API ISD 13 bản tin Hà Đông và 95 Nội Bài trong hai ngày; ISD đã bị thay thế, inventory cũ không chứng minh cập nhật 2026 |
| HSDC | [API trạng thái JSON][HNAPI], bản đồ [HN1]; có thể truy cập không login trong kiểm tra, nhưng **không có file nhãn/history** | **Chưa rõ quyền tái sử dụng/huấn luyện**; cần hỏi HSDC, không thu gom lại thành archive khi chưa rõ điều khoản [HN2] | **X** đối với nhãn độ sâu; đã đọc JSON metadata/trạng thái. Không có timestamp để xác nhận độ mới; phát hiện tọa độ 0,0 cần QC |
| IMERG | [Earthdata Search collection gốc][IMSEARCH] → chọn thời gian/AOI/biến → tải hoặc subset; HDF5, các công cụ có thể xuất NetCDF; tài khoản Earthdata/GES DISC | Chính sách dữ liệu NASA cho phép tái sử dụng, yêu cầu lưu nguồn/citation; metadata trỏ chính sách này, không có hạn chế truy cập dữ liệu được khai báo [IMRIGHT] [NASAL] | **A** đối với giá trị mưa: CMR HTTP 200 xác nhận một granule thật; thử Range file không xác thực trả HTTP 400. Early ~4 giờ, Late ~14 giờ, Final ~3,5 tháng [IM1] |
| Mưa 172 trạm VN | [ZIP mưa][VNRAIN] 6.045.403 byte; [XLSX trạm][VNST] 38.726 byte; World Bank/ENERGYDATA công bố, không yêu cầu key khi thử | **CC BY 4.0** theo catalog phát hành; provenance ghi nguồn quan trắc từ HydroMeteorological Data Center VN [VN1] | **M metadata / D giá trị mưa**: XLSX HTTP 200; ZIP Range 206. ZIP ngoài chứa 3 ZIP vùng và `KV1.rar`, chưa đọc series mưa; dữ liệu cũ, không realtime |
| Trung Trang–Hòn Dấu | [XLSX tác giả][VNRIVER], 1.309.181 byte; không login khi thử | **CC BY 4.0** theo record; phải trích tác giả và làm rõ mốc cao độ/đơn vị Q trước xử lý [VN2] | **M**: HTTP 206; đọc workbook, shared strings và phần đầu 3 sheet bằng Range; chưa tính tỷ lệ thiếu/bao phủ cuối kỳ; phát hành archive 08/2024 |
| CHIRPS v3 | [GeoTIFF ngày 07/09/2024][CHFILE]; [thư mục daily sat][CHDIR]; có NetCDF/COG; không login ở đường tải đã thử | Trang chính chủ ghi **CC BY 4.0**, đồng thời có lời tuyên bố public-domain; áp dụng attribution để không suy rộng quyền [CH1] | **D**: index và HEAD file HTTP 200, 16.022.730 byte; chưa trích pixel Hà Nội. Prelim: 2 ngày sau pentad; Final thường tuần 3 tháng sau [CH1] |
| ERA5-Land CDS | [Tab Download gốc][ERDOWNLOAD] → chọn `total_precipitation`, ngày/giờ/AOI → “Show API request code”; GRIB, tùy đường xuất có NetCDF | **CC-BY** theo catalog hiện hành; tài khoản CDS, token cá nhân và phải chấp nhận Terms trước tải [ER1] [CDSAPI] | **A**: đã đọc catalog, chưa có token/chưa tải subset. ERA5-Land-T trễ ~5 ngày; bản final ghi đè khoảng 2 tháng sau [ER2] |
| NASA POWER | [JSON mẫu Hà Nội][PWQUERY]; đổi `format=CSV` để tải bảng; không cần key ở phép thử | Dữ liệu NASA mở; lưu citation dự án, service version/ngày truy cập; không suy quyền thương hiệu/chứng thực NASA [PW3] [NASAL] | **M**: HTTP 200, 48 giá trị mỗi biến, không `-999` trong mẫu; khí tượng thường trễ 2–3 ngày, dữ liệu gần hiện tại có thể được thay bằng bản tốt hơn [PW2] |
| GloFAS | [Tab Download EWDS][GFDOWNLOAD]: tài khoản/chấp nhận CEMS-FLOODS; GRIB2/NetCDF-4. [API mẫu 3 ngày][GFQUERY]: không key | Kho gốc theo **CEMS-FLOODS datasets licence**, phải đọc/chấp nhận; API tiện dụng theo CC BY 4.0 và điều kiện dịch vụ Open-Meteo [GF1] [OML] | **M qua API / A kho gốc**: HTTP 200, 3 giá trị daily; chưa xác minh đúng nhánh sông. Intermediate cập nhật ngày, consolidated theo tháng; đều là mô phỏng [GF1] |
| NYC street-segment events | [CSV `nyc_merged.csv`][EVCSV], 4.990.286 byte; không login ở phép thử | Record khai **CC BY 4.0**, nhưng hợp nhất NOAA/311/FloodNet/MyCoast: **quyền upstream/tái cấp phép chưa rà soát xong**, nhất là FloodNet [EV1] | **M**: prefix 8 KiB, HTTP 206, 19 cột/22 hàng; thời điểm báo cáo không bảo đảm là giờ khởi phát; không suy chưa báo cáo = không ngập |

## 5. Hai bộ quốc tế đáng tải trước: dùng thế nào để không đổi sai bài toán?

### 5.1. FloodNet NYC — nhãn gần ứng dụng nhất

- Landing gốc của nhóm NYU/CUNY: [archive 2020–2023][FN1]. File bắt đầu nhỏ, thao tác được: [tháng 09/2021][FNCSV]; mở rộng bằng [tháng 07/2021][FNJUL] và [tháng 08/2021][FNAUG].
- Schema đã kiểm tra gồm `time`, `deployment_id`, `dev_id`, ba trường depth, `dist_mm`, `batt_v`, `f_cnt`, `lat`, `lon`, `date_deployed`, `deploy_type`, `nearest_weather_station`, `nearest_tidal_id`, `mounted_over`, `sensor_mount` và thông tin vị trí. Thời gian theo UTC; đổi `mm → cm` bằng chia 10. [FN1]
- Tác giả khuyến nghị `depth_proc_mm`, nhưng đây là sản phẩm lọc/hiệu chuẩn. **Trước backtest vận hành phải kiểm tra bộ lọc có nhìn dữ liệu tương lai hoặc cập nhật hồi cứu không**; nhãn xử lý hậu kỳ và feature khả dụng tại thời điểm quyết định không tự động là cùng một thứ. [FN1]
- Chọn deployment thuộc kiểu ngập mưa phù hợp; tách coastal/tidal khi có metadata. Không coi tất cả sensor là một phố có cùng hệ thống thoát nước hoặc mốc lắp.
- Dùng lag độ sâu hợp lệ tại `t` làm đầu vào; đích là độ sâu tại `t+10/20/30 phút`. Không cần có mưa mới bắt đầu được thử nghiệm tự hồi quy; thêm weather NYC chỉ khi có cùng thời gian/vị trí.
- Null có thể do không nhận được echo; người/vật dưới cảm biến có thể tạo blip/box. Độ sâu tại chỗ lắp không đồng nghĩa độ sâu lớn nhất toàn đường. Nguồn tự nêu rõ các giới hạn này. [FN1]
- **Ràng buộc phải giữ:** record CC BY-NC-SA 4.0 **và** [thỏa thuận bổ sung][FNL]; chỉ phi thương mại; ghi “FloodNet (New York University and The City University of New York)”; phái sinh được phép phải theo CC BY-NC-SA 4.0.
- Thỏa thuận cấm chia sẻ/tái đăng original Data, kể cả một phần, cho bên thứ ba khi chưa có đồng ý bằng văn bản. Vì vậy **không commit CSV thô lên GitHub, không đính kèm raw records trong báo cáo**. Phân phối trọng số mô hình/phái sinh hoặc dùng thương mại cần làm rõ với chủ sở hữu; không suy share-alike áp dụng ra sao cho mọi artifact. [FNL]

**Archive cũ dự phòng:** [FloodSense v2.0][FN2], có [metadata 2.436 byte][FN2META] và [CSV khoảng 1,736 GB][FN2CSV]. Record này ghi **CC BY 4.0**, không phải license giống archive mới.
Mẫu CSV cũ có 68 cột, trong đó tên `measurement` xuất hiện hai lần; parser phải giải quyết trùng tên có chủ đích. Hai archive có thể chồng lấn; **không chia train/test bằng tên archive** rồi để cùng trận/trạm lọt sang cả hai phía.
Đối với thương mại hoặc bàn giao/phân phối, xin xác nhận quyền áp dụng đúng bản cũ; không coi license khác nhau là cách lách thỏa thuận của nguồn mới. [FN2] [FNL]

### 5.2. Bellinge — bộ mưa và mực nước đô thị phút có quan trắc thật

- Tác giả cung cấp cả dữ liệu sensor thô/cleaned, gauge, radar, mô hình SWMM và metadata tại [collection DTU][BECOLL]; bài mô tả gốc giải thích nhịp đo và mốc nước. [BE1]
- Cặp cần tải cho nghiên cứu phi thương mại: [cleaned sensor ZIP][BECLEAN] + [rain gauge ZIP][BERAIN]. Nếu cần lựa chọn khác về quyền mưa, xem riêng [radar/khí tượng item 3b][BE4], không tự đánh đồng gauge với radar.
- Đã đọc phần đầu `G71F06R_LevelInlet_System2000p1_proc_v6.csv`: các cột `time`, `raw_value`, `value_no_errors`, các cờ QC, `depth_s`, `level`; timestamp cách một phút trong mẫu từ 01/08/2010.
- Đã đọc `5425_ts.txt`: header **`Rainfall Intensity[mu-m/sec]:Mean_Step_Accumulated`**, tách bằng `;`; đây là **cường độ**, không phải số mm mưa mỗi hàng. `1 µm/s = 0,06 mm/phút = 3,6 mm/giờ`; muốn lượng mưa phải tích phân theo khoảng đúng.
- Gauge có tệp missing/planned closing; không mặc định khoảng trống là mưa bằng 0. Sensor cleaned có NaN/cờ lỗi; tác giả ghi có nội suy khoảng thiếu ngắn và thay đổi hệ SCADA/hạ tầng. [BE1] [BE3]
- Cleaned data được đưa về UTC; cao độ `level` có mốc khác `depth_s`. Tác giả có ví dụ thay đổi cấu trúc năm 2015 gây dịch nền mực nước. Không diễn giải toàn bộ dịch nền là hỏng cảm biến. [BE1]
- Có thể huấn luyện dự báo **mực nước trong mạng thoát nước** 10/20/30 phút trên phần giao thời gian mưa–sensor. Đó là benchmark phù hợp cho chuỗi và QC, **không phải chứng cứ dự báo độ sâu đường Hà Nội**.

### 5.3. Dataset sự kiện theo đoạn đường NYC — chỉ là phần bổ sung

[Record của Qin][EV1] và [CSV][EVCSV] có `event_id`, node/cạnh, tọa độ hai đầu, `geometry_wkt`, `length_m`, `event_datetime`, `source_file`.
Phù hợp demo gắn sự kiện lên cạnh đường hoặc nghiên cứu thiên lệch báo cáo. Không có độ sâu liên tục và nhãn âm được kiểm định; **không huấn luyện hồi quy `depth(t+10 phút)` trực tiếp**, không lấy mọi đoạn chưa xuất hiện làm negative.
Giấy phép upstream chưa được xác minh đầy đủ; không chọn làm bộ tối thiểu nếu FloodNet sensor đã đáp ứng nhiệm vụ.

## 6. Nguồn Hà Nội/Việt Nam: đâu là dữ liệu dùng được, đâu còn phải xin?

### 6.1. HSDC: đầu mối có giá trị, chưa phải kho nhãn tải được

[Trang úng ngập][HN1] nạp [JavaScript][HNJS] gọi `GET /ungngap/api/flood/getflood` mỗi 10 giây.
JSON đã kiểm tra có `Code`, `Content`; trong từng item chỉ thấy `TramId`, `TenTram`, `Lng`, `Lat`, `Icon`. Không thấy `observed_at`, depth số, lượng mưa, lịch sử hay export. [HNAPI]
Do đó chỉ gọi đây là **metadata/trạng thái bản đồ hiện tại xem được**, không gọi là archive hoặc API huấn luyện độ sâu.
Liên hệ theo [chính sách HSDC Maps][HN2], email **tnhn@thoatnuochanoi.vn**, xin: vị trí/mốc lắp, chuỗi mưa và độ sâu phút, timestamp/múi giờ, calibration/QC, thời gian mất trạm, ngày thay cảm biến và quyền dùng/phân phối cho nghiên cứu.
Nếu chỉ được bảng tổng hợp điểm ngập sau trận, có thể chuyển sang bài toán sự kiện đã ghi nhận; không giả thành nhãn liên tục từng phút.

### 6.2. NOAA: ưu tiên GHCNh mới, dùng ISD để tái lập lịch sử đã kiểm tra

[GHCNh chính chủ][N2] đang thay thế ISD; dữ liệu có `DATE`, giá trị, measurement/quality/source codes. [Metadata giấy phép][NLIC] ghi CC0.
[Danh sách trạm mới][NSTATIONS] cho thấy Hà Đông **`VMM00048825`**, Nội Bài **`VMI0000VVNB`**; khác ID ISD tương ứng `48825099999`, `48820099999`. Không nối chỉ bằng tên hoặc suy ID theo một công thức.
Tải [PSV Hà Đông năm 2024][NPSV], mở dạng phân cách `|`; giữ timestamp và cờ QC, chọn đúng kỳ mưa, không chỉ lấy một cột số.
API ISD nhỏ đã kiểm tra, có thể đổi `format=json` thành `format=csv`:

```text
https://www.ncei.noaa.gov/access/services/data/v1?dataset=global-hourly&stations=48825099999&startDate=2024-09-07&endDate=2024-09-08&dataTypes=TMP,DEW,AA1,AA2,AA3&format=json&includeAttributes=true&includeStationName=true&includeStationLocation=true
```

Mẫu Hà Đông có 13 bản tin, `AA1` xuất hiện 8 bản tin, `AA2` 2 bản tin; đó không phải 48 quan trắc mưa giờ đầy đủ.
Theo [format ISD][NFORMAT], `AA1`–`AA4` chứa **kỳ tích lũy giờ, depth/10 mm, condition, quality**. Không cộng trùng các khoảng 3/6/12/24 giờ; không nội suy mưa tổng 12 giờ thành ground truth mưa phút.
Mẫu Nội Bài cùng hai ngày có 95 bản tin nhiệt độ/điểm sương nhưng **không có AA1/AA2/AA3**. Điều này không chứng minh mọi thời kỳ Nội Bài đều thiếu mưa, nhưng bác bỏ giả định cứ chọn trạm gần là có đủ rainfall.
Độ trễ/archive không đủ phục vụ trực tiếp quyết định 10 phút; để vận hành phải có luồng đo/dự báo với `available_at`, không dùng lịch sử tải sau như dữ liệu đã biết lúc đó.

### 6.3. Hai bộ Việt Nam có đường tải cụ thể

**Mưa 172 trạm:** [World Bank/ENERGYDATA][VN1] là đơn vị phát hành bản sao; nguồn quan trắc được ghi là HydroMeteorological Data Center Việt Nam, không phải trạm do World Bank vận hành.
Đã đọc [XLSX metadata][VNST]: Láng (ID 119), Hà Đông (111), Sơn Tây (113) được đánh dấu `yes`; không mặc định mọi trạm trong workbook đều có series.
[ZIP dữ liệu][VNRAIN] chứa `KV2-23Tr.zip`, `KV3-21tr.zip`, `KV4-14Tr.zip`, `KV1.rar`. Cần công cụ mở RAR và kiểm tra file bên trong; **chưa đọc giá trị/đơn vị hay ngày cuối của từng trạm**, nên đây không phải lời xác nhận series Láng hoàn chỉnh.
Tọa độ metadata có dạng như `10551`, `2102`, không được đưa thẳng vào GIS như độ thập phân. Cần xác minh quy ước kinh/vĩ độ của bảng trước chuyển đổi.
Thời kỳ 1975–2006 không giao với pilot mới hay FloodNet NYC; dùng cho khí hậu/đối chứng, không làm nhãn ngập.

**Mực nước Trung Trang–Hòn Dấu:** [dataset tác giả][VN2] và [XLSX][VNRIVER] tải được bằng Range; có ba sheet mực nước Trung Trang, mực nước Hòn Dấu, lưu lượng Trung Trang.
Header xác nhận water level `cm`, bố trí ngày × giờ ở hai sheet đầu; sheet Q có ngày/giờ/giá trị nhưng phần header đã đọc chưa nêu đơn vị Q. Không tự nhận cm ở đây là độ sâu trên mặt đường.
Cần hỏi mốc cao độ, múi giờ, đơn vị/quy ước dấu Q, cơ quan quan trắc và QC; dữ liệu cửa sông có cơ chế khác cống/đường nội đô. Độ phân giải **giờ không đủ để kiểm định horizon 10 phút**, dù có thể thử dự báo bước giờ.

## 7. Ba truy vấn Hà Nội nhỏ có thể sao chép, đã kiểm thử

Tọa độ yêu cầu: **21.0285, 105.8542**. Các ngày sau đều trước 02/11/2026. Đây là phép thử khả năng lấy dữ liệu, **không phải bộ train đầy đủ** hay giả định đã có nhãn ngập cùng ngày.

### Q1 — Historical Weather / ERA5, CSV hai ngày

```text
https://archive-api.open-meteo.com/v1/archive?latitude=21.0285&longitude=105.8542&start_date=2024-09-07&end_date=2024-09-08&hourly=precipitation,rain,temperature_2m,relative_humidity_2m&models=era5&timezone=Asia%2FBangkok&precipitation_unit=mm&format=csv
```

Đã nhận **HTTP 200** CSV; bản JSON cùng tham số có `hourly.time`, `precipitation`, `rain`, `temperature_2m`, `relative_humidity_2m`: **48 mốc**, 00:00 ngày 07/09 tới 23:00 ngày 08/09, không null trong bốn biến của mẫu.
Timezone `Asia/Bangkok` là UTC+7, phù hợp offset giờ Hà Nội ở đây; ô mô hình trả về **21.0, 105.75**, không phải cảm biến đặt tại tọa độ yêu cầu.
`precipitation` là lượng của **giờ trước**, đơn vị mm; không phải cường độ tức thời. CSV có khối metadata trước header thời gian, cần parser đúng. ERA5 là tái phân tích, không phải dự báo đã phát hành trong trận. [OM1]

### Q2 — Historical Forecast / GFS, JSON hai ngày

```text
https://historical-forecast-api.open-meteo.com/v1/forecast?latitude=21.0285&longitude=105.8542&start_date=2024-09-07&end_date=2024-09-08&hourly=precipitation,rain&models=gfs_global&timezone=GMT&precipitation_unit=mm
```

Đã nhận **HTTP 200**, 48 mốc giờ UTC; `precipitation` có 48 giá trị không null nhưng **`rain` null 48/48**. Không thay null bằng 0; trong phép thử này chỉ dùng được `precipitation` cho mưa tổng.
Đây là chuỗi **ghép các giờ đầu của nhiều run**, không phải mọi forecast cho một thời điểm phát hành cố định. Giữ model thay vì `best_match` thay đổi ngầm. [OM2]

### Q3 — Single Runs / IFS, một run hai ngày

```text
https://single-runs-api.open-meteo.com/v1/forecast?latitude=21.0285&longitude=105.8542&run=2026-09-07T00%3A00&forecast_days=2&hourly=precipitation,rain&models=ecmwf_ifs&timezone=GMT&precipitation_unit=mm
```

Đã nhận **HTTP 200**, 48 mốc từ 00:00 ngày 07/09 tới 23:00 ngày 08/09/2026 UTC; mỗi biến có **1 null ở mốc đầu**, 47 giá trị còn lại.
`run` là **giờ khởi tạo UTC, không phải giờ dữ liệu đã tới người dùng**; tài liệu nêu global model thường cần thêm 4–6 giờ. Lưu URL/run/giờ nhận ngoài phản hồi và chỉ dùng từ lúc đã phát hành. [OM3]
Đã thử thêm run IFS 07/09/2024, cũng trả 48 mốc; **không dùng thành chứng cứ vintage 2024**: tài liệu Single Runs ghi phần lịch sử IFS đầu kỳ là **Cycle 49R1 hindcasts**. Có dữ liệu theo `run=` không đủ chứng minh đó là forecast thực sự sẵn có đúng ngày cũ. [OM3]

Open-Meteo phân biệt **CC BY 4.0 của dữ liệu** với **free API phi thương mại**; quota tại lần đọc: dưới 10.000 calls/ngày, 5.000/giờ, 600/phút. Không suy từ một vài truy vấn thành quyền tải vô hạn. [OML] [OMT]

## 8. Các nguồn mưa/lưới: tải đúng sản phẩm và dùng đúng độ trễ

### IMERG: đáng nghiên cứu thêm, nhưng chưa có mẫu số mưa trong phiên này

- [CMR collection][IM2] trả HTTP 200, xác nhận `GPM_3IMERGHH`, V07, 0,1°/half-hourly. [Truy vấn granule nhỏ][IMQUERY] trả một granule 00:00–00:29:59 UTC ngày 07/09/2024 và [đường HDF5 cụ thể][IMFILE].
- CMR là **catalog**, không phải 48 giá trị mưa tại Hà Nội. Thử Range đường dữ liệu không xác thực trả HTTP 400; chưa có Earthdata login/subset, nên không ghi là đã đọc HDF5.
- Cách tải: đăng nhập [Earthdata Search][IMSEARCH], chọn collection V07, AOI nhỏ quanh Hà Nội, ngày 07–08/09/2024; chọn biến precipitation và subset nếu được dịch vụ hỗ trợ; không tải cả lưới toàn cầu nhiều năm.
- Half-hourly thường lưu tốc độ `mm/h`; lượng nửa giờ là tốc độ trung bình nhân 0,5 giờ khi đúng semantics sản phẩm. Giữ version/run, quality/fill, không đổi tên trực tiếp thành mưa mm hoặc depth cm. [IM1]
- **Early ~4 giờ vẫn quá trễ để coi là mưa vừa xảy ra đã biết tại phút t**. Final tốt cho nghiên cứu hồi cứu nhưng dùng hiệu chỉnh hậu kỳ; chỉ dùng như feature vận hành với độ trễ tương ứng, hoặc ghi rõ là thí nghiệm hồi cứu. [IM1]
- Metadata collection đã đọc ghi ngày cuối 30/09/2025; đây có thể là giới hạn/cập nhật metadata của collection đó. Chưa khẳng định thiếu toàn bộ IMERG 2026 hay đã tải được kho mới nhất.

### CHIRPS v3, ERA5-Land và POWER: ưu tiên thấp hơn cho street nowcast

- [CHIRPS v3 daily sat][CHDIR] có file cụ thể [07/09/2024][CHFILE]. `sat` phân rã pentad theo IMERG Late; `rnl` theo ERA5. **Daily không phải một luồng quan trắc trạm độc lập**; hai bản cùng bị ràng buộc bởi tổng pentad. [CH2]
- CHIRPS v3 Final trễ tới tháng sau; v3 là sản phẩm hồi cứu đối với nhiều ngày cũ. Không thể dùng tổng ngày/pentad chưa kết thúc làm đầu vào dự báo phút. V2 được thông báo dừng sản xuất sau 12/2026; nếu bắt đầu mới nên pin v3 và ghi `sat/rnl`, không trộn ngầm hai phiên bản. [CH1] [CH3]
- [ERA5-Land CDS][ERDOWNLOAD]: chọn 07–08/09/2024, 00–23 UTC, `total_precipitation` và biến cần thiết, bbox `[21.2,105.7,20.9,106.0]` theo **Bắc,Tây,Nam,Đông**; lấy mã yêu cầu từ form chính chủ thay vì dùng token người khác. [CDSAPI]
- ERA5-Land chuẩn có quy ước **tích lũy từ đầu forecast/ngày**, khác ERA5; đọc product và de-accumulate đúng chu kỳ, rồi đổi `m × 1000 → mm`. Một số sản phẩm ARCO đã de-accumulate: không lấy sai phân lần nữa. [ER2] [ER3]
- [NASA POWER mẫu][PWQUERY] đã trả JSON gồm `header`, `geometry`, `properties.parameter`, `parameters`; `PRECTOTCORR`, `T2M`, `RH2M` mỗi biến 48 giá trị, fill value `-999`, sample không thiếu. Bắt buộc đặt `time-standard=UTC`: mặc định LST là **giờ mặt trời**, không mặc nhiên là giờ hành chính Hà Nội. [PW1]
- POWER tiện cho nhập liệu/đối chiếu hơn là mưa siêu cục bộ. Không ghép nhiều tọa độ cách vài trăm mét rồi coi như nhiều trạm độc lập nếu cùng ô khí tượng nguồn. [PW4]
- [GloFAS EWDS][GF1] đã có v5 operational theo catalog 2026, trong khi [Open-Meteo Flood][GF2] mô tả v4; phải pin sản phẩm/version, không coi hai kho là giống hệt. API thử tại tọa độ trung tâm Hà Nội trả 3 số daily nhưng **chưa xác nhận đúng nhánh sông**, tuyệt đối không diễn giải thành ngập đường.

## 9. Nhật ký kiểm thử nhỏ và giới hạn chứng cứ

Tất cả kiểm tra ghi nhận dưới đây thuộc đợt **02/11/2026**. Mẫu ZIP/XLSX được đọc bằng Range/giải nén trong bộ nhớ; không đưa dataset lớn hoặc script vào workspace. Các mẫu FloodNet/HSDC/sự kiện NYC do nhánh kiểm tra phối hợp cung cấp; landing/thỏa thuận FloodNet cũng được đọc trực tiếp khi tổng hợp.

| Phép thử | HTTP / phạm vi đã đọc | Điều thực sự xác nhận |
| --- | --- | --- |
| FloodNet 09/2021 [FNCSV] | **206**, `bytes 0-8191/16025889` | Header 21 cột; 33 hàng đầy đủ trong prefix; không đếm tổng tháng, không công bố raw records |
| FloodSense v2 [FN2META] [FN2CSV] | **206**; metadata đủ 2.436 byte; CSV prefix 8 KiB | Metadata trạm; CSV 68 cột, 25 hàng đầy đủ, tên cột lặp; chưa đọc ngày cuối toàn tệp |
| NYC segment events [EVCSV] | **206**, prefix 8 KiB / tổng 4.990.286 byte | 19 cột, 22 hàng đầy đủ trong prefix; không có cột depth |
| HSDC [HNAPI] | GET JSON thành công; không ghi số HTTP cụ thể từ log phối hợp | `Code=1`, `Content` list; chỉ trường định danh/vị trí/icon, không numeric depth/time/history |
| Open-Meteo Q1 JSON + CSV | **200** cả hai; khoảng 2 KiB mỗi phản hồi | 48 mốc, 4 biến có đơn vị; không null trong mẫu |
| Open-Meteo Q2 | **200**, JSON | 48 mốc; precipitation không null; rain 48 null |
| Open-Meteo Q3 và run IFS 2024 bổ sung | **200** từng truy vấn | 48 mốc/run; precipitation/rain mỗi biến 1 null; dữ liệu tồn tại không chứng minh vintage |
| ISD Hà Đông / Nội Bài, 07–08/09/2024 | **200**, JSON; lần lượt 13 / 95 bản tin | AA1 có 8, AA2 có 2 tại Hà Đông; không có AA1–AA3 tại Nội Bài trong mẫu |
| GHCNh Hà Đông [NPSV] | **206**, `bytes 0-32767/2446516` | 329 cột, 26 hàng đầy đủ trong prefix; có DATE và cờ nguồn/QC; không thống kê cả năm |
| Bellinge sensor/rain ZIP [BECLEAN] [BERAIN] | **206**, các phần central directory và member, mỗi phần vài KiB | CSV sensor phút và TXT intensity mưa đã đọc thật; có cờ lỗi/NaN, không kiểm tra toàn bộ 390 MB |
| Metadata mưa VN [VNST] / ZIP [VNRAIN] | **200**, XLSX 38.726 byte; **206** ZIP directory | Có tên/trạng thái trạm Hà Nội; biết archive lồng ZIP/RAR; chưa đọc giá trị rainfall |
| Trung Trang–Hòn Dấu [VNRIVER] | **206**, prefix/central directory/XML chọn lọc | Ba sheet; water-level unit cm, hourly; chưa tính missing rate hoặc xác nhận Q unit |
| NASA POWER [PWQUERY] | **200**, JSON khoảng 3,3 KiB | API v2.10.3, nguồn MERRA2/POWER; 48 giá trị mỗi biến, không `-999` trong mẫu |
| IMERG CMR / dữ liệu HDF5 | CMR **200**, 1 metadata granule; HDF5 Range không auth **400** | Có granule và link tải gốc; **chưa đọc giá trị mưa** |
| CHIRPS [CHFILE] | HEAD **200**, `image/tiff`, 16.022.730 byte | File có thật; chưa lấy giá trị pixel Hà Nội |
| ERA5-Land CDS / GloFAS EWDS | Đọc catalog/form, chưa xác thực tải | **A**, chưa có subset nhị phân; không điền số record giả |
| GloFAS API [GFQUERY] | **200**, JSON | 3 mốc ngày 07–09/09/2021, đơn vị `m³/s`; chưa xác nhận liên hệ đúng sông/điểm pilot |

Các lỗi truy cập landing NASA GPM/GES DISC trong công cụ đọc trang không được dùng để kết luận dataset không tồn tại; CMR gốc vẫn trả metadata. Ngược lại, metadata thành công không được nâng thành “đã tải giá trị mưa”.
NCEI cũng đang thông báo di chuyển dữ liệu/cloud: giữ link khám phá gốc và tên trạm–năm bên cạnh link file; kiểm tra lại trước tải lớn. [N1] [N2]

## 10. Hợp đồng ghép feature–label và chống rò rỉ

1. **Cùng địa bàn + cùng thời kỳ:** depth NYC đi với weather NYC; depth pilot Hà Nội đi với weather Hà Nội. **Không ghép mưa Hà Nội với độ sâu NYC theo timestamp để huấn luyện “mô hình Hà Nội”.**
2. Hai ngày API mẫu 2024/2026 chỉ để kiểm tra; phải lấy đúng phần giao với nhãn thực. Mưa 1975–2006 không tạo được cặp với depth 2021 hoặc pilot mới.
3. Phân biệt `observed_at/valid_time`, `run/init_time`, `issued_at`, `received_at/available_at`; feature phải thực sự đã khả dụng trước quyết định `t`.
4. Reanalysis/IMERG Final/CHIRPS Final dùng thông tin hậu kỳ; Historical Forecast là chuỗi ghép; Single Runs có cả phần hindcast. Không đánh đồng các nguồn này thành dự báo nguyên bản đã nhận lúc `t`. [OM1] [OM2] [OM3] [IM1] [CH2]
5. Không nâng tần suất bằng nội suy hourly/daily rồi tuyên bố có ground truth 1 phút. Forward-fill feature cũ phải giữ tuổi dữ liệu; không forward-fill target để tạo nhãn ngập giả.
6. Mực nước trạm/cống cần mốc; lưu lượng cần đơn vị/kỳ tích lũy/quy ước dấu; rainfall cần phân biệt tổng trong khoảng và tốc độ. QC không được thay null/fill bằng “khô”.
7. Tách theo **sự kiện và thời gian**, giữ trạm liên quan trong cùng phía; purge cửa sổ nhãn 30 phút ở biên. Hai archive FloodNet chồng lấn không được chia thành train/test độc lập.
8. Không dùng `depth_proc_mm`/cleaned series làm feature online khi chưa kiểm tra tính nhân quả bộ lọc; có thể dùng nhãn hậu kiểm nhưng phải nói rõ mục tiêu đánh giá.
9. Lưu deployment/calibration/version; tính missing rate, số trận ngập, số ngày khô và độ bao phủ **sau tải/kiểm tra thật**. Báo cáo này chưa có các thống kê đó.
10. Đổi ngưỡng vận hành, tạo negative hoặc xếp rủi ro đoạn đường là thiết kế nhãn riêng; không suy tự động từ một tọa độ trạm hay một báo cáo người dân.

## 11. Bộ tối thiểu nên tải trước và phần còn thiếu

### A. Có thể bắt đầu huấn luyện thử ngay, phi thương mại

1. Đọc/lưu phiên bản [thỏa thuận FloodNet][FNL], rồi tải riêng [09/2021][FNCSV] để audit schema, deployment, QC và nhãn.
2. Khi pipeline đọc đúng, mở rộng [07/2021][FNJUL], [08/2021][FNAUG] và các tháng khác trong [record][FN1] để tìm nhiều sự kiện/train–validation–test; một trận cực đoan không đủ chứng minh tổng quát.
3. Khởi đầu bằng lịch sử depth; chưa cần tải weather hay cả kho 4,5 GB. Nếu thêm mưa, dùng vị trí/trạm NYC và thời kỳ overlap, giữ đúng vintage.
4. **Còn thiếu:** kiểm định causal của preprocessing, số trận độc lập, missing rate và chất lượng theo deployment; quyền phân phối trọng số/sản phẩm hoặc thương mại chưa được bảo đảm.
5. Nếu muốn cặp mưa–mực nước phút sẵn có: tải [Bellinge sensor][BECLEAN] + [gauge][BERAIN] đúng giấy phép phi thương mại; ghi rõ đang dự báo **trong mạng cống**, không độ sâu đường.

### B. Hà Nội: tải feature trước, thu hoặc xin target song song

1. Dùng Q1 để kiểm tra nhập CSV; cho backtest có forecast chọn Q3 hoặc tự lưu forecast từ ngày triển khai, kèm `available_at`.
2. Tải [GHCNh Hà Đông 2024][NPSV] nếu nhãn lịch sử cùng kỳ được cấp; nếu pilot 2026, khám phá lại năm/trạm hiện hành từ [nguồn gốc][N2], không ghép mặc định với file 2024.
3. Lắp/thu 1–3 trạm có mốc mặt đường, UTC, log thô/QC và đối soát thước; xin [HSDC][HN2] chuỗi quan trắc cùng địa bàn nếu có quyền.
4. **Còn thiếu quyết định:** nhãn độ sâu phút Hà Nội, mưa tại chỗ nếu cần, mốc lắp, quyền sử dụng, đủ sự kiện và overlap. Không thay nhãn này bằng ERA5, GloFAS, OSM hoặc biểu tượng bản đồ.
5. IMERG là bước bổ sung có điều kiện tài khoản/độ trễ; CHIRPS/POWER/mưa ngày VN chưa phải ưu tiên tải hàng loạt cho horizon 10–30 phút.

### C. Chỉ chọn nếu nghiên cứu thủy văn sông/cửa sông

Tải [XLSX Trung Trang–Hòn Dấu][VNRIVER], xác nhận mốc/múi giờ/đơn vị Q và đánh giá bước giờ; ghép mưa của lưu vực liên quan, không chỉ một điểm mưa Hà Nội tùy tiện.
[GloFAS gốc][GF1] dùng cho đối chứng/tiền huấn luyện lưu lượng **mô hình** ở bước ngày, không thay quan trắc hoặc suy trực tiếp thành cm mặt đường.
**Còn thiếu:** nhiệm vụ/lead time thủy văn riêng, QC trạm, thuộc tính lưu vực và nhãn quan trắc độc lập để đánh giá mô phỏng.

### GIS tĩnh và nguồn không chọn làm nhãn chính

- [OpenStreetMap/Geofabrik Việt Nam][OSM] có đường để ánh xạ trạm/sự kiện, theo ODbL; **không cung cấp nhãn độ sâu/thời gian ngập**.
- [Copernicus DEM][DEM] là địa hình/DSM hỗ trợ đặc trưng và khảo sát, không phải cm ngập đường; không lấy độ phân giải/cao độ lưới làm mốc cảm biến chính xác centimet.
- CAMELS/Caravan hoặc catalog lưu lượng sông hữu ích cho hydrology nhưng không lấp chỗ trống street-depth phút; không ưu tiên tải thêm khi FloodNet/Bellinge đã phù hợp hơn cho kiểm thử chuỗi.
- Bộ ảnh vệ tinh/UAV có mask ngập không thay được chuỗi depth tại trạm. Bài báo chỉ ghi “data available on request” không được xếp vào nhóm đã tải được.

## 12. Liên kết nguồn sơ cấp

Các mã dưới đây là liên kết tới đơn vị tạo/phát hành dữ liệu, tài liệu/API chính chủ hoặc record do tác giả công bố. Không dùng bài tổng hợp/Kaggle không rõ provenance để xác nhận quyền hoặc độ phân giải.

- **NYU/CUNY:** [FloodNet archive 2023][FN1], [FloodSense v2][FN2], [thỏa thuận sử dụng][FNL].
- **HSDC Hà Nội:** [bản đồ úng ngập][HN1], [đầu mối/chính sách HSDC Maps][HN2].
- **DTU/VCS và tác giả:** [Bellinge collection][BECOLL], [bài mô tả dữ liệu][BE1]; từng item có license riêng.
- **Open-Meteo:** [Historical Weather][OM1], [Historical Forecast][OM2], [Single Runs][OM3], [license dữ liệu][OML] và [Terms dịch vụ][OMT].
- **NOAA NCEI:** [GHCNh mới][N2], [ISD cũ][N1], [XML xác nhận CC0 của GHCNh][NLIC].
- **NASA/GES DISC:** [IMERG technical documentation][IM1], [CMR catalog][IM2], [metadata điều kiện sử dụng][IMRIGHT].
- **World Bank/ENERGYDATA:** [mưa 172 trạm Việt Nam và provenance][VN1].
- **Pénicaud / Zenodo:** [mực nước và lưu lượng Trung Trang–Hòn Dấu][VN2].
- **UCSB Climate Hazards Center:** [CHIRPS v3][CH1], [quy ước dữ liệu daily][CH2].
- **Copernicus/ECMWF:** [ERA5-Land catalog][ER1], [tài liệu ERA5-Land][ER2], [đăng ký và gọi CDS API][CDSAPI].
- **NASA POWER:** [Hourly API][PW1], [FAQ độ trễ][PW2], [hướng dẫn trích dẫn][PW3].
- **CEMS/ECMWF:** [GloFAS historical gốc][GF1], [đường tải EWDS][GFDOWNLOAD]; [Open-Meteo Flood][GF2] là giao diện khác, không thay thế metadata/version gốc.
- **Qin / Zenodo:** [sự kiện ngập theo đoạn đường NYC][EV1], chưa hoàn tất rà quyền upstream.
- **GIS phụ trợ:** [Geofabrik/OSM Việt Nam][OSM], [Copernicus DEM][DEM]; không phải nguồn nhãn ngập.

[FN1]: https://zenodo.org/records/10211443
[FNCSV]: https://zenodo.org/records/10211443/files/floodnet-flood-sensor-sep-2021.csv?download=1
[FNJUL]: https://zenodo.org/records/10211443/files/floodnet-flood-sensor-jul-2021.csv?download=1
[FNAUG]: https://zenodo.org/records/10211443/files/floodnet-flood-sensor-aug-2021.csv?download=1
[FNL]: https://docs.google.com/document/d/1jd5Q2UYj_0PwMRplFISmhT6LswpS08D9/export?format=txt
[FN2]: https://zenodo.org/records/7245376
[FN2META]: https://zenodo.org/records/7245376/files/metadata.csv?download=1
[FN2CSV]: https://zenodo.org/records/7245376/files/FloodNet-data-export.csv?download=1
[HN1]: https://thoatnuochanoi.vn/ungngap
[HN2]: https://thoatnuochanoi.vn/policy
[HNJS]: https://thoatnuochanoi.vn/ungngap/js/index.js
[HNAPI]: https://thoatnuochanoi.vn/ungngap/api/flood/getflood
[OM1]: https://open-meteo.com/en/docs/historical-weather-api
[OM2]: https://open-meteo.com/en/docs/historical-forecast-api
[OM3]: https://open-meteo.com/en/docs/single-runs-api
[OML]: https://open-meteo.com/en/licence
[OMT]: https://open-meteo.com/en/terms
[BE1]: https://essd.copernicus.org/articles/13/4779/2021/
[BECOLL]: https://doi.org/10.11583/DTU.c.5029124
[BE2]: https://api.figshare.com/v2/articles/12509249
[BE3]: https://api.figshare.com/v2/articles/12509774
[BE4]: https://api.figshare.com/v2/articles/12513236
[BECLEAN]: https://ndownloader.figshare.com/files/30592524
[BERAIN]: https://ndownloader.figshare.com/files/30592644
[N1]: https://www.ncei.noaa.gov/products/land-based-station/integrated-surface-database
[N2]: https://www.ncei.noaa.gov/products/global-historical-climatology-network-hourly
[NLIC]: https://www.ncei.noaa.gov/metadata/geoportal/rest/metadata/item/gov.noaa.ncdc:C01688/xml
[NOLD]: https://www.ncei.noaa.gov/metadata/geoportal/rest/metadata/item/gov.noaa.ncdc:C00532/html
[NFORMAT]: https://www.ncei.noaa.gov/pub/data/noaa/isd-format-document.pdf
[NSTATIONS]: https://www.ncei.noaa.gov/oa/global-historical-climatology-network/hourly/doc/ghcnh-station-list.txt
[NPSV]: https://www.ncei.noaa.gov/oa/global-historical-climatology-network/hourly/access/by-year/2024/psv/GHCNh_VMM00048825_2024.psv
[NISDCSV]: https://www.ncei.noaa.gov/data/global-hourly/access/2024/48825099999.csv
[VN1]: https://energydata.info/dataset/rainfall-data-from-172-weather-stations-in-vietnam
[VNST]: https://datacatalogfiles.worldbank.org/ddh-published/0039854/DR0049607/meteostationvn.xlsx
[VNRAIN]: https://datacatalogfiles.worldbank.org/ddh-published/0039854/DR0049608/all_rainfall_data_by_location.zip
[VN2]: https://zenodo.org/records/13283821
[VNRIVER]: https://zenodo.org/records/13283821/files/Data_2021-2022.xlsx?download=1
[IM1]: https://gpm.nasa.gov/resources/documents/imerg-v07-technical-documentation
[IM2]: https://cmr.earthdata.nasa.gov/search/collections.json?short_name=GPM_3IMERGHH&version=07&page_size=2
[IMRIGHT]: https://cmr.earthdata.nasa.gov/search/concepts/C2723754847-GES_DISC.umm_json
[IMSEARCH]: https://search.earthdata.nasa.gov/search/granules?p=C2723754847-GES_DISC
[IMQUERY]: https://cmr.earthdata.nasa.gov/search/granules.json?collection_concept_id=C2723754847-GES_DISC&temporal=2024-09-07T00:00:00Z,2024-09-07T00:29:59Z&page_size=1
[IMFILE]: https://data.gesdisc.earthdata.nasa.gov/data/GPM_L3/GPM_3IMERGHH.07/2024/251/3B-HHR.MS.MRG.3IMERG.20240907-S000000-E002959.0000.V07B.HDF5
[NASAL]: https://www.earthdata.nasa.gov/engage/open-data-services-software-policies/data-use-guidance
[CH1]: https://www.chc.ucsb.edu/data/chirps3
[CH2]: https://data.chc.ucsb.edu/products/CHIRPS/v3.0/daily/readme.txt
[CH3]: https://www.chc.ucsb.edu/data/chirps
[CHDIR]: https://data.chc.ucsb.edu/products/CHIRPS/v3.0/daily/final/sat/2024/
[CHFILE]: https://data.chc.ucsb.edu/products/CHIRPS/v3.0/daily/final/sat/2024/chirps-v3.0.sat.2024.09.07.tif
[ER1]: https://cds.climate.copernicus.eu/datasets/reanalysis-era5-land?tab=overview
[ER2]: https://confluence.ecmwf.int/pages/viewpage.action?pageId=505384848
[ER3]: https://confluence.ecmwf.int/spaces/CKB/pages/536218894/ERA5-Land+hourly+Analysis+Ready+Cloud+Optimised+ARCO+data+on+single+levels+from+1950+to+present+Product+User+Guide+PUG
[ERDOWNLOAD]: https://cds.climate.copernicus.eu/datasets/reanalysis-era5-land?tab=download
[CDSAPI]: https://cds.climate.copernicus.eu/how-to-api
[PW1]: https://power.larc.nasa.gov/docs/services/api/temporal/hourly/
[PW2]: https://power.larc.nasa.gov/docs/faqs/data/
[PW3]: https://power.larc.nasa.gov/docs/referencing/
[PW4]: https://power.larc.nasa.gov/docs/tutorials/service-data-request/api/
[PWQUERY]: https://power.larc.nasa.gov/api/temporal/hourly/point?parameters=PRECTOTCORR,T2M,RH2M&community=AG&longitude=105.8542&latitude=21.0285&start=20240907&end=20240908&format=JSON&time-standard=UTC
[GF1]: https://ewds.climate.copernicus.eu/datasets/cems-glofas-historical?tab=overview
[GF2]: https://open-meteo.com/en/docs/flood-api
[GFDOWNLOAD]: https://ewds.climate.copernicus.eu/datasets/cems-glofas-historical?tab=download
[GFQUERY]: https://flood-api.open-meteo.com/v1/flood?latitude=21.0285&longitude=105.8542&start_date=2021-09-07&end_date=2021-09-09&daily=river_discharge&timezone=GMT
[EV1]: https://zenodo.org/records/18062104
[EVCSV]: https://zenodo.org/records/18062104/files/nyc_merged.csv?download=1
[OSM]: https://download.geofabrik.de/asia/vietnam.html
[DEM]: https://dataspace.copernicus.eu/explore-data/data-collections/copernicus-contributing-missions/collections-description/COP-DEM
