---
description: "AI usage logging is fully automatic — do NOT call any log_* script manually"
activation: always-on
---

# AI Usage Logging — Automatic

Logging prompt vào `.ai-log/session.jsonl` đã được **tự động hoá hoàn toàn**. Bạn (AI agent) **KHÔNG** cần — và **KHÔNG** nên — chạy bất kỳ lệnh logging nào sau mỗi task.

## Cơ chế

Khi student `git push`:
1. Hook `Stop` và pre-push chạy `scripts/log_antigravity.py --auto`, đọc transcript của Antigravity CLI/IDE từ các thư mục hiện hành trong `~/.gemini/` và sweep prompt (`USER_INPUT` + `USER_EXPLICIT`) thuộc repo hiện tại trong 24 giờ gần nhất.
2. Pre-push hook chạy `scripts/submit_log.py`, đẩy `.ai-log/session.jsonl` lên grading server.

Toàn bộ prompt user đã gõ trong Antigravity IDE/CLI được capture **nguyên văn từ disk**, không cần AI tự tóm tắt.

## Không làm những việc sau

- ❌ **KHÔNG** gọi bất kỳ script log nào sau mỗi task; hook tự thu thập prompt thật.
- ❌ **KHÔNG** chạy `scripts/log_manual.py` cho tool đã có hook; script này chỉ dành cho web tool.
- ❌ **KHÔNG** sửa hoặc xoá file trong `.ai-log/` — chúng được pre-push hook và submit script quản lý.

## Khi nào cần can thiệp

- Nếu pre-push hook báo lỗi → báo lại cho user, đừng tự ý bypass `--no-verify`.
- Với web tool không có lifecycle hook, dùng `.agents/workflows/log.md`.

## Cài đặt một lần sau khi clone repo

```bash
# Linux / macOS / Git Bash
bash scripts/setup_hooks.sh

# Windows PowerShell
powershell -ExecutionPolicy Bypass -File scripts\setup_hooks.ps1
```
