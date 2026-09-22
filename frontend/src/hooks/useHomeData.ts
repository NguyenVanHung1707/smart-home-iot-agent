import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { approvalsToUi, devicesToRooms, eventsToActivity, roomId, roomIcon } from "../api/adapters";
import {
  apiFetch,
  createDevice as backendCreateDevice,
  decideApproval as backendDecideApproval,
  deleteDevice as backendDeleteDevice,
  deleteRoom as backendDeleteRoom,
  dismissDiscoveredDevice as backendDismissDiscoveredDevice,
  getDiscoveredDevices as backendGetDiscoveredDevices,
  getVoiceStatus,
  pairDiscoveredDevice as backendPairDiscoveredDevice,
  renameRoom as backendRenameRoom,
  sendDeviceCommand as sendBackendDeviceCommand,
  setSimulatorFault as backendSetSimulatorFault,
  triggerDiscoveryScan as backendTriggerDiscoveryScan,
  updateDevice as backendUpdateDevice,
} from "../api/client";
import type {
  ApiApproval,
  ApiDevice,
  ApiDeviceCommand,
  ApiSimulatorEvent,
  VoiceStatus,
} from "../api/types";
import type {
  ActivityItem,
  AppNotification,
  Approval,
  CreateDevicePayload,
  DataMode,
  Device,
  DiscoveredDevice,
  Role,
  Room,
  UpdateDevicePayload,
} from "../types";
import { createId } from "../utils/id";

const pollMs = 3000;
const voiceStatusPollMs = 10000;

export interface ActiveToast {
  id: string;
  type: "error" | "success" | "info";
  message: string;
}

