import { useEffect, useMemo, useState } from "react";
import { recentCommands } from "../data/mockHome";
import type { DataMode, HistoryItem, Role } from "../types";
import { formatTime, historyStorageKey } from "../utils";
import { createId } from "../utils/id";

const maxHistoryItems = 30;

function isHistoryItem(item: unknown): item is HistoryItem {
  if (!item || typeof item !== "object") return false;
  const candidate = item as Partial<HistoryItem>;
  return (
    typeof candidate.id === "string" &&
    ["done", "pending", "declined"].includes(candidate.status ?? "") &&
    typeof candidate.command === "string" &&
    typeof candidate.result === "string" &&
    typeof candidate.time === "string"
  );
}

function readHistory(key: string) {
  try {
    const raw = localStorage.getItem(key);
    if (!raw) return recentCommands;
    const parsed = JSON.parse(raw);
    return Array.isArray(parsed) ? parsed.filter(isHistoryItem).slice(0, maxHistoryItems) : recentCommands;
  } catch {
    return recentCommands;
  }
}

export function useHistoryStorage(role: Role, dataMode: DataMode = "simulator") {
  const storageKey = useMemo(() => historyStorageKey(role, dataMode), [role, dataMode]);
  const [history, setHistory] = useState<HistoryItem[]>(() => readHistory(storageKey));

  useEffect(() => {
    setHistory(readHistory(storageKey));
  }, [storageKey]);

  useEffect(() => {
    localStorage.setItem(storageKey, JSON.stringify(history.slice(0, maxHistoryItems)));
  }, [history, storageKey]);

  function addHistory(
    message: string,
    result = "Đã ghi nhận và xử lý yêu cầu tại HomeMind Hub.",
    status: HistoryItem["status"] = "done",
  ) {
    const clean = message.trim();
    if (!clean) return;
    const item: HistoryItem = {
      id: createId("h"),
      status,
      command: clean.startsWith("“") ? clean : `“${clean}”`,
      result,
      time: formatTime(),
    };
    setHistory((current) => [item, ...current].slice(0, maxHistoryItems));
  }

  return { history, addHistory };
}
