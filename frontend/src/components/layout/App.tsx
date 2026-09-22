import { useRef, useState } from "react";
import type { ReactNode } from "react";
import { processVoice } from "../../api/client";
import type { ApiDeviceCommand } from "../../api/types";
import { roomsPerPage } from "../../data/mockHome";
import { useHistoryStorage } from "../../hooks/useHistoryStorage";
import { useHomeData } from "../../hooks/useHomeData";
import { usePresets } from "../../hooks/usePresets";
import { useVoiceRecognition } from "../../hooks/useVoiceRecognition";
import { adminNav, defaultPageByRole, isPageAllowedForRole, memberNav } from "../../navigation";
import type { ChatMessage, DataMode, Device, NavItem, Page, Role, Room, ThemeMode, VoiceMode } from "../../types";
import { assistantReply } from "../../utils";
import { createId } from "../../utils/id";
import { ActivityPage } from "../admin/ActivityPage";
import { ApprovalsPage } from "../admin/ApprovalsPage";
import { PerformancePage } from "../admin/PerformancePage";
import { SettingsPage } from "../admin/SettingsPage";
import { HistoryPage } from "../history/HistoryPage";
import { MqttPage } from "../mqtt/MqttPage";
import { PresetsPage } from "../rooms/PresetsPage";
import { RequestsPage } from "../requests/RequestsPage";
import { RoomsPage } from "../rooms/RoomsPage";
import { ModePinModal } from "../security/ModePinModal";
import { PinModal } from "../security/PinModal";
import { VoiceOverlay } from "../voice/VoiceOverlay";
import { NotificationCenterModal } from "./NotificationCenterModal";
import { PageShell } from "./PageShell";
import { Sidebar } from "./Sidebar";
import { TopGreeting } from "./TopGreeting";

export function App({
  role,
  userName,
  theme,
  onToggleTheme,
  onSignOut,
}: {
  role: Role;
  userName: string;
  theme: ThemeMode;
  onToggleTheme: () => void;
  onSignOut: () => void;
}) {
  return role === "homeadmin" ? (
    <HomeAdminApp theme={theme} onToggleTheme={onToggleTheme} userName={userName} onSignOut={onSignOut} />
  ) : (
    <MemberApp theme={theme} onToggleTheme={onToggleTheme} userName={userName} onSignOut={onSignOut} />
  );
}

