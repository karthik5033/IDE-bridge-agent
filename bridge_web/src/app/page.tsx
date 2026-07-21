"use client";

import { useEffect, useState, useRef } from "react";
import { Play, Square, Activity, Bot, Code, MonitorPlay, Loader2, Eraser, AlertOctagon, Send, ChevronDown, Settings, X, CheckCircle2, Circle } from "lucide-react";

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
  const [hasStarted, setHasStarted] = useState(false);
  const [hasCheckpoint, setHasCheckpoint] = useState(false);
  
  const [models, setModels] = useState<string[]>([]);
  const [activeModel, setActiveModel] = useState<string>("");
  const [isDropdownOpen, setIsDropdownOpen] = useState(false);
  
  const [isSettingsOpen, setIsSettingsOpen] = useState(false);
  const [configData, setConfigData] = useState({ dev_server_cwd: "", max_turns: 40, critic_retry_cap: 3, critic_mode: "chatgpt" });
  const [activePhase, setActivePhase] = useState<number>(0);
  
  const wsRef = useRef<WebSocket | null>(null);
  
  const scrollRefs = {
    antigravity: useRef<HTMLDivElement>(null),
    claude: useRef<HTMLDivElement>(null),
    chatgpt: useRef<HTMLDivElement>(null),
    system: useRef<HTMLDivElement>(null),
  };
  
  const logIdCounter = useRef(0);

  const checkCheckpointStatus = async () => {
    try {
      const res = await fetch(`http://${window.location.hostname}:8000/api/checkpoint`);
      if (res.ok) {
        const data = await res.json();
        setHasCheckpoint(data.has_checkpoint);
      }
    } catch (err) {
      console.warn("Failed to check checkpoint:", err);
    }
  };

  useEffect(() => {
    checkCheckpointStatus();
    const interval = setInterval(checkCheckpointStatus, 5000);
    return () => clearInterval(interval);
  }, []);

  const fetchConfig = async () => {
    try {
      const res = await fetch(`http://${window.location.hostname}:8000/api/config`);
      if (res.ok) {
        const data = await res.json();
        setConfigData(data);
      }
    } catch (err) {
      console.warn("Failed to fetch config:", err);
    }
  };

  const saveConfig = async () => {
    try {
      await fetch(`http://${window.location.hostname}:8000/api/config`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(configData)
      });
      setIsSettingsOpen(false);
    } catch (err) {
      console.warn("Failed to save config:", err);
    }
  };

  useEffect(() => {
    fetchConfig();
  }, []);

  // Fetch Models
  useEffect(() => {
    const fetchModels = async () => {
      try {
        const res = await fetch(`http://${window.location.hostname}:8000/api/models`);
        if (!res.ok) {
          setModels(["API Offline"]);
          return;
        }
        const data = await res.json();
        if (data.models && data.models.length > 0) {
          setModels(data.models);
        } else {
          setModels(["No Models Found"]);
        }
        if (data.active) setActiveModel(data.active);
      } catch (err) {
        // Silently catch the error to prevent Next.js error overlay and console errors
        setModels(["API Offline"]);
      }
    };

    fetchModels();
  }, []);

  useEffect(() => {
    let reconnectTimer: NodeJS.Timeout;
    
    const connect = () => {
      const ws = new WebSocket(`ws://${window.location.hostname}:8000/ws/stream`);
      
      ws.onopen = () => setIsConnected(true);
      
      ws.onclose = () => {
        setIsConnected(false);
        reconnectTimer = setTimeout(connect, 2000);
      };
      
      ws.onmessage = (event) => {
        const data = JSON.parse(event.data);
        if (data.type === "log") {
          const msg = data.data.message;
          const logObj = { id: logIdCounter.current++, message: msg };
          
          if (msg.includes("[System] Agent gracefully stopped.")) {
            setAgentState("idle");
          }
          if (msg.includes("Starting Phase 1")) setActivePhase(1);
          else if (msg.includes("Starting Phase 2")) setActivePhase(2);
          else if (msg.includes("Starting Phase 3")) setActivePhase(3);
          else if (msg.includes("Goal Achieved") || msg.includes("gracefully completed")) setActivePhase(4);
  
          // Log Routing Logic
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
    };

    connect();
    
    return () => {
      clearTimeout(reconnectTimer);
      if (wsRef.current) wsRef.current.close();
    };
  }, []);

  // Auto-scroll effect for vertical logs
  useEffect(() => {
    Object.values(scrollRefs).forEach(ref => {
      if (ref.current) {
        ref.current.scrollTop = ref.current.scrollHeight;
      }
    });
  }, [antigravityLogs, claudeLogs, chatgptLogs, systemLogs, activePrompt]);

  // Auto-center horizontal slider to active panel
  useEffect(() => {
    if (activePanel) {
      const container = document.getElementById("panels-container");
      const el = document.getElementById(`panel-${activePanel}`);
      if (container && el) {
        const scrollLeft = el.offsetLeft - container.offsetWidth / 2 + el.offsetWidth / 2;
        container.scrollTo({ left: scrollLeft, behavior: "smooth" });
      }
    }
  }, [activePanel]);

  const clearLogs = () => {
    setAntigravityLogs([]);
    setClaudeLogs([]);
    setChatgptLogs([]);
    setSystemLogs([]);
    setActivePanel(null);
    setHasStarted(false);
  };

  const handleStart = async (resume: boolean = false) => {
    if (!initialTask && !resume) return;
    setAgentState("running");
    setHasStarted(true);
    try {
      const res = await fetch(`http://${window.location.hostname}:8000/api/start`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ task: initialTask || "Resume Task", resume })
      });
      if (res.ok) {
        setSystemLogs(prev => [...prev, { id: logIdCounter.current++, message: `[System] Bridge Engine Started (Resume: ${resume}) in Background...` }]);
        if (resume) setHasCheckpoint(false);
      }
    } catch (error) {
      console.warn("Failed to start:", error);
      setAgentState("idle");
    }
  };

  const handleStop = async () => {
    setAgentState("stopping");
    try {
      await fetch(`http://${window.location.hostname}:8000/api/stop`, { method: "POST" });
      setSystemLogs(prev => [...prev, { id: logIdCounter.current++, message: "[System] Stop signal sent. Waiting for agent to halt..." }]);
      
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
      console.warn("Failed to reach backend:", error);
      setAgentState("idle");
    }
  };

  const handleModelChange = async (newModel: string) => {
    setActiveModel(newModel);
    try {
      await fetch(`http://${window.location.hostname}:8000/api/models/active`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ model_name: newModel })
      });
    } catch (err) {
      console.warn("Failed to change model:", err);
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
      <div id={`panel-${panelKey}`} className={`shrink-0 w-[85vw] sm:w-[480px] h-[340px] flex flex-col rounded-2xl overflow-hidden transition-all duration-300 snap-center shadow-2xl ${
        isActive 
          ? 'ring-2 ring-[#E9D9B9]/60 bg-[#2C2B29] scale-[1.02]' 
          : 'bg-[#2A2927] hover:bg-[#2C2B29] border border-[#3A3937] scale-100 opacity-90 hover:opacity-100'
      }`}>
        <div className="flex items-center gap-3 px-5 py-3 border-b border-[#3A3937]/50 bg-[#242321]/30">
          <Icon size={16} className={isActive ? 'text-[#E9D9B9]' : 'text-[#8A8987]'} />
          <span className={`text-xs font-semibold uppercase tracking-wider ${isActive ? 'text-[#E9D9B9]' : 'text-[#8A8987]'}`}>{title}</span>
          {isActive && <span className="w-1.5 h-1.5 rounded-full bg-[#E9D9B9] animate-pulse ml-auto shadow-[0_0_8px_rgba(233,217,185,0.8)]" />}
        </div>
        <div className="flex-1 p-5 font-mono text-[13px] leading-relaxed overflow-y-auto" ref={scrollRefs[scrollRefKey as keyof typeof scrollRefs]}>
          {logs.length === 0 ? (
            <div className="text-[#6A6967] mt-2 italic flex items-center justify-center h-full opacity-50">Waiting for logs...</div>
          ) : (
            logs.map((log: LogEvent) => (
              <div 
                key={log.id}
                className={`mb-3 break-words ${
                  log.message.includes('Error') || log.message.includes('Exception') || log.message.includes('fail') 
                    ? 'text-[#DA8769] font-medium' 
                    : 'text-[#C5BDB0]'
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
    <div className="h-screen w-screen overflow-hidden bg-[#242321] text-[#E6DED0] font-sans flex flex-col selection:bg-[#E9D9B9] selection:text-[#242321]">
      {/* Settings Button */}
      <button 
        onClick={() => setIsSettingsOpen(true)}
        className="absolute top-6 right-6 p-2 rounded-full hover:bg-[#3A3937] transition-colors text-[#8A8987] hover:text-[#E9D9B9] z-50"
      >
        <Settings size={20} />
      </button>

      {/* Main Content Area */}
      <div className={`flex-1 flex flex-col items-center px-4 w-full max-w-4xl mx-auto min-h-0 overflow-y-auto hide-scrollbar transition-all duration-700 ease-in-out ${
        hasStarted ? "justify-start pt-[8vh] pb-8" : "justify-center"
      }`}>
        
        {/* Title (Collapses when running) */}
        <div className={`flex items-center gap-3 transition-all duration-700 ease-in-out overflow-hidden cursor-default ${
          hasStarted ? "h-0 opacity-0 mb-0 scale-95 pointer-events-none mt-0" : "h-[40px] opacity-100 mb-8 mt-4 scale-100"
        }`}>
          <div className="text-[#DA8769] flex items-center justify-center">
            {/* Custom Sunburst SVG */}
            <svg width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round" className="animate-[spin_20s_linear_infinite]">
              <path d="M12 2v20M4.93 4.93l14.14 14.14M2 12h20M4.93 19.07L19.07 4.93" />
            </svg>
          </div>
          <h1 className="text-3xl md:text-4xl tracking-tight" style={{ fontFamily: 'Georgia, "Times New Roman", serif' }}>Antigravity Bridge</h1>
        </div>

        {/* Input Container */}
        <div className={`w-full bg-[#2A2927]/90 backdrop-blur-md shadow-2xl border transition-all duration-700 focus-within:border-[#6A6967] ${
          hasStarted ? "rounded-2xl p-2 border-[#3A3937]/50 max-w-3xl" : "rounded-[2rem] p-3 border-[#3A3937] hover:border-[#4A4947]"
        }`}>
          <div className="flex items-center gap-3 px-3 py-2">
            <span className="text-[#8A8987] ml-2 text-2xl font-light cursor-pointer hover:text-[#E6DED0] transition-colors">+</span>
            <input 
              value={initialTask}
              onChange={(e) => setInitialTask(e.target.value)}
              placeholder="How can I help you today?"
              className="flex-1 bg-transparent border-none focus:outline-none text-[1.1rem] text-[#E6DED0] placeholder-[#6A6967] h-12 ml-2"
              disabled={agentState !== "idle"}
              onKeyDown={(e) => {
                if (e.key === 'Enter' && initialTask && agentState === 'idle') {
                  handleStart();
                }
              }}
            />
            {/* Custom Model Dropdown */}
            <div className="relative mr-2">
              <div 
                onClick={() => agentState === 'idle' && setIsDropdownOpen(!isDropdownOpen)}
                className={`flex items-center gap-2 px-3 py-1.5 rounded-lg transition-colors cursor-pointer border border-[#4A4947] ${
                  agentState !== 'idle' ? 'opacity-50 cursor-not-allowed bg-[#3A3937]/20' : 'bg-[#3A3937]/40 hover:bg-[#3A3937]/80'
                }`}
              >
                <span className="text-xs text-[#D6CEBF] font-medium min-w-[80px] text-right">
                  {models.length === 0 ? "Loading..." : activeModel}
                </span>
                <ChevronDown size={14} className="text-[#A6A095]" />
              </div>
              
              {isDropdownOpen && models.length > 0 && agentState === 'idle' && (
                <>
                  <div className="fixed inset-0 z-40" onClick={() => setIsDropdownOpen(false)} />
                  <div className="absolute top-full mt-2 right-0 bg-[#2A2927] border border-[#4A4947] rounded-xl shadow-[0_8px_30px_rgb(0,0,0,0.5)] py-1.5 z-50 min-w-[160px] animate-in fade-in zoom-in-95 duration-100">
                    {models.map(m => (
                      <div 
                        key={m} 
                        onClick={() => {
                          handleModelChange(m);
                          setIsDropdownOpen(false);
                        }}
                        className={`px-4 py-2.5 text-sm cursor-pointer transition-colors mx-1.5 rounded-md ${
                          activeModel === m 
                            ? 'bg-[#3A3937] text-[#E9D9B9] font-medium' 
                            : 'text-[#C5BDB0] hover:bg-[#3A3937]/60 hover:text-white'
                        }`}
                      >
                        {m}
                      </div>
                    ))}
                  </div>
                </>
              )}
            </div>

            {/* Send Button */}
            <button 
              onClick={() => handleStart(false)}
              disabled={!initialTask || agentState !== 'idle'}
              className="flex items-center justify-center w-10 h-10 rounded-xl bg-[#E9D9B9] text-[#242321] hover:bg-white disabled:opacity-50 disabled:bg-[#3A3937] disabled:text-[#8A8987] transition-colors ml-1"
            >
              <Send size={18} className={initialTask && agentState === 'idle' ? 'ml-0.5' : ''} />
            </button>
          </div>
        </div>

        {/* Action Buttons */}
        <div className="flex flex-wrap items-center justify-center gap-3 mt-4 pb-2">
          {agentState === "idle" ? (
            <>
              {hasCheckpoint && (
                <button onClick={() => handleStart(true)} className="flex items-center gap-2 px-5 py-2.5 bg-[#4A6B53] hover:bg-[#5C8567] rounded-full text-sm font-medium transition-colors border border-[#5C8567] shadow-sm text-[#E9D9B9]">
                  <Play size={14} className="text-[#E9D9B9]" /> Resume Agent
                </button>
              )}
              <button onClick={() => handleStart(false)} className="flex items-center gap-2 px-5 py-2.5 bg-[#363533] hover:bg-[#464543] rounded-full text-sm font-medium transition-colors border border-[#4A4947] shadow-sm">
                <Play size={14} className="text-[#A6A095]" /> {hasCheckpoint ? "Start Fresh" : "Start Agent"}
              </button>
            </>
          ) : agentState === "running" ? (
            <button onClick={handleStop} className="flex items-center gap-2 px-5 py-2.5 bg-[#DA8769]/10 hover:bg-[#DA8769]/20 text-[#DA8769] rounded-full text-sm font-medium transition-colors border border-[#DA8769]/30 shadow-sm">
              <Square size={14} className="fill-current" /> Stop Agent
            </button>
          ) : (
            <button disabled className="flex items-center gap-2 px-5 py-2.5 bg-[#363533] rounded-full text-sm font-medium opacity-50 border border-[#4A4947]">
              <Loader2 size={14} className="animate-spin" /> Stopping...
            </button>
          )}

          <button onClick={clearLogs} className="flex items-center gap-2 px-5 py-2.5 bg-[#363533] hover:bg-[#464543] rounded-full text-sm font-medium transition-colors border border-[#4A4947] shadow-sm">
            <Eraser size={14} className="text-[#A6A095]" /> Clear Logs
          </button>

          {agentState !== "idle" && (
            <button onClick={handleStop} className="flex items-center gap-2 px-5 py-2.5 bg-[#363533] hover:bg-red-950/40 hover:text-red-400 rounded-full text-sm font-medium transition-colors border border-[#4A4947] shadow-sm text-[#A6A095]">
              <AlertOctagon size={14} /> Force Stop
            </button>
          )}

          <div className="ml-4 flex items-center gap-2 text-xs font-medium text-[#6A6967] uppercase tracking-widest px-4 py-2 rounded-full border border-[#3A3937]">
            <div className={`w-1.5 h-1.5 rounded-full ${isConnected ? 'bg-emerald-500/80 shadow-[0_0_6px_rgba(16,185,129,0.5)]' : 'bg-red-500/80'}`} />
            {isConnected ? 'Live' : 'Offline'}
          </div>
        </div>

        {/* Phase Tracker (Visible only when running) */}
        <div className={`w-full max-w-2xl mt-6 transition-all duration-700 ease-in-out ${
          hasStarted ? "opacity-100 translate-y-0 h-16" : "opacity-0 translate-y-4 h-0 overflow-hidden pointer-events-none"
        }`}>
          <div className="flex items-center justify-between relative px-8">
            <div className="absolute top-4 left-12 right-12 h-[2px] bg-[#3A3937] z-0" />
            <div className="absolute top-4 left-12 h-[2px] bg-[#E9D9B9] z-0 transition-all duration-1000" style={{ width: activePhase >= 4 ? '100%' : activePhase === 3 ? '100%' : activePhase === 2 ? '50%' : '0%' }} />
            
            {[
              { id: 1, label: "Architect" },
              { id: 2, label: "Builder" },
              { id: 3, label: "Critic" }
            ].map(phase => (
              <div key={phase.id} className="relative z-10 flex flex-col items-center gap-2">
                <div className={`w-8 h-8 rounded-full flex items-center justify-center transition-all duration-500 shadow-md ${
                  activePhase > phase.id ? 'bg-[#E9D9B9] text-[#242321]' : 
                  activePhase === phase.id ? 'bg-[#2A2927] border-2 border-[#E9D9B9] text-[#E9D9B9] animate-pulse shadow-[0_0_10px_rgba(233,217,185,0.4)]' : 
                  'bg-[#2A2927] border-2 border-[#4A4947] text-[#6A6967]'
                }`}>
                  {activePhase > phase.id ? <CheckCircle2 size={16} /> : <span className="text-xs font-bold">{phase.id}</span>}
                </div>
                <span className={`text-[10px] font-bold uppercase tracking-wider transition-colors duration-500 ${
                  activePhase >= phase.id ? 'text-[#E9D9B9]' : 'text-[#6A6967]'
                }`}>{phase.label}</span>
              </div>
            ))}
          </div>
        </div>



        {/* Quick Stats Panel */}
        <div className="flex items-center gap-4 mt-2 text-[11px] font-mono text-[#6A6967]">
          <span>Target: {configData.dev_server_cwd.split('\\').pop() || configData.dev_server_cwd.split('/').pop() || 'None'}</span>
          <span>•</span>
          <span>Critic: {configData.critic_mode === 'chatgpt' ? 'ChatGPT' : 'Local'}</span>
          <span>•</span>
          <span>Max Turns: {configData.max_turns}</span>
        </div>

        {/* Active Prompt Response Input */}
        {activePrompt && (
          <div className="fixed bottom-8 left-1/2 -translate-x-1/2 z-50 w-[90%] max-w-2xl bg-[#2C2B29]/95 border-2 border-[#E9D9B9] rounded-2xl p-5 flex flex-col gap-4 shadow-[0_0_40px_rgba(233,217,185,0.15)] backdrop-blur-md animate-in fade-in slide-in-from-bottom-8">
            <div className="flex items-center gap-3">
              <span className="w-2.5 h-2.5 rounded-full bg-[#E9D9B9] animate-pulse shadow-[0_0_8px_rgba(233,217,185,0.8)]" />
              <span className="text-sm font-bold tracking-wide text-[#E9D9B9]">{activePrompt}</span>
            </div>
            <div className="flex gap-2">
              {activePrompt.toLowerCase().includes("(y/n)") ? (
                <>
                  <button onClick={() => { 
                    if (wsRef.current && wsRef.current.readyState === WebSocket.OPEN) {
                      wsRef.current.send(JSON.stringify({ type: "input_response", value: "y" }));
                      setActivePrompt(null);
                    }
                  }} className="flex-1 bg-[#E9D9B9] text-[#242321] hover:bg-white px-8 py-3 rounded-xl text-sm font-bold transition-all shadow-md">Yes</button>
                  <button onClick={() => { 
                    if (wsRef.current && wsRef.current.readyState === WebSocket.OPEN) {
                      wsRef.current.send(JSON.stringify({ type: "input_response", value: "n" }));
                      setActivePrompt(null);
                    }
                  }} className="flex-1 border-2 border-[#E9D9B9]/40 text-[#E9D9B9] hover:bg-[#E9D9B9]/10 px-8 py-3 rounded-xl text-sm font-bold transition-all">No</button>
                </>
              ) : (
                <>
                  <input 
                    value={promptResponse}
                    onChange={(e) => setPromptResponse(e.target.value)}
                    placeholder="Type response..."
                    className="flex-1 bg-[#1A1918] border border-[#4A4947] focus:border-[#E9D9B9] outline-none text-[#E6DED0] px-4 py-3 rounded-xl text-sm transition-colors shadow-inner"
                    onKeyDown={(e) => e.key === 'Enter' && handlePromptSubmit()}
                    autoFocus
                  />
                  <button onClick={handlePromptSubmit} className="bg-[#E9D9B9] text-[#242321] hover:bg-white px-8 py-3 rounded-xl text-sm font-bold transition-all shadow-md">
                    Send
                  </button>
                </>
              )}
            </div>
          </div>
        )}

      </div>

      {/* Horizontal Slideshow Logs */}
      <div id="panels-container" className={`w-full overflow-x-auto px-6 sm:px-12 snap-x snap-mandatory hide-scrollbar shrink-0 transition-all duration-700 ease-in-out ${
        hasStarted ? "opacity-100 pb-12 pt-6 translate-y-0 h-auto max-h-[500px]" : "opacity-0 translate-y-10 h-0 overflow-hidden pointer-events-none"
      }`}>
        <div className="flex gap-6 min-w-max">
          {/* Invisible spacer for padding start */}
          <div className="w-[calc(50vw-250px)] shrink-0" />
          
          <LogPanel title="Antigravity (Local Builder)" icon={Code} logs={antigravityLogs} scrollRefKey="antigravity" panelKey="antigravity" />
          <LogPanel title="Claude (Architect)" icon={Bot} logs={claudeLogs} scrollRefKey="claude" panelKey="claude" />
          <LogPanel title="ChatGPT (Critic)" icon={Activity} logs={chatgptLogs} scrollRefKey="chatgpt" panelKey="chatgpt" />
          <LogPanel title="Webpage Inspector & System" icon={MonitorPlay} logs={systemLogs} scrollRefKey="system" panelKey="system" />
          
          {/* Invisible spacer for padding end */}
          <div className="w-[calc(50vw-250px)] shrink-0" />
        </div>
      </div>
      
      {/* Settings Modal */}
      {isSettingsOpen && (
        <div className="fixed inset-0 z-[100] flex items-center justify-center bg-black/60 backdrop-blur-sm animate-in fade-in duration-200">
          <div className="bg-[#2A2927] border border-[#4A4947] rounded-2xl w-[90%] max-w-md p-6 shadow-2xl animate-in zoom-in-95 duration-200">
            <div className="flex items-center justify-between mb-6">
              <h2 className="text-xl font-medium text-[#E9D9B9]">Settings</h2>
              <button onClick={() => setIsSettingsOpen(false)} className="text-[#8A8987] hover:text-[#E6DED0] transition-colors">
                <X size={20} />
              </button>
            </div>
            
            <div className="space-y-4">
              <div>
                <label className="block text-[10px] font-bold text-[#8A8987] mb-1.5 uppercase tracking-wider">Target Directory</label>
                <input 
                  value={configData.dev_server_cwd}
                  onChange={e => setConfigData({...configData, dev_server_cwd: e.target.value})}
                  className="w-full bg-[#1A1918] border border-[#4A4947] focus:border-[#E9D9B9] outline-none text-[#E6DED0] px-3 py-2.5 rounded-lg text-sm transition-colors"
                />
              </div>
              
              <div className="flex gap-4">
                <div className="flex-1">
                  <label className="block text-[10px] font-bold text-[#8A8987] mb-1.5 uppercase tracking-wider">Max Turns</label>
                  <input 
                    type="number"
                    value={configData.max_turns}
                    onChange={e => setConfigData({...configData, max_turns: parseInt(e.target.value) || 40})}
                    className="w-full bg-[#1A1918] border border-[#4A4947] focus:border-[#E9D9B9] outline-none text-[#E6DED0] px-3 py-2.5 rounded-lg text-sm transition-colors"
                  />
                </div>
                <div className="flex-1">
                  <label className="block text-[10px] font-bold text-[#8A8987] mb-1.5 uppercase tracking-wider">Critic Retries</label>
                  <input 
                    type="number"
                    value={configData.critic_retry_cap}
                    onChange={e => setConfigData({...configData, critic_retry_cap: parseInt(e.target.value) || 3})}
                    className="w-full bg-[#1A1918] border border-[#4A4947] focus:border-[#E9D9B9] outline-none text-[#E6DED0] px-3 py-2.5 rounded-lg text-sm transition-colors"
                  />
                </div>
              </div>
              
              <div>
                <label className="block text-[10px] font-bold text-[#8A8987] mb-1.5 uppercase tracking-wider">Critic Mode</label>
                <select 
                  value={configData.critic_mode}
                  onChange={e => setConfigData({...configData, critic_mode: e.target.value})}
                  className="w-full bg-[#1A1918] border border-[#4A4947] focus:border-[#E9D9B9] outline-none text-[#E6DED0] px-3 py-2.5 rounded-lg text-sm transition-colors appearance-none cursor-pointer"
                >
                  <option value="chatgpt">ChatGPT (Web)</option>
                  <option value="local">Local Model (Qwen-VL)</option>
                </select>
              </div>
            </div>
            
            <div className="mt-8 flex justify-end gap-3">
              <button onClick={() => { setIsSettingsOpen(false); fetchConfig(); }} className="px-4 py-2 text-sm font-medium text-[#8A8987] hover:text-[#E6DED0] transition-colors">Cancel</button>
              <button onClick={saveConfig} className="px-4 py-2 bg-[#E9D9B9] text-[#242321] hover:bg-white rounded-lg text-sm font-medium transition-colors shadow-md">Save Changes</button>
            </div>
          </div>
        </div>
      )}

      {/* Hide Scrollbar Style */}
      <style dangerouslySetInnerHTML={{__html: `
        .hide-scrollbar::-webkit-scrollbar {
          display: none;
        }
        .hide-scrollbar {
          -ms-overflow-style: none;
          scrollbar-width: none;
        }
      `}} />
    </div>
  );
}
