import type { IconName } from "../../types";

export interface LandingStat {
  value: string;
  label: string;
}

export const landingStats: LandingStat[] = [
  { value: "An toàn", label: "Xác nhận trước các thao tác nhạy cảm" },
  { value: "Riêng tư", label: "Dữ liệu luôn ở trong nhà" },
  { value: "Tiện lợi", label: "Một nơi điều khiển nhiều thiết bị" },
  { value: "Thông minh", label: "Hiểu yêu cầu, tự lập kế hoạch" },
];

/** Id của thiết bị trên sơ đồ mạch ở section "Một câu nói, nhiều việc được làm". */
export type LandingDeviceId = "bulb" | "ac" | "fan" | "curtain" | "door" | "sensor";

export interface LandingFlowDevice {
  id: LandingDeviceId;
  label: string;
  icon: IconName;
}

/** Thứ tự trong mảng cũng là thứ tự cột thiết bị nối vào mic bằng dây mạch. */
export const landingFlowDevices: LandingFlowDevice[] = [
  { id: "bulb", label: "Đèn", icon: "bulb" },
  { id: "ac", label: "Điều hòa", icon: "ac" },
  { id: "fan", label: "Quạt", icon: "fan" },
  { id: "curtain", label: "Rèm", icon: "sunrise" },
  { id: "door", label: "Cửa", icon: "lock" },
  { id: "sensor", label: "Cảm biến", icon: "thermo" },
];

export interface LandingCommand {
  say: string;
  reply: string;
  icon: IconName;
  /** Thiết bị được câu lệnh này chạm tới; dây mạch tương ứng sẽ sáng lên. */
  targets: LandingDeviceId[];
}

export const landingCommands: LandingCommand[] = [
  {
    say: "Tắt hết đèn và chỉnh điều hòa phòng khách 24 độ",
    reply: "Đã tắt 6 đèn và đặt điều hòa phòng khách ở 24°C.",
    icon: "bulb",
    targets: ["bulb", "ac"],
  },
  {
    say: "Mở rèm phòng ngủ rồi bật quạt lên mức 2",
    reply: "Đã mở rèm phòng ngủ và đặt quạt ở mức 2.",
    icon: "fan",
    targets: ["curtain", "fan"],
  },
  {
    say: "Mở khóa cửa trước",
    reply: "Tác vụ an ninh cần mã PIN. Vui lòng xác thực để tiếp tục.",
    icon: "lock",
    targets: ["door"],
  },
  {
    say: "Trong nhà có chỗ nào đang nóng không?",
    reply: "Phòng bếp đang 31°C, cao nhất trong nhà. Bạn có muốn bật quạt bếp?",
    icon: "thermo",
    targets: ["sensor", "fan"],
  },
];

export interface LandingPipelineStep {
  step: string;
  title: string;
  detail: string;
  icon: IconName;
}

export const landingPipeline: LandingPipelineStep[] = [
  {
    step: "01",
    title: "Lắng nghe",
    detail:
      "HomeMind nhận câu lệnh bằng tiếng Việt một cách tự nhiên, không cần ghi nhớ cú pháp hay thao tác phức tạp.",
    icon: "mic",
  },
  {
    step: "02",
    title: "Hiểu & suy luận",
    detail:
      "Hệ thống tự phân tích điều bạn muốn, chia nhỏ các bước cần làm và hỏi lại khi thông tin chưa rõ.",
    icon: "cpu",
  },
  {
    step: "03",
    title: "Thực thi & trả lời",
    detail:
      "HomeMind điều khiển các thiết bị phù hợp, xác nhận các thao tác quan trọng và thông báo lại khi hoàn tất.",
    icon: "sparkles",
  },
];

export interface LandingFeature {
  title: string;
  detail: string;
  icon: IconName;
}

export const landingSecurity: LandingFeature[] = [
  {
    title: "Bảo mật an toàn",
    detail: "Xác nhận an toàn trước các thao tác bảo mật",
    icon: "lock",
  },
  {
    title: "Phê duyệt thao tác",
    detail: "Yêu cầu nhạy cảm cần được chủ nhà xác nhận.",
    icon: "shield",
  },
  {
    title: "Cảnh báo bất thường",
    detail: "Phát hiện và thông báo khi có thao tác đáng ngờ.",
    icon: "check",
  },
  {
    title: "Nhật ký hoạt động",
    detail: "Mọi thao tác đều được ghi lại để dễ kiểm tra.",
    icon: "list",
  },
];

export interface LandingFaq {
  question: string;
  answer: string;
}

export const landingFaqs: LandingFaq[] = [
  {
    question: "Hệ thống có cần internet để hoạt động không?",
    answer:
      "Không. Nhận diện giọng nói, suy luận và tổng hợp giọng nói đều chạy trong Hub tại nhà. Mất internet thì việc điều khiển thiết bị vẫn hoạt động bình thường.",
  },
  {
    question: "Có cần card đồ họa rời không?",
    answer:
      "Không. Zipformer bản lượng tử hóa int8 chỉ dùng khoảng 150MB RAM và chạy trên CPU. Một máy mini PC hoặc Raspberry Pi đủ mạnh là đủ.",
  },
  {
    question: "Nếu chưa có ESP32 thì thử được không?",
    answer:
      "Được. Dự án kèm Device Simulator mô phỏng đầy đủ thiết bị qua MQTT, bao gồm cả các tình huống lỗi như thiết bị offline hay timeout.",
  },
  {
    question: "Ra lệnh nhiều việc một lúc có được không?",
    answer:
      "Được. Agent tách câu ghép thành nhiều hành động, ví dụ \"tắt hết đèn và chỉnh điều hòa phòng khách 24 độ\", và hỏi lại khi câu lệnh còn thiếu thông tin.",
  },
  {
    question: "Giọng nói có mở được cửa nhà tôi không?",
    answer:
      "Không mở trực tiếp. Tác vụ an ninh luôn phải qua mã PIN hoặc được chủ nhà phê duyệt trên giao diện trước khi Hub phát lệnh.",
  },
  {
    question: "Làm sao để có tài khoản?",
    answer:
      "Chủ nhà cài đặt Hub sẽ có tài khoản quản trị đầu tiên, sau đó tạo tài khoản cho từng thành viên trong gia đình từ mục Cài đặt.",
  },
];