function useHomeAppController(role: Role) {
  const [page, setPage] = useState<Page>(defaultPageByRole[role]);
  const [sidebarOpen, setSidebarOpen] = useState(() => (typeof window !== "undefined" ? window.innerWidth > 900 : true));
  const [roomPage, setRoomPage] = useState(0);
  const [selectedRoom, setSelectedRoom] = useState<Room | null>(null);
  const [selectedHistoryId, setSelectedHistoryId] = useState<string | null>(null);
  const [requestCancelled, setRequestCancelled] = useState(false);
  const [notifCenterOpen, setNotifCenterOpen] = useState(false);
  const [modePinModalOpen, setModePinModalOpen] = useState(false);

  const [pinModalOpen, setPinModalOpen] = useState(false);
  const [pinDevice, setPinDevice] = useState<Device | null>(null);

  const [command, setCommand] = useState("");
  const [chatCommand, setChatCommand] = useState("");
  const [voiceThreadsByMode, setVoiceThreadsByMode] = useState<Record<DataMode, ChatMessage[]>>({
    simulator: [],
    real: [],
  });
  const [chatsByMode, setChatsByMode] = useState<Record<DataMode, ChatMessage[]>>({
    simulator: [],
    real: [],
  });
  const [submittingVoice, setSubmittingVoice] = useState(false);
  const [actionError, setActionError] = useState("");
  const [actionNotice, setActionNotice] = useState("");

  const home = useHomeData(role);
  const presetState = usePresets(home.dataMode);
  const sessionIdsByModeRef = useRef<Record<DataMode, string | null>>({
    simulator: null,
    real: null,
  });
  const { history, addHistory } = useHistoryStorage(role, home.dataMode);

  const chat = chatsByMode[home.dataMode] || [];
  const voiceThread = voiceThreadsByMode[home.dataMode] || [];

  function appendChatMessage(mode: DataMode, ...newMsgs: ChatMessage[]) {
    setChatsByMode((cur) => ({
      ...cur,
      [mode]: [...(cur[mode] || []), ...newMsgs],
    }));
  }

  function appendVoiceMessage(mode: DataMode, ...newMsgs: ChatMessage[]) {
    setVoiceThreadsByMode((cur) => ({
      ...cur,
      [mode]: [...(cur[mode] || []), ...newMsgs],
    }));
  }

  const {
    voice,
    ttsEnabled,
    setTtsEnabled,
    speak,
    closeVoice,
    stopVoice,
    resetTranscript,
    toggleVoice,
  } = useVoiceRecognition();

  function notify(message: string) {
    setActionNotice(message);
    setTimeout(() => setActionNotice(""), 4000);
  }

  function navigate(next: Page) {
    if (isPageAllowedForRole(role, next)) {
      setPage(next);
      if (typeof window !== "undefined" && window.innerWidth <= 900) {
        setSidebarOpen(false);
      }
    }
  }

  async function submitCommand(message: string, source: "voice" | "manual" = "voice") {
    const clean = message.trim();
    if (!clean || submittingVoice) return;
    setSubmittingVoice(true);
    setActionError("");
    const currentMode = home.dataMode;

    try {
      if (home.isUsingFallback) {
        const replyText = assistantReply(clean);
        addHistory(clean, replyText);
        if (source === "voice") {
          appendVoiceMessage(
            currentMode,
            { id: createId("u"), role: "user", text: clean },
            { id: createId("a"), role: "assistant", text: replyText },
          );
        }
        if (ttsEnabled) {
          void speak(replyText);
        }
        return;
      }

      const currentSessionId = sessionIdsByModeRef.current[currentMode];
      const data = await processVoice(clean, currentSessionId);
      sessionIdsByModeRef.current[currentMode] = data.session_id;
      addHistory(clean, data.response || "Hub đã lập kế hoạch và thực thi.");

      if (source === "voice") {
        appendVoiceMessage(
          currentMode,
          { id: createId("u"), role: "user", text: clean },
          { id: createId("a"), role: "assistant", text: data.response || assistantReply(clean) },
        );
      }

      if (ttsEnabled && data.response) {
        void speak(data.response);
      }

      await home.refresh({ silent: true });
    } catch (caught) {
      const messageText = caught instanceof Error ? caught.message : "Không gửi được lệnh đến Hub.";
      setActionError(messageText);
      addHistory(clean, messageText, "declined");
      if (source === "voice") {
        appendVoiceMessage(
          currentMode,
          { id: createId("u"), role: "user", text: clean },
          { id: createId("a"), role: "assistant", text: messageText },
        );
      }
    } finally {
      setSubmittingVoice(false);
      setCommand("");
      stopVoice();
      resetTranscript();
    }
  }

  async function submitChatMessage(message: string) {
    const clean = message.trim();
    if (!clean || submittingVoice) return;
    setSubmittingVoice(true);
    setActionError("");
    const currentMode = home.dataMode;

    try {
      if (home.isUsingFallback) {
        const replyText = assistantReply(clean);
        appendChatMessage(
          currentMode,
          { id: createId("cu"), role: "user", text: clean },
          { id: createId("ca"), role: "assistant", text: replyText },
        );
        if (ttsEnabled) {
          void speak(replyText);
        }
        return;
      }

      const currentSessionId = sessionIdsByModeRef.current[currentMode];
      const data = await processVoice(clean, currentSessionId);
      sessionIdsByModeRef.current[currentMode] = data.session_id;
      appendChatMessage(
        currentMode,
        { id: createId("cu"), role: "user", text: clean },
        { id: createId("ca"), role: "assistant", text: data.response || assistantReply(clean) },
      );

      if (ttsEnabled && data.response) {
        void speak(data.response);
      }

      await home.refresh({ silent: true });
    } catch (caught) {
      const messageText = caught instanceof Error ? caught.message : "Không gửi được tin nhắn đến Hub.";
      setActionError(messageText);
      appendChatMessage(
        currentMode,
        { id: createId("cu"), role: "user", text: clean },
        { id: createId("ca"), role: "assistant", text: messageText },
      );
    } finally {
      setSubmittingVoice(false);
      setChatCommand("");
      stopVoice();
      resetTranscript();
    }
  }

  function currentSubmitter(mode = voice.mode) {
    return mode === "chat"
      ? submitChatMessage
      : (message: string) => submitCommand(message, "voice");
  }

  function handleToggleVoice(mode: VoiceMode = voice.mode) {
    toggleVoice(mode, (text) => void currentSubmitter(mode)(text));
  }

  function sendVoiceOverlay() {
    const transcriptText = [voice.finalTranscript, voice.interimTranscript].filter(Boolean).join(" ").trim();
    const manual = voice.mode === "chat" ? chatCommand : command;
    stopVoice();
    void currentSubmitter()(transcriptText || manual);
    resetTranscript();
  }

  async function handleApproval(id: string, decision: "approve" | "reject") {
    setActionError("");
    try {
      await home.decideApproval(id, decision);
      notify(decision === "approve" ? "\u0110\u00e3 duy\u1ec7t y\u00eau c\u1ea7u an ninh th\u00e0nh c\u00f4ng." : "\u0110\u00e3 t\u1eeb ch\u1ed1i y\u00eau c\u1ea7u.");
    } catch (caught) {
      setActionError(caught instanceof Error ? caught.message : "Kh\u00f4ng c\u1eadp nh\u1eadt \u0111\u01b0\u1ee3c y\u00eau c\u1ea7u ph\u00ea duy\u1ec7t.");
    }
  }

  async function handleDeviceCommand(device: Device, deviceCommand: ApiDeviceCommand, pin?: string) {
    setActionError("");
    try {
      await home.sendDeviceCommand(device, deviceCommand, pin);
      addHistory(`${deviceCommand.action.toUpperCase()} ${device.name}`, `${device.name} \u0111\u00e3 c\u1eadp nh\u1eadt tr\u1ea1ng th\u00e1i.`);
    } catch (caught) {
      const messageText = caught instanceof Error ? caught.message : "Kh\u00f4ng g\u1eedi \u0111\u01b0\u1ee3c l\u1ec7nh \u0111\u1ebfn thi\u1ebft b\u1ecb.";
      setActionError(messageText);
      addHistory(`${deviceCommand.action.toUpperCase()} ${device.name}`, messageText, "declined");
    }
  }

  function handleRequestPinUnlock(device: Device) {
    setPinDevice(device);
    setPinModalOpen(true);
  }

  async function handlePinUnlockSuccess(device: Device) {
    await handleDeviceCommand(device, { action: "unlock" }, "1234");
    notify(`Đã xác thực mã PIN! ${device.name} đã được mở khóa an toàn.`);
  }

  function handleToggleDataMode(nextMode: DataMode) {
    if (nextMode === "simulator") {
      home.setDataMode("simulator");
      return;
    }
    if (nextMode === "real") {
      if (home.dataMode === "real") return;
      setModePinModalOpen(true);
    }
  }

  function handleModePinSuccess() {
    home.setDataMode("real");
    notify("Đã chuyển sang chế độ Mô hình nhà thông minh (ESP32 MQTT thật)");
  }

  const transcript = [voice.finalTranscript, voice.interimTranscript].filter(Boolean).join(" ").trim();
  const assistantMessages = (voice.mode === "chat" ? chat : voiceThread).filter(
    (message) => message.role === "assistant",
  );
  const latestAssistant = assistantMessages[assistantMessages.length - 1]?.text || "";
  const selectedLiveRoom = selectedRoom
    ? home.rooms.find((room) => room.id === selectedRoom.id) ?? selectedRoom
    : null;

  const currentRoomPage = Math.min(roomPage, Math.max(0, Math.ceil(home.rooms.length / roomsPerPage) - 1));

  const visibleError = actionError || home.error;

  return {
    role,
    page,
    sidebarOpen,
    roomPage: currentRoomPage,
    selectedLiveRoom,
    selectedHistoryId,
    requestCancelled,
    notifCenterOpen,
    modePinModalOpen,
    pinModalOpen,
    pinDevice,
    command,
    chatCommand,
    voiceThread,
    chat,
    activeMessages: voice.mode === "chat" ? chat : voiceThread,
    submittingVoice,
    actionError,
    actionNotice,
    transcript,
    latestAssistant,
    visibleError,
    history,
    home,
    presets: presetState.presets,
    updatePresets: presetState.updatePresets,
    voice,
    ttsEnabled,
    setSidebarOpen,
    setRoomPage,
    setSelectedRoom,
    setSelectedHistoryId,
    setRequestCancelled,
    setNotifCenterOpen,
    setModePinModalOpen,
    setPinModalOpen,
    setPinDevice,
    setCommand,
    setChatCommand,
    setTtsEnabled,
    setActionError,
    setActionNotice,
    closeVoice,
    stopVoice,
    navigate,
    handleToggleVoice,
    sendVoiceOverlay,
    handleApproval,
    handleDeviceCommand,
    handleRequestPinUnlock,
    handlePinUnlockSuccess,
    handleToggleDataMode,
    handleModePinSuccess,
    notify,
  };
}

