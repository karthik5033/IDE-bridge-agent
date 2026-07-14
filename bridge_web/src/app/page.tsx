"use client";

import { useEffect, useState, useRef } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Play, Square, Send, Activity, Bot, Code, MonitorPlay, Loader2 } from "lucide-react";

type LogEvent = {
  id: number;
  message: string;
};

type AgentState = "idle" | "running" | "stopping";

export default function Dashboard() {
  const [antigravityLogs, setAntigravityLogs] = useState<LogEvent[]>([]);
  const [claudeLogs, setClaudeLogs] = useState<LogEvent[]>([]);
  const [chatgptLogs, setChatgptLogs] = useState<LogEvent[]>([]);
  const [systemLogs, setSystemLogs] = useState<LogEvent[]>([]);
  
  const [isConnected, setIsConnected] = useState(false);
  const [activePrompt, setActivePrompt] = useState<string | null>(null);
  const [promptResponse, setPromptResponse] = useState("");
  const [initialTask, setInitialTask] = useState("");
  const [agentState, setAgentState] = useState<AgentState>("idle");
  const [activePanel, setActivePanel] = useState<string | null>(null);
  
  const wsRef = useRef<WebSocket | null>(null);
  
  const scrollRefs = {
    antigravity: useRef<HTMLDivElement>(null),
    claude: useRef<HTMLDivElement>(null),
    chatgpt: useRef<HTMLDivElement>(null),
    system: useRef<HTMLDivElement>(null),
  };
  
  const logIdCounter = useRef(0);

  useEffect(() => {
    const ws = new WebSocket("ws://localhost:8000/ws/stream");
    
    ws.onopen = () => setIsConnected(true);
    ws.onclose = () => setIsConnected(false);
    
    ws.onmessage = (event) => {
      const data = JSON.parse(event.data);
      if (data.type === "log") {
        const msg = data.data.message;
        const logObj = { id: logIdCounter.current++, message: msg };
        
        if (msg.includes("[System] Agent gracefully stopped.")) {
          setAgentState("idle");
        }

        // Log Routing Logic — also track which panel is currently active
        if (msg.includes("[Antigravity]")) {
          setAntigravityLogs(prev => [...prev, logObj]);
          setActivePanel("antigravity");
        } else if (msg.includes("[Critic]") || msg.toLowerCase().includes("chatgpt")) {
          setChatgptLogs(prev => [...prev, logObj]);
          setActivePanel("chatgpt");
        } else if (msg.includes("Chat UI") || msg.includes("Phase 1:") || msg.toLowerCase().includes("claude") || msg.includes("[Orchestrator]")) {
          setClaudeLogs(prev => [...prev, logObj]);
          setActivePanel("claude");
        } else {
          setSystemLogs(prev => [...prev, logObj]);
          setActivePanel("system");
        }
      } else if (data.type === "input_required") {
        setActivePrompt(data.data.prompt);
      }
    };
    
    wsRef.current = ws;
    
    return () => ws.close();
  }, []);

  // Auto-scroll effect for all panels
  useEffect(() => {
    Object.values(scrollRefs).forEach(ref => {
      if (ref.current) {
        ref.current.scrollTop = ref.current.scrollHeight;
      }
    });
  }, [antigravityLogs, claudeLogs, chatgptLogs, systemLogs, activePrompt]);

  const handleStart = async () => {
    if (!initialTask) return;
    setAgentState("running");
    try {
      const res = await fetch("http://localhost:8000/api/start", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ task: initialTask })
      });
      if (res.ok) {
        setSystemLogs(prev => [...prev, { id: logIdCounter.current++, message: "[System] Bridge Engine Started in Background..." }]);
      }
    } catch (error) {
      console.error(error);
      setAgentState("idle");
    }
  };

  const handleStop = async () => {
    setAgentState("stopping");
    try {
      await fetch("http://localhost:8000/api/stop", { method: "POST" });
      setSystemLogs(prev => [...prev, { id: logIdCounter.current++, message: "[System] Stop signal sent. Waiting for agent to halt..." }]);
      // Fallback: if the backend never emits the stopped signal (e.g. thread already crashed),
      // force reset to idle after 5 seconds
      setTimeout(() => {
        setAgentState(prev => {
          if (prev === "stopping") {
            setSystemLogs(logs => [...logs, { id: logIdCounter.current++, message: "[System] Agent stopped (timeout fallback)." }]);
            return "idle";
          }
          return prev;
        });
      }, 5000);
    } catch (error) {
      console.error(error);
      setAgentState("idle");
    }
  };

  const handlePromptSubmit = () => {
    if (wsRef.current && wsRef.current.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify({ type: "input_response", value: promptResponse }));
      setActivePrompt(null);
      setPromptResponse("");
    }
  };

  const LogPanel = ({ title, icon: Icon, logs, scrollRefKey, panelKey }: any) => {
    const isActive = activePanel === panelKey;
    return (
    <div className={`flex flex-col border-r border-b overflow-hidden h-full min-h-0 transition-all duration-300 ${
      isActive 
        ? 'border-l-2 border-l-emerald-500 bg-emerald-50/30 dark:bg-emerald-950/10 border-zinc-200 dark:border-zinc-800' 
        : 'border-zinc-200 dark:border-zinc-800 bg-white dark:bg-zinc-950'
    }`}>
      <div className={`flex items-center gap-2 px-3 py-2 border-b transition-colors duration-300 ${
        isActive 
          ? 'bg-emerald-100/60 dark:bg-emerald-900/20 border-zinc-200 dark:border-zinc-800' 
          : 'bg-zinc-100 dark:bg-zinc-900 border-zinc-200 dark:border-zinc-800'
      }`}>
        <Icon size={14} className={isActive ? 'text-emerald-600' : 'text-zinc-500'} />
        <span className={`text-xs font-semibold uppercase tracking-wider ${isActive ? 'text-emerald-700 dark:text-emerald-400' : 'text-zinc-700 dark:text-zinc-300'}`}>{title}</span>
        {isActive && <span className="w-1.5 h-1.5 rounded-full bg-emerald-500 animate-pulse ml-auto" />}
      </div>
      <div className="flex-1 p-3 font-mono text-[12px] leading-relaxed overflow-y-auto" ref={scrollRefs[scrollRefKey as keyof typeof scrollRefs]}>
        {logs.length === 0 ? (
          <div className="text-zinc-400 opacity-50 mt-2">Waiting for logs...</div>
        ) : (
          logs.map((log: LogEvent) => (
            <div 
              key={log.id}
              className={`mb-2 break-words ${
                log.message.includes('Error') || log.message.includes('Exception') || log.message.includes('fail') 
                  ? 'text-red-600 dark:text-red-400 font-medium' 
                  : 'text-zinc-800 dark:text-zinc-300'
              }`}
            >
              {log.message}
            </div>
          ))
        )}
      </div>
    </div>
  );
  };

  return (
    <div className="h-screen w-screen overflow-hidden bg-zinc-50 dark:bg-black text-zinc-900 dark:text-zinc-50 font-sans flex flex-col">
      
      {/* Top Header & Command Bar */}
      <header className="flex items-center justify-between px-4 py-3 bg-white dark:bg-zinc-950 border-b border-zinc-200 dark:border-zinc-800 z-10 shrink-0">
        <div className="flex items-center gap-6 flex-1">
          <div className="flex items-center gap-2">
            <Activity size={18} className="text-zinc-900 dark:text-white" />
            <h1 className="text-sm font-bold tracking-tight">Antigravity Bridge</h1>
            <div className={`w-1.5 h-1.5 rounded-full ml-2 mr-1 ${isConnected ? 'bg-green-500' : 'bg-red-500'}`} />
            <span className="text-xs text-zinc-500">{isConnected ? "Connected" : "Disconnected"}</span>
          </div>

          <div className="flex items-center w-full max-w-xl">
            <Input 
              value={initialTask}
              onChange={(e) => setInitialTask(e.target.value)}
              placeholder="Enter initial task..."
              className="h-8 text-xs bg-zinc-50 dark:bg-zinc-900 border-zinc-200 dark:border-zinc-800 rounded-sm rounded-r-none focus-visible:ring-0 focus-visible:border-zinc-400"
              disabled={agentState !== "idle"}
            />
            {agentState === "idle" && (
              <Button onClick={handleStart} className="h-8 px-4 rounded-sm rounded-l-none bg-black hover:bg-zinc-800 text-white text-xs whitespace-nowrap">
                <Play size={12} className="mr-1.5" /> Start Agent
              </Button>
            )}
            {agentState === "running" && (
              <Button onClick={handleStop} variant="destructive" className="h-8 px-4 rounded-sm rounded-l-none text-xs whitespace-nowrap">
                <Square size={12} className="mr-1.5" /> Stop Agent
              </Button>
            )}
            {agentState === "stopping" && (
              <Button disabled variant="outline" className="h-8 px-4 rounded-sm rounded-l-none text-xs border-zinc-200 text-zinc-500 whitespace-nowrap">
                <Loader2 size={12} className="mr-1.5 animate-spin" /> Stopping...
              </Button>
            )}
          </div>
        </div>

        {/* Active Prompt Alert Top Right */}
        {activePrompt && (
          <div className="flex items-center gap-3 bg-yellow-50 dark:bg-yellow-900/20 border border-yellow-200 dark:border-yellow-800/50 px-3 py-1.5 rounded-sm shadow-sm shrink-0 ml-4">
            <div className="flex items-center gap-2 border-r border-yellow-200 dark:border-yellow-800 pr-3">
              <span className="w-2 h-2 rounded-full bg-yellow-500 animate-pulse" />
              <span className="text-xs font-semibold text-yellow-800 dark:text-yellow-400 max-w-[200px] truncate" title={activePrompt}>{activePrompt}</span>
            </div>
            <div className="flex gap-1.5 pl-1">
              {activePrompt.toLowerCase().includes("(y/n)") ? (
                <>
                  <Button onClick={() => { 
                    if (wsRef.current && wsRef.current.readyState === WebSocket.OPEN) {
                      wsRef.current.send(JSON.stringify({ type: "input_response", value: "y" }));
                      setActivePrompt(null);
                    }
                  }} size="sm" className="bg-zinc-900 hover:bg-black text-white h-7 px-3 text-xs rounded-sm">Yes</Button>
                  <Button onClick={() => { 
                    if (wsRef.current && wsRef.current.readyState === WebSocket.OPEN) {
                      wsRef.current.send(JSON.stringify({ type: "input_response", value: "n" }));
                      setActivePrompt(null);
                    }
                  }} size="sm" variant="outline" className="h-7 px-3 text-xs rounded-sm border-yellow-300 text-yellow-800 hover:bg-yellow-100">No</Button>
                </>
              ) : (
                <>
                  <Input 
                    value={promptResponse}
                    onChange={(e) => setPromptResponse(e.target.value)}
                    placeholder="Type response..."
                    className="w-48 h-7 text-xs bg-white dark:bg-black border-yellow-200 focus-visible:ring-yellow-500 rounded-sm"
                    onKeyDown={(e) => e.key === 'Enter' && handlePromptSubmit()}
                    autoFocus
                  />
                  <Button onClick={handlePromptSubmit} size="sm" className="bg-zinc-900 hover:bg-black text-white h-7 px-3 text-xs rounded-sm">
                    Send
                  </Button>
                </>
              )}
            </div>
          </div>
        )}
      </header>

      {/* 4-Panel Grid Fill */}
      <div className="flex-1 grid grid-cols-1 lg:grid-cols-2 grid-rows-2 min-h-0">
        <LogPanel title="Antigravity (Local Builder)" icon={Code} logs={antigravityLogs} scrollRefKey="antigravity" panelKey="antigravity" />
        <LogPanel title="Claude (Architect)" icon={Bot} logs={claudeLogs} scrollRefKey="claude" panelKey="claude" />
        <LogPanel title="ChatGPT (Critic)" icon={Activity} logs={chatgptLogs} scrollRefKey="chatgpt" panelKey="chatgpt" />
        <LogPanel title="Webpage Inspector & System" icon={MonitorPlay} logs={systemLogs} scrollRefKey="system" panelKey="system" />
      </div>

    </div>
  );
}