export function useHomeData(role: Role = "homeadmin") {
  const [dataMode, setDataModeState] = useState<DataMode>(() => {
    if (typeof window === "undefined") return "simulator";
    const saved = localStorage.getItem("homemind-data-mode");
    return saved === "real" ? "real" : "simulator";
  });

  const [liveDevices, setLiveDevices] = useState<ApiDevice[]>([]);
  const [liveApprovals, setLiveApprovals] = useState<ApiApproval[]>([]);
  const [liveEvents, setLiveEvents] = useState<ApiSimulatorEvent[]>([]);
  const [liveDiscovered, setLiveDiscovered] = useState<DiscoveredDevice[]>([]);
  const [notificationsByMode, setNotificationsByMode] = useState<Record<DataMode, AppNotification[]>>({
    simulator: [],
    real: [],
  });
  const [activeToast, setActiveToast] = useState<ActiveToast | null>(null);

  const readCustomRoomsForMode = (mode: DataMode) => {
    if (typeof window === "undefined") return [];
    try {
      const saved = localStorage.getItem(`homemind-${mode}-custom-rooms`) || localStorage.getItem("homemind-custom-rooms");
      return saved ? JSON.parse(saved) : [];
    } catch {
      return [];
    }
  };

  const [customRooms, setCustomRooms] = useState<Array<{ name: string; icon: import("../types").IconName }>>(() => {
    return readCustomRoomsForMode(dataMode);
  });

  const saveCustomRooms = (newRooms: Array<{ name: string; icon: import("../types").IconName }>) => {
    setCustomRooms(newRooms);
    if (typeof window !== "undefined") {
      localStorage.setItem(`homemind-${dataMode}-custom-rooms`, JSON.stringify(newRooms));
    }
  };

  const [voiceStatus, setVoiceStatus] = useState<VoiceStatus | null>({
    enabled: true,
    ready: true,
    stt: { ready: true, model: "Zipformer-vi", vad: true },
    tts: { ready: true, voice: "Piper-vi" },
  });

  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  const isUsingFallback = false;

  const prevOnlineMapRef = useRef<Map<string, boolean>>(new Map());
  const prevDiscoveredSetRef = useRef<Set<string>>(new Set());
  const prevPendingApprovalsRef = useRef<Set<string>>(new Set());
  const hasInitialRunRef = useRef(false);

  const notifications = notificationsByMode[dataMode] || [];

  const setDataMode = (mode: DataMode) => {
    setDataModeState(mode);
    setCustomRooms(readCustomRoomsForMode(mode));
    if (typeof window !== "undefined") {
      localStorage.setItem("homemind-data-mode", mode);
    }
  };

  const rawDevices = liveDevices;
  const rawApprovals = liveApprovals;
  const rawEvents = liveEvents;
  const discoveredDevices = liveDiscovered;

  const rooms: Room[] = useMemo(() => {
    const baseRooms = devicesToRooms(rawDevices);
    const existingNames = new Set(baseRooms.map((r) => r.name.toLowerCase()));
    const extraRooms: Room[] = [];
    for (const cr of customRooms) {
      if (!existingNames.has(cr.name.toLowerCase())) {
        extraRooms.push({
          id: roomId(cr.name),
          name: cr.name,
          icon: cr.icon || roomIcon(cr.name),
          summary: "Chưa có thiết bị",
          devices: [],
        });
      }
    }
    return [...baseRooms, ...extraRooms];
  }, [rawDevices, customRooms]);

  const approvals: Approval[] = useMemo(() => approvalsToUi(rawApprovals, rawDevices), [rawApprovals, rawDevices]);
  const activity: ActivityItem[] = useMemo(() => {
    return eventsToActivity(rawEvents, rawDevices);
  }, [rawEvents, rawDevices]);

  // Track device online/offline, new discovery, and security approval transitions for real-time notification
  useEffect(() => {
    if (!rawDevices.length && !rawApprovals.length) return;

    if (!hasInitialRunRef.current) {
      rawDevices.forEach((d) => prevOnlineMapRef.current.set(d.id, d.online));
      discoveredDevices.forEach((d) => prevDiscoveredSetRef.current.add(d.device_id));
      rawApprovals.filter((a) => a.status === "pending").forEach((a) => prevPendingApprovalsRef.current.add(a.id));
      hasInitialRunRef.current = true;
      return;
    }

    const newAlerts: AppNotification[] = [];
    const now = new Date();
    const timeStr = `${String(now.getHours()).padStart(2, "0")}:${String(now.getMinutes()).padStart(2, "0")}`;

    // 1. Check device online / offline transitions
    rawDevices.forEach((d) => {
      const prevOnline = prevOnlineMapRef.current.get(d.id);
      if (prevOnline === true && d.online === false) {
        newAlerts.push({
          id: createId("notif-off"),
          type: "offline",
          title: "Thiết bị mất kết nối",
          message: `${d.name} (${d.room}) đã bị ngắt tín hiệu.`,
          time: timeStr,
          timestamp: Date.now(),
          read: false,
          deviceId: d.id,
        });
      } else if (prevOnline === false && d.online === true) {
        newAlerts.push({
          id: createId("notif-on"),
          type: "online",
          title: "Khôi phục kết nối",
          message: `${d.name} (${d.room}) đã kết nối lại thành công.`,
          time: timeStr,
          timestamp: Date.now(),
          read: false,
          deviceId: d.id,
        });
      }
      prevOnlineMapRef.current.set(d.id, d.online);
    });

    // 2. Check new discovered devices
    discoveredDevices.forEach((disc) => {
      if (!prevDiscoveredSetRef.current.has(disc.device_id)) {
        newAlerts.push({
          id: createId("notif-disc"),
          type: "discovery",
          title: "Phát hiện thiết bị MQTT mới",
          message: `Tìm thấy ${disc.name || disc.device_id} (${disc.room || "Chưa phân loại"}). Sẵn sàng ghép nối!`,
          time: timeStr,
          timestamp: Date.now(),
          read: false,
          deviceId: disc.device_id,
        });
        prevDiscoveredSetRef.current.add(disc.device_id);
      }
    });

    // 3. Check new pending security approvals (for admin)
    if (role === "homeadmin") {
      const currentPending = rawApprovals.filter((a) => a.status === "pending");
      const devMap = new Map(rawDevices.map((d) => [d.id, d.name]));
      currentPending.forEach((appr) => {
        if (!prevPendingApprovalsRef.current.has(appr.id)) {
          const devName = devMap.get(appr.device_id) || appr.device_id;
          const reqBy = appr.requested_by || "Thành viên nhà";
          const actionText = appr.command.action === "unlock" ? "mở khóa" : appr.command.action;
          newAlerts.push({
            id: createId("notif-appr"),
            type: "approval",
            title: "Yêu cầu an ninh mới",
            message: `${reqBy} vừa gửi yêu cầu ${actionText} "${devName}". Vui lòng phê duyệt!`,
            time: timeStr,
            timestamp: Date.now(),
            read: false,
            deviceId: appr.device_id,
          });
        }
      });
      prevPendingApprovalsRef.current = new Set(currentPending.map((a) => a.id));
    }

    if (newAlerts.length > 0) {
      setNotificationsByMode((prev) => ({
        ...prev,
        [dataMode]: [...newAlerts, ...(prev[dataMode] || [])].slice(0, 40),
      }));
      const first = newAlerts[0];
      setActiveToast({
        id: first.id,
        type: first.type === "offline" ? "error" : first.type === "online" ? "success" : "info",
        message: `${first.title}: ${first.message}`,
      });
    }
  }, [rawDevices, discoveredDevices, rawApprovals, role, dataMode]);

  // Auto-dismiss active toast after 5s
  useEffect(() => {
    if (!activeToast) return;
    const t = window.setTimeout(() => setActiveToast(null), 5000);
    return () => window.clearTimeout(t);
  }, [activeToast]);

  const refreshVoiceStatus = useCallback(async () => {
    try {
      const status = await getVoiceStatus();
      setVoiceStatus(status);
    } catch {
      setVoiceStatus(null);
    }
  }, []);

  const refresh = useCallback(async ({ silent = false }: { silent?: boolean } = {}) => {
    if (!silent) setLoading(true);
    try {
      const [devs, apprs, evts, disc] = await Promise.all([
        apiFetch<ApiDevice[]>("/devices"),
        apiFetch<ApiApproval[]>("/approvals"),
        role === "homeadmin" ? apiFetch<ApiSimulatorEvent[]>("/simulator/events") : Promise.resolve([]),
        role === "homeadmin" ? backendGetDiscoveredDevices().catch(() => [] as DiscoveredDevice[]) : Promise.resolve([]),
      ]);
      setLiveDevices(devs);
      setLiveApprovals(apprs);
      setLiveEvents(evts);
      setLiveDiscovered(disc || []);
      setError("");
    } catch (caught) {
      const msg = caught instanceof Error ? caught.message : "Không tải được dữ liệu từ Hub.";
      setError(msg);
    } finally {
      if (!silent) setLoading(false);
    }
  }, [role]);

  useEffect(() => {
    void refresh();
    void refreshVoiceStatus();
    const timer = window.setInterval(() => {
      if (typeof document !== "undefined" && document.hidden) return;
      void refresh({ silent: true });
    }, pollMs);
    const vTimer = window.setInterval(() => {
      if (typeof document !== "undefined" && document.hidden) return;
      void refreshVoiceStatus();
    }, voiceStatusPollMs);
    return () => {
      window.clearInterval(timer);
      window.clearInterval(vTimer);
    };
  }, [refresh, refreshVoiceStatus]);

  useEffect(() => {
    hasInitialRunRef.current = false;
    prevOnlineMapRef.current.clear();
    prevDiscoveredSetRef.current.clear();
    prevPendingApprovalsRef.current.clear();
    setActiveToast(null);
    void refresh();
  }, [dataMode, refresh]);

  async function decideApproval(id: string, decision: "approve" | "reject") {
    await backendDecideApproval(id, decision);
    await refresh({ silent: true });
  }

  async function sendDeviceCommand(device: Device, command: ApiDeviceCommand, pin?: string) {
    await sendBackendDeviceCommand(device.id, command, pin);
    await refresh({ silent: true });
  }

  async function addDevice(payload: CreateDevicePayload) {
    await backendCreateDevice(payload);
    await refresh({ silent: true });
  }

  async function deleteDevice(deviceId: string) {
    await backendDeleteDevice(deviceId);
    await refresh({ silent: true });
  }

  async function updateDevice(deviceId: string, payload: UpdateDevicePayload) {
    await backendUpdateDevice(deviceId, payload);
    await refresh({ silent: true });
  }

  async function pairDiscoveredDevice(deviceId: string, name?: string, room?: string) {
    await backendPairDiscoveredDevice(deviceId, { name, room });
    await refresh({ silent: true });
  }

  async function dismissDiscoveredDevice(deviceId: string) {
    await backendDismissDiscoveredDevice(deviceId);
    await refresh({ silent: true });
  }

  async function setSimulatorFault(deviceId: string, mode: "none" | "offline" | "timeout") {
    await backendSetSimulatorFault(deviceId, mode);
    await refresh({ silent: true });
  }

  async function renameRoom(oldName: string, newName: string) {
    const cleanNew = newName.trim();
    if (!cleanNew || cleanNew.toLowerCase() === oldName.toLowerCase()) return;

    await backendRenameRoom(oldName, cleanNew);
    await refresh({ silent: true });

    // Update custom rooms list if it was a custom room
    const updatedCustom = customRooms.map((cr) =>
      cr.name.toLowerCase() === oldName.toLowerCase() ? { ...cr, name: cleanNew } : cr,
    );
    saveCustomRooms(updatedCustom);
  }

  async function deleteRoom(roomName: string) {
    const clean = roomName.trim();
    if (!clean) return;

    await backendDeleteRoom(clean);

    const updatedCustom = customRooms.filter((cr) => cr.name.toLowerCase() !== clean.toLowerCase());
    saveCustomRooms(updatedCustom);

    await refresh({ silent: true });
  }

  async function addRoom(name: string, icon: import("../types").IconName = "house", deviceIds: string[] = []) {
    const cleanName = name.trim();
    if (!cleanName) return;

    if (deviceIds.length > 0) {
      for (const devId of deviceIds) {
        await backendUpdateDevice(devId, { room: cleanName });
      }
      await refresh({ silent: true });
    }

    // Register into custom rooms
    if (!customRooms.some((cr) => cr.name.toLowerCase() === cleanName.toLowerCase())) {
      saveCustomRooms([...customRooms, { name: cleanName, icon }]);
    }
  }

  async function scanDevices() {
    await backendTriggerDiscoveryScan();
    await refresh({ silent: true });
    setTimeout(() => void refresh({ silent: true }), 600);
    setTimeout(() => void refresh({ silent: true }), 1500);
  }

  function markAllNotificationsRead() {
    setNotificationsByMode((prev) => ({
      ...prev,
      [dataMode]: (prev[dataMode] || []).map((n) => ({ ...n, read: true })),
    }));
  }

  function clearNotifications() {
    setNotificationsByMode((prev) => ({
      ...prev,
      [dataMode]: [],
    }));
  }

  function dismissNotification(id: string) {
    setNotificationsByMode((prev) => ({
      ...prev,
      [dataMode]: (prev[dataMode] || []).filter((n) => n.id !== id),
    }));
  }

  function dismissToast() {
    setActiveToast(null);
  }

  const unreadNotificationsCount = useMemo(
    () => notifications.filter((n) => !n.read).length,
    [notifications],
  );

  const pendingApprovalsCount = useMemo(
    () => rawApprovals.filter((item) => item.status === "pending").length,
    [rawApprovals],
  );

  const notificationCount = unreadNotificationsCount + pendingApprovalsCount;

  return {
    rawDevices,
    rooms,
    approvals,
    activity,
    events: rawEvents,
    discoveredDevices,
    notifications,
    activeToast,
    unreadNotificationsCount,
    notificationCount,
    loading,
    error,
    isUsingFallback,
    dataMode,
    setDataMode,
    voiceStatus,
    refresh,
    decideApproval,
    sendDeviceCommand,
    addDevice,
    deleteDevice,
    updateDevice,
    renameRoom,
    deleteRoom,
    addRoom,
    scanDevices,
    pairDiscoveredDevice,
    dismissDiscoveredDevice,
    setSimulatorFault,
    markAllNotificationsRead,
    clearNotifications,
    dismissNotification,
    dismissToast,
  };
}