type HomeAppController = ReturnType<typeof useHomeAppController>;

interface SessionShellProps {
  theme: ThemeMode;
  onToggleTheme: () => void;
  userName: string;
  onSignOut: () => void;
}

function HomeAdminApp({ theme, onToggleTheme, userName, onSignOut }: SessionShellProps) {
  const app = useHomeAppController("homeadmin");

  return (
    <HomeAppFrame
      app={app}
      navItems={adminNav}
      notificationCount={app.home.notificationCount}
      theme={theme}
      onToggleTheme={onToggleTheme}
      userName={userName}
      onSignOut={onSignOut}
    >
      {app.page === "Rooms" ? (
        <RoomsPage
          role={app.role}
          rooms={app.home.rooms}
          approvals={app.home.approvals}
          discoveredDevices={app.home.discoveredDevices}
          roomPage={app.roomPage}
          selectedRoom={app.selectedLiveRoom}
          listening={app.voice.listening}
          onRoomPage={app.setRoomPage}
          onOpenRoom={app.setSelectedRoom}
          onCloseRoom={() => app.setSelectedRoom(null)}
          onOpenVoice={() => app.handleToggleVoice("command")}
          onNavigateApprovals={() => app.navigate("Approvals")}
          presets={app.presets}
          onPresetsChange={app.updatePresets}
          onDeviceCommand={app.handleDeviceCommand}
          onRequestPinUnlock={app.handleRequestPinUnlock}
          onAddDevice={async (payload) => {
            await app.home.addDevice(payload);
            app.notify(`\u0110\u00e3 th\u00eam thi\u1ebft b\u1ecb "${payload.name}" v\u00e0o ${payload.room}!`);
          }}
          onDeleteDevice={async (deviceId) => {
            await app.home.deleteDevice(deviceId);
            app.notify("\u0110\u00e3 x\u00f3a thi\u1ebft b\u1ecb kh\u1ecfi h\u1ec7 th\u1ed1ng.");
            app.setSelectedRoom(null);
          }}
          onUpdateDevice={async (deviceId, payload) => {
            await app.home.updateDevice(deviceId, payload);
            app.notify(`\u0110\u00e3 chuy\u1ec3n thi\u1ebft b\u1ecb "${payload.name || deviceId}" v\u00e0o ${payload.room}!`);
          }}
          onRenameRoom={async (oldName, newName) => {
            await app.home.renameRoom(oldName, newName);
            app.notify(`Đã đổi tên phòng "${oldName}" thành "${newName}"!`);
            app.setSelectedRoom(null);
          }}
          onDeleteRoom={async (roomName) => {
            await app.home.deleteRoom(roomName);
            app.notify(`Đã xóa phòng "${roomName}" và các thiết bị liên quan.`);
            app.setSelectedRoom(null);
          }}
          onAddRoom={async (name, icon, deviceIds) => {
            await app.home.addRoom(name, icon, deviceIds);
            app.notify(`\u0110\u00e3 t\u1ea1o ph\u00f2ng m\u1edbi "${name}" th\u00e0nh c\u00f4ng!`);
          }}
          onScanDevices={async () => {
            await app.home.scanDevices();
            app.notify("\u0110\u00e3 ph\u00e1t s\u00f3ng l\u1ec7nh qu\u00e9t thi\u1ebft b\u1ecb t\u1edbi to\u00e0n b\u1ed9 ESP32!");
          }}
          onPairDiscovered={async (deviceId, name, room) => {
            await app.home.pairDiscoveredDevice(deviceId, name, room);
            app.notify(`\u0110\u00e3 gh\u00e9p n\u1ed1i thi\u1ebft b\u1ecb "${name || deviceId}" th\u00e0nh c\u00f4ng!`);
          }}
          onDismissDiscovered={app.home.dismissDiscoveredDevice}
        />
      ) : null}

      {app.page === "History" ? (
        <HistoryPage
          history={app.history}
          selectedId={app.selectedHistoryId}
          onSelect={(item) => app.setSelectedHistoryId(item.id)}
        />
      ) : null}

      {app.page === "Approvals" ? (
        <ApprovalsPage
          approvals={app.home.approvals}
          onApprove={(id) => void app.handleApproval(id, "approve")}
          onReject={(id) => void app.handleApproval(id, "reject")}
        />
      ) : null}

      {app.page === "Activity" ? <ActivityPage activity={app.home.activity} /> : null}

      {app.page === "Performance" ? <PerformancePage /> : null}

      {app.page === "MQTT" ? (
        <MqttPage
          devices={app.home.rawDevices}
          events={app.home.events}
          dataMode={app.home.dataMode}
          onDeviceCommand={(dev) => void app.handleDeviceCommand(dev, { action: "toggle" })}
          onSetFault={app.home.setSimulatorFault}
        />
      ) : null}

      {app.page === "Settings" ? <SettingsPage /> : null}

      {app.page === "Presets" ? (
        <PresetsPage
          role={app.role}
          devices={app.home.rooms.flatMap((room) => room.devices)}
          presets={app.presets}
          onPresetsChange={app.updatePresets}
          onDeviceCommand={app.handleDeviceCommand}
        />
      ) : null}

      <PinModal
        open={app.pinModalOpen}
        device={app.pinDevice}
        onClose={() => {
          app.setPinModalOpen(false);
          app.setPinDevice(null);
        }}
        onUnlockSuccess={app.handlePinUnlockSuccess}
      />

      <NotificationCenterModal
        open={app.notifCenterOpen}
        notifications={app.home.notifications}
        approvals={app.home.approvals}
        onClose={() => app.setNotifCenterOpen(false)}
        onMarkAllRead={app.home.markAllNotificationsRead}
        onClearAll={app.home.clearNotifications}
        onDismissNotification={app.home.dismissNotification}
        onOpenApprovals={() => app.navigate("Approvals")}
        onOpenAddDevice={() => app.navigate("Rooms")}
      />
    </HomeAppFrame>
  );
}

