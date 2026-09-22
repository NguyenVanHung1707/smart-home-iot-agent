import { SectionHeading } from "../shared/SectionHeading";

function Rows({ items }: { items: Array<[string, string]> }) {
  return (
    <div className="hm-rows">
      {items.map(([label, value]) => (
        <p key={label}>
          <span>{label}</span>
          <b>{value}</b>
        </p>
      ))}
    </div>
  );
}

export function PerformancePage() {
  return (
    <section className="hm-admin-page" aria-label="Hiệu năng hệ thống">
      <SectionHeading eyebrow="Edge Node Diagnostics" title="Hiệu năng vận hành Hub" />
      <p className="hm-page-intro">
        Các chỉ số tài nguyên phần cứng và độ trễ xử lý AI / MQTT tại chỗ trên thiết bị Raspberry Pi 4.
      </p>
      <div className="hm-two-grid">
        <div className="hm-panel">
          <h3 className="hm-panel-title">Phần cứng & Bộ nhớ</h3>
          <Rows
            items={[
              ["Thiết bị", "Raspberry Pi 4 Model B"],
              ["Kiến trúc", "ARM Cortex-A72 @ 1.8GHz"],
              ["Nhiệt độ CPU", "61.2°C (An toàn)"],
              ["Bộ nhớ RAM", "2.8 GB / 3.8 GB"],
              ["Bộ nhớ Swap", "0 MB (Không phân mảnh)"],
              ["Lưu trữ SD/SSD", "14.2 GB / 64 GB"],
            ]}
          />
        </div>
        <div className="hm-panel">
          <h3 className="hm-panel-title">Runtime & AI Pipeline</h3>
          <Rows
            items={[
              ["LLM Engine", "Llama.cpp · Qwen 2.5 1.5B Q4_K_M"],
              ["STT Model", "Sherpa ONNX Zipformer 80M INT8"],
              ["VAD Backend", "Silero VAD / Energy Filter (Local)"],
              ["TTS Engine", "Piper TTS (Giọng tiếng Việt)"],
              ["MQTT Latency", "Median 110ms · P99 240ms"],
              ["Sự cố OOM", "0 sự cố"],
            ]}
          />
        </div>
      </div>
    </section>
  );
}
