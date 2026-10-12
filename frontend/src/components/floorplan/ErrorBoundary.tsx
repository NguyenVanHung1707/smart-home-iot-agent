import React, { Component, ErrorInfo, ReactNode } from "react";
import { AlertTriangle, RefreshCw, RotateCcw } from "lucide-react";

interface ErrorBoundaryProps {
  children: ReactNode;
  fallbackTitle?: string;
  onReset?: () => void;
}

interface ErrorBoundaryState {
  hasError: boolean;
  error: Error | null;
}

export class ErrorBoundary extends Component<ErrorBoundaryProps, ErrorBoundaryState> {
  public state: ErrorBoundaryState = {
    hasError: false,
    error: null,
  };

  public static getDerivedStateFromError(error: Error): ErrorBoundaryState {
    return { hasError: true, error };
  }

  public componentDidCatch(error: Error, errorInfo: ErrorInfo) {
    console.error("Uncaught error in Floorplan / 3D Viewer:", error, errorInfo);
  }

  public handleRetry = () => {
    this.setState({ hasError: false, error: null });
    if (this.props.onReset) {
      this.props.onReset();
    }
  };

  public render() {
    if (this.state.hasError) {
      return (
        <div
          style={{
            display: "flex",
            flexDirection: "column",
            alignItems: "center",
            justifyContent: "center",
            height: "100%",
            minHeight: "450px",
            width: "100%",
            padding: "2rem",
            textAlign: "center",
            background: "rgba(26, 34, 29, 0.96)",
            color: "#f5f2eb",
          }}
        >
          <div
            style={{
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              width: "56px",
              height: "56px",
              borderRadius: "50%",
              background: "rgba(239, 68, 68, 0.15)",
              color: "#ef4444",
              marginBottom: "1rem",
            }}
          >
            <AlertTriangle size={30} />
          </div>
          <h3 style={{ fontSize: "1.15rem", fontWeight: 700, marginBottom: "0.5rem" }}>
            {this.props.fallbackTitle || "Đã xảy ra sự cố khi hiển thị Mô hình 3D"}
          </h3>
          <p
            style={{
              color: "#94a39b",
              fontSize: "0.88rem",
              maxWidth: "480px",
              marginBottom: "1.5rem",
              lineHeight: 1.5,
            }}
          >
            {this.state.error?.message || "Không thể khởi tạo ngữ cảnh WebGL Three.js hoặc xảy ra lỗi tính toán kích thước phòng."}
          </p>
          <div style={{ display: "flex", gap: "0.75rem", flexWrap: "wrap", justifyContent: "center" }}>
            <button
              type="button"
              onClick={this.handleRetry}
              className="hm-btn hm-btn-primary"
              style={{
                display: "inline-flex",
                alignItems: "center",
                gap: "0.4rem",
                padding: "0.5rem 1.1rem",
                fontSize: "0.85rem",
              }}
            >
              <RefreshCw size={15} />
              <span>Thử lại</span>
            </button>
            {this.props.onReset && (
              <button
                type="button"
                onClick={this.props.onReset}
                className="hm-btn hm-btn-secondary"
                style={{
                  display: "inline-flex",
                  alignItems: "center",
                  gap: "0.4rem",
                  padding: "0.5rem 1.1rem",
                  fontSize: "0.85rem",
                }}
              >
                <RotateCcw size={15} />
                <span>Khôi phục mặc định</span>
              </button>
            )}
          </div>
        </div>
      );
    }

    return this.props.children;
  }
}