function MemberApp({ theme, onToggleTheme, userName, onSignOut }: SessionShellProps) {
  const app = useHomeAppController("member");

  return (
    <HomeAppFrame
      app={app}
      navItems={memberNav}
      notificationCount={app.home.unreadNotificationsCount}
      theme={theme}
      onToggleTheme={onToggleTheme}
      userName={userName}
      onSignOut={onSignOut}
    >
      {app.page === "Rooms" ? (
        <RoomsPage
          role={app.role}
          rooms={app.home.rooms}
          approvals={app.home.approvals}
          discoveredDevices={[]}
          roomPage={app.roomPage}
          selectedRoom={app.selectedLiveRoom}
          listening={app.voice.listening}
          onRoomPage={app.setRoomPage}
          onOpenRoom={app.setSelectedRoom}
          onCloseRoom={() => app.setSelectedRoom(null)}
          onOpenVoice={() => app.handleToggleVoice("command")}
          onDeviceCommand={app.handleDeviceCommand}
          onRequestPinUnlock={(device) => void app.handleDeviceCommand(device, { action: "unlock" })}
          presets={app.presets}
          onPresetsChange={app.updatePresets}
        />
      ) : null}

      {app.page === "History" ? (
        <HistoryPage
          history={app.history}
          selectedId={app.selectedHistoryId}
          onSelect={(item) => app.setSelectedHistoryId(item.id)}
        />
      ) : null}

      {app.page === "Presets" ? (
        <PresetsPage
          role={app.role}
          devices={app.home.rooms.flatMap((room) => room.devices)}
          presets={app.presets}
          onPresetsChange={app.updatePresets}
          onDeviceCommand={app.handleDeviceCommand}
        />
      ) : null}

      {app.page === "Requests" ? (
        <RequestsPage
          approvals={app.home.approvals}
          cancelled={app.requestCancelled}
          onCancel={() => app.setRequestCancelled(true)}
          onCancelApproval={async (id) => {
            await app.home.decideApproval(id, "reject");
            app.notify("Đã hủy yêu cầu phê duyệt an ninh.");
          }}
        />
      ) : null}

      <NotificationCenterModal
        open={app.notifCenterOpen}
        notifications={app.home.notifications}
        approvals={[]}
        onClose={() => app.setNotifCenterOpen(false)}
        onMarkAllRead={app.home.markAllNotificationsRead}
        onClearAll={app.home.clearNotifications}
        onDismissNotification={app.home.dismissNotification}
      />
    </HomeAppFrame>
  );
}

function HomeAppFrame({
  app,
  navItems,
  notificationCount,
  theme,
  onToggleTheme,
  userName,
  onSignOut,
  children,
}: {
  app: HomeAppController;
  navItems: NavItem[];
  notificationCount: number;
  theme: ThemeMode;
  onToggleTheme: () => void;
  userName: string;
  onSignOut: () => void;
  children: ReactNode;
}) {
  return (
    <main className={`hm-app ${app.sidebarOpen ? "sidebar-open" : "sidebar-closed"}`}>
      {app.sidebarOpen ? (
        <div
          className="hm-sidebar-backdrop"
          aria-hidden="true"
          onClick={() => app.setSidebarOpen(false)}
        />
      ) : null}
      <div className="hm-wrap">
        <div className="hm-layout">
          <Sidebar
            role={app.role}
            navItems={navItems}
            page={app.page}
            open={app.sidebarOpen}
            onNavigate={app.navigate}
          />
          <PageShell home={app.page === "Rooms"}>
            <TopGreeting
              role={app.role}
              userName={userName}
              sidebarOpen={app.sidebarOpen}
              notificationCount={notificationCount}
              dataMode={app.home.dataMode}
              theme={theme}
              onToggleDataMode={app.handleToggleDataMode}
              onToggleTheme={onToggleTheme}
              onToggleSidebar={() => app.setSidebarOpen((open) => !open)}
              onOpenNotifications={() => app.setNotifCenterOpen(true)}
              onSignOut={onSignOut}
            />

            {app.visibleError ? (
              <div className="hm-toast error" role="alert">
                <span>{app.visibleError}</span>
                <button type="button" onClick={() => app.setActionError("")}>&times;</button>
              </div>
            ) : null}

            {app.actionNotice ? (
              <div className="hm-toast success" role="status">
                <span>{app.actionNotice}</span>
                <button type="button" onClick={() => app.setActionNotice("")}>&times;</button>
              </div>
            ) : null}

            {app.home.activeToast ? (
              <div className={`hm-toast ${app.home.activeToast.type}`} role="alert">
                <span>{app.home.activeToast.message}</span>
                <button type="button" onClick={() => app.home.dismissToast()}>&times;</button>
              </div>
            ) : null}

            {children}
          </PageShell>
        </div>
      </div>

      <VoiceOverlay
        open={app.voice.open}
        mode={app.voice.mode}
        listening={app.voice.listening}
        busy={app.submittingVoice}
        error={app.voice.error || app.actionError}
        transcript={app.transcript}
        manualValue={app.voice.mode === "chat" ? app.chatCommand : app.command}
        messages={app.activeMessages}
        latestAssistant={app.latestAssistant}
        voiceStatusReady={Boolean(app.home.voiceStatus?.ready)}
        ttsEnabled={app.ttsEnabled}
        onClose={app.closeVoice}
        onStop={app.stopVoice}
        onToggle={() => app.handleToggleVoice(app.voice.mode)}
        onSwitchMode={(mode) => {
          app.closeVoice();
          setTimeout(() => app.handleToggleVoice(mode), 100);
        }}
        onToggleTts={() => app.setTtsEnabled((val) => !val)}
        onManualChange={app.voice.mode === "chat" ? app.setChatCommand : app.setCommand}
        onSend={app.sendVoiceOverlay}
      />

      <ModePinModal
        open={app.modePinModalOpen}
        onClose={() => app.setModePinModalOpen(false)}
        onSuccess={app.handleModePinSuccess}
      />
    </main>
  );
}
